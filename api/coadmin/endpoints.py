"""Routes for module coaadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import traceback

coaadmin_endpoints = Blueprint("coaadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ READ semua akun COA
@coaadmin_endpoints.route('/readCoa', methods=['GET'])
def read_coa():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM chart_of_accounts ORDER BY kode_akun ASC"
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE akun COA baru (Tanpa validasi tipe_akun)
@coaadmin_endpoints.route('/createCoa', methods=['POST'])
def create_coa():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        kode_akun = data.get("kode_akun")
        nama_akun = data.get("nama_akun")
        tipe_akun = data.get("tipe_akun")
        deskripsi = data.get("deskripsi")

        # Validasi input (hanya cek jika wajib diisi)
        if not all([kode_akun, nama_akun, tipe_akun]):
            return jsonify({"message": "ERROR", "error": "Kode akun, nama akun, dan tipe akun wajib diisi"}), 400
        
        # --- Validasi tipe_akun telah dihapus ---

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO chart_of_accounts
            (kode_akun, nama_akun, tipe_akun, deskripsi)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (kode_akun, nama_akun, tipe_akun, deskripsi))
        connection.commit()

        return jsonify({"message": "Akun COA berhasil ditambahkan"}), 201
    
    except Exception as e:
        if 'idx_kode_akun_unik' in str(e):
             return jsonify({"message": "ERROR", "error": "Kode akun sudah ada. Harap gunakan kode lain."}), 409
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE akun COA (Tanpa validasi tipe_akun)
@coaadmin_endpoints.route('/updateCoa/<int:id_coa>', methods=['PUT'])
def update_coa(id_coa):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        kode_akun = data.get("kode_akun")
        nama_akun = data.get("nama_akun")
        tipe_akun = data.get("tipe_akun")
        deskripsi = data.get("deskripsi")

        # Validasi input (hanya cek jika wajib diisi)
        if not all([kode_akun, nama_akun, tipe_akun]):
            return jsonify({"message": "ERROR", "error": "Kode akun, nama akun, dan tipe akun wajib diisi"}), 400

        # --- Validasi tipe_akun telah dihapus ---

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            UPDATE chart_of_accounts
            SET kode_akun = %s, nama_akun = %s, tipe_akun = %s, deskripsi = %s
            WHERE id_coa = %s
        """
        cursor.execute(query, (kode_akun, nama_akun, tipe_akun, deskripsi, id_coa))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Akun COA tidak ditemukan"}), 404

        return jsonify({"message": "Akun COA berhasil diperbarui"}), 200
    
    except Exception as e:
        if 'idx_kode_akun_unik' in str(e):
             return jsonify({"message": "ERROR", "error": "Kode akun sudah ada. Harap gunakan kode lain."}), 409
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE akun COA
@coaadmin_endpoints.route('/deleteCoa/<int:id_coa>', methods=['DELETE'])
def delete_coa(id_coa):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM chart_of_accounts WHERE id_coa = %s"
        cursor.execute(query, (id_coa,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Akun COA tidak ditemukan"}), 404

        return jsonify({"message": "Akun COA berhasil dihapus"}), 200
    
    except Exception as e:
        if 'foreign key constraint' in str(e).lower():
            return jsonify({"message": "ERROR", "error": "Tidak dapat menghapus akun COA karena sedang digunakan oleh Kategori Produk atau Ruangan."}), 400
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()