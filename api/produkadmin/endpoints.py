"""Routes for module produkadmin"""
import os
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
        # --- PERUBAHAN DI SINI ---
        # 1. Tambahkan LEFT JOIN ke tabel tenant (asumsi nama tabel 'tenant' dan foreign key 'id_tenant')
        # 2. Ambil kolom nama_tenant dari tabel tenant
        query = """
        SELECT p.id_produk, 
               p.nama_produk, 
               p.deskripsi_produk, 
               p.harga,
               p.status_ketersediaan, 
               p.foto_produk,
               k.id_kategori, 
               k.nama_kategori,
               t.nama_tenant  -- <-- Tambahkan ini
        FROM produk_fnb p
        JOIN kategori_produk k ON p.id_kategori = k.id_kategori
        LEFT JOIN tenants t ON k.id_tenant = t.id_tenant -- <-- Tambahkan ini
        ORDER BY p.id_produk DESC
        """
        # --- AKHIR PERUBAHAN ---
        
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
        id_kategori = request.form.get("id_kategori")

        # handle upload file
        file = request.files.get("foto_produk")
        file_url = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            file_url = f"{filename}"

        query = """
        INSERT INTO produk_fnb (id_kategori, nama_produk, deskripsi_produk, harga, status_ketersediaan, foto_produk)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (id_kategori, nama_produk, deskripsi_produk, harga, status_ketersediaan, file_url))
        conn.commit()

        return jsonify({"message": "Produk berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ✅ UPDATE PRODUK
@produkadmin_endpoints.route("/updateProduk/<int:id_produk>", methods=["PUT"])
def update_produk(id_produk):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        nama_produk = request.form.get("nama_produk")
        deskripsi_produk = request.form.get("deskripsi_produk")
        harga = request.form.get("harga")
        status_ketersediaan = request.form.get("status_ketersediaan", "Active")
        id_kategori = request.form.get("id_kategori")

        # cek produk lama
        cursor.execute("SELECT foto_produk FROM produk_fnb WHERE id_produk=%s", (id_produk,))
        old = cursor.fetchone()
        file_url = old[0] if old else None

        # handle upload file baru
        file = request.files.get("foto_produk")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            file_url = f"{filename}"

        query = """
        UPDATE produk_fnb
        SET id_kategori=%s, nama_produk=%s, deskripsi_produk=%s, harga=%s, status_ketersediaan=%s, foto_produk=%s
        WHERE id_produk=%s
        """
        cursor.execute(query, (id_kategori, nama_produk, deskripsi_produk, harga, status_ketersediaan, file_url, id_produk))
        conn.commit()

        return jsonify({"message": "Produk berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
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