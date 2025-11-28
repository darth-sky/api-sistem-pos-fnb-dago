"""Routes for module ruangan"""
import os
import sys
from flask import Blueprint, jsonify, request
import pytz
from api.utils.ipaymu_helper import create_ipaymu_payment
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required, get_jwt_identity
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from datetime import datetime, time, timedelta, timezone
import math
import traceback
from datetime import datetime # --- PERUBAHAN 1: Impor library datetime ---
from mysql.connector import Error as DbError

ruangan_endpoints = Blueprint('ruangan', __name__)
UPLOAD_FOLDER = "img"

@ruangan_endpoints.route('/private-office-rooms', methods=['GET'])
def get_private_office_rooms():
    """
    Mengambil semua ruangan aktif, digabungkan dengan kategori dan paket harganya,
    untuk halaman pemesanan bulk/tim.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua ruangan aktif beserta nama kategorinya
        query_rooms = """
        SELECT 
            r.id_ruangan, 
            r.nama_ruangan, 
            r.harga_per_jam, 
            r.kapasitas, 
            r.gambar_ruangan, 
            r.fitur_ruangan, 
            kr.nama_kategori
        FROM ruangan r
        JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
        WHERE r.status_ketersediaan = 'Active'
        ORDER BY kr.nama_kategori, r.nama_ruangan;
        """
        cursor.execute(query_rooms)
        rooms = cursor.fetchall()

        # 2. Ambil paket harga untuk setiap ruangan
        # (Ini lebih efisien daripada JOIN N-N)
        query_paket = "SELECT id_paket, durasi_jam, harga_paket FROM paket_harga_ruangan WHERE id_ruangan = %s"
        
        for room in rooms:
            cursor.execute(query_paket, (room['id_ruangan'],))
            room['paket_harga'] = cursor.fetchall()

        return jsonify(rooms), 200

    except Exception as e:
        print(f"Error pada /private-office-rooms: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@ruangan_endpoints.route('/bookRuanganBulk', methods=['POST'])
@jwt_required()
def book_ruangan_bulk_revised(): 
    """
    Membuat transaksi & booking untuk BANYAK ruangan sekaligus,
    dengan MEMECAH menjadi booking harian (tanpa timezone).
    Mendukung integrasi iPaymu.
    """
    connection = None
    cursor = None
    try:
        data = request.json
        identity = get_jwt_identity()

        # --- Proses ID User ---
        try:
            if isinstance(identity, dict):
                id_user = identity.get('id_user')
                if id_user is None: raise ValueError("Key 'id_user' missing.")
            else: id_user = identity
        except (TypeError, ValueError, AttributeError) as e:
            return jsonify({"message": "ERROR", "error": f"Invalid token identity: {e}"}), 400
        if id_user is None: return jsonify({"message": "ERROR", "error": "User ID missing."}), 400

        # --- Ambil Data Format BARU dari Frontend ---
        room_ids = data.get("room_ids")
        tanggal_mulai_str = data.get("tanggal_mulai")
        tanggal_selesai_str = data.get("tanggal_selesai")
        jam_mulai_int = data.get("jam_mulai")
        jam_selesai_int = data.get("jam_selesai")
        
        # Default metode pembayaran
        metode_pembayaran = data.get("metode_pembayaran", "Non-Tunai") 
        
        booking_source = data.get("booking_source", "PrivateOffice") 
        include_saturday = data.get("include_saturday", False)
        include_sunday = data.get("include_sunday", False)

        # Validasi Input Dasar
        if not all([room_ids, tanggal_mulai_str, tanggal_selesai_str, isinstance(jam_mulai_int, int), isinstance(jam_selesai_int, int)]):
            return jsonify({"message": "ERROR", "error": "Data input tidak lengkap atau format jam salah."}), 400
        if jam_selesai_int <= jam_mulai_int:
             return jsonify({"message": "ERROR", "error": "Jam selesai harus setelah jam mulai."}), 400

        try:
            tanggal_mulai_date = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
            tanggal_selesai_date = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()
            if tanggal_selesai_date < tanggal_mulai_date:
                raise ValueError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
        except ValueError as e:
             return jsonify({"message": "ERROR", "error": f"Format tanggal salah: {e}"}), 400
        
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        connection.start_transaction()

        total_harga_transaksi = 0
        parsed_bookings_daily = [] 

        # Ambil detail harga semua ruangan
        placeholders = ','.join(['%s'] * len(room_ids))
        cursor.execute(f"SELECT id_ruangan, nama_ruangan, harga_per_jam FROM ruangan WHERE id_ruangan IN ({placeholders})", tuple(room_ids))
        room_details = {room['id_ruangan']: room for room in cursor.fetchall()}

        if len(room_details) != len(set(room_ids)):
             missing_ids = set(room_ids) - set(room_details.keys())
             raise ValueError(f"Satu atau lebih ID ruangan tidak ditemukan: {missing_ids}")

        # --- TAHAP 1: VALIDASI PER HARI & KALKULASI HARGA ---
        current_date_check = tanggal_mulai_date
        while current_date_check <= tanggal_selesai_date:
            # Cek hari libur (Sabtu/Minggu)
            day_of_week = current_date_check.weekday() 
            if day_of_week == 5 and not include_saturday:
                current_date_check += timedelta(days=1)
                continue
            if day_of_week == 6 and not include_sunday:
                current_date_check += timedelta(days=1)
                continue
            
            waktu_mulai_dt = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_mulai_int)
            waktu_selesai_dt = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_selesai_int)

            # Penyesuaian lintas hari (jika ada)
            if waktu_selesai_dt <= waktu_mulai_dt:
                 waktu_selesai_dt += timedelta(days=1)
                 if tanggal_selesai_date == tanggal_mulai_date and len(room_ids) * (tanggal_selesai_date - tanggal_mulai_date + timedelta(days=1)).days == 1 :
                      raise ValueError("Untuk booking satu hari, jam selesai harus setelah jam mulai di hari yang sama.")
                 elif current_date_check == tanggal_selesai_date:
                      waktu_selesai_dt -= timedelta(days=1) 

            waktu_mulai_db_str = waktu_mulai_dt.strftime('%Y-%m-%d %H:%M:%S')
            waktu_selesai_db_str = waktu_selesai_dt.strftime('%Y-%m-%d %H:%M:%S')

            for room_id in room_ids:
                # --- PERBAIKAN VALIDASI KETERSEDIAAN (Hanya blokir yg Lunas) ---
                check_query = """
                    SELECT br.id_booking 
                    FROM booking_ruangan br
                    JOIN transaksi t ON br.id_transaksi = t.id_transaksi
                    WHERE br.id_ruangan = %s 
                      AND (br.waktu_mulai < %s AND br.waktu_selesai > %s)
                      AND t.status_pembayaran = 'Lunas'
                """
                cursor.execute(check_query, (room_id, waktu_selesai_db_str, waktu_mulai_db_str))
                
                if cursor.fetchone():
                    connection.rollback()
                    room_name = room_details.get(room_id, {}).get('nama_ruangan', f'ID {room_id}')
                    return jsonify({"message": "ERROR", "error": f"Slot untuk {room_name} pada {current_date_check.strftime('%d-%m-%Y')} jam {jam_mulai_int}:00 - {jam_selesai_int}:00 sudah terisi."}), 409

                # Kalkulasi durasi & harga
                room_info = room_details[room_id]
                harga_per_jam = room_info['harga_per_jam']
                if harga_per_jam is None: raise ValueError(f"Harga per jam untuk {room_info['nama_ruangan']} tidak valid.")

                durasi_detik_hari_ini = (waktu_selesai_dt - waktu_mulai_dt).total_seconds()
                durasi_jam_hitung_hari_ini = (durasi_detik_hari_ini + 3599) // 3600
                if durasi_jam_hitung_hari_ini == 0: durasi_jam_hitung_hari_ini = 1
                durasi_menit_simpan_hari_ini = int(durasi_detik_hari_ini / 60)

                harga_booking_hari_ini = durasi_jam_hitung_hari_ini * harga_per_jam
                total_harga_transaksi += harga_booking_hari_ini

                parsed_bookings_daily.append({
                    "id_ruangan": room_id,
                    "waktu_mulai_str": waktu_mulai_db_str,
                    "waktu_selesai_str": waktu_selesai_db_str,
                    "durasi_menit": durasi_menit_simpan_hari_ini
                })

            current_date_check += timedelta(days=1)

        # --- TAHAP 2: BUAT 1 TRANSAKSI INDUK (Status Awal: Belum Lunas) ---
        insert_transaksi = """
        INSERT INTO transaksi (id_user, total_harga_final, metode_pembayaran, status_pembayaran, status_order, booking_source, tanggal_transaksi)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        total_final = int(round(total_harga_transaksi))
        
        # Set default untuk iPaymu
        metode_bayar_db = 'Ipaymu'
        status_bayar_db = 'Belum Lunas'
        
        cursor.execute(insert_transaksi, (
            id_user, 
            total_final, 
            metode_bayar_db, 
            status_bayar_db, 
            "Baru", 
            booking_source
        ))
        id_transaksi_baru = cursor.lastrowid

        # --- TAHAP 3: MASUKKAN SEMUA BOOKING HARIAN ---
        insert_booking_query = """
        INSERT INTO booking_ruangan (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi, kredit_terpakai)
        VALUES (%s, %s, %s, %s, %s, 0)
        """
        for b in parsed_bookings_daily:
            cursor.execute(insert_booking_query, (
                id_transaksi_baru,
                b['id_ruangan'],
                b['waktu_mulai_str'],
                b['waktu_selesai_str'],
                b['durasi_menit']
            ))

        # --- TAHAP 4: REQUEST LINK IPAYMU ---
        # Ambil data user
        cursor.execute("SELECT nama, email, no_telepon FROM users WHERE id_user = %s", (id_user,))
        user_data = cursor.fetchone()
        
        buyer_name = user_data['nama'] if user_data else "Guest Bulk"
        buyer_email = user_data['email'] if user_data else "guest@dago.com"
        buyer_phone = user_data['no_telepon'] or "08123456789"

        ipaymu_res = create_ipaymu_payment(
            id_transaksi=id_transaksi_baru,
            amount=total_final,
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            buyer_email=buyer_email
        )

        payment_url = None
        if ipaymu_res['success']:
            payment_url = ipaymu_res['url']
            connection.commit() # Commit jika sukses dapat link
        else:
            connection.rollback() # Batal simpan jika gagal konek payment gateway
            return jsonify({"message": "ERROR", "error": f"Gagal generate link pembayaran: {ipaymu_res.get('message')}"}), 500

        return jsonify({
            "message": f"Pesanan bulk booking berhasil dibuat. Silakan lakukan pembayaran.",
            "id_transaksi": id_transaksi_baru,
            "total_harga": total_final,
            "payment_url": payment_url 
        }), 201

    except ValueError as ve:
        if connection: connection.rollback()
        print(f"Validation Error: {ve}")
        return jsonify({"message": "ERROR", "error": str(ve)}), 400
    except Exception as e:
        if connection: connection.rollback()
        print(f"Unexpected Error: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": "Terjadi kesalahan internal pada server."}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()







