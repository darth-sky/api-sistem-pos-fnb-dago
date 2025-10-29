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
# ✅ PERBAIKAN: Endpoint untuk mengambil SEMUA event space booking


@eventspacesadmin_endpoints.route('/bookings', methods=['GET'])
def get_all_bookings():
    """
    Mengambil semua data booking event dengan informasi lengkap,
    termasuk alasan pembatalan jika ada.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query JOIN sekarang juga mengambil 'alasan_pembatalan'
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
                be.status_booking AS status,
                be.alasan_pembatalan AS rejectionReason  -- <-- PERUBAHAN DI SINI
            FROM booking_event be
            JOIN transaksi t ON be.id_transaksi = t.id_transaksi
            JOIN users u ON t.id_user = u.id_user
            JOIN event_spaces es ON be.id_event_space = es.id_event_space
            ORDER BY t.tanggal_transaksi DESC
        """
        cursor.execute(query)
        all_bookings = cursor.fetchall()

        # Logika pengkategorian tidak perlu diubah
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
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
            
# Endpoint untuk MENYETUJUI booking
@eventspacesadmin_endpoints.route('/bookings/<int:booking_id>/approve', methods=['POST'])
def approve_booking(booking_id):
    """
    Menyetujui booking event, mengubah status booking menjadi 'Confirmed'
    dan mengubah status transaksi terkait menjadi 'Lunas' dan 'Selesai'.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        # PERUBAHAN 1: Gunakan dictionary=True untuk membaca id_transaksi
        cursor = connection.cursor(dictionary=True) 
        
        # --- LOGIKA UPDATE GANDA ---

        # 1. Ambil id_transaksi dari booking_event yang akan disetujui
        cursor.execute("SELECT id_transaksi FROM booking_event WHERE id_booking_event = %s", (booking_id,))
        booking_to_approve = cursor.fetchone()

        if not booking_to_approve:
            return jsonify({"success": False, "message": "Booking tidak ditemukan"}), 404
        
        id_transaksi_to_complete = booking_to_approve['id_transaksi']

        # 2. Update tabel booking_event (menjadi 'Confirmed')
        query_booking = "UPDATE booking_event SET status_booking = 'Confirmed' WHERE id_booking_event = %s"
        cursor.execute(query_booking, (booking_id,))
        
        # 3. PERUBAHAN 2: Update juga tabel transaksi (menjadi 'Lunas' dan 'Selesai')
        query_transaksi = """
            UPDATE transaksi 
            SET status_pembayaran = 'Lunas', status_order = 'Selesai'
            WHERE id_transaksi = %s
        """
        cursor.execute(query_transaksi, (id_transaksi_to_complete,))

        # 4. PERUBAHAN 3: Commit HANYA setelah kedua update berhasil
        connection.commit()
        
        # --- AKHIR LOGIKA UPDATE GANDA ---
        
        return jsonify({"success": True, "message": f"Booking {booking_id} approved and transaction completed."}), 200

    except Exception as e:
        if connection:
            # Rollback akan membatalkan KEDUA update jika salah satu gagal
            connection.rollback() 
        return jsonify({"success": False, "message": str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ✅ PERBAIKAN: Endpoint untuk MENOLAK booking
@eventspacesadmin_endpoints.route('/bookings/<int:booking_id>/reject', methods=['POST'])
def reject_booking(booking_id):
    """
    Menolak booking dan menyimpan alasan penolakan.
    Juga membatalkan transaksi terkait.
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        reason = data.get('reason', None)

        connection = get_connection()
        # PERUBAHAN 1: Gunakan dictionary=True untuk membaca id_transaksi
        cursor = connection.cursor(dictionary=True) 
        
        # --- LOGIKA UPDATE GANDA ---

        # 1. Ambil id_transaksi dari booking_event yang akan ditolak
        cursor.execute("SELECT id_transaksi FROM booking_event WHERE id_booking_event = %s", (booking_id,))
        booking_to_reject = cursor.fetchone()

        if not booking_to_reject:
            return jsonify({"success": False, "message": "Booking tidak ditemukan"}), 404
        
        id_transaksi_to_cancel = booking_to_reject['id_transaksi']

        # 2. Update tabel booking_event (seperti sebelumnya)
        query_booking = """
            UPDATE booking_event 
            SET status_booking = 'Dibatalkan', alasan_pembatalan = %s 
            WHERE id_booking_event = %s
        """
        cursor.execute(query_booking, (reason, booking_id))
        
        # 3. PERUBAHAN 2: Update juga tabel transaksi
        query_transaksi = """
            UPDATE transaksi 
            SET status_pembayaran = 'Dibatalkan', status_order = 'Batal'
            WHERE id_transaksi = %s
        """
        cursor.execute(query_transaksi, (id_transaksi_to_cancel,))

        # 4. PERUBAHAN 3: Commit HANYA setelah kedua update berhasil
        connection.commit()
        
        # --- AKHIR LOGIKA UPDATE GANDA ---
        
        return jsonify({"success": True, "message": f"Booking {booking_id} rejected and transaction cancelled."}), 200

    except Exception as e:
        if connection:
            # Rollback akan membatalkan KEDUA update jika salah satu gagal
            connection.rollback() 
        return jsonify({"success": False, "message": str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        

@eventspacesadmin_endpoints.route('/read', methods=['GET'])
def readEventSpaces():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM event_spaces ORDER BY id_event_space DESC"
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()



# ✅ CREATE an event space (Diperbarui)
@eventspacesadmin_endpoints.route('/create', methods=['POST'])
def createEventSpace():
    connection = None
    cursor = None
    try:
        # Ambil data dari form-data
        nama = request.form.get("nama_event_space")
        harga = request.form.get("harga_paket")
        # PERBAIKAN: Sesuaikan nilai default dengan ENUM baru di database
        status = request.form.get("status_ketersediaan", 'Active') 
        deskripsi = request.form.get("deskripsi_event_space")
        kapasitas = request.form.get("kapasitas")
        fitur = request.form.get("fitur_ruangan")

        if not nama or not harga or not status:
            return jsonify({"message": "ERROR", "error": "Nama, harga, dan status wajib diisi"}), 400

        # Handle upload file
        gambar_filename = None
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and file.filename != '':
                # Anda bisa menambahkan validasi 'allowed_file' di sini jika perlu
                filename = secure_filename(file.filename)
                # Opsi: buat nama file unik untuk menghindari tumpukan
                # unique_filename = str(uuid.uuid4()) + "_" + filename
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
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
# ✅ UPDATE an event space (Diperbarui)
@eventspacesadmin_endpoints.route('/update/<int:id_event_space>', methods=['PUT'])
def updateEventSpace(id_event_space):
    connection = None
    cursor = None
    try:
        # Ambil data dari form-data
        nama = request.form.get("nama_event_space")
        harga = request.form.get("harga_paket")
        # PERBAIKAN: Sesuaikan nilai default dengan ENUM baru
        status = request.form.get("status_ketersediaan", 'Active') 
        deskripsi = request.form.get("deskripsi_event_space")
        kapasitas = request.form.get("kapasitas")
        fitur = request.form.get("fitur_ruangan")

        if not nama or not harga or not status:
            return jsonify({"message": "ERROR", "error": "Nama, harga, dan status wajib diisi"}), 400

        connection = get_connection()
        # Menggunakan dictionary cursor untuk mengambil nama file lama
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT gambar_ruangan FROM event_spaces WHERE id_event_space = %s", (id_event_space,))
        existing_data = cursor.fetchone()
        if not existing_data:
            return jsonify({"message": "ERROR", "error": "Event Space tidak ditemukan"}), 404

        gambar_filename = existing_data['gambar_ruangan'] # Mulai dengan gambar lama

        # Handle upload file jika ada file baru
        if "gambar_ruangan" in request.files:
            file = request.files["gambar_ruangan"]
            if file and file.filename != '':
                # Hapus file lama jika ada
                if gambar_filename and os.path.exists(os.path.join(UPLOAD_FOLDER, gambar_filename)):
                    os.remove(os.path.join(UPLOAD_FOLDER, gambar_filename))
                
                # Simpan file baru
                filename = secure_filename(file.filename)
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                gambar_filename = filename # Ganti dengan nama file baru

        # Lakukan update
        update_query = """
        UPDATE event_spaces SET 
        nama_event_space = %s, deskripsi_event_space = %s, harga_paket = %s, 
        kapasitas = %s, status_ketersediaan = %s, fitur_ruangan = %s, gambar_ruangan = %s
        WHERE id_event_space = %s
        """
        # Gunakan cursor baru tanpa dictionary untuk eksekusi update
        update_cursor = connection.cursor()
        update_cursor.execute(update_query, (nama, deskripsi, harga, kapasitas, status, fitur, gambar_filename, id_event_space))
        connection.commit()
        update_cursor.close()

        return jsonify({"message": "Event Space berhasil diperbarui"}), 200
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE an event space (Diperbarui dengan penghapusan file)
@eventspacesadmin_endpoints.route('/delete/<int:id_event_space>', methods=['DELETE'])
def deleteEventSpace(id_event_space):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Dapatkan nama file gambar sebelum dihapus dari DB
        cursor.execute("SELECT gambar_ruangan FROM event_spaces WHERE id_event_space = %s", (id_event_space,))
        event_space = cursor.fetchone()
        
        if not event_space:
            return jsonify({"message": "ERROR", "error": "Event Space tidak ditemukan"}), 404
        
        # 2. Hapus data dari database
        delete_cursor = connection.cursor()
        delete_cursor.execute("DELETE FROM event_spaces WHERE id_event_space = %s", (id_event_space,))
        connection.commit()
        delete_cursor.close()

        # 3. Hapus file gambar dari server jika ada
        image_to_delete = event_space['gambar_ruangan']
        if image_to_delete and os.path.exists(os.path.join(UPLOAD_FOLDER, image_to_delete)):
            os.remove(os.path.join(UPLOAD_FOLDER, image_to_delete))

        return jsonify({"message": "Event Space berhasil dihapus"}), 200
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()