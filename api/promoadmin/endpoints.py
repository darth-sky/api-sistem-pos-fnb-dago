"""Routes for module promoadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename
from decimal import Decimal
from datetime import datetime, timedelta

promoadmin_endpoints = Blueprint("promoadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@promoadmin_endpoints.route('/readPromo', methods=['GET'])
def read_promo():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM promo ORDER BY id_promo DESC"
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Mengubah format tanggal dan waktu menjadi string agar JSON-serializable
        for row in results:
            for key, value in row.items():
                if isinstance(value, (bytes, bytearray)):
                    row[key] = value.decode('utf-8')
                # Cek jika objek date/time/timedelta
                elif hasattr(value, 'isoformat'): 
                    row[key] = value.isoformat()
                # Khusus untuk timedelta yang tidak punya isoformat()
                elif isinstance(value, timedelta):
                    row[key] = str(value)
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
# ✅ CREATE promo (FIXED: Added kategori_promo)
@promoadmin_endpoints.route('/createPromo', methods=['POST'])
def create_promo():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        
        # Ambil data
        kode_promo = data.get("kode_promo")
        deskripsi_promo = data.get("deskripsi_promo")
        nilai_diskon = data.get("nilai_diskon")
        tanggal_mulai = data.get("tanggal_mulai")
        tanggal_selesai = data.get("tanggal_selesai")
        waktu_mulai = data.get("waktu_mulai") 
        waktu_selesai = data.get("waktu_selesai")
        status_aktif = data.get("status_aktif", "inaktif")
        
        # Field Baru
        syarat = data.get("syarat") 
        # Default ke 'all' jika tidak dikirim, agar sesuai ENUM database
        kategori_promo = data.get("kategori_promo", "all") 

        if not all([kode_promo, nilai_diskon, tanggal_mulai, tanggal_selesai]):
            return jsonify({"message": "ERROR", "error": "Field wajib harus diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # Query INSERT
        query = """
            INSERT INTO promo (
                kode_promo, deskripsi_promo, nilai_diskon, 
                tanggal_mulai, tanggal_selesai, waktu_mulai, 
                waktu_selesai, status_aktif, syarat, kategori_promo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Parameter Tuple (Pastikan urutan sama persis dengan query)
        cursor.execute(query, (
            kode_promo, deskripsi_promo, nilai_diskon, 
            tanggal_mulai, tanggal_selesai, waktu_mulai, 
            waktu_selesai, status_aktif, syarat, kategori_promo
        ))
        
        connection.commit()
        return jsonify({"message": "Promo berhasil ditambahkan"}), 201

    except Exception as e:
        print(f"Error Create Promo: {e}") # Log error ke terminal
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ UPDATE promo (FIXED: Added kategori_promo & Fixed Parameter Order)
@promoadmin_endpoints.route('/updatePromo/<int:id_promo>', methods=['PUT'])
def update_promo(id_promo):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        
        # Ambil data
        kode_promo = data.get("kode_promo")
        deskripsi_promo = data.get("deskripsi_promo")
        nilai_diskon = data.get("nilai_diskon")
        tanggal_mulai = data.get("tanggal_mulai")
        tanggal_selesai = data.get("tanggal_selesai")
        waktu_mulai = data.get("waktu_mulai")
        waktu_selesai = data.get("waktu_selesai")
        status_aktif = data.get("status_aktif")
        
        # Field Baru
        syarat = data.get("syarat")
        kategori_promo = data.get("kategori_promo", "all") # Default 'all' jika null

        if not all([kode_promo, nilai_diskon, tanggal_mulai, tanggal_selesai, status_aktif]):
            return jsonify({"message": "ERROR", "error": "Semua field wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # Query UPDATE
        query = """
            UPDATE promo 
            SET kode_promo = %s, 
                deskripsi_promo = %s, 
                nilai_diskon = %s, 
                tanggal_mulai = %s, 
                tanggal_selesai = %s, 
                waktu_mulai = %s, 
                waktu_selesai = %s, 
                status_aktif = %s,
                syarat = %s,
                kategori_promo = %s
            WHERE id_promo = %s
        """
        
        # Parameter Tuple (URUTAN SANGAT PENTING!)
        # Harus urut sesuai %s di query:
        # 1.kode, 2.deskripsi, 3.nilai, 4.tgl_mulai, 5.tgl_selesai, 
        # 6.waktu_mulai, 7.waktu_selesai, 8.status, 9.syarat, 10.kategori, 11.id_promo (WHERE)
        cursor.execute(query, (
            kode_promo, deskripsi_promo, nilai_diskon, 
            tanggal_mulai, tanggal_selesai, waktu_mulai, 
            waktu_selesai, status_aktif, syarat, kategori_promo,
            id_promo
        ))
        
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Promo tidak ditemukan"}), 404

        return jsonify({"message": "Promo berhasil diperbarui"}), 200

    except Exception as e:
        print(f"Error Update Promo: {e}") # Log error ke terminal
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
# ✅ DELETE promo
@promoadmin_endpoints.route('/deletePromo/<int:id_promo>', methods=['DELETE'])
def delete_promo(id_promo):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM promo WHERE id_promo = %s"
        cursor.execute(query, (id_promo,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Promo tidak ditemukan"}), 404

        return jsonify({"message": "Promo berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()