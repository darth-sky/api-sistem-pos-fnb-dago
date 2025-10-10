"""Routes for module ruangan"""
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
from datetime import datetime # --- PERUBAHAN 1: Impor library datetime ---

ruangan_endpoints = Blueprint('ruangan', __name__)
UPLOAD_FOLDER = "img"

# event

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

        # Langkah 1: Query diubah untuk mengambil JUMLAH ruangan (room_count)
        query = """
            SELECT 
                kr.id_kategori_ruangan,
                kr.nama_kategori AS title,
                kr.deskripsi AS `desc`,
                kr.gambar_kategori_ruangan AS img_filename,
                (SELECT SUM(r.kapasitas) FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan) AS total_capacity,
                -- TAMBAHKAN SUBQUERY INI untuk menghitung jumlah ruangan
                (SELECT COUNT(r.id_ruangan) FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan) AS room_count,
                (SELECT MIN(phr.harga_paket) FROM paket_harga_ruangan phr JOIN ruangan r ON phr.id_ruangan = r.id_ruangan WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan AND phr.harga_paket > 0) AS min_price,
                (SELECT r.fitur_ruangan FROM ruangan r WHERE r.id_kategori_ruangan = kr.id_kategori_ruangan LIMIT 1) AS fasilitas_sample
            FROM 
                kategori_ruangan kr
            WHERE
                kr.nama_kategori IN ('Space Monitor', 'Open Space', 'Room Meeting'); 
        """
        cursor.execute(query)
        workspaces = cursor.fetchall()
        
        formatted_workspaces = []
        # Langkah 2: Logika di Python diubah untuk format baru
        for ws in workspaces:
            fasilitas_list = ws['fasilitas_sample'].strip().split('\n') if ws['fasilitas_sample'] else []
            price_str = f"Rp{int(ws['min_price']):,}".replace(',', '.') if ws['min_price'] else "N/A"

            capacity_display = ""
            if ws['title'] == 'Room Meeting':
                # Format sebagai jumlah ruangan jika "Room Meeting"
                capacity_display = f"{ws['room_count']}"
            else:
                # Format sebagai total kapasitas untuk kategori lain
                capacity_display = int(ws['total_capacity']) if ws['total_capacity'] else 0

            formatted_workspaces.append({
                "category": "Working Space",
                "title": ws['title'],
                "desc": ws['desc'],
                "img": ws['img_filename'],
                "capacity": capacity_display,  # Menggunakan hasil format baru
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
             "img": "space-lesehan1.jpeg",
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
            

@ruangan_endpoints.route('/readPromo', methods=['GET'])
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
# @jwt_required() # Pastikan endpoint ini aman
def book_ruangan():
    """
    Buat transaksi & booking untuk ruangan.
    Mendukung multi-hari, pembayaran kredit membership, dan benefit virtual office.
    """
    connection = None
    cursor = None
    try:
        data = request.json
        
        # --- Ambil semua data dari payload ---
        id_user = data.get("id_user")
        id_ruangan = data["id_ruangan"]
        tanggal_mulai_str = data["tanggal_mulai"]
        tanggal_selesai_str = data["tanggal_selesai"]
        jam_mulai = int(data["jam_mulai"])
        jam_selesai = int(data["jam_selesai"])
        total_harga = data["total_harga_final"]
        
        payment_method = data.get("paymentMethod")
        membership_id = data.get("membershipId")
        credit_cost = data.get("creditCost", 0)
        virtual_office_id = data.get("virtualOfficeId")
        benefit_cost = data.get("benefitCost", 0) # Total jam benefit yg akan dipakai

        # --- Konversi & Kalkulasi Awal ---
        tanggal_mulai = datetime.strptime(tanggal_mulai_str, "%Y-%m-%d").date()
        tanggal_selesai = datetime.strptime(tanggal_selesai_str, "%Y-%m-%d").date()
        durasi_per_hari = jam_selesai - jam_mulai

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        connection.start_transaction()

        # --- VALIDASI KETERSEDIAAN (Tidak berubah) ---
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

        # --- VALIDASI ULANG SISA BENEFIT/KREDIT DI SISI SERVER (PENGAMAN) ---
        if payment_method == 'credit':
            cursor.execute("SELECT sisa_credit FROM memberships WHERE id_memberships = %s AND id_user = %s", (membership_id, id_user))
            member = cursor.fetchone()
            if not member or member['sisa_credit'] < credit_cost:
                connection.rollback()
                return jsonify({"message": "ERROR", "error": "Kredit tidak mencukupi atau membership tidak valid."}), 400
        
        elif payment_method == 'virtual_office':
            # Logika ini mirip dengan endpoint `getVOClientByUserId` untuk validasi terakhir
            cursor.execute("SELECT pvo.benefit_jam_meeting_room_per_bulan, pvo.benefit_jam_working_space_per_bulan FROM client_virtual_office cvo JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo WHERE cvo.id_client_vo = %s AND cvo.id_user = %s AND cvo.status_client_vo = 'Aktif'", (virtual_office_id, id_user))
            paket_vo = cursor.fetchone()
            if not paket_vo:
                connection.rollback()
                return jsonify({"message": "ERROR", "error": "Klien Virtual Office tidak valid."}), 400
            
            # (Tambahkan logika pengecekan sisa benefit di sini jika diperlukan sebagai pengaman tambahan)

        # --- LOGIKA UTAMA: PEMBUATAN TRANSAKSI & BOOKING ---
        
        # 1. Tentukan detail untuk tabel transaksi
        harga_transaksi = 0
        metode_pembayaran_db = "qris" # Default
        if payment_method == 'normal':
            harga_transaksi = total_harga
        elif payment_method == 'credit':
            metode_pembayaran_db = "Membership Credit"
        elif payment_method == 'virtual_office':
            metode_pembayaran_db = "Virtual Office Benefit"

        # 2. Buat satu record transaksi
        insert_transaksi = "INSERT INTO transaksi (id_user, total_harga_final, metode_pembayaran, status_pembayaran, status_order, lokasi_pemesanan) VALUES (%s, %s, %s, 'Lunas', 'Baru', %s)"
        cursor.execute(insert_transaksi, (id_user, harga_transaksi, metode_pembayaran_db, f"ruangan_{id_ruangan}"))
        id_transaksi = cursor.lastrowid
        
        # 3. Proses pengurangan (jika ada)
        if payment_method == 'credit':
            update_credit_query = "UPDATE memberships SET sisa_credit = sisa_credit - %s WHERE id_memberships = %s"
            cursor.execute(update_credit_query, (credit_cost, membership_id))
            if cursor.rowcount == 0:
                connection.rollback()
                return jsonify({"message": "ERROR", "error": "Gagal mengurangi kredit membership."}), 500

        # 4. Ambil kategori ruangan untuk menentukan `jenis_benefit` VO
        cursor.execute("SELECT kr.nama_kategori FROM ruangan r JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan WHERE r.id_ruangan = %s", (id_ruangan,))
        kategori_ruangan = cursor.fetchone()
        jenis_benefit_vo = 'meeting_room' if kategori_ruangan and 'Meeting' in kategori_ruangan['nama_kategori'] else 'working_space'

        # 5. Loop untuk membuat record booking per hari & mencatat penggunaan benefit
        current_date_insert = tanggal_mulai
        while current_date_insert <= tanggal_selesai:
            waktu_mulai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_mulai)
            waktu_selesai_db = datetime.combine(current_date_insert, datetime.min.time()).replace(hour=jam_selesai)
            
            id_mships = membership_id if payment_method == 'credit' else None
            kredit_per_hari = durasi_per_hari if payment_method == 'credit' else 0
            
            # Insert ke booking_ruangan
            insert_booking = "INSERT INTO booking_ruangan (id_transaksi, id_ruangan, id_memberships, waktu_mulai, waktu_selesai, durasi, kredit_terpakai) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(insert_booking, (id_transaksi, id_ruangan, id_mships, waktu_mulai_db, waktu_selesai_db, durasi_per_hari, kredit_per_hari))
            id_booking_baru = cursor.lastrowid

            # JIKA VIRTUAL OFFICE, catat penggunaannya di tabel `penggunaan_benefit_vo`
            if payment_method == 'virtual_office':
                durasi_menit_harian = durasi_per_hari * 60
                insert_usage_query = "INSERT INTO penggunaan_benefit_vo (id_client_vo, id_booking, jenis_benefit, durasi_terpakai_menit, tanggal_penggunaan) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(insert_usage_query, (virtual_office_id, id_booking_baru, jenis_benefit_vo, durasi_menit_harian, waktu_mulai_db))

            current_date_insert += timedelta(days=1)

        # Jika semua berhasil, commit transaksi
        connection.commit()

        return jsonify({"message": "Booking berhasil", "id_transaksi": id_transaksi}), 201

    except Exception as e:
        if connection: connection.rollback()
        print(f"Error pada /bookRuangan: {e}") # Logging error
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