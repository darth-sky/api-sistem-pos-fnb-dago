"""Routes for module virtualOffice"""
import os
from flask import Blueprint, jsonify, request
import mysql
from api.utils.ipaymu_helper import create_ipaymu_payment
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from datetime import date, datetime, timedelta
import traceback

virtualOffice_endpoints = Blueprint('virtualOffice', __name__)
UPLOAD_FOLDER = "img"

import traceback # untuk debugging lebih detail
from werkzeug.utils import secure_filename

# Definisikan folder upload, mirip seperti di produkadmin
VO_UPLOAD_FOLDER = "uploads/vo_documents"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

# Buat folder jika belum ada
if not os.path.exists(VO_UPLOAD_FOLDER):
    os.makedirs(VO_UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS




@virtualOffice_endpoints.route('/paket-vo/<int:paket_id>', methods=['GET'])
def get_paket_vo_by_id(paket_id):
    """
    Endpoint untuk mengambil detail satu paket Virtual Office berdasarkan ID.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = "SELECT * FROM paket_virtual_office WHERE id_paket_vo = %s"
        cursor.execute(query, (paket_id,))
        paket = cursor.fetchone()

        if not paket:
            return jsonify({"message": "ERROR", "error": "Paket tidak ditemukan"}), 404
        
        # Ubah harga menjadi string agar konsisten dengan data statis sebelumnya jika perlu
        paket['harga'] = str(paket['harga'])

        return jsonify({"message": "OK", "data": paket}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()


# Ganti endpoint register_virtual_office yang lama dengan yang ini
@virtualOffice_endpoints.route('/register', methods=['POST'])
def register_virtual_office():
    """
    Proses pendaftaran VO oleh user.
    Menyimpan data dengan status 'Baru' dan tanggal NULL untuk disetujui admin.
    """
    connection = None
    cursor = None
    try:
        # --- 1. Ambil Data dari Form dan File ---
        id_user_str = request.form.get("id_user")
        id_user = int(id_user_str) if id_user_str and id_user_str.isdigit() else None
        id_paket_vo = request.form.get("id_paket_vo")
        nama = request.form.get("nama")
        jabatan = request.form.get("jabatan")
        nama_perusahaan_klien = request.form.get("nama_perusahaan_klien")
        bidang_perusahaan = request.form.get("bidang_perusahaan")
        alamat_perusahaan = request.form.get("alamat_perusahaan")
        email_perusahaan = request.form.get("email_perusahaan")
        alamat_domisili = request.form.get("alamat_domisili")
        nomor_telepon = request.form.get("nomor_telepon")
        # PERBAIKAN: tanggal_mulai tidak lagi diambil dari form

        if not all([id_user, id_paket_vo, nama_perusahaan_klien]):
            return jsonify({"message": "Data wajib tidak lengkap"}), 400

        # --- 2. Proses dan Simpan File Dokumen ---
        file = request.files.get('dokumenPendukung')
        doc_filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # Simpan file ke folder upload Anda
            filepath = os.path.join(VO_UPLOAD_FOLDER, filename) # Pastikan VO_UPLOAD_FOLDER sudah didefinisikan
            file.save(filepath)
            doc_filename = filename
        else:
            return jsonify({"message": "Dokumen pendukung wajib diunggah."}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- 3. Ambil Detail Paket & Buat Transaksi ---
        cursor.execute("SELECT harga FROM paket_virtual_office WHERE id_paket_vo = %s", (id_paket_vo,))
        paket = cursor.fetchone()
        if not paket:
            return jsonify({"message": "Paket Virtual Office tidak ditemukan"}), 404

        # Buat transaksi dengan status 'Belum Lunas'
# ... kode sebelumnya ...

        # --- 3. Ambil Detail Paket & Buat Transaksi ---
        cursor.execute("SELECT harga FROM paket_virtual_office WHERE id_paket_vo = %s", (id_paket_vo,))
        paket = cursor.fetchone()
        if not paket:
            return jsonify({"message": "Paket Virtual Office tidak ditemukan"}), 404

        # --- PERBAIKAN DISINI ---
        # Ubah status_pembayaran dari 'Belum Lunas' menjadi 'Menunggu Konfirmasi'
        # Ubah status_order dari 'Baru' menjadi 'Pending' (atau sesuaikan dengan enum order Anda)
        cursor.execute(
            "INSERT INTO transaksi (id_user, total_harga_final, metode_pembayaran, status_pembayaran, status_order) VALUES (%s, %s, %s, %s, %s)",
            (id_user, paket["harga"], "Non-Tunai", "Menunggu Konfirmasi", "Pending")
        )
        id_transaksi = cursor.lastrowid

        # ... kode setelahnya ...

        # --- 4. Simpan Data Klien VO dengan tanggal NULL dan status 'Baru' ---
        insert_vo_query = """
        INSERT INTO client_virtual_office (
            id_user, id_paket_vo, id_transaksi, nama, jabatan, nama_perusahaan_klien, 
            bidang_perusahaan, alamat_perusahaan, email_perusahaan, alamat_domisili, 
            nomor_telepon, tanggal_mulai, tanggal_berakhir, status_client_vo, doc_path
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, 'Menunggu Persetujuan', %s)
        """
        cursor.execute(insert_vo_query, (
            id_user, id_paket_vo, id_transaksi, nama, jabatan, nama_perusahaan_klien,
            bidang_perusahaan, alamat_perusahaan, email_perusahaan, alamat_domisili,
            nomor_telepon, doc_filename
        ))

        connection.commit()
        
        return jsonify({
            "message": "OK",
            "id_transaksi": id_transaksi
        }), 201

    except Exception as e:
        if connection: connection.rollback()
        print(f"ERROR: {e}")
        traceback.print_exc()
        return jsonify({"message": "Terjadi kesalahan pada server", "error": str(e)}), 500
    
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'connection' in locals() and connection: connection.close()


# # Ganti endpoint register_virtual_office yang lama dengan yang ini
# @virtualOffice_endpoints.route('/register', methods=['POST'])
# def register_virtual_office():
#     """
#     Proses pendaftaran Virtual Office:
#     1. Menerima data dari form-data (termasuk file).
#     2. Menyimpan dokumen pendukung.
#     3. Membuat transaksi pembelian paket VO.
#     4. Menghitung tanggal mulai & berakhir secara aman.
#     5. Menyimpan detail klien di client_virtual_office.
#     """
#     connection = None
#     cursor = None
#     try:
#         # --- 1. Ambil Data dari Form dan File ---
#         id_user_str = request.form.get("id_user")
#         id_user = int(id_user_str) if id_user_str and id_user_str.isdigit() else None
#         id_paket_vo = request.form.get("id_paket_vo")
#         nama = request.form.get("nama")
#         jabatan = request.form.get("jabatan")
#         nama_perusahaan_klien = request.form.get("nama_perusahaan_klien")
#         bidang_perusahaan = request.form.get("bidang_perusahaan")
#         alamat_perusahaan = request.form.get("alamat_perusahaan")
#         email_perusahaan = request.form.get("email_perusahaan")
#         alamat_domisili = request.form.get("alamat_domisili")
#         nomor_telepon = request.form.get("nomor_telepon")
#         tanggal_mulai_str = request.form.get("tanggal_mulai") # Format: YYYY-MM-DD

#         if not id_paket_vo or not nama_perusahaan_klien:
#             return jsonify({"message": "ID paket dan nama perusahaan wajib diisi"}), 400

#         # --- 2. Proses dan Simpan File yang Diunggah ---
#         file = request.files.get('dokumenPendukung')
#         doc_filename = None
#         if file and allowed_file(file.filename):
#             filename = secure_filename(file.filename)
#             filepath = os.path.join(VO_UPLOAD_FOLDER, filename)
#             file.save(filepath)
#             doc_filename = filename
#         else:
#             return jsonify({"message": "File dokumen pendukung (PDF/JPG/PNG) wajib diunggah."}), 400

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # --- 3. Ambil Detail Paket & Buat Transaksi ---
#         cursor.execute("SELECT harga, durasi FROM paket_virtual_office WHERE id_paket_vo = %s", (id_paket_vo,))
#         paket = cursor.fetchone()
#         if not paket:
#             return jsonify({"message": "Paket Virtual Office tidak ditemukan"}), 404

#         cursor.execute(
#             "INSERT INTO transaksi (id_user, total_harga_final, metode_pembayaran, status_pembayaran, status_order) VALUES (%s, %s, %s, %s, %s)",
#             (id_user, paket["harga"], "Non-Tunai", "Belum Lunas", "Baru")
#         )
#         id_transaksi = cursor.lastrowid

#         # --- 4. Hitung Tanggal Mulai dan Berakhir dengan Aman ---
#         start_date_for_calc = tanggal_mulai_str if tanggal_mulai_str else 'CURDATE()'
        
#         query_end_date = f"SELECT DATE_ADD({ 'CURDATE()' if not tanggal_mulai_str else '%s' }, INTERVAL %s DAY) as end_date"
        
#         params_end_date = (paket["durasi"],) if not tanggal_mulai_str else (start_date_for_calc, paket["durasi"])

#         cursor.execute(query_end_date, params_end_date)
#         end_date_result = cursor.fetchone()
        
#         if not end_date_result:
#             raise Exception("Gagal menghitung tanggal berakhir")
#         end_date = end_date_result["end_date"]

#         # --- 5. Simpan Data Klien VO ke Database ---
#         insert_vo_query = """
#         INSERT INTO client_virtual_office (
#             id_user, id_paket_vo, id_transaksi, nama, jabatan, nama_perusahaan_klien, 
#             bidang_perusahaan, alamat_perusahaan, email_perusahaan, alamat_domisili, 
#             nomor_telepon, tanggal_mulai, tanggal_berakhir, status_client_vo, doc_path
#         )
#         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Baru', %s)
#         """
#         cursor.execute(insert_vo_query, (
#             id_user, id_paket_vo, id_transaksi, nama, jabatan, nama_perusahaan_klien,
#             bidang_perusahaan, alamat_perusahaan, email_perusahaan, alamat_domisili,
#             nomor_telepon, tanggal_mulai_str, end_date, doc_filename
#         ))

#         connection.commit()
        
#         return jsonify({
#             "message": "OK",
#             "id_transaksi": id_transaksi
#         }), 201

#     except Exception as e:
#         if connection:
#             connection.rollback()
#         print(f"ERROR: {e}")
#         traceback.print_exc()
#         return jsonify({"message": "Terjadi kesalahan pada server", "error": str(e)}), 500
    
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()




@virtualOffice_endpoints.route('/read', methods=['GET'])
@jwt_required()
def read():
    """Routes for module get list virtualOffice"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT * FROM tb_virtualOffice"
    cursor.execute(select_query)
    results = cursor.fetchall()
    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200


# halaman virtual office yang berisi paket paket vo start
@virtualOffice_endpoints.route('/paket_vo', methods=['GET'])
def get_paket_vo():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # PERBAIKAN: Tambahkan "WHERE status = 'Active'" untuk memfilter data
        query = """
        SELECT id_paket_vo, nama_paket, harga, durasi, 
               benefit_jam_meeting_room_per_bulan, 
               benefit_jam_working_space_per_bulan, 
               deskripsi_layanan
        FROM paket_virtual_office
        WHERE status = 'Active'
        ORDER BY harga ASC 
        """
        cursor.execute(query)
        result = cursor.fetchall()

        return jsonify({"message": "OK", "datas": result}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
# halaman virutal office yang berisi paket paket vo end


# halaman cekmasavo start

# @virtualOffice_endpoints.route('/cekMasaVO/<int:id_user>', methods=['GET'])
# def get_vo_detail(id_user):
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         query = """
#         SELECT 
#             cvo.id_client_vo,
#             cvo.tanggal_mulai,
#             cvo.tanggal_berakhir,
#             cvo.status_client_vo,
#             pvo.nama_paket,
#             pvo.harga,
#             pvo.durasi
#         FROM client_virtual_office cvo
#         JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
#         WHERE cvo.id_user = %s
#         ORDER BY cvo.tanggal_mulai DESC
#         LIMIT 1
#         """
#         cursor.execute(query, (id_user,))
#         result = cursor.fetchone()

#         if not result:
#             return jsonify({"message": "Not Found"}), 404

#         return jsonify({"message": "OK", "data": result})

#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


@virtualOffice_endpoints.route('/cekMasaVO/<int:id_user>', methods=['GET'])
def get_vo_detail(id_user):
    """
    Mengambil detail Virtual Office (VO) TERBARU seorang user,
    termasuk riwayat pemakaian benefit jika sudah aktif.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # PERBAIKAN: Hapus filter status 'Aktif' dan urutkan berdasarkan ID terbaru
        # Ini memastikan kita selalu mendapatkan data pendaftaran terakhir dari user,
        # baik yang statusnya 'Baru', 'Aktif', 'Ditolak', atau 'Kadaluarsa'.
        query_vo = """
            SELECT 
                cvo.id_client_vo, cvo.id_paket_vo, cvo.tanggal_mulai, cvo.id_transaksi, 
                cvo.tanggal_berakhir, cvo.status_client_vo, pvo.nama_paket, 
                pvo.harga, pvo.durasi
            FROM client_virtual_office cvo
            JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
            WHERE cvo.id_user = %s
            ORDER BY cvo.id_client_vo DESC
            LIMIT 1
        """
        cursor.execute(query_vo, (id_user,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"message": "Not Found", "error": "Tidak ada data pendaftaran Virtual Office ditemukan"}), 404

        # Inisialisasi riwayat sebagai array kosong
        result['riwayat_pemakaian'] = []

        # HANYA ambil riwayat jika statusnya sudah 'Aktif'
        if result['status_client_vo'] == 'Aktif':
            id_client_vo = result['id_client_vo']
            query_history = """
                SELECT p.tanggal_penggunaan, p.jenis_benefit, p.durasi_terpakai_menit, r.nama_ruangan
                FROM penggunaan_benefit_vo p
                JOIN booking_ruangan br ON p.id_booking = br.id_booking
                JOIN ruangan r ON br.id_ruangan = r.id_ruangan
                WHERE p.id_client_vo = %s
                ORDER BY p.tanggal_penggunaan DESC
            """
            cursor.execute(query_history, (id_client_vo,))
            history_data = cursor.fetchall()
            result['riwayat_pemakaian'] = history_data

        return jsonify({"message": "OK", "data": result}), 200

    except Exception as e:
        print(f"Error in /cekMasaVO: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()



# @virtualOffice_endpoints.route('/cekMasaVO/<int:id_user>', methods=['GET'])
# def get_vo_detail(id_user):
#     """
#     Mengambil detail Virtual Office (VO) seorang user,
#     termasuk riwayat pemakaian benefit.
#     """
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # Query 1: Ambil data utama Virtual Office Client (sudah benar)
#         query_vo = """
#             SELECT 
#                 cvo.id_client_vo,
#                 cvo.id_paket_vo,
#                 cvo.tanggal_mulai,
#                 cvo.tanggal_berakhir,
#                 cvo.status_client_vo,
#                 pvo.nama_paket,
#                 pvo.harga,
#                 pvo.durasi
#             FROM client_virtual_office cvo
#             JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
#             WHERE cvo.id_user = %s
#             ORDER BY cvo.tanggal_berakhir DESC
#             LIMIT 1
#         """
#         cursor.execute(query_vo, (id_user,))
#         result = cursor.fetchone()

#         if not result:
#             return jsonify({"message": "Not Found", "error": "Data Virtual Office tidak ditemukan"}), 404

#         # PERBAIKAN: Query 2 - Ambil riwayat penggunaan benefit
#         id_client_vo = result['id_client_vo']
        
#         query_history = """
#             SELECT 
#                 p.tanggal_penggunaan,
#                 p.jenis_benefit,
#                 p.durasi_terpakai_menit,
#                 r.nama_ruangan
#             FROM penggunaan_benefit_vo p
#             JOIN booking_ruangan br ON p.id_booking = br.id_booking
#             JOIN ruangan r ON br.id_ruangan = r.id_ruangan
#             WHERE p.id_client_vo = %s
#             ORDER BY p.tanggal_penggunaan DESC
#         """
#         cursor.execute(query_history, (id_client_vo,))
#         history_data = cursor.fetchall()

#         # Tambahkan data riwayat ke dalam hasil respons
#         result['riwayat_pemakaian'] = history_data

#         return jsonify({"message": "OK", "data": result}), 200

#     except Exception as e:
#         traceback.print_exc() # Untuk debugging di server
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
            
            
# @virtualOffice_endpoints.route('/cekMasaVO/<int:id_user>', methods=['GET'])
# def get_vo_detail(id_user):
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         query = """
#         SELECT 
#             cvo.id_client_vo,
#             cvo.id_paket_vo,         -- <-- TAMBAHKAN BARIS INI
#             cvo.tanggal_mulai,
#             cvo.tanggal_berakhir,
#             cvo.status_client_vo,
#             pvo.nama_paket,
#             pvo.harga,
#             pvo.durasi
#         FROM client_virtual_office cvo
#         JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
#         WHERE cvo.id_user = %s
#         ORDER BY cvo.tanggal_mulai DESC
#         LIMIT 1
#         """
#         cursor.execute(query, (id_user,))
#         result = cursor.fetchone()

#         if not result:
#             return jsonify({"message": "Not Found"}), 404

#         return jsonify({"message": "OK", "data": result})

#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# halaman cekmasavo end

# @virtualOffice_endpoints.route('/register', methods=['POST'])
# def register_virtual_office():
#     """
#     Proses pendaftaran Virtual Office:
#     1. Buat transaksi pembelian paket VO
#     2. Simpan detail klien di client_virtual_office
#     """
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         print("DEBUG DATA VO:", data)
        
#         id_user = data.get("id_user")  # bisa NULL kalau guest
#         id_paket_vo = data.get("id_paket_vo")

#         # Data tambahan
#         nama = data.get("nama")
#         jabatan = data.get("jabatan")
#         nama_perusahaan_klien = data.get("nama_perusahaan_klien")
#         bidang_perusahaan = data.get("bidang_perusahaan")
#         alamat_perusahaan = data.get("alamat_perusahaan")
#         email_perusahaan = data.get("email_perusahaan")
#         alamat_domisili = data.get("alamat_domisili")
#         nomor_telepon = data.get("nomor_telepon")

#         if not id_paket_vo or not nama_perusahaan_klien:
#             return jsonify({"message": "ID paket dan nama perusahaan wajib diisi"}), 400

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # 🔹 Ambil detail paket virtual office
#         cursor.execute("""
#             SELECT harga, durasi 
#             FROM paket_virtual_office 
#             WHERE id_paket_vo = %s
#         """, (id_paket_vo,))
#         paket = cursor.fetchone()

#         if not paket:
#             return jsonify({"message": "Paket Virtual Office tidak ditemukan"}), 404

#         # 🔹 Insert transaksi
#         insert_transaksi = """
#         INSERT INTO transaksi (id_user, tanggal_transaksi, total_harga_final, 
#                                metode_pembayaran, status_pembayaran, status_order)
#         VALUES (%s, NOW(), %s, %s, %s, %s)
#         """
#         cursor.execute(insert_transaksi, (
#             id_user, paket["harga"], "Non-Tunai", "Lunas", "Baru",
#         ))
#         id_transaksi = cursor.lastrowid

#         # 🔹 Hitung tanggal mulai & berakhir
#         cursor.execute("SELECT CURDATE() as today")
#         today = cursor.fetchone()["today"]
#         cursor.execute("SELECT DATE_ADD(CURDATE(), INTERVAL %s DAY) as end_date", (paket["durasi"],))
#         end_date = cursor.fetchone()["end_date"]

#         # 🔹 Insert ke client_virtual_office
#         insert_vo = """
#         INSERT INTO client_virtual_office (
#             id_user, id_paket_vo, id_transaksi,
#             nama, jabatan, nama_perusahaan_klien, bidang_perusahaan,
#             alamat_perusahaan, email_perusahaan, alamat_domisili, nomor_telepon,
#             tanggal_mulai, tanggal_berakhir, status_client_vo
#         )
#         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Aktif')
#         """
#         cursor.execute(insert_vo, (
#             id_user, id_paket_vo, id_transaksi,
#             nama, jabatan, nama_perusahaan_klien, bidang_perusahaan,
#             alamat_perusahaan, email_perusahaan, alamat_domisili, nomor_telepon,
#             today, end_date
#         ))

#         connection.commit()
#         return jsonify({
#             "message": "OK",
#             "id_transaksi": id_transaksi
#         }), 201

#     except Exception as e:
#         if connection:
#             connection.rollback()
#             print("ERROR REGISTER VO:", str(e))
#             traceback.print_exc()  # tampilkan error detail di terminal
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()


@virtualOffice_endpoints.route('/readDetailPaketVirtualOffice/<int:id>', methods=['GET'])
def readDetailPaketVirtualOffice(id):
    """Routes for module get detail paket virtual office by ID"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = """
        SELECT 
            id_paket_vo,
            nama_paket,
            harga,
            durasi,
            benefit_jam_meeting_room_per_bulan,
            benefit_jam_working_space_per_bulan
        FROM paket_virtual_office
        WHERE id_paket_vo = %s
        """
        cursor.execute(select_query, (id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"message": "NOT FOUND"}), 404
        return jsonify({"message": "OK", "data": result}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@virtualOffice_endpoints.route('/readPaketVirtualOffice', methods=['GET'])
def readPaketVirtualOffice():
    """Routes for module get list paket virtual office"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = """
        SELECT 
            id_paket_vo,
            nama_paket,
            harga,
            durasi,
            benefit_jam_meeting_room_per_bulan,
            benefit_jam_working_space_per_bulan
        FROM paket_virtual_office
        """
        cursor.execute(select_query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@virtualOffice_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_virtualOffice (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_virtualOffice": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@virtualOffice_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_virtualOffice SET title=%s, description=%s WHERE id_virtualOffice=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_virtualOffice": product_id}
    return jsonify(data), 200


@virtualOffice_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_virtualOffice WHERE id_virtualOffice = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_virtualOffice": product_id}
    return jsonify(data)


@virtualOffice_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@virtualOffice_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list virtualOffice"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_virtualOffice WHERE id_virtualOffice = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200

@virtualOffice_endpoints.route('/daftar-vo', methods=['POST'])
def daftar_vo():
    connection = None
    cursor = None
    try:
        data = request.json
        print("📥 Data diterima:", data)  # debug

        connection = get_connection()
        cursor = connection.cursor()

        insert_query = """
        INSERT INTO virtual_office (
            id_user, id_paket_vo, nama_perusahaan, bidang_usaha,
            alamat_perusahaan, email_perusahaan, jabatan,
            alamat_domisili, nomor_telepon,
            metode_pembayaran, tanggal_mulai, tanggal_selesai
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (
            data.get("id_user"),          # foreign key ke tabel users
            data.get("id_paket_vo"),      # foreign key ke tabel paket
            data.get("nama_perusahaan"),
            data.get("bidang_usaha"),
            data.get("alamat_perusahaan"),
            data.get("email_perusahaan"),
            data.get("jabatan"),
            data.get("alamat_domisili"),
            data.get("nomor_telepon"),
            data.get("metode_pembayaran"),
            data.get("tanggal_mulai"),
            data.get("tanggal_selesai"),
        )

        cursor.execute(insert_query, values)
        connection.commit()

        return jsonify({"message": "Pendaftaran berhasil"}), 201

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# Cek VO
@virtualOffice_endpoints.route("/cek-vo/<int:id_user>", methods=["GET"])
def cek_vo(id_user):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT v.*, p.nama_paket, p.harga, p.durasi
            FROM vo_subscriptions v
            JOIN paket_vo p ON v.id_paket_vo = p.id_paket_vo
            WHERE v.id_user = %s
            ORDER BY v.id DESC LIMIT 1
        """, (id_user,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"data": {"status": "notfound"}}), 200

        # Tentukan status aktif/expired
        today = datetime.date.today()
        tanggal_selesai = result["tanggal_selesai"]
        status = "aktif" if tanggal_selesai >= today else "expired"

        response = {
            "status": status,
            "paket": result["nama_paket"],
            "harga": result["harga"],
            "tanggalMulai": str(result["tanggal_mulai"]),
            "tanggalBerakhir": str(result["tanggal_selesai"]),
            "benefits": [
                {"nama": "Alamat bisnis untuk legalitas usaha", "included": True, "used": True},
                {"nama": "Penerimaan surat & paket", "included": True, "used": True},
                {"nama": "Free meeting room", "included": True, "quota": 4, "used": 1, "unit": "jam/bulan"},
                {"nama": "Free working space", "included": True, "quota": 8, "used": 3, "unit": "jam/bulan"},
                {"nama": "Nama/logo perusahaan di website", "included": True, "used": True},
                {"nama": "Free wifi member", "included": True, "used": True},
            ],
            "riwayatPenggunaan": [
                {"id": 1, "tanggal": "2025-09-10", "aktivitas": "Menggunakan meeting room", "durasi": "2 jam", "type": "meeting"},
                {"id": 2, "tanggal": "2025-09-11", "aktivitas": "Menerima paket", "type": "mail"}
            ]
        }

        return jsonify({"data": response}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()
        
        

@virtualOffice_endpoints.route('/submit-payment/<int:transaction_id>', methods=['POST'])
def confirm_vo_payment_and_activate(transaction_id):
    """
    PERUBAHAN LOGIKA: 
    Tidak lagi menerima file upload. 
    Langsung menganggap pembayaran valid dan mengaktifkan layanan VO.
    """
    connection = None
    cursor = None
    try:
        # --- 1. Validasi File DIHAPUS ---

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- 2. Update Transaksi (tanpa path file) ---
        query_update_tx = """
            UPDATE transaksi 
            SET 
                status_pembayaran = 'Lunas',
                metode_pembayaran = 'Non-Tunai' -- Tetap asumsi Non-Tunai atau sesuaikan
            WHERE 
                id_transaksi = %s AND status_pembayaran = 'Belum Lunas'
        """
        # --- PERBAIKAN DI SINI: Hapus 'filename' ---
        cursor.execute(query_update_tx, (transaction_id,)) # Hanya transaction_id
        
        if cursor.rowcount == 0:
            # Rollback tidak diperlukan di sini karena belum ada perubahan permanen
            # Cek dulu apakah memang sudah lunas/aktif sebelumnya
            cursor.execute("SELECT cvo.status_client_vo, t.status_pembayaran FROM client_virtual_office cvo JOIN transaksi t ON cvo.id_transaksi = t.id_transaksi WHERE cvo.id_transaksi = %s", (transaction_id,))
            current_state = cursor.fetchone()
            if current_state and current_state['status_client_vo'] == 'Aktif' and current_state['status_pembayaran'] == 'Lunas':
                 return jsonify({"message": "OK", "info": "Layanan sudah aktif sebelumnya."}), 200
            elif current_state:
                 return jsonify({"message": "ERROR", "error": f"Transaksi tidak bisa diupdate. Status Pembayaran: {current_state['status_pembayaran']}, Status VO: {current_state['status_client_vo']}"}), 409 # Conflict
            else:
                 return jsonify({"message": "ERROR", "error": "Transaksi tidak ditemukan"}), 404

        # --- 3. Dapatkan Info Klien & Paket untuk Aktivasi (Sama) ---
        query_get_info = """
            SELECT 
                cvo.id_client_vo, 
                pvo.durasi
            FROM client_virtual_office cvo
            JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
            WHERE cvo.id_transaksi = %s
        """
        cursor.execute(query_get_info, (transaction_id,))
        client_info = cursor.fetchone()

        if not client_info:
            connection.rollback() # Rollback update transaksi jika data klien tidak ada
            return jsonify({"message": "ERROR", "error": "Data klien VO terkait tidak ditemukan setelah update transaksi"}), 404
        
        id_client_vo = client_info['id_client_vo']
        durasi_hari = client_info['durasi']

        # --- 4. Hitung Tanggal & Aktifkan Layanan VO (Sama, ini sudah mengisi tanggal) ---
        tanggal_mulai_baru = date.today()
        tanggal_berakhir_baru = tanggal_mulai_baru + timedelta(days=durasi_hari)

        query_activate_vo = """
            UPDATE client_virtual_office
            SET 
                status_client_vo = 'Aktif',
                tanggal_mulai = %s,
                tanggal_berakhir = %s
            WHERE
                id_client_vo = %s AND status_client_vo = 'Menunggu Pembayaran' 
        """
        cursor.execute(query_activate_vo, (tanggal_mulai_baru, tanggal_berakhir_baru, id_client_vo))
        
        if cursor.rowcount == 0:
            connection.rollback() 
            cursor.execute("SELECT status_client_vo FROM client_virtual_office WHERE id_client_vo = %s", (id_client_vo,))
            current_status = cursor.fetchone()
            error_msg = f"Gagal mengaktifkan VO. Status saat ini: {current_status['status_client_vo'] if current_status else 'Tidak Ditemukan'}"
            return jsonify({"message": "ERROR", "error": error_msg}), 409 # 409 Conflict

        # Jika semua berhasil
        connection.commit()
        return jsonify({"message": "OK", "new_status": "Aktif"}), 200

    except Exception as e:
        if connection: connection.rollback()
        print(f"Error in /submit-payment (no upload): {e}")
        traceback.print_exc()
        # Berikan detail error yang lebih spesifik jika memungkinkan
        error_detail = str(e)
        if isinstance(e, mysql.connector.Error): # Cek jika error dari mysql connector
             error_detail = f"MySQL Error {e.errno}: {e.msg}"
        return jsonify({"message": "ERROR", "error": f"Terjadi kesalahan server: {error_detail}"}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'connection' in locals() and connection and connection.is_connected(): # Cek is_connected
            connection.close()
            
            
            
@virtualOffice_endpoints.route('/get-payment-link/<int:id_transaksi>', methods=['GET'])
def get_payment_link_vo(id_transaksi):
    """
    Mengambil ulang URL pembayaran iPaymu untuk transaksi yang belum lunas.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil detail transaksi & user
        cursor.execute("""
            SELECT t.total_harga_final, t.status_pembayaran, 
                   u.nama, u.email, u.no_telepon,
                   cvo.nama as nama_pendaftar, cvo.email_perusahaan, cvo.nomor_telepon as telp_perusahaan
            FROM transaksi t
            JOIN client_virtual_office cvo ON t.id_transaksi = cvo.id_transaksi
            JOIN users u ON t.id_user = u.id_user
            WHERE t.id_transaksi = %s
        """, (id_transaksi,))
        trx = cursor.fetchone()

        if not trx:
            return jsonify({"message": "Transaksi tidak ditemukan"}), 404
        
        if trx['status_pembayaran'] == 'Lunas':
            return jsonify({"message": "Transaksi sudah lunas"}), 400

        # 2. Tentukan data pembeli (prioritas data VO > data User)
        buyer_name = trx['nama_pendaftar'] or trx['nama']
        buyer_email = trx['email_perusahaan'] or trx['email'] or "guest@dago.com"
        buyer_phone = trx['telp_perusahaan'] or trx['no_telepon'] or "08123456789"

        # 3. Request Link Baru ke iPaymu
        # (iPaymu akan mengembalikan link yang sama jika session ID masih aktif, atau baru jika expired)
        ipaymu_res = create_ipaymu_payment(
            id_transaksi=id_transaksi,
            amount=trx['total_harga_final'],
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            buyer_email=buyer_email
        )

        if ipaymu_res['success']:
            return jsonify({
                "message": "OK",
                "payment_url": ipaymu_res['url']
            }), 200
        else:
            return jsonify({"message": "ERROR", "error": ipaymu_res.get('message')}), 500

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()            