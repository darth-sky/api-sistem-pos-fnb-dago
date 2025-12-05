"""Routes for module acara"""
import os
import uuid
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from datetime import datetime, timedelta
import math
import traceback
from datetime import date
from werkzeug.utils import secure_filename


acara_endpoints = Blueprint('acara', __name__)
UPLOAD_FOLDER = "img"


UPLOAD_FOLDER = 'img' # Disarankan folder terpisah untuk gambar acara
# --- CRUD Endpoints for katalog_acara ---
# ✅ READ All Acara (Endpoint for Admin Table)


@acara_endpoints.route('/getAcaraAdmin', methods=['GET'])
def get_all_acara_admin():
    """Mengambil semua data acara untuk tabel admin."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT
                id_acara, judul_acara, tanggal_acara, waktu_mulai, waktu_selesai,
                lokasi, harga, deskripsi, tags, gambar_url, status_acara
            FROM katalog_acara
            ORDER BY tanggal_acara DESC
        """
        cursor.execute(query)
        acara_list = cursor.fetchall()

        # --- PERBAIKAN DI SINI ---
        import datetime # Pastikan datetime diimpor

        for acara in acara_list:
            # Konversi tanggal ke ISO format string (YYYY-MM-DD)
            if isinstance(acara.get('tanggal_acara'), datetime.date):
                acara['tanggal_acara'] = acara['tanggal_acara'].isoformat()

            # Konversi timedelta (waktu) ke string format HH:MM:SS
            if isinstance(acara.get('waktu_mulai'), datetime.timedelta):
                # Ubah timedelta menjadi total detik, lalu format
                total_seconds = int(acara['waktu_mulai'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                acara['waktu_mulai'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}" # Format HH:MM:SS
                # Atau jika hanya perlu HH:MM:
                # acara['waktu_mulai'] = f"{hours:02d}:{minutes:02d}"

            if isinstance(acara.get('waktu_selesai'), datetime.timedelta):
                total_seconds = int(acara['waktu_selesai'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                acara['waktu_selesai'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}" # Format HH:MM:SS
                # Atau jika hanya perlu HH:MM:
                # acara['waktu_selesai'] = f"{hours:02d}:{minutes:02d}"

            # Konversi tags string ke array
            if acara.get('tags') and isinstance(acara['tags'], str):
                 acara['tags'] = acara['tags'].split(',')
            elif not acara.get('tags'): # Handle jika tags NULL atau kosong
                 acara['tags'] = []
            # Jika sudah array (misal karena konversi sebelumnya), biarkan saja

        # --- AKHIR PERBAIKAN ---

        return jsonify({"message": "OK", "datas": acara_list}), 200
    except Exception as e:
        # Tambahkan print untuk debugging jika perlu
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        

# ✅ CREATE Acara (with image upload)
@acara_endpoints.route('/createAcara', methods=['POST'])
def create_acara():
    """Membuat acara baru."""
    connection = None
    cursor = None
    try:
        # Ambil data form teks
        judul_acara = request.form.get("judul_acara")
        tanggal_acara = request.form.get("tanggal_acara") # Format YYYY-MM-DD
        waktu_mulai = request.form.get("waktu_mulai")     # Format HH:MM
        waktu_selesai = request.form.get("waktu_selesai") # Format HH:MM
        lokasi = request.form.get("lokasi")
        harga = request.form.get("harga", "Gratis") # Default ke Gratis
        deskripsi = request.form.get("deskripsi")
        tags_input = request.form.get("tags") # String dipisah koma

        if not all([judul_acara, tanggal_acara, waktu_mulai, waktu_selesai]):
            return jsonify({"message": "ERROR", "error": "Judul, tanggal, waktu mulai, dan waktu selesai wajib diisi"}), 400

        tags_db = None
        if tags_input:
            # Bersihkan spasi ekstra dan gabungkan kembali
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            tags_db = ','.join(tags_list) # Simpan sebagai string dipisah koma

        gambar_filename = "default_event.jpg" # Default image
        if 'gambar_url' in request.files:
            file = request.files['gambar_url']
            if file.filename != '':
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                gambar_filename = unique_filename

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO katalog_acara
            (judul_acara, tanggal_acara, waktu_mulai, waktu_selesai, lokasi, harga, deskripsi, tags, gambar_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            judul_acara, tanggal_acara, waktu_mulai, waktu_selesai, lokasi, harga,
            deskripsi, tags_db, gambar_filename
        ))
        connection.commit()

        return jsonify({"message": "Acara berhasil ditambahkan"}), 201

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE Acara (with optional image upload)
@acara_endpoints.route('/updateAcara/<int:id_acara>', methods=['PUT'])
def update_acara(id_acara):
    """Memperbarui acara yang ada."""
    connection = None
    cursor = None
    try:
        # Ambil data form teks
        judul_acara = request.form.get("judul_acara")
        tanggal_acara = request.form.get("tanggal_acara")
        waktu_mulai = request.form.get("waktu_mulai")
        waktu_selesai = request.form.get("waktu_selesai")
        lokasi = request.form.get("lokasi")
        harga = request.form.get("harga", "Gratis")
        deskripsi = request.form.get("deskripsi")
        tags_input = request.form.get("tags")

        if not all([judul_acara, tanggal_acara, waktu_mulai, waktu_selesai]):
             return jsonify({"message": "ERROR", "error": "Judul, tanggal, waktu mulai, dan waktu selesai wajib diisi"}), 400

        tags_db = None
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            tags_db = ','.join(tags_list)

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Dapatkan nama file gambar lama
        cursor.execute("SELECT gambar_url FROM katalog_acara WHERE id_acara = %s", (id_acara,))
        acara = cursor.fetchone()
        if not acara:
            return jsonify({"message": "ERROR", "error": "Acara tidak ditemukan"}), 404

        old_image = acara.get('gambar_url')
        gambar_filename = old_image if old_image else "default_event.jpg"

        # Cek jika ada file baru yang diupload
        if 'gambar_url' in request.files:
            file = request.files['gambar_url']
            if file.filename != '':
                # Hapus gambar lama jika ada DAN bukan default
                if old_image and old_image != "default_event.jpg" and os.path.exists(os.path.join(UPLOAD_FOLDER, old_image)):
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, old_image))
                    except OSError as e:
                        print(f"Error deleting old file {old_image}: {e}") # Log error, tapi lanjutkan

                # Simpan gambar baru
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                gambar_filename = unique_filename

        # Update database
        # Gunakan cursor non-dictionary untuk execute update
        cursor = connection.cursor()
        query_update = """
            UPDATE katalog_acara SET
            judul_acara = %s, tanggal_acara = %s, waktu_mulai = %s, waktu_selesai = %s,
            lokasi = %s, harga = %s, deskripsi = %s, tags = %s, gambar_url = %s
            WHERE id_acara = %s
        """
        cursor.execute(query_update, (
            judul_acara, tanggal_acara, waktu_mulai, waktu_selesai, lokasi, harga,
            deskripsi, tags_db, gambar_filename, id_acara
        ))
        connection.commit()

        return jsonify({"message": "Acara berhasil diperbarui"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@acara_endpoints.route('/updateAcaraStatus/<int:id_acara>/status', methods=['PUT'])
def update_acara_status(id_acara):
    """Mengubah status_acara (aktif/inaktif)."""
    connection = None
    cursor = None
    try:
        data = request.get_json()
        new_status = data.get('status_acara')

        if new_status not in ['aktif', 'inaktif']:
            return jsonify({"message": "ERROR", "error": "Status tidak valid"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = "UPDATE katalog_acara SET status_acara = %s WHERE id_acara = %s"
        cursor.execute(query, (new_status, id_acara))

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Acara tidak ditemukan"}), 404

        connection.commit()
        return jsonify({"message": f"Status acara berhasil diubah menjadi {new_status}"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE Acara
@acara_endpoints.route('/deleteAcara/<int:id_acara>', methods=['DELETE'])
def delete_acara(id_acara):
    """Menghapus acara."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Dapatkan nama file gambar untuk dihapus
        cursor.execute("SELECT gambar_url FROM katalog_acara WHERE id_acara = %s", (id_acara,))
        acara = cursor.fetchone()

        # Hapus data dari database
        # Gunakan cursor non-dictionary untuk execute delete
        cursor = connection.cursor()
        cursor.execute("DELETE FROM katalog_acara WHERE id_acara = %s", (id_acara,))

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Acara tidak ditemukan"}), 404

        # Hapus file gambar jika ada dan bukan default
        if acara and acara.get('gambar_url') and acara['gambar_url'] != "default_event.jpg":
            image_path = os.path.join(UPLOAD_FOLDER, acara['gambar_url'])
            if os.path.exists(image_path):
                 try:
                    os.remove(image_path)
                 except OSError as e:
                     print(f"Error deleting file {image_path}: {e}") # Log error

        connection.commit()
        return jsonify({"message": "Acara berhasil dihapus"}), 200

    except Exception as e:
        if connection: connection.rollback()
        # Periksa jika error karena foreign key constraint (misal acara terhubung ke tabel lain)
        if "foreign key constraint fails" in str(e).lower():
             return jsonify({"message": "ERROR", "error": "Acara tidak dapat dihapus karena masih terhubung dengan data lain."}), 409 # Conflict
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@acara_endpoints.route('/Getacara', methods=['GET'])
def get_semua_acara():
    """
    Mengambil semua daftar acara dari katalog.
    Status ('upcoming'/'past') akan dihitung secara dinamis.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERBAIKAN DI BAWAH ---
        # 1. Kita ganti string format dengan placeholder %s
        query = """
        SELECT
            id_acara AS id,
            judul_acara AS title,
            DATE_FORMAT(tanggal_acara, %s) AS date, 
            CONCAT(
                TIME_FORMAT(waktu_mulai, %s),
                ' - ', 
                TIME_FORMAT(waktu_selesai, %s),
                ' WIB'
            ) AS time,
            lokasi AS location,
            harga AS price,
            IF(tanggal_acara >= CURDATE(), 'upcoming', 'past') AS status,
            deskripsi AS description,
            tags, 
            gambar_url AS imageUrl
        FROM
            katalog_acara
        WHERE
            status_acara = 'aktif'
        ORDER BY
            tanggal_acara DESC
        """
        
        # 2. Tentukan string format sebagai variabel Python
        date_format_str = '%d %M %Y'
        time_format_str = '%H:%i'

        # 3. Lewatkan string format itu sebagai PARAMETER ke cursor.execute
        # Ini adalah cara paling aman dan anti-error
        cursor.execute(query, (date_format_str, time_format_str, time_format_str))
        acara_list = cursor.fetchall()

        # --- AKHIR PERBAIKAN ---

        # Proses 'tags' dari string "A,B,C" menjadi array ["A", "B", "C"]
        for acara in acara_list:
            if acara['tags'] and isinstance(acara['tags'], str):
                acara['tags'] = acara['tags'].split(',')
            else:
                acara['tags'] = []
        
        return jsonify({
            "message": "OK",
            "data": acara_list
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        