"""Routes for module membershipadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

membershipadmin_endpoints = Blueprint("membershipadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@membershipadmin_endpoints.route('/getAllPaket', methods=['GET'])
def getAllPaket():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        select_query = """
        SELECT 
            id_paket_membership, 
            id_kategori_ruangan, 
            nama_paket, 
            harga, 
            durasi, 
            kuota, 
            deskripsi_benefit, 
            fitur_membership,
            status_paket -- ✅ PERUBAHAN: Menambahkan kolom status_paket
        FROM paket_membership
        ORDER BY id_paket_membership DESC
        """
        cursor.execute(select_query)
        pakets = cursor.fetchall()

        return jsonify({"message": "OK", "datas": pakets}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
@membershipadmin_endpoints.route('/createPaket', methods=['POST'])
def createPaket():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        
        id_kategori_ruangan = data.get("id_kategori_ruangan")
        nama_paket = data.get("nama_paket")
        harga = data.get("harga")
        durasi = data.get("durasi")
        kuota = data.get("kuota")
        deskripsi_benefit = data.get("deskripsi_benefit")
        fitur_membership = data.get("fitur_membership")
        # ✅ PERUBAHAN: Ambil status_paket, jika tidak ada, defaultnya 'Aktif'.
        status_paket = data.get("status_paket", "Aktif")

        # Validasi sederhana
        if not all([id_kategori_ruangan, nama_paket, harga, durasi, kuota]):
            return jsonify({"message": "ERROR", "error": "Field wajib tidak boleh kosong."}), 400

        connection = get_connection()
        cursor = connection.cursor()

        insert_query = """
        INSERT INTO paket_membership 
        (id_kategori_ruangan, nama_paket, harga, durasi, kuota, deskripsi_benefit, fitur_membership, status_paket)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            id_kategori_ruangan, 
            nama_paket, 
            harga, 
            durasi, 
            kuota, 
            deskripsi_benefit, 
            fitur_membership,
            status_paket # ✅ PERUBAHAN: Menambahkan status_paket ke parameter
        )
        
        cursor.execute(insert_query, params)
        connection.commit()

        return jsonify({"message": "Paket membership berhasil ditambahkan"}), 201
    
    except Exception as e:
        # Mengembalikan error 500 dengan detail
        return jsonify({
            "message": "INTERNAL_SERVER_ERROR", 
            "error": "Gagal menyimpan data ke database.", 
            "detail": str(e) 
        }), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
@membershipadmin_endpoints.route('/updatePaket/<int:id_paket_membership>', methods=['PUT'])
def updatePaket(id_paket_membership):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        id_kategori_ruangan = data.get("id_kategori_ruangan")
        nama_paket = data.get("nama_paket")
        harga = data.get("harga")
        durasi = data.get("durasi")
        kuota = data.get("kuota")
        deskripsi_benefit = data.get("deskripsi_benefit")
        fitur_membership = data.get("fitur_membership")
        # ✅ PERUBAHAN: Mengambil status_paket dari data yang dikirim frontend
        status_paket = data.get("status_paket")

        # --- Validasi Data Wajib ---
        if not all([id_kategori_ruangan, nama_paket, harga, durasi, kuota, status_paket]):
            return jsonify({"message": "ERROR", "error": "Semua field, termasuk status, wajib diisi untuk update."}), 400

        connection = get_connection()
        cursor = connection.cursor()

        update_query = """
        UPDATE paket_membership
        SET 
            id_kategori_ruangan = %s, 
            nama_paket = %s, 
            harga = %s, 
            durasi = %s, 
            kuota = %s, 
            deskripsi_benefit = %s, 
            fitur_membership = %s,
            status_paket = %s -- ✅ PERUBAHAN: Menambahkan update untuk status_paket
        WHERE id_paket_membership = %s
        """
        params = (
            id_kategori_ruangan, nama_paket, harga, durasi, kuota, 
            deskripsi_benefit, fitur_membership, 
            status_paket, # ✅ PERUBAHAN: Menambahkan variabel status
            id_paket_membership
        )
        cursor.execute(update_query, params)
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Paket tidak ditemukan atau tidak ada data yang berubah"}), 404

        return jsonify({"message": "Paket membership berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
        
@membershipadmin_endpoints.route('/deletePaket/<int:id_paket_membership>', methods=['DELETE'])
def deletePaket(id_paket_membership):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        delete_query = "DELETE FROM paket_membership WHERE id_paket_membership = %s"
        cursor.execute(delete_query, (id_paket_membership,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Paket tidak ditemukan"}), 404

        return jsonify({"message": "Paket membership berhasil dihapus secara permanen"}), 200
    except Exception as e:
        # Penanganan untuk error foreign key constraint (jika paket sudah pernah dibeli)
        if 'foreign key constraint' in str(e).lower():
            return jsonify({
                "message": "DELETE_FAILED",
                "error": "Paket ini tidak bisa dihapus karena sudah memiliki riwayat transaksi."
            }), 409 # 409 Conflict adalah status yang tepat
        
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ READ PRODUK
@membershipadmin_endpoints.route("/readProduk", methods=["GET"])
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
# @membershipadmin_endpoints.route("/readProduk", methods=["GET"])
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
@membershipadmin_endpoints.route("/createProduk", methods=["POST"])
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
@membershipadmin_endpoints.route("/updateProduk/<int:id_produk>", methods=["PUT"])
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
@membershipadmin_endpoints.route("/deleteProduk/<int:id_produk>", methods=["DELETE"])
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




@membershipadmin_endpoints.route('/readKategoriTenant', methods=['GET'])
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
@membershipadmin_endpoints.route('/createKategori', methods=['POST'])
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
@membershipadmin_endpoints.route('/updateKategori/<id_kategori>', methods=['PUT'])
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
@membershipadmin_endpoints.route('/deleteKategori/<id_kategori>', methods=['DELETE'])
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