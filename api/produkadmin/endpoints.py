"""Routes for module produkadmin"""
import os
import uuid
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

produkadmin_endpoints = Blueprint("produkadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ✅ READ PRODUK
@produkadmin_endpoints.route("/readProduk", methods=["GET"])
def read_produk():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT p.id_produk,
               p.nama_produk,
               p.deskripsi_produk,
               p.harga,
               p.status_ketersediaan,
               p.status_visibilitas, -- <-- TAMBAHKAN INI
               p.foto_produk,
               k.id_kategori,
               k.nama_kategori,
               t.nama_tenant
        FROM produk_fnb p
        JOIN kategori_produk k ON p.id_kategori = k.id_kategori
        LEFT JOIN tenants t ON k.id_tenant = t.id_tenant
        ORDER BY p.id_produk DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
        
# @produkadmin_endpoints.route("/readProduk", methods=["GET"])
# def read_produk():
#     try:
#         conn = get_connection()
#         cursor = conn.cursor(dictionary=True)
#         query = """
#         SELECT p.id_produk AS id_produk, 
#                p.nama_produk, 
#                p.deskripsi_produk, 
#                p.harga,
#                p.status_ketersediaan, 
#                p.foto_produk,
#                k.id_kategori, 
#                k.nama_kategori
#         FROM produk_fnb p
#         JOIN kategori_produk k ON p.id_kategori = k.id_kategori
#         ORDER BY p.id_produk DESC
#         """
#         cursor.execute(query)
#         results = cursor.fetchall()
#         return jsonify({"message": "OK", "datas": results}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if conn: conn.close()

# ✅ CREATE PRODUK
@produkadmin_endpoints.route("/createProduk", methods=["POST"])
def create_produk():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        nama_produk = request.form.get("nama_produk")
        deskripsi_produk = request.form.get("deskripsi_produk")
        harga = request.form.get("harga")
        status_ketersediaan = request.form.get("status_ketersediaan", "Active")
        status_visibilitas = request.form.get("status_visibilitas", "Aktif") # <-- TAMBAHKAN INI
        id_kategori = request.form.get("id_kategori")

        # ... (handle upload file tetap sama) ...
        file = request.files.get("foto_produk")
        file_url = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            file_url = f"{filename}"


        query = """
        INSERT INTO produk_fnb (id_kategori, nama_produk, deskripsi_produk, harga, status_ketersediaan, status_visibilitas, foto_produk)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """                                             # <-- Tambah %s
        cursor.execute(query, (id_kategori, nama_produk, deskripsi_produk, harga, status_ketersediaan, status_visibilitas, file_url)) # <-- Tambah var
        conn.commit()

        return jsonify({"message": "Produk berhasil ditambahkan"}), 201
    except Exception as e:
        conn.rollback() # Rollback jika error
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@produkadmin_endpoints.route("/updateProduk/<int:id_produk>", methods=["PUT"])
def update_produk(id_produk):
    conn = None # Inisialisasi conn
    cursor = None # Inisialisasi cursor
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True) # Gunakan dictionary=True untuk fetchone nanti

        # Ambil data dari form
        nama_produk = request.form.get("nama_produk")
        deskripsi_produk = request.form.get("deskripsi_produk")
        harga = request.form.get("harga")
        status_ketersediaan = request.form.get("status_ketersediaan")
        status_visibilitas = request.form.get("status_visibilitas") # Ambil status visibilitas
        id_kategori = request.form.get("id_kategori")

        # --- Validasi Input Sederhana (opsional tapi disarankan) ---
        if not all([nama_produk, harga, status_ketersediaan, status_visibilitas, id_kategori]):
             return jsonify({"message": "ERROR", "error": "Field wajib tidak boleh kosong"}), 400
        try:
            harga_int = int(harga)
            id_kategori_int = int(id_kategori)
            if harga_int < 0:
                 raise ValueError("Harga tidak boleh negatif")
        except ValueError as ve:
             return jsonify({"message": "ERROR", "error": f"Input tidak valid: {ve}"}), 400
        # --- Akhir Validasi ---


        # Cek produk lama untuk mendapatkan nama file foto lama
        cursor.execute("SELECT foto_produk FROM produk_fnb WHERE id_produk=%s", (id_produk,))
        old_product = cursor.fetchone() # Fetch sebagai dictionary
        old_file_name = old_product['foto_produk'] if old_product else None
        current_file_url = old_file_name # Defaultnya pakai file lama

        # Handle upload file baru
        file = request.files.get("foto_produk")
        new_file_saved = False # Flag untuk menandakan file baru disimpan
        if file and allowed_file(file.filename):
            # Generate nama file unik baru
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}") # Gunakan UUID
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            try:
                 file.save(filepath)
                 current_file_url = filename # Gunakan nama file baru
                 new_file_saved = True
                 print(f"File baru disimpan: {filepath}") # Logging
            except Exception as e:
                 print(f"Gagal menyimpan file baru: {e}") # Logging error simpan file
                 # Pertimbangkan: Lanjutkan update tanpa ganti foto atau batalkan?
                 # Di sini kita lanjutkan tanpa ganti foto jika save gagal
                 current_file_url = old_file_name

        # --- Hapus file lama JIKA file baru berhasil disimpan DAN file lama ada ---
        if new_file_saved and old_file_name:
             old_filepath = os.path.join(UPLOAD_FOLDER, old_file_name)
             if os.path.exists(old_filepath):
                  try:
                       os.remove(old_filepath)
                       print(f"File lama dihapus: {old_filepath}") # Logging
                  except OSError as e:
                       print(f"Gagal menghapus file lama {old_filepath}: {e}") # Log error hapus file

        # Query UPDATE dengan jumlah parameter yang benar
        query = """
        UPDATE produk_fnb
        SET id_kategori=%s,
            nama_produk=%s,
            deskripsi_produk=%s,
            harga=%s,
            status_ketersediaan=%s,
            status_visibilitas=%s,
            foto_produk=%s
        WHERE id_produk=%s
        """
        # Pastikan urutan variabel sesuai dengan %s di query
        params = (
            id_kategori,
            nama_produk,
            deskripsi_produk,
            harga,
            status_ketersediaan,
            status_visibilitas, # Pastikan ini ada
            current_file_url,   # Nama file (lama atau baru)
            id_produk           # ID produk untuk WHERE clause
        )

        # DEBUG: Cetak query dan parameter sebelum eksekusi
        print("Executing UPDATE query:", query)
        print("With parameters:", params)

        # Gunakan cursor baru karena yg lama pakai dictionary=True
        cursor_update = conn.cursor()
        cursor_update.execute(query, params)
        conn.commit()
        cursor_update.close() # Tutup cursor update

        return jsonify({"message": "Produk berhasil diperbarui"}), 200

    except Exception as e:
        # Rollback jika terjadi error
        if conn:
            conn.rollback()
        print(f"Error updating product: {e}") # Cetak error ke log server
        import traceback
        traceback.print_exc() # Cetak traceback lengkap
        return jsonify({"message": "ERROR", "error": f"Terjadi kesalahan internal: {str(e)}"}), 500
    finally:
        # Selalu tutup cursor dan koneksi
        if cursor: cursor.close()
        if conn: conn.close()
        
        
