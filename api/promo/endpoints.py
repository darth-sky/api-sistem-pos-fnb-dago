"""Routes for module promo"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from datetime import datetime, timedelta
import math
import traceback
from datetime import date


promo_endpoints = Blueprint('promo', __name__)
UPLOAD_FOLDER = "img"

@promo_endpoints.route('/active', methods=['GET'])
def get_active_promos():
    """Mengambil semua promo yang aktif dari database."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        today = date.today()
        
        # --- PERUBAHAN 1: Hapus DATE_FORMAT dari query ---
        # Biarkan database mengirim tipe data DATE asli
        query = """
            SELECT 
                kode_promo,
                deskripsi_promo,
                nilai_diskon,
                tanggal_mulai,
                tanggal_selesai
            FROM promo
            WHERE status_aktif = 'aktif' AND tanggal_selesai >= %s
            ORDER BY tanggal_mulai DESC;
        """
        
        cursor.execute(query, (today,))
        promos = cursor.fetchall()

        for promo in promos:
            # Format nilai diskon
            nilai = int(promo['nilai_diskon'])
            if nilai < 100:
                promo['nilai_diskon'] = f"{nilai}%"
            else:
                promo['nilai_diskon'] = f"Rp {nilai:,}".replace(',', '.')

            # --- PERUBAHAN 2: Format tanggal menggunakan Python ---
            # 'fetchall()' akan mengembalikan objek date, kita format di sini
            if isinstance(promo['tanggal_mulai'], date):
                promo['tanggal_mulai'] = promo['tanggal_mulai'].strftime('%Y-%m-%d')
            if isinstance(promo['tanggal_selesai'], date):
                promo['tanggal_selesai'] = promo['tanggal_selesai'].strftime('%Y-%m-%d')
            
        return jsonify({"message": "OK", "datas": promos}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@promo_endpoints.route('/workspaces', methods=['GET'])
def get_workspaces_summary():
    """
    Mengambil ringkasan dari setiap kategori promo.
    Endpoint ini HANYA mengirim NAMA FILE gambar.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                kr.id_kategori_promo,
                kr.nama_kategori AS title,
                kr.deskripsi AS `desc`,
                kr.gambar_kategori_promo AS img_filename, 
                (SELECT SUM(r.kapasitas) FROM promo r WHERE r.id_kategori_promo = kr.id_kategori_promo) AS total_capacity,
                (SELECT MIN(r.harga_per_jam) FROM promo r WHERE r.id_kategori_promo = kr.id_kategori_promo AND r.harga_per_jam > 0) AS min_price,
                (SELECT r.fitur_promo FROM promo r WHERE r.id_kategori_promo = kr.id_kategori_promo LIMIT 1) AS fasilitas_sample
            FROM 
                kategori_promo kr
            WHERE
                kr.nama_kategori IN ('Space Monitor', 'Open Space', 'Room Meeting'); 
        """
        cursor.execute(query)
        workspaces = cursor.fetchall()
        
        formatted_workspaces = []
        for ws in workspaces:
            fasilitas_list = ws['fasilitas_sample'].strip().split('\n') if ws['fasilitas_sample'] else []
            price_str = f"Rp{ws['min_price']:,}".replace(',', '.') if ws['min_price'] else "N/A"

            formatted_workspaces.append({
                "category": "Working Space",
                "title": ws['title'],
                "desc": ws['desc'],
                # --- PERUBAHAN: Hanya kirim nama file ---
                "img": ws['img_filename'],
                "capacity": int(ws['total_capacity']) if ws['total_capacity'] else 0,
                "time": "08:00 - 22:00",
                "date": datetime.now().strftime("%d %b %Y"),
                "price": price_str,
                "features": ["Wifi", "Refill Water", "AC"],
                "fasilitas": fasilitas_list,
            })
            
        formatted_workspaces.append({
             "category": "Working Space",
             "title": "Space Lesehan",
             "desc": "Space lesehan dengan dudukan bantal dan meja.",
             # --- PERUBAHAN: Hanya kirim nama file ---
             "img": "space-lesehan1.jpeg",
             "capacity": 8,
             "time": "09:00 - 21:00",
             "date": datetime.now().strftime("%d %b %Y"),
             "price": "FREE",
             "features": ["Wifi", "Refill Water"],
             "fasilitas": ["Meja lesehan & bantal duduk", "Akses Wi-Fi", "Colokan listrik"],
             "note": "*Dengan syarat melakukan pemesanan F&B di lokasi",
        })

        return jsonify({"message": "OK", "datas": formatted_workspaces}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
@promo_endpoints.route('/promo/<int:id_promo>/booked_hours/<string:tanggal>', methods=['GET'])
def get_booked_hours(id_promo, tanggal):
    """
    Endpoint untuk mendapatkan jam-jam yang sudah dibooking untuk promo tertentu
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
            FROM booking_promo
            WHERE id_promo = %s AND DATE(waktu_mulai) = %s
        """
        cursor.execute(query, (id_promo, selected_date))
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
            

@promo_endpoints.route('/readPromo', methods=['GET'])
def readPromo():
    """Routes for module get list promo"""
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = "SELECT * FROM promo WHERE status_aktif = 'aktif'"
        cursor.execute(select_query)
        results = cursor.fetchall()

        # Convert timedelta or datetime to string
        for row in results:
            for key, value in row.items():
                if isinstance(value, (timedelta, datetime)):
                    row[key] = str(value)

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

from flask import jsonify, request
# Pastikan Anda mengimpor fungsi untuk koneksi database Anda, contoh:
# from your_app.db import get_connection

@promo_endpoints.route('/readMembershipByUserId', methods=['GET'])
def readMembershipByUserId():
    """
    Mengambil data membership aktif yang dimiliki oleh seorang user
    berdasarkan kategori promo tertentu.
    Query parameters:
      - id_user: ID dari user yang ingin diperiksa.
      - id_kategori_promo: ID dari kategori promo (e.g., Open Space, Room Meeting).
    """
    # 1. Ambil query parameter dari request URL
    id_user = request.args.get('id_user')
    id_kategori_promo = request.args.get('id_kategori_promo')

    # 2. Validasi input
    if not id_user or not id_kategori_promo:
        return jsonify({
            'message': 'Parameter id_user dan id_kategori_promo diperlukan'
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
        # lalu memfilternya berdasarkan user dan kategori promo
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
                kr.nama_kategori as nama_kategori_promo
            FROM 
                memberships m
            JOIN 
                paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
            JOIN
                kategori_promo kr ON pm.id_kategori_promo = kr.id_kategori_promo
            WHERE 
                m.id_user = %s 
                AND pm.id_kategori_promo = %s
                AND m.status_memberships = 'Active';
        """

        # 5. Eksekusi query dengan parameter yang aman
        cursor.execute(query, (id_user, id_kategori_promo))
        memberships = cursor.fetchall()

        # 6. Kirim response
        if not memberships:
            return jsonify({
                'message': 'Tidak ada membership aktif yang ditemukan untuk user dan kategori promo ini'
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


@promo_endpoints.route('/readpromo', methods=['GET'])
def readpromo():
    """Routes for module get list promo with price packages AND today's schedule"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Ambil semua data promo dan paketnya (seperti sebelumnya)
        query_promo = """
            SELECT r.*, k.nama_kategori
            FROM promo r
            JOIN kategori_promo k ON r.id_kategori_promo = k.id_kategori_promo
        """
        cursor.execute(query_promo)
        promo_list = cursor.fetchall()

        for promo in promo_list:
            query_paket = "SELECT durasi_jam, harga_paket FROM paket_harga_promo WHERE id_promo = %s"
            cursor.execute(query_paket, (promo['id_promo'],))
            promo['paket_harga'] = cursor.fetchall()
            
        # === PERUBAHAN BARU DIMULAI DI SINI ===
        
        # 2. Ambil semua booking untuk HARI INI
        today_date = datetime.now().date()
        query_bookings_today = """
            SELECT id_promo, waktu_mulai, waktu_selesai
            FROM booking_promo
            WHERE DATE(waktu_mulai) = %s
        """
        cursor.execute(query_bookings_today, (today_date,))
        bookings_today = cursor.fetchall()
        
        # 3. Kelompokkan jam yang sudah dibooking berdasarkan id_promo
        booked_hours_map = {}
        for booking in bookings_today:
            room_id = booking['id_promo']
            if room_id not in booked_hours_map:
                booked_hours_map[room_id] = set()
            
            start_hour = booking['waktu_mulai'].hour
            end_hour = booking['waktu_selesai'].hour
            for hour in range(start_hour, end_hour):
                booked_hours_map[room_id].add(hour)
        
        # 4. Sisipkan jadwal booking hari ini ke setiap objek promo
        for promo in promo_list:
            room_id = promo['id_promo']
            if room_id in booked_hours_map:
                # Ubah set menjadi list agar bisa di-serialize ke JSON
                promo['jadwal_hari_ini'] = sorted(list(booked_hours_map[room_id]))
            else:
                promo['jadwal_hari_ini'] = [] # Beri array kosong jika tidak ada booking
        # === PERUBAHAN SELESAI ===

        return jsonify({"message": "OK", "datas": promo_list}), 200
        
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# @promo_endpoints.route('/readpromo', methods=['GET'])
# def readpromo():
#     """Routes for module get list promo with price packages"""
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
        
#         # Query pertama: Ambil semua data promo
#         select_promo_query = """
#             SELECT r.*, k.nama_kategori
#             FROM promo r
#             JOIN kategori_promo k ON r.id_kategori_promo = k.id_kategori_promo
#         """
#         cursor.execute(select_promo_query)
#         promo_list = cursor.fetchall()
        
#         # --- PERUBAHAN DIMULAI DI SINI ---
#         # Untuk setiap promo, ambil data paket harganya
#         for promo in promo_list:
#             select_paket_query = """
#                 SELECT durasi_jam, harga_paket 
#                 FROM paket_harga_promo 
#                 WHERE id_promo = %s
#             """
#             cursor.execute(select_paket_query, (promo['id_promo'],))
#             paket_harga = cursor.fetchall()
            
#             # Tambahkan data paket harga ke dalam objek promo
#             promo['paket_harga'] = paket_harga
#         # --- PERUBAHAN SELESAI DI SINI ---

#         return jsonify({"message": "OK", "datas": promo_list}), 200
        
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

# @promo_endpoints.route('/readpromo', methods=['GET'])
# def readpromo():
#     """Routes for module get list promo"""
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         select_query = select_query = """
#         SELECT r.*, k.nama_kategori
#         FROM promo r
#         JOIN kategori_promo k ON r.id_kategori_promo = k.id_kategori_promo
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
            
@promo_endpoints.route('/readMembership', methods=['GET'])
def readMembership():
    """Ambil daftar paket membership + kategori promo"""
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
            kr.id_kategori_promo,
            kr.nama_kategori
        FROM paket_membership pm
        JOIN kategori_promo kr 
            ON pm.id_kategori_promo = kr.id_kategori_promo
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
            
            
# File: promo_endpoints.py
@promo_endpoints.route('/event-spaces', methods=['GET'])
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
                gambar_promo,
                fitur_promo
            FROM event_spaces
            WHERE status_ketersediaan = 'Tersedia'
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

@promo_endpoints.route('/event-spaces/<int:space_id>', methods=['GET'])
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
                gambar_promo,
                fitur_promo
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
@promo_endpoints.route('/bookingEvent', methods=['POST'])
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



# @promo_endpoints.route('/bookingEvent', methods=['POST'])
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




@promo_endpoints.route('/bookpromo', methods=['POST'])
def book_promo():
    """Buat transaksi baru + booking promo (mendukung multi-hari)"""
    connection = None
    cursor = None
    try:
        data = request.json
        id_user = data.get("id_user")
        nama_guest = data.get("nama_guest")
        id_promo = data["id_promo"]
        
        # --- PERUBAHAN: Terima rentang tanggal dan jam ---
        tanggal_mulai_str = data["tanggal_mulai"] # Format "YYYY-MM-DD"
        tanggal_selesai_str = data["tanggal_selesai"] # Format "YYYY-MM-DD"
        jam_mulai = int(data["jam_mulai"]) # Format jam (integer), misal: 9
        jam_selesai = int(data["jam_selesai"]) # Format jam (integer), misal: 17

        metode_pembayaran = data.get("metode_pembayaran", "Tunai")
        total_harga = data["total_harga_final"]

        # Konversi string tanggal ke objek date
        tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
        tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()

        # Hitung durasi per hari
        durasi_per_hari = jam_selesai - jam_mulai

        connection = get_connection()
        cursor = connection.cursor()
        
        # Mulai transaksi database
        connection.start_transaction()

        # --- VALIDASI KETERSEDIAAN SEBELUM INSERT ---
        current_date_check = tanggal_mulai
        while current_date_check <= tanggal_selesai:
            waktu_mulai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_mulai)
            waktu_selesai_check = datetime.combine(current_date_check, datetime.min.time()).replace(hour=jam_selesai)
            
            check_query = """
                SELECT id_booking FROM booking_promo 
                WHERE id_promo = %s 
                AND (waktu_mulai < %s AND waktu_selesai > %s)
            """
            cursor.execute(check_query, (id_promo, waktu_selesai_check, waktu_mulai_check))
            if cursor.fetchone():
                # Jika ada booking yang overlap, batalkan semua
                connection.rollback()
                return jsonify({"message": "ERROR", "error": f"Slot pada tanggal {current_date_check.strftime('%d-%m-%Y')} sudah terisi."}), 409 # 409 Conflict
            
            current_date_check += timedelta(days=1)

        # 1. Insert satu kali ke tabel transaksi
        insert_transaksi = """
        INSERT INTO transaksi (id_user, nama_guest, total_harga_final, metode_pembayaran, status_pembayaran, status_order, lokasi_pemesanan) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_transaksi, (id_user, nama_guest, total_harga, metode_pembayaran, "Lunas", "Baru", f"promo_{id_promo}"))
        id_transaksi = cursor.lastrowid

        # 2. Loop dan insert ke booking_promo untuk setiap hari
        current_date_insert = tanggal_mulai
        while current_date_insert <= tanggal_selesai:
            waktu_mulai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_mulai)
            waktu_selesai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_selesai)
            
            insert_booking = """
            INSERT INTO booking_promo (id_transaksi, id_promo, waktu_mulai, waktu_selesai, durasi)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_booking, (id_transaksi, id_promo, waktu_mulai_db, waktu_selesai_db, durasi_per_hari))
            
            current_date_insert += timedelta(days=1)

        connection.commit()

        return jsonify({"message": "Booking multi-hari berhasil", "id_transaksi": id_transaksi}), 201

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# @promo_endpoints.route('/bookpromo', methods=['POST'])
# def book_promo():
#     """Buat transaksi baru + booking promo"""
#     connection = None
#     cursor = None
#     try:
#         data = request.json
#         id_user = data.get("id_user")   # bisa None kalau guest
#         nama_guest = data.get("nama_guest")
#         id_promo = data["id_promo"]
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
#             "Lunas", "Baru", f"promo_{id_promo}"
#         ))
#         id_transaksi = cursor.lastrowid

#         # 2. Insert ke booking_promo
#         insert_booking = """
#         INSERT INTO booking_promo
#         (id_transaksi, id_promo, waktu_mulai, waktu_selesai, durasi)
#         VALUES (%s, %s, %s, %s, %s)
#         """
#         cursor.execute(insert_booking, (
#             id_transaksi, id_promo, waktu_mulai, waktu_selesai, durasi
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




@promo_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_promo (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_promo": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@promo_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_promo SET title=%s, description=%s WHERE id_promo=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_promo": product_id}
    return jsonify(data), 200


@promo_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_promo WHERE id_promo = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_promo": product_id}
    return jsonify(data)


@promo_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@promo_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list promo"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_promo WHERE id_promo = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200