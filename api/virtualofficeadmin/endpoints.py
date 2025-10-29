"""Routes for module virtualofficeadmin"""
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
        status = data.get("status", 'Active') # PERBAIKAN: Ambil status, default 'Active'

        if not all([nama_paket, harga, durasi]):
            return jsonify({"message": "ERROR", "error": "Nama paket, harga, dan durasi wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO paket_virtual_office 
            (nama_paket, harga, durasi, benefit_jam_meeting_room_per_bulan, benefit_jam_working_space_per_bulan, deskripsi_layanan, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        # PERBAIKAN: Tambahkan 'status' ke parameter query
        cursor.execute(query, (nama_paket, harga, durasi, benefit_meeting, benefit_workspace, deskripsi, status))
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
        status = data.get("status", 'Active') # PERBAIKAN: Ambil status

        if not all([nama_paket, harga, durasi]):
            return jsonify({"message": "ERROR", "error": "Nama paket, harga, dan durasi wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            UPDATE paket_virtual_office 
            SET nama_paket = %s, harga = %s, durasi = %s, 
                benefit_jam_meeting_room_per_bulan = %s, 
                benefit_jam_working_space_per_bulan = %s, 
                deskripsi_layanan = %s,
                status = %s  -- PERBAIKAN: Tambahkan field status
            WHERE id_paket_vo = %s
        """
        # PERBAIKAN: Tambahkan 'status' ke parameter query
        cursor.execute(query, (nama_paket, harga, durasi, benefit_meeting, benefit_workspace, deskripsi, status, id_paket_vo))
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
        


# Ganti endpoint /getRequests Anda dengan ini
@virtualofficeadmin_endpoints.route('/getRequests', methods=['GET'])
def get_all_vo_requests():
    """Mengambil semua data klien VO dan mengkategorikannya."""
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # --- PERBAIKAN: JOIN dengan transaksi untuk tgl pengajuan ---
        query = """
            SELECT 
                cvo.*, 
                u.nama as nama_user, 
                pvo.nama_paket,
                t.tanggal_transaksi as tanggal_pengajuan  -- Ambil tanggal pengajuan dari transaksi
            FROM client_virtual_office cvo
            JOIN users u ON cvo.id_user = u.id_user
            JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
            JOIN transaksi t ON cvo.id_transaksi = t.id_transaksi  -- JOIN ke transaksi
            ORDER BY cvo.id_client_vo DESC
        """
        cursor.execute(query)
        all_requests = cursor.fetchall()

        # --- PERBAIKAN: Tambah kategori 'Menunggu Pembayaran' ---
        categorized = {
            'pending': [], 
            'waiting_payment': [],  # Kategori baru
            'active': [], 
            'rejected': [], 
            'expired': []
        }
        
        for req in all_requests:
            status = req['status_client_vo']
            if status == 'Menunggu Persetujuan':  # <--- PERBAIKAN (bukan 'Baru')
                categorized['pending'].append(req)
            elif status == 'Menunggu Pembayaran': # <--- Kategori baru
                categorized['waiting_payment'].append(req)
            elif status == 'Aktif':
                categorized['active'].append(req)
            elif status == 'Ditolak':
                categorized['rejected'].append(req)
            elif status == 'Kadaluarsa':
                categorized['expired'].append(req)
        
        return jsonify({"message": "OK", "datas": categorized}), 200
    except Exception as e:
        print(f"Error in /getRequests: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()
        
        

# Ganti endpoint /approveRequests Anda dengan ini
@virtualofficeadmin_endpoints.route('/approveRequests/<int:client_id>/approve', methods=['POST'])
def approve_vo_request(client_id):
    """
    PERUBAHAN LOGIKA:
    Hanya menyetujui pendaftaran dan mengubah status ke 'Menunggu Pembayaran'.
    TIDAK mengaktifkan layanan atau mengatur tanggal.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor() 

        # --- PERBAIKAN: Hanya update status, JANGAN set tanggal ---
        query_update = """
            UPDATE client_virtual_office 
            SET status_client_vo = 'Menunggu Pembayaran'
            WHERE id_client_vo = %s AND status_client_vo = 'Menunggu Persetujuan'
        """
        cursor.execute(query_update, (client_id,))
        
        if cursor.rowcount == 0:
            connection.rollback()
            return jsonify({"message": "ERROR", "error": "Permintaan tidak ditemukan atau statusnya salah"}), 404

        connection.commit()
        return jsonify({"message": "Request approved, waiting for payment"}), 200
        
    except Exception as e:
        if connection: connection.rollback()
        print(f"Error in /approveRequests: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()
        
                
# Ganti endpoint /rejectRequests Anda dengan ini
@virtualofficeadmin_endpoints.route('/rejectRequests/<int:client_id>/reject', methods=['POST'])
def reject_vo_request(client_id):
    """
    Menolak permintaan VO dan membatalkan transaksi terkait.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True) # Butuh dictionary untuk baca id_transaksi

        # 1. Ambil id_transaksi sebelum me-reject
        cursor.execute("SELECT id_transaksi FROM client_virtual_office WHERE id_client_vo = %s", (client_id,))
        client_data = cursor.fetchone()

        if not client_data:
             return jsonify({"message": "ERROR", "error": "Client not found"}), 404

        id_transaksi = client_data['id_transaksi']

        # 2. Update status client_virtual_office
        cursor.execute("UPDATE client_virtual_office SET status_client_vo = 'Ditolak' WHERE id_client_vo = %s", (client_id,))
        
        # --- PERBAIKAN: Batalkan juga transaksinya ---
        if id_transaksi:
            cursor.execute("UPDATE transaksi SET status_pembayaran = 'Dibatalkan' WHERE id_transaksi = %s", (id_transaksi,))

        connection.commit()
        
        return jsonify({"message": "Request rejected successfully"}), 200
    except Exception as e:
        if connection: connection.rollback()
        print(f"Error in /rejectRequests: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'connection' in locals(): connection.close()
        
        