# ✅ DELETE PRODUK
@produkadmin_endpoints.route("/deleteProduk/<int:id_produk>", methods=["DELETE"])
def delete_produk(id_produk):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # hapus file kalau ada
        cursor.execute("SELECT foto_produk FROM produk_fnb WHERE id_produk=%s", (id_produk,))
        old = cursor.fetchone()
        if old and old[0]:
            old_path = old[0].lstrip("/")  # hapus leading slash
            if os.path.exists(old_path):
                os.remove(old_path)

        # hapus produk
        cursor.execute("DELETE FROM produk_fnb WHERE id_produk=%s", (id_produk,))
        conn.commit()

        return jsonify({"message": "Produk berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()




@produkadmin_endpoints.route('/readKategoriTenant', methods=['GET'])
def readKategori():
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT k.id_kategori, k.nama_kategori, t.id_tenant, t.nama_tenant
        FROM kategori_produk k
        JOIN tenants t ON k.id_tenant = t.id_tenant
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ CREATE kategori
@produkadmin_endpoints.route('/createKategori', methods=['POST'])
def createKategori():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_kategori = data.get("nama_kategori")
        id_tenant = data.get("id_tenant")

        if not nama_kategori or not id_tenant:
            return jsonify({"message": "ERROR", "error": "nama_kategori dan id_tenant wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        insert_query = """
        INSERT INTO kategori_produk (nama_kategori, id_tenant)
        VALUES (%s, %s)
        """
        cursor.execute(insert_query, (nama_kategori, id_tenant))
        connection.commit()

        return jsonify({"message": "Kategori berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ UPDATE kategori
@produkadmin_endpoints.route('/updateKategori/<id_kategori>', methods=['PUT'])
def updateKategori(id_kategori):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_kategori = data.get("nama_kategori")
        id_tenant = data.get("id_tenant")

        if not nama_kategori or not id_tenant:
            return jsonify({"message": "ERROR", "error": "nama_kategori dan id_tenant wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        update_query = """
        UPDATE kategori_produk
        SET nama_kategori = %s, id_tenant = %s
        WHERE id_kategori = %s
        """
        cursor.execute(update_query, (nama_kategori, id_tenant, id_kategori))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Kategori tidak ditemukan"}), 404

        return jsonify({"message": "Kategori berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ DELETE kategori
@produkadmin_endpoints.route('/deleteKategori/<id_kategori>', methods=['DELETE'])
def deleteKategori(id_kategori):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        delete_query = "DELETE FROM kategori_produk WHERE id_kategori = %s"
        cursor.execute(delete_query, (id_kategori,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Kategori tidak ditemukan"}), 404

        return jsonify({"message": "Kategori berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@produkadmin_endpoints.route('/tenants', methods=['GET'])
def get_all_tenants_for_dropdown():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query sederhana untuk mengambil semua tenant
        cursor.execute("SELECT id_tenant, nama_tenant FROM tenants ORDER BY nama_tenant ASC")
        tenants = cursor.fetchall()
        return jsonify({"message": "OK", "datas": tenants}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()