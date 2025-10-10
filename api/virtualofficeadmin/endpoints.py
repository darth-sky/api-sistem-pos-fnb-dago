"""Routes for module virtualofficeadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

virtualofficeadmin_endpoints = Blueprint("virtualofficeadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ✅ READ semua paket virtual office
@virtualofficeadmin_endpoints.route('/readPaket', methods=['GET'])
def read_paket_vo():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM paket_virtual_office ORDER BY id_paket_vo DESC"
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE paket virtual office
@virtualofficeadmin_endpoints.route('/createPaket', methods=['POST'])
def create_paket_vo():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_paket = data.get("nama_paket")
        harga = data.get("harga")
        durasi = data.get("durasi")
        benefit_meeting = data.get("benefit_jam_meeting_room_per_bulan", 0)
        benefit_workspace = data.get("benefit_jam_working_space_per_bulan", 0)
        deskripsi = data.get("deskripsi_layanan")

        if not all([nama_paket, harga, durasi]):
            return jsonify({"message": "ERROR", "error": "Nama paket, harga, dan durasi wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO paket_virtual_office 
            (nama_paket, harga, durasi, benefit_jam_meeting_room_per_bulan, benefit_jam_working_space_per_bulan, deskripsi_layanan) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nama_paket, harga, durasi, benefit_meeting, benefit_workspace, deskripsi))
        connection.commit()

        return jsonify({"message": "Paket Virtual Office berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE paket virtual office
@virtualofficeadmin_endpoints.route('/updatePaket/<int:id_paket_vo>', methods=['PUT'])
def update_paket_vo(id_paket_vo):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_paket = data.get("nama_paket")
        harga = data.get("harga")
        durasi = data.get("durasi")
        benefit_meeting = data.get("benefit_jam_meeting_room_per_bulan", 0)
        benefit_workspace = data.get("benefit_jam_working_space_per_bulan", 0)
        deskripsi = data.get("deskripsi_layanan")

        if not all([nama_paket, harga, durasi]):
            return jsonify({"message": "ERROR", "error": "Nama paket, harga, dan durasi wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            UPDATE paket_virtual_office 
            SET nama_paket = %s, harga = %s, durasi = %s, 
                benefit_jam_meeting_room_per_bulan = %s, 
                benefit_jam_working_space_per_bulan = %s, 
                deskripsi_layanan = %s
            WHERE id_paket_vo = %s
        """
        cursor.execute(query, (nama_paket, harga, durasi, benefit_meeting, benefit_workspace, deskripsi, id_paket_vo))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Paket Virtual Office tidak ditemukan"}), 404

        return jsonify({"message": "Paket Virtual Office berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE paket virtual office
@virtualofficeadmin_endpoints.route('/deletePaket/<int:id_paket_vo>', methods=['DELETE'])
def delete_paket_vo(id_paket_vo):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM paket_virtual_office WHERE id_paket_vo = %s"
        cursor.execute(query, (id_paket_vo,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Paket Virtual Office tidak ditemukan"}), 404

        return jsonify({"message": "Paket Virtual Office berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()