@ruangan_endpoints.route('/check-availability-bulk', methods=['POST'])
def check_availability_bulk():
    """
    Memeriksa ketersediaan untuk BANYAK ruangan pada rentang tanggal dan jam tertentu.
    Mengembalikan daftar slot yang TIDAK TERSEDIA.
    """
    connection = None
    cursor = None
    try:
        data = request.json
        room_ids = data.get("room_ids") # Array of integer IDs
        tanggal_mulai_str = data.get("tanggal_mulai") # "YYYY-MM-DD"
        tanggal_selesai_str = data.get("tanggal_selesai") # "YYYY-MM-DD"
        jam_mulai_int = data.get("jam_mulai") # Integer hour (0-23)
        jam_selesai_int = data.get("jam_selesai") # Integer hour (0-23)

        # --- Validasi Input Dasar (mirip /bookRuanganBulk) ---
        if not all([room_ids, tanggal_mulai_str, tanggal_selesai_str, isinstance(jam_mulai_int, int), isinstance(jam_selesai_int, int)]):
            return jsonify({"message": "ERROR", "error": "Data input tidak lengkap atau format jam salah."}), 400
        if jam_selesai_int <= jam_mulai_int:
             return jsonify({"message": "ERROR", "error": "Jam selesai harus setelah jam mulai."}), 400
        if not isinstance(room_ids, list) or not all(isinstance(rid, int) for rid in room_ids):
             return jsonify({"message": "ERROR", "error": "room_ids harus berupa array integer."}), 400

        try:
            tanggal_mulai_date = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
            tanggal_selesai_date = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()
            if tanggal_selesai_date < tanggal_mulai_date:
                raise ValueError("Tanggal selesai tidak boleh sebelum tanggal mulai.")
        except ValueError as e:
             return jsonify({"message": "ERROR", "error": f"Format tanggal salah: {e}"}), 400
        # --- End Validasi Input Dasar ---

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        unavailable_slots = []
        placeholders = ','.join(['%s'] * len(room_ids))

        # Ambil nama ruangan sekali saja untuk pesan error yang lebih baik
        cursor.execute(f"SELECT id_ruangan, nama_ruangan FROM ruangan WHERE id_ruangan IN ({placeholders})", tuple(room_ids))
        room_names = {room['id_ruangan']: room['nama_ruangan'] for room in cursor.fetchall()}

        current_date_check = tanggal_mulai_date
        while current_date_check <= tanggal_selesai_date:
            waktu_mulai_dt = datetime.combine(current_date_check, time(jam_mulai_int))
            waktu_selesai_dt = datetime.combine(current_date_check, time(jam_selesai_int))

            # Penyesuaian jika melintasi tengah malam (sama seperti di booking)
            if waktu_selesai_dt <= waktu_mulai_dt:
                 waktu_selesai_dt += timedelta(days=1)
                 if tanggal_selesai_date == tanggal_mulai_date and len(room_ids) * (tanggal_selesai_date - tanggal_mulai_date + timedelta(days=1)).days == 1 :
                      raise ValueError("Untuk booking satu hari, jam selesai harus setelah jam mulai di hari yang sama.")
                 elif current_date_check == tanggal_selesai_date:
                      waktu_selesai_dt -= timedelta(days=1)

            waktu_mulai_db_str = waktu_mulai_dt.strftime('%Y-%m-%d %H:%M:%S')
            waktu_selesai_db_str = waktu_selesai_dt.strftime('%Y-%m-%d %H:%M:%S')

            # Query untuk cek konflik PADA HARI INI untuk SEMUA ruangan yang diminta
            check_query = f"""
                SELECT id_ruangan
                FROM booking_ruangan
                WHERE id_ruangan IN ({placeholders})
                  AND waktu_mulai < %s
                  AND waktu_selesai > %s
            """
            # Parameter: room_ids tuple, waktu_selesai_db_str, waktu_mulai_db_str
            params = tuple(room_ids) + (waktu_selesai_db_str, waktu_mulai_db_str)
            cursor.execute(check_query, params)
            conflicts = cursor.fetchall()

            if conflicts:
                for conflict in conflicts:
                    room_id = conflict['id_ruangan']
                    unavailable_slots.append({
                        "room_id": room_id,
                        "nama_ruangan": room_names.get(room_id, f"ID {room_id}"),
                        "tanggal": current_date_check.strftime('%Y-%m-%d'),
                        "jam_mulai": jam_mulai_int,
                        "jam_selesai": jam_selesai_int,
                        "message": f"{room_names.get(room_id, f'Ruangan ID {room_id}')} tidak tersedia pada {current_date_check.strftime('%d-%m-%Y')} jam {jam_mulai_int}:00 - {jam_selesai_int}:00"
                    })

            current_date_check += timedelta(days=1) # Pindah ke hari berikutnya

        # Jika tidak ada konflik, unavailable_slots akan kosong
        return jsonify({
            "message": "OK",
            "available": len(unavailable_slots) == 0,
            "unavailable_slots": unavailable_slots
        }), 200

    except ValueError as ve: # Tangkap error validasi format/logika
        print(f"Validation Error check availability: {ve}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(ve)}), 400
    except Exception as e:
        print(f"Error pada /check-availability-bulk: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": "Terjadi kesalahan internal saat memeriksa ketersediaan."}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()





def check_room_availability(cursor, room_id, start_time_utc, end_time_utc):
    """
    (PLACEHOLDER - GANTI DENGAN LOGIKA ANDA)
    Memeriksa apakah ruangan tersedia dalam rentang waktu tertentu.
    Harus mengembalikan True jika tersedia, False jika tidak.
    """
    # Contoh Query Sederhana (HARUS DISESUAIKAN):
    query = """
        SELECT COUNT(*) as conflicts
        FROM booking_ruangan
        WHERE id_ruangan = %s
          AND (
            (%s < waktu_selesai AND %s > waktu_mulai) -- Ada overlap
          )
          AND id_transaksi NOT IN (SELECT id_transaksi FROM transaksi WHERE status_pembayaran = 'Dibatalkan') -- Abaikan yang dibatalkan
    """
    try:
        cursor.execute(query, (room_id, start_time_utc, end_time_utc))
        result = cursor.fetchone()
        # Jika fetchone() mengembalikan None atau 'conflicts' tidak ada, anggap error/tidak tersedia
        if result is None or 'conflicts' not in result:
             print(f"--- DEBUG Availability Check: Error fetching conflicts for room {room_id}")
             return False # Atau lemparkan exception
        print(f"--- DEBUG Availability Check: Room {room_id} conflicts found: {result['conflicts']}")
        return result['conflicts'] == 0 # Tersedia jika tidak ada konflik
    except Exception as e:
        print(f"--- DEBUG Availability Check: DB Error checking room {room_id}: {e}")
        # Sebaiknya lemparkan exception di sini agar transaksi dibatalkan
        raise DbError(f"Database error saat memeriksa ketersediaan: {e}") # Import DbError dari mysql.connector.errors


# --- Endpoint Utama dengan Perbaikan & Debugging ---
@ruangan_endpoints.route('/createBulk', methods=['POST'])
@jwt_required()
def create_bulk_booking():
    print("\n--- DEBUG: >>> ENTERED create_bulk_booking function <<< ---")
    """
    Endpoint untuk membuat multiple booking ruangan (Private Office style)
    oleh pengguna yang sudah login.
    """
    
    connection = None
    cursor_dict = None # Cursor dictionary untuk check_availability
    cursor_normal_trans = None # Cursor normal untuk insert transaksi
    cursor_normal_book = None # Cursor normal untuk insert booking

    print("\n--- DEBUG: Incoming request to /createBulk ---") # Tanda mulai request

    try:
        # 1. Ambil ID User dari Token JWT
        current_user = get_jwt_identity()
        print(f"--- DEBUG: JWT Identity Received: {current_user}")

        # Pastikan identity adalah dictionary
        if not isinstance(current_user, dict):
             print("--- DEBUG: ERROR - JWT identity is not a dictionary.")
             return jsonify({"message": "ERROR", "error": "Format token tidak sesuai."}), 401

        id_user_login = current_user.get('id_user')
        print(f"--- DEBUG: Extracted User ID from token: {id_user_login}")

        if not id_user_login:
            print("--- DEBUG: ERROR - User ID ('id_user') not found in token identity.")
            return jsonify({"message": "ERROR", "error": "Informasi pengguna ('id_user') tidak ditemukan dalam token."}), 401

        # 2. Ambil & Cetak Data dari Request Body
        data = request.get_json()
        print(f"--- DEBUG: Raw Request Body Received:\n{data}")
        if not data:
            print("--- DEBUG: ERROR - Request body JSON is empty.")
            return jsonify({"message": "ERROR", "error": "Request body JSON tidak ditemukan."}), 400

        # 3. Validasi Input Dasar
        metode_pembayaran_str = data.get('metode_pembayaran', 'Non-Tunai')
        status_pembayaran_str = data.get('status_pembayaran', 'Belum Lunas')
        status_order_str = data.get('status_order', 'Baru')
        bookings_detail = data.get('bookings')
        print(f"--- DEBUG: Parsed - Metode: {metode_pembayaran_str}, Status Bayar: {status_pembayaran_str}, Status Order: {status_order_str}")
        print(f"--- DEBUG: Parsed - Bookings Detail Count: {len(bookings_detail) if isinstance(bookings_detail, list) else 'Invalid'}")

        if not bookings_detail or not isinstance(bookings_detail, list) or len(bookings_detail) == 0:
            print("--- DEBUG: ERROR - Bookings detail array is invalid or empty.")
            return jsonify({"message": "ERROR", "error": "Detail booking (array 'bookings') tidak lengkap atau format salah."}), 400

        # Validasi Enum Values (Penting!)
        valid_metode = ['Tunai', 'Non-Tunai']
        valid_status_bayar = ['Lunas', 'Belum Lunas', 'Dibatalkan', 'Disimpan'] # Tambah Disimpan jika perlu
        valid_status_order = ['Baru', 'Diproses', 'Sebagian_diproses', 'Selesai', 'Batal']
        if metode_pembayaran_str not in valid_metode:
            print(f"--- DEBUG: ERROR - Invalid metode_pembayaran: {metode_pembayaran_str}")
            return jsonify({"message": "ERROR", "error": f"Nilai metode pembayaran tidak valid: {metode_pembayaran_str}"}), 400 # 400 untuk input salah
        if status_pembayaran_str not in valid_status_bayar:
             print(f"--- DEBUG: ERROR - Invalid status_pembayaran: {status_pembayaran_str}")
             return jsonify({"message": "ERROR", "error": f"Nilai status pembayaran tidak valid: {status_pembayaran_str}"}), 400
        if status_order_str not in valid_status_order:
             print(f"--- DEBUG: ERROR - Invalid status_order: {status_order_str}")
             return jsonify({"message": "ERROR", "error": f"Nilai status order tidak valid: {status_order_str}"}), 400

        # --- Inisialisasi Koneksi Database ---
        connection = get_connection()
        if not connection:
            print("--- DEBUG: ERROR - Failed to get database connection.")
            return jsonify({"message": "ERROR", "error": "Tidak dapat terhubung ke database."}), 500
        # Gunakan cursor dictionary hanya jika diperlukan (misal di check_availability)
        cursor_dict = connection.cursor(dictionary=True)

        # 4. Buat Transaksi Utama (Gunakan cursor terpisah tanpa dictionary)
        total_harga_final = 0 # TODO: Hitung harga jika perlu (ini penting!)
        now_utc = datetime.now(timezone.utc) # Gunakan UTC untuk konsistensi

        query_insert_transaksi = """
            INSERT INTO transaksi
            (id_user, nama_guest, total_harga_final, metode_pembayaran, status_pembayaran, status_order, tanggal_transaksi)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor_normal_trans = connection.cursor() # Cursor normal untuk INSERT
        id_transaksi_baru = None
        try:
            print(f"--- DEBUG: Executing INSERT INTO transaksi with User ID: {id_user_login}, Time: {now_utc}")
            cursor_normal_trans.execute(query_insert_transaksi, (
                id_user_login,
                None, # nama_guest NULL
                total_harga_final, metode_pembayaran_str, status_pembayaran_str,
                status_order_str, now_utc
            ))
            id_transaksi_baru = cursor_normal_trans.lastrowid
            if not id_transaksi_baru:
                print("--- DEBUG: ERROR - Failed to get lastrowid after inserting transaction.")
                raise Exception("Gagal membuat record transaksi (lastrowid is null).")
            print(f"--- DEBUG: Main Transaction Record Created with ID: {id_transaksi_baru}")
        except Exception as trans_err:
             print(f"--- DEBUG: ERROR inserting transaction: {trans_err}")
             raise # Lemparkan lagi agar ditangkap di blok except utama
        finally:
            if cursor_normal_trans: cursor_normal_trans.close() # Tutup cursor ini segera

        # 5. Validasi Ketersediaan & Siapkan Insert Booking Ruangan
        query_insert_booking = """
            INSERT INTO booking_ruangan
            (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi, kredit_terpakai)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        bookings_to_insert = []
        booked_room_details = [] # Daftar konflik untuk pesan error

        for i, booking_item in enumerate(bookings_detail):
            print(f"\n--- DEBUG: Processing booking item #{i+1}: {booking_item}")

            id_ruangan = booking_item.get('id_ruangan')
            waktu_mulai_iso = booking_item.get('waktu_mulai')
            waktu_selesai_iso = booking_item.get('waktu_selesai')
            print(f"--- DEBUG #{i+1}: Ruangan ID: {id_ruangan}, Mulai ISO: {waktu_mulai_iso}, Selesai ISO: {waktu_selesai_iso}")

            # Validasi Kelengkapan Data Item Booking
            if not all([id_ruangan, waktu_mulai_iso, waktu_selesai_iso]):
                print(f"--- DEBUG #{i+1}: ERROR - Incomplete booking item data.")
                # Kembalikan 422 karena data tidak bisa diproses
                connection.rollback(); return jsonify({"message": "ERROR", "error": f"Data booking item #{i+1} tidak lengkap."}), 422

            # Konversi & Validasi Waktu (Penyebab umum 422)
            try:
                # Pastikan string ISO valid sebelum parsing
                if not isinstance(waktu_mulai_iso, str) or not isinstance(waktu_selesai_iso, str):
                    raise ValueError("Format waktu harus string ISO.")

                # Handle timezone 'Z' (UTC) dengan benar
                waktu_mulai_dt_utc = datetime.fromisoformat(waktu_mulai_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
                waktu_selesai_dt_utc = datetime.fromisoformat(waktu_selesai_iso.replace('Z', '+00:00')).astimezone(timezone.utc)
                print(f"--- DEBUG #{i+1}: Parsed Mulai UTC: {waktu_mulai_dt_utc}, Parsed Selesai UTC: {waktu_selesai_dt_utc}")

                if waktu_selesai_dt_utc <= waktu_mulai_dt_utc:
                    print(f"--- DEBUG #{i+1}: ERROR - End time ({waktu_selesai_dt_utc}) is not after start time ({waktu_mulai_dt_utc}).")
                    raise ValueError("Waktu selesai harus setelah waktu mulai.")

                # Validasi tambahan: Waktu mulai tidak boleh di masa lalu
                # if waktu_mulai_dt_utc < datetime.now(timezone.utc) - timedelta(minutes=5): # Toleransi 5 menit
                #     print(f"--- DEBUG #{i+1}: ERROR - Start time is in the past.")
                #     raise ValueError("Waktu mulai tidak boleh di masa lalu.")

            except ValueError as e:
                print(f"--- DEBUG #{i+1}: ERROR - Invalid time format or logic: {e}")
                # Kembalikan 422 karena data waktu tidak bisa diproses
                connection.rollback(); return jsonify({"message": "ERROR", "error": f"Format atau logika waktu tidak valid untuk item #{i+1}: {e}"}), 422
            except Exception as time_err: # Tangkap error parsing lain
                print(f"--- DEBUG #{i+1}: ERROR - Unexpected error parsing time: {time_err}")
                connection.rollback(); return jsonify({"message": "ERROR", "error": f"Gagal memproses waktu untuk item #{i+1}."}), 422

            # Validasi Ketersediaan (Penyebab 409)
            try:
                if not check_room_availability(cursor_dict, id_ruangan, waktu_mulai_dt_utc, waktu_selesai_dt_utc):
                    cursor_dict.execute("SELECT nama_ruangan FROM ruangan WHERE id_ruangan = %s", (id_ruangan,))
                    room_info = cursor_dict.fetchone()
                    room_name = room_info['nama_ruangan'] if room_info else f"ID {id_ruangan}"
                    # Format waktu lokal (misal WITA = UTC+8) untuk pesan error yang lebih ramah
                    wita = timezone(timedelta(hours=8))
                    start_local = waktu_mulai_dt_utc.astimezone(wita).strftime('%d/%m %H:%M')
                    end_local = waktu_selesai_dt_utc.astimezone(wita).strftime('%H:%M')
                    booked_room_details.append(f"'{room_name}' ({start_local} - {end_local})")
                    print(f"--- DEBUG #{i+1}: CONFLICT - Room ID {id_ruangan} is not available at specified time.")
            except DbError as db_avail_err: # Tangkap error DB dari check_availability
                 print(f"--- DEBUG #{i+1}: DB ERROR during availability check: {db_avail_err}")
                 connection.rollback(); return jsonify({"message": "ERROR", "error": "Gagal memeriksa ketersediaan ruangan."}), 500

            # Hitung Durasi (dalam menit)
            durasi_menit = max(0, int((waktu_selesai_dt_utc - waktu_mulai_dt_utc).total_seconds() / 60))
            print(f"--- DEBUG #{i+1}: Calculated Duration: {durasi_menit} minutes.")

            # Siapkan tuple untuk executemany (gunakan waktu UTC)
            bookings_to_insert.append((
                id_transaksi_baru, id_ruangan,
                waktu_mulai_dt_utc, waktu_selesai_dt_utc, # Simpan sebagai UTC di DB
                durasi_menit, 0 # kredit_terpakai default 0
            ))

        # Jika ada konflik ketersediaan, batalkan seluruh transaksi
        if booked_room_details:
            connection.rollback()
            error_message = "Ruangan berikut tidak tersedia pada waktu yang dipilih: " + ", ".join(booked_room_details) + ". Silakan ubah pilihan waktu atau ruangan Anda."
            print(f"--- DEBUG: ERROR - Availability conflicts found, rolling back. Details: {booked_room_details}")
            return jsonify({"message": "ERROR", "error": error_message}), 409 # 409 Conflict

        # 6. Jalankan Insert Booking (Gunakan cursor terpisah tanpa dictionary)
        if bookings_to_insert:
            cursor_normal_book = connection.cursor() # Cursor normal untuk INSERT
            try:
                print(f"--- DEBUG: Executing bulk INSERT INTO booking_ruangan for {len(bookings_to_insert)} items.")
                cursor_normal_book.executemany(query_insert_booking, bookings_to_insert)
                print(f"--- DEBUG: Successfully executed bulk insert for booking items.")
            except Exception as insert_err:
                connection.rollback()
                print(f"--- DEBUG: ERROR executing bulk insert booking_ruangan: {insert_err}")
                return jsonify({"message": "ERROR", "error": "Gagal menyimpan detail booking ke database."}), 500
            finally:
                if cursor_normal_book: cursor_normal_book.close() # Tutup cursor ini
        else:
            # Ini seharusnya tidak terjadi jika validasi awal `bookings_detail` benar
            connection.rollback()
            print("--- DEBUG: ERROR - No valid booking items to insert after processing loop.")
            return jsonify({"message": "ERROR", "error": "Tidak ada detail booking yang valid untuk disimpan."}), 400

        # 7. Commit Transaksi jika semua berhasil
        connection.commit()
        print(f"--- DEBUG: <<< SUCCESS >>> Bulk booking successful for user {id_user_login}, transaction {id_transaksi_baru}")
        return jsonify({"message": "Pesanan ruangan berhasil dibuat!", "id_transaksi": id_transaksi_baru}), 201

    except ValueError as ve: # Tangkap ValueError lebih spesifik (bisa dari parsing waktu atau int())
        if connection: connection.rollback()
        print(f"--- DEBUG: ValueError (likely data processing error): {ve}")
        # Kembalikan 422 karena data tidak bisa diproses
        return jsonify({"message": "ERROR", "error": f"Data tidak dapat diproses: {ve}"}), 422
    except Exception as e: # Tangkap semua error lain sebagai 500
        if connection: connection.rollback()
        # Cetak traceback lengkap untuk debugging error tak terduga
        print(f"--- DEBUG: !!! UNHANDLED EXCEPTION in /createBulk !!!")
        print(f"--- Exception Type: {type(e).__name__}")
        print(f"--- Exception Args: {e.args}")
        traceback.print_exc(file=sys.stdout) # Cetak ke log server
        return jsonify({"message": "ERROR", "error": "Terjadi kesalahan internal pada server."}), 500
    finally:
        # Selalu pastikan cursor dan koneksi ditutup
        if cursor_dict: cursor_dict.close()
        # cursor_normal_trans dan cursor_normal_book sudah ditutup di dalam try/finally masing-masing
        if connection: connection.close()
        print("--- DEBUG: Finished processing /createBulk request ---") # Tanda akhir request


@ruangan_endpoints.route('/getVOClientByUserId', methods=['GET'])
def get_vo_client_by_user_id():
    """
    Mengambil data klien Virtual Office beserta sisa benefit yang dihitung
    berdasarkan bulan dari tanggal yang diminta.
    Query parameters:
      - id_user: ID dari user.
      - target_date: Tanggal target untuk pengecekan benefit (format: YYYY-MM-DD).
    """
    id_user = request.args.get('id_user')
    target_date_str = request.args.get('target_date')

    if not id_user:
        return jsonify({'message': 'Parameter id_user diperlukan'}), 400

    # Gunakan tanggal hari ini jika parameter target_date tidak diberikan
    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else datetime.now().date()
    except ValueError:
        return jsonify({'message': 'Format tanggal tidak valid, gunakan YYYY-MM-DD'}), 400

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Dapatkan data klien VO dan total jatah benefit bulanannya
        query_client = """
            SELECT 
                cvo.id_client_vo,
                cvo.nama_perusahaan_klien,
                pvo.benefit_jam_meeting_room_per_bulan,
                pvo.benefit_jam_working_space_per_bulan
            FROM 
                client_virtual_office cvo
            JOIN 
                paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
            WHERE 
                cvo.id_user = %s AND cvo.status_client_vo = 'Aktif'
            LIMIT 1;
        """
        cursor.execute(query_client, (id_user,))
        client_data = cursor.fetchone()

        if not client_data:
            return jsonify({'message': 'Klien Virtual Office aktif tidak ditemukan'}), 404

        id_client_vo = client_data['id_client_vo']

        # 2. Hitung total menit benefit yang sudah terpakai PADA BULAN TARGET
        query_usage = """
            SELECT 
                jenis_benefit, 
                SUM(durasi_terpakai_menit) as total_menit_terpakai
            FROM 
                penggunaan_benefit_vo
            WHERE
                id_client_vo = %s
                AND MONTH(tanggal_penggunaan) = %s
                AND YEAR(tanggal_penggunaan) = %s
            GROUP BY 
                jenis_benefit;
        """
        cursor.execute(query_usage, (id_client_vo, target_date.month, target_date.year))
        usage_data = cursor.fetchall()

        # Siapkan struktur untuk menampung hasil perhitungan
        usage_map = {
            'meeting_room': 0,
            'working_space': 0
        }
        for row in usage_data:
            usage_map[row['jenis_benefit']] = row['total_menit_terpakai']

        # 3. Hitung sisa benefit dalam jam
        total_mr_minutes = (client_data.get('benefit_jam_meeting_room_per_bulan') or 0) * 60
        used_mr_minutes = usage_map['meeting_room']
        sisa_mr_jam = (total_mr_minutes - used_mr_minutes) / 60

        total_ws_minutes = (client_data.get('benefit_jam_working_space_per_bulan') or 0) * 60
        used_ws_minutes = usage_map['working_space']
        sisa_ws_jam = (total_ws_minutes - used_ws_minutes) / 60
        
        # Pastikan tidak ada nilai negatif
        sisa_mr_jam = max(0, sisa_mr_jam)
        sisa_ws_jam = max(0, sisa_ws_jam)


        # 4. Susun response JSON
        response_data = {
            "id_client_vo": id_client_vo,
            "nama_perusahaan_klien": client_data['nama_perusahaan_klien'],
            "benefit_tersisa": {
                "meeting_room": sisa_mr_jam,
                "working_space": sisa_ws_jam
            }
        }

        return jsonify({'data': response_data}), 200

    except Exception as e:
        print(f"Error pada get_vo_client_by_user_id: {e}")
        return jsonify({'message': 'Terjadi kesalahan pada server'}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@ruangan_endpoints.route('/workspaces', methods=['GET'])
def get_workspaces_summary():
    """
    Mengambil ringkasan dari setiap kategori ruangan dengan format kapasitas kondisional.
    Untuk Room Meeting, menampilkan jumlah ruangan. Untuk lainnya, total kapasitas.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # PERBAIKAN: Mengubah klausa WHERE untuk mencakup semua jenis Room Meeting
        query = """
            SELECT 
                kr.id_kategori_ruangan,
                kr.nama_kategori AS title,
                kr.deskripsi AS `desc`,
                kr.gambar_kategori_ruangan AS img_filename,
                (SELECT SUM(r.kapasitas) FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan) AS total_capacity,
                (SELECT COUNT(r.id_ruangan) FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan) AS room_count,
                (SELECT MIN(phr.harga_paket) FROM paket_harga_ruangan phr JOIN ruangan r ON phr.id_ruangan = r.id_ruangan WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan AND phr.harga_paket > 0) AS min_price,
                (SELECT r.fitur_ruangan FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan LIMIT 1) AS fasilitas_sample
            FROM 
                kategori_ruangan kr
            WHERE
                -- Menggunakan LIKE untuk mengambil 'Room Meeting Besar' dan 'Room Meeting Kecil'
                kr.nama_kategori IN ('Space Monitor', 'Open Space') OR kr.nama_kategori LIKE 'Room Meeting%%';
        """
        cursor.execute(query)
        workspaces = cursor.fetchall()
        
        formatted_workspaces = []
        for ws in workspaces:
            fasilitas_list = ws['fasilitas_sample'].strip().split('\n') if ws['fasilitas_sample'] else []
            price_str = f"Rp{int(ws['min_price']):,}".replace(',', '.') if ws['min_price'] else "N/A"

            capacity_display = ""
            # PERBAIKAN: Cek jika judul mengandung "Room Meeting"
            if 'Room Meeting' in ws['title']:
                # Format sebagai jumlah ruangan
                capacity_display = f"{ws['room_count']}"
            else:
                # Format sebagai total kapasitas untuk kategori lain
                capacity_display = int(ws['total_capacity']) if ws['total_capacity'] else 0

            formatted_workspaces.append({
                "category": "Working Space",
                "title": ws['title'],
                "desc": ws['desc'],
                "img": ws['img_filename'],
                "capacity": capacity_display,
                "time": "08:00 - 22:00",
                "date": datetime.now().strftime("%d %b %Y"),
                "price": price_str,
                "features": ["Wifi", "Refill Water", "AC"],
                "fasilitas": [f.strip() for f in fasilitas_list if f.strip()],
            })
            
        # Menambahkan data statis untuk "Space Lesehan"
        formatted_workspaces.append({
             "category": "Working Space",
             "title": "Space Lesehan",
             "desc": "Space lesehan dengan dudukan bantal dan meja.",
             "img": "space_lesehan.jpg",
             "capacity": "Fleksibel",
             "time": "08:00 - 22:00",
             "date": datetime.now().strftime("%d %b %Y"),
             "price": "FREE",
             "features": ["Wifi", "Refill Water"],
             "fasilitas": ["Ruangan Full AC","Meja lesehan & bantal duduk", "Akses Wi-Fi", "Colokan listrik"],
             "note": "*Dengan syarat melakukan pemesanan F&B di lokasi",
        })

        return jsonify({"message": "OK", "datas": formatted_workspaces}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()   



@ruangan_endpoints.route('/ruangan/<int:id_ruangan>/booked_hours/<string:tanggal>', methods=['GET'])
def get_booked_hours(id_ruangan, tanggal):
    """
    Endpoint untuk mendapatkan jam-jam yang sudah dibooking untuk ruangan tertentu
    pada tanggal tertentu.
    """
    connection = None
    cursor = None
    try:
        # Validasi format tanggal
        try:
            selected_date = datetime.strptime(tanggal, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"message": "ERROR", "error": "Format tanggal salah. Gunakan YYYY-MM-DD."}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT waktu_mulai, waktu_selesai
            FROM booking_ruangan
            WHERE id_ruangan = %s AND DATE(waktu_mulai) = %s
        """
        cursor.execute(query, (id_ruangan, selected_date))
        bookings = cursor.fetchall()

        # Proses data untuk membuat daftar jam yang terisi
        booked_hours = set()
        for booking in bookings:
            start_hour = booking['waktu_mulai'].hour
            end_hour = booking['waktu_selesai'].hour
            # Tambahkan semua jam dari rentang waktu booking ke dalam set
            # (Contoh: booking 09:00-11:00 akan mengisi jam 9 dan 10)
            for hour in range(start_hour, end_hour):
                booked_hours.add(hour)

        return jsonify({"message": "OK", "datas": {"booked_hours": list(booked_hours)}}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
            
            
# Di atas file, pastikan Anda mengimpor json
import json
from datetime import datetime, timedelta
from flask import jsonify

# ... (kode lainnya)

@ruangan_endpoints.route('/readPromos', methods=['GET'])
def readPromo():
    """Routes for module get list promo"""
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # DIUBAH: Mengganti SELECT * dengan nama kolom eksplisit untuk memaksa pembacaan kolom 'syarat'
        select_query = """
            SELECT 
                id_promo, kode_promo, deskripsi_promo, nilai_diskon, 
                tanggal_mulai, tanggal_selesai, waktu_mulai, waktu_selesai, 
                status_aktif, syarat 
            FROM promo
            WHERE status_aktif = 'aktif'
              AND CURDATE() BETWEEN tanggal_mulai AND tanggal_selesai
        """
        cursor.execute(select_query)
        results = cursor.fetchall()

        # Proses setiap baris hasil
        for row in results:
            if row.get('syarat') and isinstance(row['syarat'], str):
                try:
                    row['syarat'] = json.loads(row['syarat'])
                except json.JSONDecodeError:
                    row['syarat'] = None

            for key, value in row.items():
                if isinstance(value, (datetime, timedelta)):
                    row[key] = str(value)

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

# @ruangan_endpoints.route('/readPromo', methods=['GET'])
# def readPromo():
#     """Routes for module get list promo"""
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         select_query = "SELECT * FROM promo WHERE status_aktif = 'aktif'"
#         cursor.execute(select_query)
#         results = cursor.fetchall()

#         # Convert timedelta or datetime to string
#         for row in results:
#             for key, value in row.items():
#                 if isinstance(value, (timedelta, datetime)):
#                     row[key] = str(value)

#         return jsonify({"message": "OK", "datas": results}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

from flask import jsonify, request
# Pastikan Anda mengimpor fungsi untuk koneksi database Anda, contoh:
# from your_app.db import get_connection


@ruangan_endpoints.route('/readMembershipByUserId', methods=['GET'])
def readMembershipByUserId():
    """
    Mengambil data membership aktif yang dimiliki oleh seorang user
    berdasarkan kategori ruangan tertentu.
    Query parameters:
      - id_user: ID dari user yang ingin diperiksa.
      - id_kategori_ruangan: ID dari kategori ruangan (e.g., Open Space, Room Meeting).
    """
    # 1. Ambil query parameter dari request URL
    id_user = request.args.get('id_user')
    id_kategori_ruangan = request.args.get('id_kategori_ruangan')

    # 2. Validasi input
    if not id_user or not id_kategori_ruangan:
        return jsonify({
            'message': 'Parameter id_user dan id_kategori_ruangan diperlukan'
        }), 400

    conn = None
    cursor = None
    try:
        # 3. Buat koneksi ke database
        # (Gantilah 'get_connection' dengan fungsi koneksi database Anda)
        conn = get_connection() 
        # Menggunakan dictionary=True agar hasil query bisa langsung di-serialize ke JSON
        cursor = conn.cursor(dictionary=True)

        # 4. Buat query SQL untuk mengambil data
        # Query ini menggabungkan tabel memberships dan paket_membership
        # lalu memfilternya berdasarkan user dan kategori ruangan
        query = """
            SELECT 
                m.id_memberships,
                m.id_user,
                m.tanggal_mulai,
                m.tanggal_berakhir,
                m.total_credit,
                m.sisa_credit,
                m.status_memberships,
                pm.nama_paket,
                pm.harga,
                kr.nama_kategori as nama_kategori_ruangan
            FROM 
                memberships m
            JOIN 
                paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
            JOIN
                kategori_ruangan kr ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
            WHERE 
                m.id_user = %s 
                AND pm.id_kategori_ruangan = %s
                AND m.status_memberships = 'Active';
        """

        # 5. Eksekusi query dengan parameter yang aman
        cursor.execute(query, (id_user, id_kategori_ruangan))
        memberships = cursor.fetchall()

        # 6. Kirim response
        if not memberships:
            return jsonify({
                'message': 'Tidak ada membership aktif yang ditemukan untuk user dan kategori ruangan ini'
            }), 404
        
        return jsonify(memberships), 200

    except Exception as e:
        # Penanganan jika terjadi error pada server atau database
        print(f"Error: {e}") # Sebaiknya di-log ke file
        return jsonify({'message': 'Terjadi kesalahan pada server'}), 500
        
    finally:
        # 7. Pastikan koneksi dan cursor ditutup
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@ruangan_endpoints.route('/readRuangan', methods=['GET'])
def readRuangan():
    """Routes for module get list ruangan with price packages AND today's schedule"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Ambil semua data ruangan dan paketnya (seperti sebelumnya)
        query_ruangan = """
            SELECT r.*, k.nama_kategori
            FROM ruangan r
            JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
            WHERE k.status = 'Active'
        """
        cursor.execute(query_ruangan)
        ruangan_list = cursor.fetchall()

        for ruangan in ruangan_list:
            query_paket = "SELECT durasi_jam, harga_paket FROM paket_harga_ruangan WHERE id_ruangan = %s"
            cursor.execute(query_paket, (ruangan['id_ruangan'],))
            ruangan['paket_harga'] = cursor.fetchall()
            
        # === PERUBAHAN BARU DIMULAI DI SINI ===
        
        # 2. Ambil semua booking untuk HARI INI
        today_date = datetime.now().date()
        query_bookings_today = """
            SELECT id_ruangan, waktu_mulai, waktu_selesai
            FROM booking_ruangan
            WHERE DATE(waktu_mulai) = %s
        """
        cursor.execute(query_bookings_today, (today_date,))
        bookings_today = cursor.fetchall()
        
        # 3. Kelompokkan jam yang sudah dibooking berdasarkan id_ruangan
        booked_hours_map = {}
        for booking in bookings_today:
            room_id = booking['id_ruangan']
            if room_id not in booked_hours_map:
                booked_hours_map[room_id] = set()
            
            start_hour = booking['waktu_mulai'].hour
            end_hour = booking['waktu_selesai'].hour
            for hour in range(start_hour, end_hour):
                booked_hours_map[room_id].add(hour)
        
        # 4. Sisipkan jadwal booking hari ini ke setiap objek ruangan
        for ruangan in ruangan_list:
            room_id = ruangan['id_ruangan']
            if room_id in booked_hours_map:
                # Ubah set menjadi list agar bisa di-serialize ke JSON
                ruangan['jadwal_hari_ini'] = sorted(list(booked_hours_map[room_id]))
            else:
                ruangan['jadwal_hari_ini'] = [] # Beri array kosong jika tidak ada booking
        # === PERUBAHAN SELESAI ===

        return jsonify({"message": "OK", "datas": ruangan_list}), 200
        
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# @ruangan_endpoints.route('/readRuangan', methods=['GET'])
# def readRuangan():
#     """Routes for module get list ruangan with price packages"""
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
        
#         # Query pertama: Ambil semua data ruangan
#         select_ruangan_query = """
#             SELECT r.*, k.nama_kategori
#             FROM ruangan r
#             JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
#         """
#         cursor.execute(select_ruangan_query)
#         ruangan_list = cursor.fetchall()
        
#         # --- PERUBAHAN DIMULAI DI SINI ---
#         # Untuk setiap ruangan, ambil data paket harganya
#         for ruangan in ruangan_list:
#             select_paket_query = """
#                 SELECT durasi_jam, harga_paket 
#                 FROM paket_harga_ruangan 
#                 WHERE id_ruangan = %s
#             """
#             cursor.execute(select_paket_query, (ruangan['id_ruangan'],))
#             paket_harga = cursor.fetchall()
            
#             # Tambahkan data paket harga ke dalam objek ruangan
#             ruangan['paket_harga'] = paket_harga
#         # --- PERUBAHAN SELESAI DI SINI ---

#         return jsonify({"message": "OK", "datas": ruangan_list}), 200
        
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

# @ruangan_endpoints.route('/readRuangan', methods=['GET'])
# def readRuangan():
#     """Routes for module get list ruangan"""
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         select_query = select_query = """
#         SELECT r.*, k.nama_kategori
#         FROM ruangan r
#         JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
#         """
#         cursor.execute(select_query)
#         results = cursor.fetchall()
#         return jsonify({"message": "OK", "datas": results}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
            
@ruangan_endpoints.route('/readMembership', methods=['GET'])
def readMembership():
    """Ambil daftar paket membership + kategori ruangan"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            pm.id_paket_membership,
            pm.nama_paket,
            pm.harga,
            pm.durasi,
            pm.kuota,
            pm.deskripsi_benefit,
            kr.id_kategori_ruangan,
            kr.nama_kategori
        FROM paket_membership pm
        JOIN kategori_ruangan kr 
            ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
        """
        cursor.execute(query)
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
            
# File: ruangan_endpoints.py
@ruangan_endpoints.route('/event-spaces', methods=['GET'])
def get_all_event_spaces():
    """
    Endpoint publik untuk mengambil semua event space yang tersedia.
    Tidak memerlukan autentikasi.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query untuk mengambil data dari tabel event_spaces
        query = """
            SELECT
                id_event_space,
                nama_event_space,
                deskripsi_event_space,
                harga_paket,
                kapasitas,
                gambar_ruangan,
                fitur_ruangan
            FROM event_spaces
            WHERE status_ketersediaan = 'Active'
        """
        cursor.execute(query)
        event_spaces = cursor.fetchall()

        return jsonify(event_spaces), 200

    except Exception as e:
        # Mengembalikan pesan error jika terjadi masalah
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        # Memastikan koneksi database selalu ditutup
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

@ruangan_endpoints.route('/event-spaces/<int:space_id>', methods=['GET'])
def get_event_space_by_id(space_id):
    """
    Endpoint untuk mengambil detail satu event space berdasarkan ID.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                id_event_space,
                nama_event_space,
                deskripsi_event_space,
                harga_paket,
                kapasitas,
                gambar_ruangan,
                fitur_ruangan
            FROM event_spaces
            WHERE id_event_space = %s
        """
        cursor.execute(query, (space_id,))
        event_space = cursor.fetchone()

        if not event_space:
            return jsonify({"msg": "Event space not found"}), 404

        return jsonify(event_space), 200

    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()
            

# Di file endpoint Python Anda
@ruangan_endpoints.route('/bookingEvent', methods=['POST'])
def create_booking():
    data = request.get_json()

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Insert transaksi (tetap sama)
        transaksi_query = """
            INSERT INTO transaksi (id_user, total_harga_final, status_pembayaran, status_order)
            VALUES (%s, %s, 'Belum Lunas', 'Baru')
        """
        cursor.execute(transaksi_query, (data.get("id_user"), data.get("total_harga_final")))
        id_transaksi = cursor.lastrowid

        # 2. Insert booking_event (diperbarui dengan kolom baru)
        booking_query = """
            INSERT INTO booking_event (
                id_event_space, id_user, id_transaksi, tanggal_event, 
                waktu_mulai, waktu_selesai, status_booking,
                nama_acara, deskripsi, jumlah_peserta, kebutuhan_tambahan
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'Baru', %s, %s, %s, %s)
        """
        cursor.execute(
            booking_query,
            (
                data.get("id_event_space"),
                data.get("id_user"),
                id_transaksi,
                data.get("tanggal_event"),
                data.get("waktu_mulai"), # Pastikan frontend mengirim format 'YYYY-MM-DD HH:MM:SS'
                data.get("waktu_selesai"),# Pastikan frontend mengirim format 'YYYY-MM-DD HH:MM:SS'
                data.get("nama_acara"),
                data.get("deskripsi"),
                data.get("jumlah_peserta"),
                data.get("kebutuhan_tambahan")
            )
        )
        id_booking = cursor.lastrowid

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Booking berhasil dibuat",
            "data": {
                "id_booking_event": id_booking,
                "id_transaksi": id_transaksi
            }
        }), 201
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()



# @ruangan_endpoints.route('/bookingEvent', methods=['POST'])
# def create_booking():
#     """
#     Endpoint untuk membuat booking baru.
#     """
#     data = request.get_json()

#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # 1. Insert transaksi
#         transaksi_query = """
#             INSERT INTO transaksi (id_user, total_harga_final, status_pembayaran, status_order, nama_guest)
#             VALUES (%s, %s, %s, %s, %s)
#         """
#         cursor.execute(
#             transaksi_query,
#             (
#                 data.get("id_user"),  # NULL jika guest
#                 data.get("total_harga_final"),
#                 "Belum Lunas",  # default status pembayaran
#                 "Baru",         # default status order
#                 data.get("nama_pemesan")
#             )
#         )
#         id_transaksi = cursor.lastrowid

#         # 2. Insert booking_event
#         booking_query = """
#             INSERT INTO booking_event (id_event_space, id_user, id_transaksi, tanggal_event, waktu_mulai, waktu_selesai, status_booking)
#             VALUES (%s, %s, %s, %s, %s, %s, %s)
#         """
#         cursor.execute(
#             booking_query,
#             (
#                 data.get("id_event_space"),
#                 data.get("id_user"),
#                 id_transaksi,
#                 data.get("tanggal_event"),
#                 data.get("waktu_mulai"),
#                 data.get("waktu_selesai"),
#                 "Baru"  # default status
#             )
#         )
#         id_booking = cursor.lastrowid

#         connection.commit()

#         return jsonify({
#             "success": True,
#             "message": "Booking berhasil dibuat",
#             "data": {
#                 "id_booking_event": id_booking,
#                 "id_transaksi": id_transaksi
#             }
#         }), 201

    # except Exception as e:
    #     return jsonify({
    #         "success": False,
    #         "message": f"Database error: {str(e)}"
    #     }), 500
    # finally:
    #     if 'cursor' in locals():
    #         cursor.close()
    #     if 'connection' in locals():
    #         connection.close()


from datetime import datetime, timedelta # Pastikan ini diimport

@ruangan_endpoints.route('/bookRuangan', methods=['POST'])
@jwt_required() # Uncomment ini agar aman!
def book_ruangan():
    """
    Buat transaksi & booking untuk ruangan.
    Mendukung multi-hari, pembayaran kredit membership, benefit virtual office, dan iPaymu.
    """
    connection = None
    cursor = None
    try:
        data = request.json
        
        # --- 1. Ambil & Validasi Data Payload ---
        id_user = data.get("id_user")
        id_ruangan = data.get("id_ruangan")
        tanggal_mulai_str = data.get("tanggal_mulai")
        tanggal_selesai_str = data.get("tanggal_selesai")
        jam_mulai = int(data.get("jam_mulai", 0))
        jam_selesai = int(data.get("jam_selesai", 0))
        total_harga = data.get("total_harga_final", 0)
        
        payment_method = data.get("paymentMethod")
        membership_id = data.get("membershipId")
        credit_cost = data.get("creditCost", 0)
        virtual_office_id = data.get("virtualOfficeId")
        
        booking_source = data.get("booking_source", "RoomDetail")

        # Validasi field wajib dasar
        if not all([id_user, id_ruangan, tanggal_mulai_str, tanggal_selesai_str, jam_mulai, jam_selesai]):
             return jsonify({"message": "ERROR", "error": "Data booking tidak lengkap."}), 400

        # --- 2. Konversi Tanggal ---
        tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
        tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()
        durasi_per_hari = jam_selesai - jam_mulai
        
        if durasi_per_hari <= 0:
             return jsonify({"message": "ERROR", "error": "Durasi booking tidak valid."}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        connection.start_transaction()

        # --- 3. Validasi Ketersediaan (Anti-Bentrok) ---
        current_date_check = tanggal_mulai
        while current_date_check <= tanggal_selesai:
            waktu_mulai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_mulai)
            waktu_selesai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_selesai)
            
            check_query = "SELECT id_booking FROM booking_ruangan WHERE id_ruangan = %s AND (waktu_mulai < %s AND waktu_selesai > %s)"
            cursor.execute(check_query, (id_ruangan, waktu_selesai_check, waktu_mulai_check))
            if cursor.fetchone():
                connection.rollback()
                return jsonify({"message": "ERROR", "error": f"Slot pada tanggal {current_date_check.strftime('%d-%m-%Y')} sudah terisi."}), 409
            
            current_date_check += timedelta(days=1)

        # --- 4. Validasi Saldo/Benefit ---
        if payment_method == 'credit':
            cursor.execute("SELECT sisa_credit FROM memberships WHERE id_memberships = %s AND id_user = %s", (membership_id, id_user))
            member = cursor.fetchone()
            if not member or member['sisa_credit'] < credit_cost:
                connection.rollback()
                return jsonify({"message": "ERROR", "error": "Kredit tidak mencukupi atau membership tidak valid."}), 400
        
        elif payment_method == 'virtual_office':
            # Ambil paket VO aktif
            cursor.execute("""
                SELECT 
                    cvo.id_client_vo,
                    pvo.benefit_jam_meeting_room_per_bulan, 
                    pvo.benefit_jam_working_space_per_bulan 
                FROM client_virtual_office cvo 
                JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo 
                WHERE cvo.id_client_vo = %s AND cvo.id_user = %s AND cvo.status_client_vo = 'Aktif'
            """, (virtual_office_id, id_user))
            paket_vo = cursor.fetchone()
            
            if not paket_vo:
                connection.rollback()
                return jsonify({"message": "ERROR", "error": "Klien Virtual Office tidak valid atau tidak aktif."}), 400

            # Cek jenis ruangan untuk menentukan kuota mana yang dicek
            cursor.execute("SELECT kr.nama_kategori FROM ruangan r JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan WHERE r.id_ruangan = %s", (id_ruangan,))
            kat_ruangan = cursor.fetchone()
            jenis_benefit = 'meeting_room' if kat_ruangan and 'Meeting' in kat_ruangan['nama_kategori'] else 'working_space'
            
            # Hitung pemakaian bulan ini
            today = datetime.now()
            cursor.execute("""
                SELECT SUM(durasi_terpakai_menit) as total_used 
                FROM penggunaan_benefit_vo 
                WHERE id_client_vo = %s AND jenis_benefit = %s AND MONTH(tanggal_penggunaan) = %s AND YEAR(tanggal_penggunaan) = %s
            """, (virtual_office_id, jenis_benefit, today.month, today.year))
            usage = cursor.fetchone()
            used_minutes = usage['total_used'] if usage and usage['total_used'] else 0
            
            limit_minutes = (paket_vo[f'benefit_jam_{jenis_benefit}_per_bulan'] or 0) * 60
            
            # Hitung durasi booking total (menit)
            total_days = (tanggal_selesai - tanggal_mulai).days + 1
            booking_minutes = durasi_per_hari * 60 * total_days
            
            if (used_minutes + booking_minutes) > limit_minutes:
                 connection.rollback()
                 return jsonify({"message": "ERROR", "error": "Sisa kuota benefit Virtual Office tidak mencukupi."}), 400


        # --- 5. Persiapan Data Transaksi ---
        harga_transaksi = 0
        metode_pembayaran_db = "qris" 
        status_pembayaran_awal = 'Lunas' # Default Lunas (untuk Credit/VO)

        if payment_method == 'normal':
            harga_transaksi = total_harga
            status_pembayaran_awal = 'Belum Lunas' # PENTING: Untuk iPaymu
            metode_pembayaran_db = "Ipaymu" # Label sementara
        elif payment_method == 'credit':
            metode_pembayaran_db = "Membership Credit"
        elif payment_method == 'virtual_office':
            metode_pembayaran_db = "Virtual Office Benefit"

        # --- 6. Insert Transaksi ---
        insert_transaksi = """
            INSERT INTO transaksi (
                id_user, total_harga_final, metode_pembayaran, 
                status_pembayaran, status_order, lokasi_pemesanan, booking_source
            ) VALUES (%s, %s, %s, %s, 'Baru', %s, %s)
        """
        cursor.execute(insert_transaksi, (
            id_user, harga_transaksi, metode_pembayaran_db, 
            status_pembayaran_awal, f"ruangan_{id_ruangan}", booking_source
        ))
        id_transaksi = cursor.lastrowid
        
        # --- 7. Kurangi Kredit (Jika pakai kredit) ---
        if payment_method == 'credit':
            update_credit_query = "UPDATE memberships SET sisa_credit = sisa_credit - %s WHERE id_memberships = %s"
            cursor.execute(update_credit_query, (credit_cost, membership_id))

        # --- 8. Loop Insert Booking & Benefit Usage ---
        current_date_insert = tanggal_mulai
        
        # Ambil ulang kategori untuk loop insert (jika belum diambil di validasi)
        if 'kat_ruangan' not in locals():
             cursor.execute("SELECT kr.nama_kategori FROM ruangan r JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan WHERE r.id_ruangan = %s", (id_ruangan,))
             kat_ruangan = cursor.fetchone()
        
        jenis_benefit_vo = 'meeting_room' if kat_ruangan and 'Meeting' in kat_ruangan['nama_kategori'] else 'working_space'

        while current_date_insert <= tanggal_selesai:
            waktu_mulai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_mulai)
            waktu_selesai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_selesai)
            
            id_mships = membership_id if payment_method == 'credit' else None
            kredit_per_hari = durasi_per_hari if payment_method == 'credit' else 0
            
            # Insert Booking
            insert_booking = """
                INSERT INTO booking_ruangan (
                    id_transaksi, id_ruangan, id_memberships, 
                    waktu_mulai, waktu_selesai, durasi, kredit_terpakai
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_booking, (
                id_transaksi, id_ruangan, id_mships, 
                waktu_mulai_db, waktu_selesai_db, durasi_per_hari, kredit_per_hari
            ))
            id_booking_baru = cursor.lastrowid

            # Insert Penggunaan Benefit VO
            if payment_method == 'virtual_office':
                durasi_menit_harian = durasi_per_hari * 60
                insert_usage_query = """
                    INSERT INTO penggunaan_benefit_vo (
                        id_client_vo, id_booking, jenis_benefit, 
                        durasi_terpakai_menit, tanggal_penggunaan
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_usage_query, (
                    virtual_office_id, id_booking_baru, jenis_benefit_vo, 
                    durasi_menit_harian, waktu_mulai_db
                ))

            current_date_insert += timedelta(days=1)

        # --- 9. Integrasi iPaymu (Jika Pembayaran Normal) ---
        payment_url = None
        if payment_method == 'normal':
            # Ambil data user lengkap
            cursor.execute("SELECT nama, email, no_telepon FROM users WHERE id_user = %s", (id_user,))
            user_data = cursor.fetchone()
            
            ipaymu_res = create_ipaymu_payment(
                id_transaksi=id_transaksi,
                amount=harga_transaksi,
                buyer_name=user_data['nama'] if user_data else "Guest",
                buyer_phone=user_data['no_telepon'],
                buyer_email=user_data['email']
            )
            
            if ipaymu_res['success']:
                payment_url = ipaymu_res['url']
                # BARU COMMIT DI SINI JIKA SUKSES
                connection.commit() 
            else:
                # JIKA GAGAL: ROLLBACK & KIRIM ERROR KE FRONTEND
                connection.rollback()
                error_message = f"Gagal koneksi ke Payment Gateway: {ipaymu_res.get('message')}"
                print(error_message) # Print di terminal backend
                return jsonify({"message": "ERROR", "error": error_message}), 500

        else:
            # Jika bukan pembayaran normal (Kredit/VO), langsung commit
            connection.commit()

        return jsonify({
            "message": "Booking berhasil diproses", 
            "id_transaksi": id_transaksi,
            "payment_url": payment_url
        }), 201

    except Exception as e:
        if connection: connection.rollback()
        import traceback
        traceback.print_exc() # Print full error di terminal backend
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
                
        
# @ruangan_endpoints.route('/bookRuangan', methods=['POST'])
# def book_ruangan():
#     """Buat transaksi baru + booking ruangan (mendukung multi-hari)"""
#     connection = None
#     cursor = None
#     try:
#         data = request.json
#         id_user = data.get("id_user")
#         nama_guest = data.get("nama_guest")
#         id_ruangan = data["id_ruangan"]
        
#         # --- PERUBAHAN: Terima rentang tanggal dan jam ---
#         tanggal_mulai_str = data["tanggal_mulai"] # Format "YYYY-MM-DD"
#         tanggal_selesai_str = data["tanggal_selesai"] # Format "YYYY-MM-DD"
#         jam_mulai = int(data["jam_mulai"]) # Format jam (integer), misal: 9
#         jam_selesai = int(data["jam_selesai"]) # Format jam (integer), misal: 17

#         metode_pembayaran = data.get("metode_pembayaran", "Tunai")
#         total_harga = data["total_harga_final"]

#         # Konversi string tanggal ke objek date
#         tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
#         tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()

#         # Hitung durasi per hari
#         durasi_per_hari = jam_selesai - jam_mulai

#         connection = get_connection()
#         cursor = connection.cursor()
        
#         # Mulai transaksi database
#         connection.start_transaction()

#         # --- VALIDASI KETERSEDIAAN SEBELUM INSERT ---
#         current_date_check = tanggal_mulai
#         while current_date_check <= tanggal_selesai:
#             waktu_mulai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_mulai)
#             waktu_selesai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_selesai)
            
#             check_query = """
#                 SELECT id_booking FROM booking_ruangan 
#                 WHERE id_ruangan = %s 
#                 AND (waktu_mulai < %s AND waktu_selesai > %s)
#             """
#             cursor.execute(check_query, (id_ruangan, waktu_selesai_check, waktu_mulai_check))
#             if cursor.fetchone():
#                 # Jika ada booking yang overlap, batalkan semua
#                 connection.rollback()
#                 return jsonify({"message": "ERROR", "error": f"Slot pada tanggal {current_date_check.strftime('%d-%m-%Y')} sudah terisi."}), 409 # 409 Conflict
            
#             current_date_check += timedelta(days=1)

#         # 1. Insert satu kali ke tabel transaksi
#         insert_transaksi = """
#         INSERT INTO transaksi (id_user, nama_guest, total_harga_final, metode_pembayaran, status_pembayaran, status_order, lokasi_pemesanan) 
#         VALUES (%s, %s, %s, %s, %s, %s, %s)
#         """
#         cursor.execute(insert_transaksi, (id_user, nama_guest, total_harga, metode_pembayaran, "Lunas", "Baru", f"ruangan_{id_ruangan}"))
#         id_transaksi = cursor.lastrowid

#         # 2. Loop dan insert ke booking_ruangan untuk setiap hari
#         current_date_insert = tanggal_mulai
#         while current_date_insert <= tanggal_selesai:
#             waktu_mulai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_mulai)
#             waktu_selesai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_selesai)
            
#             insert_booking = """
#             INSERT INTO booking_ruangan (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi)
#             VALUES (%s, %s, %s, %s, %s)
#             """
#             cursor.execute(insert_booking, (id_transaksi, id_ruangan, waktu_mulai_db, waktu_selesai_db, durasi_per_hari))
            
#             current_date_insert += timedelta(days=1)

#         connection.commit()

#         return jsonify({"message": "Booking multi-hari berhasil", "id_transaksi": id_transaksi}), 201

#     except Exception as e:
#         if connection: connection.rollback()
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()



# @ruangan_endpoints.route('/bookRuangan', methods=['POST'])
# def book_ruangan():
#     """Buat transaksi baru + booking ruangan"""
#     connection = None
#     cursor = None
#     try:
#         data = request.json
#         id_user = data.get("id_user")   # bisa None kalau guest
#         nama_guest = data.get("nama_guest")
#         id_ruangan = data["id_ruangan"]
#         waktu_mulai = data["waktu_mulai"]
#         waktu_selesai = data["waktu_selesai"]
#         metode_pembayaran = data.get("metode_pembayaran", "Tunai")
#         total_harga = data["total_harga_final"]

#         # hitung durasi dalam jam (dibulatkan ke atas jika ada menit sisa)
#         from datetime import datetime
#         import math
#         t1 = datetime.strptime(waktu_mulai, "%Y-%m-%d %H:%M:%S")
#         t2 = datetime.strptime(waktu_selesai, "%Y-%m-%d %H:%M:%S")
#         durasi = math.ceil((t2 - t1).total_seconds() / 3600)

#         connection = get_connection()
#         cursor = connection.cursor()

#         # 1. Insert ke transaksi
#         insert_transaksi = """
#         INSERT INTO transaksi 
#         (id_user, nama_guest, total_harga_final, metode_pembayaran, status_pembayaran, status_order, lokasi_pemesanan) 
#         VALUES (%s, %s, %s, %s, %s, %s, %s)
#         """
#         cursor.execute(insert_transaksi, (
#             id_user, nama_guest, total_harga, metode_pembayaran,
#             "Lunas", "Baru", f"ruangan_{id_ruangan}"
#         ))
#         id_transaksi = cursor.lastrowid

#         # 2. Insert ke booking_ruangan
#         insert_booking = """
#         INSERT INTO booking_ruangan
#         (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi)
#         VALUES (%s, %s, %s, %s, %s)
#         """
#         cursor.execute(insert_booking, (
#             id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi
#         ))

#         connection.commit()

#         return jsonify({
#             "message": "Booking berhasil",
#             "id_transaksi": id_transaksi,
#             "durasi_jam": durasi
#         }), 201

#     except Exception as e:
#         if connection: connection.rollback()
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()




@ruangan_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_ruangan (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_ruangan": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@ruangan_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_ruangan SET title=%s, description=%s WHERE id_ruangan=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_ruangan": product_id}
    return jsonify(data), 200


@ruangan_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_ruangan WHERE id_ruangan = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_ruangan": product_id}
    return jsonify(data)


@ruangan_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@ruangan_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list ruangan"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_ruangan WHERE id_ruangan = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200