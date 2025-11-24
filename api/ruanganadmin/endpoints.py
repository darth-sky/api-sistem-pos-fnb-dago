"""Routes for module ruanganadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

ruanganadmin_endpoints = Blueprint("ruanganadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Endpoint untuk Ruangan ---

@ruanganadmin_endpoints.route("/readRuangan", methods=["GET"])
def read_ruangan():
    """Endpoint untuk membaca semua data ruangan."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT 
            r.id_ruangan, 
            r.nama_ruangan, 
            r.harga_per_jam, 
            r.deskripsi_ruangan,
            r.kapasitas, 
            r.status_ketersediaan, 
            r.gambar_ruangan, 
            r.fitur_ruangan,
            kr.id_kategori_ruangan, 
            kr.nama_kategori
        FROM ruangan r
        JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
        ORDER BY r.id_ruangan DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()


@ruanganadmin_endpoints.route("/createRuangan", methods=["POST"])
def create_ruangan():
    """Endpoint untuk membuat ruangan baru."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ambil data dari form
        nama_ruangan = request.form.get("nama_ruangan")
        id_kategori_ruangan = request.form.get("id_kategori_ruangan")
        harga_per_jam = request.form.get("harga_per_jam")
        kapasitas = request.form.get("kapasitas")
        deskripsi_ruangan = request.form.get("deskripsi_ruangan")
        fitur_ruangan = request.form.get("fitur_ruangan")
        status_ketersediaan = request.form.get("status_ketersediaan", "Active")
        
        # Handle upload file
        file_url = None
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                file_url = filename
        
        query = """
        INSERT INTO ruangan (nama_ruangan, id_kategori_ruangan, harga_per_jam, kapasitas, deskripsi_ruangan, fitur_ruangan, status_ketersediaan, gambar_ruangan)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nama_ruangan, id_kategori_ruangan, harga_per_jam, kapasitas, deskripsi_ruangan, fitur_ruangan, status_ketersediaan, file_url))
        conn.commit()

        return jsonify({"message": "Ruangan berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

@ruanganadmin_endpoints.route("/updateRuangan/<int:id_ruangan>", methods=["PUT"])
def update_ruangan(id_ruangan):
    """Endpoint untuk memperbarui data ruangan."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Ambil data dari form
        nama_ruangan = request.form.get("nama_ruangan")
        id_kategori_ruangan = request.form.get("id_kategori_ruangan")
        harga_per_jam = request.form.get("harga_per_jam")
        kapasitas = request.form.get("kapasitas")
        deskripsi_ruangan = request.form.get("deskripsi_ruangan")
        fitur_ruangan = request.form.get("fitur_ruangan")
        status_ketersediaan = request.form.get("status_ketersediaan")

        # Cek gambar lama
        cursor.execute("SELECT gambar_ruangan FROM ruangan WHERE id_ruangan=%s", (id_ruangan,))
        old_data = cursor.fetchone()
        file_url = old_data[0] if old_data else None

        # Handle upload file baru
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                file_url = filename
        
        query = """
        UPDATE ruangan SET 
            nama_ruangan=%s, id_kategori_ruangan=%s, harga_per_jam=%s, kapasitas=%s, 
            deskripsi_ruangan=%s, fitur_ruangan=%s, status_ketersediaan=%s, gambar_ruangan=%s
        WHERE id_ruangan=%s
        """
        cursor.execute(query, (nama_ruangan, id_kategori_ruangan, harga_per_jam, kapasitas, deskripsi_ruangan, fitur_ruangan, status_ketersediaan, file_url, id_ruangan))
        conn.commit()

        return jsonify({"message": "Ruangan berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

@ruanganadmin_endpoints.route("/deleteRuangan/<int:id_ruangan>", methods=["DELETE"])
def delete_ruangan(id_ruangan):
    """Endpoint untuk menghapus ruangan."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Hapus file gambar jika ada
        cursor.execute("SELECT gambar_ruangan FROM ruangan WHERE id_ruangan=%s", (id_ruangan,))
        data = cursor.fetchone()
        if data and data[0]:
            filepath = os.path.join(UPLOAD_FOLDER, data[0])
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Hapus data dari database
        cursor.execute("DELETE FROM ruangan WHERE id_ruangan=%s", (id_ruangan,))
        conn.commit()

        return jsonify({"message": "Ruangan berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()


# ✅ READ kategori ruangan (SUDAH DIMODIFIKASI)
@ruanganadmin_endpoints.route('/readKategori', methods=['GET'])
def read_kategori_ruangan():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # --- MODIFIKASI: Tambahkan LEFT JOIN ke chart_of_accounts ---
        query = """
            SELECT 
                kr.id_kategori_ruangan, kr.nama_kategori, kr.deskripsi, 
                kr.gambar_kategori_ruangan, kr.status, kr.id_coa,
                coa.kode_akun, coa.nama_akun
            FROM 
                kategori_ruangan kr
            LEFT JOIN 
                chart_of_accounts coa ON kr.id_coa = coa.id_coa
            ORDER BY 
                kr.id_kategori_ruangan DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE kategori ruangan (SUDAH DIMODIFIKASI)
@ruanganadmin_endpoints.route('/createKategori', methods=['POST'])
def create_kategori_ruangan():
    connection = None
    cursor = None
    try:
        # Mengambil data dari form-data
        nama_kategori = request.form.get("nama_kategori")
        deskripsi = request.form.get("deskripsi")
        status = request.form.get("status", 'Active')
        # --- TAMBAHAN BARU: Ambil id_coa dari form ---
        id_coa = request.form.get("id_coa")
        
        # Konversi id_coa ke None jika string kosong
        if id_coa == 'null' or id_coa == '':
            id_coa = None

        if not nama_kategori:
            return jsonify({"message": "ERROR", "error": "nama_kategori wajib diisi"}), 400

        gambar_filename = None
        if 'gambar_kategori_ruangan' in request.files:
            file = request.files['gambar_kategori_ruangan']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Anda mungkin perlu nama file unik di sini
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar_filename = filename

        connection = get_connection()
        cursor = connection.cursor()
        
        # --- MODIFIKASI: Tambahkan id_coa ke query INSERT ---
        query = """
            INSERT INTO kategori_ruangan 
            (nama_kategori, deskripsi, status, gambar_kategori_ruangan, id_coa) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nama_kategori, deskripsi, status, gambar_filename, id_coa))
        connection.commit()

        return jsonify({"message": "Kategori ruangan berhasil ditambahkan"}), 201
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ UPDATE kategori ruangan (SUDAH DIMODIFIKASI)
@ruanganadmin_endpoints.route('/updateKategori/<int:id_kategori>', methods=['PUT'])
def update_kategori_ruangan(id_kategori):
    connection = None
    cursor = None
    try:
        nama_kategori = request.form.get("nama_kategori")
        deskripsi = request.form.get("deskripsi")
        status = request.form.get("status")
        # --- TAMBAHAN BARU: Ambil id_coa dari form ---
        id_coa = request.form.get("id_coa")
        
        # Konversi id_coa ke None jika string kosong
        if id_coa == 'null' or id_coa == '':
            id_coa = None

        if not nama_kategori or not status:
            return jsonify({"message": "ERROR", "error": "nama_kategori dan status wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT gambar_kategori_ruangan FROM kategori_ruangan WHERE id_kategori_ruangan = %s", (id_kategori,))
        existing_data = cursor.fetchone()
        if not existing_data:
            return jsonify({"message": "ERROR", "error": "Kategori tidak ditemukan"}), 404

        gambar_filename = existing_data['gambar_kategori_ruangan']

        if 'gambar_kategori_ruangan' in request.files:
            file = request.files['gambar_kategori_ruangan']
            if file and file.filename != '':
                if gambar_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, gambar_filename)):
                    os.remove(os.path.join(UPLOAD_FOLDER, gambar_filename))
                
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar_filename = filename
        
        update_cursor = connection.cursor()
        
        # --- MODIFIKASI: Tambahkan id_coa ke query UPDATE ---
        query = """
            UPDATE kategori_ruangan 
            SET nama_kategori = %s, deskripsi = %s, status = %s, 
                gambar_kategori_ruangan = %s, id_coa = %s
            WHERE id_kategori_ruangan = %s
        """
        update_cursor.execute(query, (nama_kategori, deskripsi, status, gambar_filename, id_coa, id_kategori))
        connection.commit()
        update_cursor.close()

        return jsonify({"message": "Kategori ruangan berhasil diperbarui"}), 200
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# @ruanganadmin_endpoints.route('/readKategori', methods=['GET'])
# def read_kategori_ruangan():
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         query = "SELECT id_kategori_ruangan, nama_kategori, deskripsi FROM kategori_ruangan ORDER BY id_kategori_ruangan DESC"
#         cursor.execute(query)
#         results = cursor.fetchall()
#         return jsonify({"message": "OK", "datas": results}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


# # ✅ CREATE kategori ruangan
# @ruanganadmin_endpoints.route('/createKategori', methods=['POST'])
# def create_kategori_ruangan():
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         nama_kategori = data.get("nama_kategori")
#         deskripsi = data.get("deskripsi")

#         if not nama_kategori:
#             return jsonify({"message": "ERROR", "error": "nama_kategori wajib diisi"}), 400

#         connection = get_connection()
#         cursor = connection.cursor()
#         query = "INSERT INTO kategori_ruangan (nama_kategori, deskripsi) VALUES (%s, %s)"
#         cursor.execute(query, (nama_kategori, deskripsi))
#         connection.commit()

#         return jsonify({"message": "Kategori ruangan berhasil ditambahkan"}), 201
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


# # ✅ UPDATE kategori ruangan
# @ruanganadmin_endpoints.route('/updateKategori/<int:id_kategori>', methods=['PUT'])
# def update_kategori_ruangan(id_kategori):
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         nama_kategori = data.get("nama_kategori")
#         deskripsi = data.get("deskripsi")

#         if not nama_kategori:
#             return jsonify({"message": "ERROR", "error": "nama_kategori wajib diisi"}), 400

#         connection = get_connection()
#         cursor = connection.cursor()
#         query = """
#             UPDATE kategori_ruangan 
#             SET nama_kategori = %s, deskripsi = %s 
#             WHERE id_kategori_ruangan = %s
#         """
#         cursor.execute(query, (nama_kategori, deskripsi, id_kategori))
#         connection.commit()

#         if cursor.rowcount == 0:
#             return jsonify({"message": "ERROR", "error": "Kategori ruangan tidak ditemukan"}), 404

#         return jsonify({"message": "Kategori ruangan berhasil diperbarui"}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


# ✅ DELETE kategori ruangan
@ruanganadmin_endpoints.route('/deleteKategori/<int:id_kategori>', methods=['DELETE'])
def delete_kategori_ruangan(id_kategori):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM kategori_ruangan WHERE id_kategori_ruangan = %s"
        cursor.execute(query, (id_kategori,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Kategori ruangan tidak ditemukan"}), 404

        return jsonify({"message": "Kategori ruangan berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
        
# Endpoint baru untuk membaca paket harga berdasarkan id_ruangan
@ruanganadmin_endpoints.route("/paketHarga/<int:id_ruangan>", methods=["GET"])
def get_paket_harga_by_ruangan(id_ruangan):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id_paket, durasi_jam, harga_paket FROM paket_harga_ruangan WHERE id_ruangan = %s", (id_ruangan,))
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

# Endpoint baru untuk menambah paket harga
@ruanganadmin_endpoints.route("/paketHarga", methods=["POST"])
def add_paket_harga():
    try:
        data = request.json
        id_ruangan = data["id_ruangan"]
        durasi_jam = data["durasi_jam"]
        harga_paket = data["harga_paket"]

        conn = get_connection()
        cursor = conn.cursor()
        query = "INSERT INTO paket_harga_ruangan (id_ruangan, durasi_jam, harga_paket) VALUES (%s, %s, %s)"
        cursor.execute(query, (id_ruangan, durasi_jam, harga_paket))
        conn.commit()
        return jsonify({"message": "Paket harga berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

# Endpoint baru untuk menghapus paket harga
@ruanganadmin_endpoints.route("/paketHarga/<int:id_paket>", methods=["DELETE"])
def delete_paket_harga(id_paket):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM paket_harga_ruangan WHERE id_paket = %s", (id_paket,))
        conn.commit()
        return jsonify({"message": "Paket harga berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
        

@ruanganadmin_endpoints.route("/paketHarga/<int:id_paket>", methods=["PUT"])
def update_paket_harga(id_paket):
    """
    Endpoint untuk memperbarui durasi dan harga paket berdasarkan id_paket.
    """
    try:
        # Ambil data baru dari request body
        data = request.json
        durasi_jam = data["durasi_jam"]
        harga_paket = data["harga_paket"]

        conn = get_connection()
        cursor = conn.cursor()

        # Query SQL untuk UPDATE
        query = """
            UPDATE paket_harga_ruangan 
            SET durasi_jam = %s, harga_paket = %s 
            WHERE id_paket = %s
        """
        cursor.execute(query, (durasi_jam, harga_paket, id_paket))
        
        # Commit perubahan ke database
        conn.commit()

        return jsonify({"message": "Paket harga berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()