"""Routes for module ruangan"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book

ruangan_endpoints = Blueprint('ruangan', __name__)
UPLOAD_FOLDER = "img"


@ruangan_endpoints.route('/readRuangan', methods=['GET'])
def readRuangan():
    """Routes for module get list ruangan"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = select_query = """
        SELECT r.*, k.nama_kategori
        FROM ruangan r
        JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
        """
        cursor.execute(select_query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
@ruangan_endpoints.route('/readMembership', methods=['GET'])
def readMembership():
    """Ambil daftar paket membership + kategori ruangan"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            pm.id_paket_membership,
            pm.nama_paket,
            pm.harga,
            pm.durasi,
            pm.kuota,
            pm.deskripsi_benefit,
            kr.id_kategori_ruangan,
            kr.nama_kategori
        FROM paket_membership pm
        JOIN kategori_ruangan kr 
            ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
        """
        cursor.execute(query)
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
            
# File: ruangan_endpoints.py
@ruangan_endpoints.route('/event-spaces', methods=['GET'])
def get_all_event_spaces():
    """
    Endpoint publik untuk mengambil semua event space yang tersedia.
    Tidak memerlukan autentikasi.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query untuk mengambil data dari tabel event_spaces
        query = """
            SELECT
                id_event_space,
                nama_event_space,
                deskripsi_event_space,
                harga_paket,
                kapasitas,
                gambar_ruangan,
                fitur_ruangan
            FROM event_spaces
            WHERE status_ketersediaan = 'Tersedia'
        """
        cursor.execute(query)
        event_spaces = cursor.fetchall()

        return jsonify(event_spaces), 200

    except Exception as e:
        # Mengembalikan pesan error jika terjadi masalah
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        # Memastikan koneksi database selalu ditutup
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()

@ruangan_endpoints.route('/event-spaces/<int:space_id>', methods=['GET'])
def get_event_space_by_id(space_id):
    """
    Endpoint untuk mengambil detail satu event space berdasarkan ID.
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                id_event_space,
                nama_event_space,
                deskripsi_event_space,
                harga_paket,
                kapasitas,
                gambar_ruangan,
                fitur_ruangan
            FROM event_spaces
            WHERE id_event_space = %s
        """
        cursor.execute(query, (space_id,))
        event_space = cursor.fetchone()

        if not event_space:
            return jsonify({"msg": "Event space not found"}), 404

        return jsonify(event_space), 200

    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection:
            connection.close()
            

@ruangan_endpoints.route('/bookingEvent', methods=['POST'])
def create_booking():
    """
    Endpoint untuk membuat booking baru.
    """
    data = request.get_json()

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Insert transaksi
        transaksi_query = """
            INSERT INTO transaksi (id_user, total_harga_final, status_pembayaran, status_order, nama_guest)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(
            transaksi_query,
            (
                data.get("id_user"),  # NULL jika guest
                data.get("total_harga_final"),
                "Belum Lunas",  # default status pembayaran
                "Baru",         # default status order
                data.get("nama_pemesan")
            )
        )
        id_transaksi = cursor.lastrowid

        # 2. Insert booking_event
        booking_query = """
            INSERT INTO booking_event (id_event_space, id_user, id_transaksi, tanggal_event, waktu_mulai, waktu_selesai, status_booking)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(
            booking_query,
            (
                data.get("id_event_space"),
                data.get("id_user"),
                id_transaksi,
                data.get("tanggal_event"),
                data.get("waktu_mulai"),
                data.get("waktu_selesai"),
                "Baru"  # default status
            )
        )
        id_booking = cursor.lastrowid

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Booking berhasil dibuat",
            "data": {
                "id_booking_event": id_booking,
                "id_transaksi": id_transaksi
            }
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()






@ruangan_endpoints.route('/bookRuangan', methods=['POST'])
def book_ruangan():
    """Buat transaksi baru + booking ruangan"""
    connection = None
    cursor = None
    try:
        data = request.json
        id_user = data.get("id_user")   # bisa None kalau guest
        nama_guest = data.get("nama_guest")
        id_ruangan = data["id_ruangan"]
        waktu_mulai = data["waktu_mulai"]
        waktu_selesai = data["waktu_selesai"]
        metode_pembayaran = data.get("metode_pembayaran", "Tunai")
        total_harga = data["total_harga_final"]

        # hitung durasi dalam jam (dibulatkan ke atas jika ada menit sisa)
        from datetime import datetime
        import math
        t1 = datetime.strptime(waktu_mulai, "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(waktu_selesai, "%Y-%m-%d %H:%M:%S")
        durasi = math.ceil((t2 - t1).total_seconds() / 3600)

        connection = get_connection()
        cursor = connection.cursor()

        # 1. Insert ke transaksi
        insert_transaksi = """
        INSERT INTO transaksi 
        (id_user, nama_guest, total_harga_final, metode_pembayaran, status_pembayaran, status_order, lokasi_pemesanan) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_transaksi, (
            id_user, nama_guest, total_harga, metode_pembayaran,
            "Lunas", "Baru", f"ruangan_{id_ruangan}"
        ))
        id_transaksi = cursor.lastrowid

        # 2. Insert ke booking_ruangan
        insert_booking = """
        INSERT INTO booking_ruangan
        (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_booking, (
            id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi
        ))

        connection.commit()

        return jsonify({
            "message": "Booking berhasil",
            "id_transaksi": id_transaksi,
            "durasi_jam": durasi
        }), 201

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()




@ruangan_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_ruangan (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_ruangan": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@ruangan_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_ruangan SET title=%s, description=%s WHERE id_ruangan=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_ruangan": product_id}
    return jsonify(data), 200


@ruangan_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_ruangan WHERE id_ruangan = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_ruangan": product_id}
    return jsonify(data)


@ruangan_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@ruangan_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list ruangan"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_ruangan WHERE id_ruangan = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200