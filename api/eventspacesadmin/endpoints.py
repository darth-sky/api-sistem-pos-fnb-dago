"""Routes for module eventspacesadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

eventspacesadmin_endpoints = Blueprint("eventspacesadmin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Tambahkan ini di file backend Python Anda

# Endpoint untuk mengambil SEMUA event space booking
@eventspacesadmin_endpoints.route('/bookings', methods=['GET'])
def get_all_bookings():
    """
    Mengambil semua data booking event dengan informasi lengkap dari beberapa tabel.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query JOIN yang sudah disesuaikan (tanpa alasan_pembatalan)
        query = """
            SELECT 
                be.id_booking_event AS id,
                u.nama AS customerName,
                be.nama_acara AS eventName,
                es.nama_event_space AS spaceName,
                be.tanggal_event AS date,
                CONCAT(DATE_FORMAT(be.waktu_mulai, '%H:%i'), ' - ', DATE_FORMAT(be.waktu_selesai, '%H:%i')) AS time,
                TIMESTAMPDIFF(HOUR, be.waktu_mulai, be.waktu_selesai) AS duration,
                be.jumlah_peserta AS guests,
                t.total_harga_final AS price,
                u.no_telepon AS phone,
                u.email AS email,
                be.deskripsi AS description,
                be.kebutuhan_tambahan AS requirements,
                t.tanggal_transaksi AS submittedAt,
                be.status_booking AS status
            FROM booking_event be
            JOIN transaksi t ON be.id_transaksi = t.id_transaksi
            JOIN users u ON t.id_user = u.id_user
            JOIN event_spaces es ON be.id_event_space = es.id_event_space
            ORDER BY t.tanggal_transaksi DESC
        """
        cursor.execute(query)
        all_bookings = cursor.fetchall()

        # Bagian ini tetap sama
        categorized_bookings = {
            'pending': [],
            'approved': [],
            'rejected': []
        }
        
        for booking in all_bookings:
            if booking['status'] == 'Baru':
                categorized_bookings['pending'].append(booking)
            elif booking['status'] == 'Confirmed' or booking['status'] == 'Selesai':
                categorized_bookings['approved'].append(booking)
            elif booking['status'] == 'Dibatalkan':
                categorized_bookings['rejected'].append(booking)

        return jsonify(categorized_bookings), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# Endpoint untuk MENYETUJUI booking
@eventspacesadmin_endpoints.route('/bookings/<int:booking_id>/approve', methods=['POST'])
def approve_booking(booking_id):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        query = "UPDATE booking_event SET status_booking = 'Confirmed' WHERE id_booking_event = %s"
        cursor.execute(query, (booking_id,))
        connection.commit()
        
        return jsonify({"success": True, "message": f"Booking {booking_id} approved."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()


# Endpoint untuk MENOLAK booking
@eventspacesadmin_endpoints.route('/bookings/<int:booking_id>/reject', methods=['POST'])
def reject_booking(booking_id):
    # Tidak perlu lagi mengambil 'reason' dari body request
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Query UPDATE yang sudah disesuaikan (hanya mengubah status)
        query = "UPDATE booking_event SET status_booking = 'Dibatalkan' WHERE id_booking_event = %s"
        cursor.execute(query, (booking_id,))
        connection.commit()
        
        return jsonify({"success": True, "message": f"Booking {booking_id} rejected."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            


# ✅ READ all event spaces
@eventspacesadmin_endpoints.route('/read', methods=['GET'])
def readEventSpaces():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM event_spaces"
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE an event space
@eventspacesadmin_endpoints.route('/create', methods=['POST'])
def createEventSpace():
    connection = None
    cursor = None
    try:
        # Ambil data dari form-data
        nama = request.form.get("nama_event_space")
        harga = request.form.get("harga_paket")
        status = request.form.get("status_ketersediaan")
        deskripsi = request.form.get("deskripsi_event_space")
        kapasitas = request.form.get("kapasitas")
        fitur = request.form.get("fitur_ruangan")

        if not nama or not harga or not status:
            return jsonify({"message": "ERROR", "error": "Nama, harga, dan status wajib diisi"}), 400

        # Handle upload file
        gambar_filename = None
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar_filename = filename

        connection = get_connection()
        cursor = connection.cursor()
        query = """
        INSERT INTO event_spaces (nama_event_space, deskripsi_event_space, harga_paket, kapasitas, status_ketersediaan, fitur_ruangan, gambar_ruangan)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nama, deskripsi, harga, kapasitas, status, fitur, gambar_filename))
        connection.commit()
        return jsonify({"message": "Event Space berhasil ditambahkan"}), 201
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
# ✅ UPDATE an event space (dengan upload gambar)
@eventspacesadmin_endpoints.route('/update/<id_event_space>', methods=['PUT'])
def updateEventSpace(id_event_space):
    connection = None
    cursor = None
    try:
        # Ambil data dari form-data
        nama = request.form.get("nama_event_space")
        harga = request.form.get("harga_paket")
        status = request.form.get("status_ketersediaan")
        deskripsi = request.form.get("deskripsi_event_space")
        kapasitas = request.form.get("kapasitas")
        fitur = request.form.get("fitur_ruangan")

        if not nama or not harga or not status:
            return jsonify({"message": "ERROR", "error": "Nama, harga, dan status wajib diisi"}), 400

        # Handle upload file jika ada file baru
        gambar_filename = request.form.get("gambar_ruangan_existing") # Ambil nama file lama
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and allowed_file(file.filename):
                # Hapus file lama jika ada (opsional, tapi disarankan)
                if gambar_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, gambar_filename)):
                    os.remove(os.path.join(UPLOAD_FOLDER, gambar_filename))
                
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar_filename = filename # Ganti dengan nama file baru

        connection = get_connection()
        cursor = connection.cursor()
        query = """
        UPDATE event_spaces SET 
        nama_event_space = %s, deskripsi_event_space = %s, harga_paket = %s, 
        kapasitas = %s, status_ketersediaan = %s, fitur_ruangan = %s, gambar_ruangan = %s
        WHERE id_event_space = %s
        """
        cursor.execute(query, (nama, deskripsi, harga, kapasitas, status, fitur, gambar_filename, id_event_space))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Event Space tidak ditemukan"}), 404

        return jsonify({"message": "Event Space berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE an event space
@eventspacesadmin_endpoints.route('/delete/<id_event_space>', methods=['DELETE'])
def deleteEventSpace(id_event_space):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM event_spaces WHERE id_event_space = %s"
        cursor.execute(query, (id_event_space,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Event Space tidak ditemukan"}), 404

        return jsonify({"message": "Event Space berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()