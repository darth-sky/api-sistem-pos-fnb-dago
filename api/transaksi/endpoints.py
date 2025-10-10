"""Routes for module transaksi"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required, get_jwt_identity
from helper.year_operation import diff_year
from helper.year_operation import check_age_book

transaksi_endpoints = Blueprint('transaksi', __name__)
UPLOAD_FOLDER = "img"


@transaksi_endpoints.route('/read', methods=['GET'])
@jwt_required()
def read():
    """Routes for module get list transaksi"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT * FROM tb_transaksi"
    cursor.execute(select_query)
    results = cursor.fetchall()
    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200


# HALAMAN TRANSAKSI PELANGGAN START

@transaksi_endpoints.route('/riwayat', methods=['GET'])
@jwt_required()
def get_riwayat_transaksi():
    try:
        identity = get_jwt_identity()
        user_id = identity.get("id_user")

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # === SOLUSI: Menggunakan GROUP_CONCAT untuk membuat string berformat JSON ===
        query = """
        SELECT 
            t.id_transaksi,
            t.tanggal_transaksi,
            t.total_harga_final,
            t.metode_pembayaran,
            t.status_pembayaran,
            t.status_order,
            
            -- Booking Ruangan: Buat string yang meniru array of objects
            (SELECT CONCAT('[', 
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_ruangan', r.nama_ruangan,
                        'waktu_mulai', br.waktu_mulai,
                        'waktu_selesai', br.waktu_selesai,
                        'durasi', br.durasi
                    )
                ), 
            ']')
            FROM booking_ruangan br JOIN ruangan r ON br.id_ruangan = r.id_ruangan WHERE br.id_transaksi = t.id_transaksi) AS bookings,

            -- Lakukan hal yang sama untuk item lainnya
            (SELECT CONCAT('[', 
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_paket', pm.nama_paket,
                        'tanggal_mulai', m.tanggal_mulai,
                        'tanggal_berakhir', m.tanggal_berakhir
                    )
                ), 
            ']')
            FROM memberships m JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership WHERE m.id_transaksi = t.id_transaksi) AS memberships,
            
            (SELECT CONCAT('[',
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_paket', pvo.nama_paket,
                        'nama_perusahaan', vo.nama_perusahaan_klien,
                        'tanggal_mulai', vo.tanggal_mulai,
                        'tanggal_berakhir', vo.tanggal_berakhir
                    )
                ),
            ']')
            FROM client_virtual_office vo JOIN paket_virtual_office pvo ON vo.id_paket_vo = pvo.id_paket_vo WHERE vo.id_transaksi = t.id_transaksi) AS virtual_offices,

            (SELECT CONCAT('[',
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_event', bes.nama_acara,
                        'nama_space', es.nama_event_space,
                        'tanggal_event', bes.tanggal_event
                    )
                ),
            ']')
            FROM booking_event bes JOIN event_spaces es ON bes.id_event_space = es.id_event_space WHERE bes.id_transaksi = t.id_transaksi) AS events

        FROM transaksi t
        WHERE t.id_user = %s
        GROUP BY t.id_transaksi
        ORDER BY t.tanggal_transaksi DESC
        """
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        
        # Logika parsing di Python tetap sama
        import json
        for row in results:
            if row['bookings']: row['bookings'] = json.loads(row['bookings'])
            if row['memberships']: row['memberships'] = json.loads(row['memberships'])
            if row['virtual_offices']: row['virtual_offices'] = json.loads(row['virtual_offices'])
            if row['events']: row['events'] = json.loads(row['events'])

        return jsonify({
            "message": "OK",
            "data": results
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'connection' in locals() and connection: connection.close()


# @transaksi_endpoints.route('/riwayat', methods=['GET'])
# @jwt_required()
# def get_riwayat_transaksi():
#     try:
#         identity = get_jwt_identity()
#         user_id = identity.get("id_user")

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         query = """
#         SELECT 
#             t.id_transaksi,
#             t.tanggal_transaksi,
#             t.total_harga_final,
#             t.metode_pembayaran,
#             t.status_pembayaran,
#             t.status_order,

#             -- Booking Ruangan
#             GROUP_CONCAT(DISTINCT CONCAT('Booking Ruangan - ', r.nama_ruangan, ' (', br.durasi, ' jam)') SEPARATOR ', ') AS booking_items,

#             -- Membership
#             GROUP_CONCAT(DISTINCT CONCAT('Paket Membership - ', pm.nama_paket) SEPARATOR ', ') AS membership_items,

#             -- Virtual Office
#             GROUP_CONCAT(DISTINCT CONCAT('Paket Virtual Office - ', pvo.nama_paket) SEPARATOR ', ') AS vo_items,

#             -- Event Space
#             GROUP_CONCAT(DISTINCT CONCAT('Booking Event Space - ', es.nama_event_space, ' (Kapasitas: ', es.kapasitas, ' orang)') SEPARATOR ', ') AS event_space_items

#         FROM transaksi t
#         LEFT JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
#         LEFT JOIN ruangan r ON br.id_ruangan = r.id_ruangan
#         LEFT JOIN memberships m ON t.id_transaksi = m.id_transaksi
#         LEFT JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
#         LEFT JOIN client_virtual_office vo ON t.id_transaksi = vo.id_transaksi
#         LEFT JOIN paket_virtual_office pvo ON vo.id_paket_vo = pvo.id_paket_vo
#         LEFT JOIN booking_event bes ON t.id_transaksi = bes.id_transaksi
#         LEFT JOIN event_spaces es ON bes.id_event_space = es.id_event_space
#         WHERE t.id_user = %s
#         GROUP BY t.id_transaksi
#         ORDER BY t.tanggal_transaksi DESC
#         """
#         cursor.execute(query, (user_id,))
#         results = cursor.fetchall()

#         return jsonify({
#             "message": "OK",
#             "data": results
#         }), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# @transaksi_endpoints.route('/riwayat', methods=['GET'])
# @jwt_required()
# def get_riwayat_transaksi():
#     try:
#         identity = get_jwt_identity()
#         user_id = identity.get("id_user")

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         query = """
#         SELECT 
#             t.id_transaksi,
#             t.tanggal_transaksi,
#             t.total_harga_final,
#             t.metode_pembayaran,
#             t.status_pembayaran,
#             t.status_order,

#             -- Booking
#             GROUP_CONCAT(DISTINCT CONCAT('Booking Ruangan - ', r.nama_ruangan, ' (', br.durasi, ' jam)') SEPARATOR ', ') AS booking_items,

#             -- Membership
#             GROUP_CONCAT(DISTINCT CONCAT('Paket Membership - ', pm.nama_paket) SEPARATOR ', ') AS membership_items,

#             -- Virtual Office
#             GROUP_CONCAT(DISTINCT CONCAT('Paket Virtual Office - ', pvo.nama_paket) SEPARATOR ', ') AS vo_items

#         FROM transaksi t
#         LEFT JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
#         LEFT JOIN ruangan r ON br.id_ruangan = r.id_ruangan
#         LEFT JOIN memberships m ON t.id_transaksi = m.id_transaksi
#         LEFT JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
#         LEFT JOIN client_virtual_office vo ON t.id_transaksi = vo.id_transaksi
#         LEFT JOIN paket_virtual_office pvo ON vo.id_paket_vo = pvo.id_paket_vo
#         WHERE t.id_user = %s
#         GROUP BY t.id_transaksi
#         ORDER BY t.tanggal_transaksi DESC
#         """

#         cursor.execute(query, (user_id,))
#         results = cursor.fetchall()

#         return jsonify({
#             "message": "OK",
#             "data": results
#         }), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


# HALAMAN TRANSAKSI PELANGGAN END

@transaksi_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_transaksi (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_transaksi": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@transaksi_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_transaksi SET title=%s, description=%s WHERE id_transaksi=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_transaksi": product_id}
    return jsonify(data), 200


@transaksi_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_transaksi WHERE id_transaksi = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_transaksi": product_id}
    return jsonify(data)


@transaksi_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@transaksi_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list transaksi"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_transaksi WHERE id_transaksi = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200