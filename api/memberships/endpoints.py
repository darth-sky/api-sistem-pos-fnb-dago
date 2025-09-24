"""Routes for module memberships"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required, get_jwt_identity
from helper.year_operation import diff_year
from helper.year_operation import check_age_book


memberships_endpoints = Blueprint('memberships', __name__)
UPLOAD_FOLDER = "img"


@memberships_endpoints.route('/read', methods=['GET'])
@jwt_required()
def read():
    """Routes for module get list memberships"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT * FROM tb_memberships"
    cursor.execute(select_query)
    results = cursor.fetchall()
    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200

@memberships_endpoints.route('/paket_detail/<int:id>', methods=['GET'])
def get_membership_detail(id):
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
            kr.nama_kategori
        FROM paket_membership pm
        JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = pm.id_kategori_ruangan
        WHERE pm.id_paket_membership = %s
        """
        cursor.execute(query, (id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"message": "Not Found"}), 404

        return jsonify({"message": "OK", "datas": [result]})
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

# membership_endpoints.py
@memberships_endpoints.route('/readMembershipsById/<int:id_user>', methods=['GET'])
def get_membership_by_user(id_user):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT m.*, p.nama_paket, p.durasi, p.kuota, p.harga
        FROM memberships m
        JOIN paket_membership p ON m.id_paket_membership = p.id_paket_membership
        WHERE m.id_user = %s AND m.status_memberships = 'Active'
        LIMIT 1
        """
        cursor.execute(query, (id_user,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"message": "Membership not found"}), 404

        return jsonify({"message": "OK", "data": result})

    except Exception as e:
        print(e)
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@memberships_endpoints.route('/readMemberships', methods=['GET'])
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
            
# @memberships_endpoints.route('/readMembershipsById/<int:id>', methods=['GET'])
# def get_membership_detail(id):
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         query = """
#         SELECT 
#             pm.id_paket_membership,
#             pm.nama_paket,
#             pm.harga,
#             pm.durasi,
#             pm.kuota,
#             pm.deskripsi_benefit,
#             kr.nama_kategori
#         FROM paket_membership pm
#         JOIN kategori_ruangan kr 
#             ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
#         WHERE pm.id_paket_membership = %s
#         """
#         cursor.execute(query, (id,))
#         result = cursor.fetchone()

#         if not result:
#             return jsonify({"message": "Not Found"}), 404

#         return jsonify({"message": "OK", "data": result}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# File: memberships_endpoints.py

@memberships_endpoints.route('/getMembershipDetail/<int:user_id>', methods=['GET'])
def getMembershipDetail(user_id):
    """Ambil detail membership user yang sedang aktif"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Query untuk mendapatkan data membership aktif user
        query = """
        SELECT 
            m.id_memberships,
            m.tanggal_mulai,
            m.tanggal_berakhir,
            m.total_credit,
            m.sisa_credit,
            m.status_memberships,
            pm.nama_paket,
            pm.harga,
            pm.durasi,
            pm.kuota,
            kr.nama_kategori,
            u.nama as nama_user
        FROM memberships m
        JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
        JOIN kategori_ruangan kr ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
        JOIN users u ON m.id_user = u.id_user
        WHERE m.id_user = %s AND m.status_memberships = 'Active'
        ORDER BY m.tanggal_mulai DESC
        LIMIT 1
        """
        
        cursor.execute(query, (user_id,))
        membership_data = cursor.fetchone()
        
        if not membership_data:
            return jsonify({"message": "No active membership found", "datas": None}), 404
        
        return jsonify({"message": "OK", "datas": membership_data}), 200
        
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@memberships_endpoints.route('/readMembershipsByUser', methods=['GET'])
@jwt_required()
def read_memberships_by_users():
    """Ambil membership user berdasarkan token"""
    connection = None
    cursor = None
    try:
        identity = get_jwt_identity()
        id_user = identity.get('id_user')

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            m.id_memberships,
            m.id_user,
            m.id_paket_membership,
            m.id_transaksi,
            m.tanggal_mulai,
            m.tanggal_berakhir,
            m.total_credit,
            m.sisa_credit,
            m.status_memberships,
            pm.nama_paket,
            pm.harga,
            pm.durasi,
            pm.kuota,
            pm.deskripsi_benefit,
            kr.id_kategori_ruangan,
            kr.nama_kategori
        FROM memberships m
        JOIN paket_membership pm 
            ON m.id_paket_membership = pm.id_paket_membership
        JOIN kategori_ruangan kr 
            ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
        WHERE m.id_user = %s
        """
        cursor.execute(query, (id_user,))
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print("Error:", e)
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()





@memberships_endpoints.route('/getMembershipHistory/<int:user_id>', methods=['GET'])
def getMembershipHistory(user_id):
    """Ambil riwayat penggunaan kredit membership user"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Query untuk mendapatkan riwayat booking yang menggunakan kredit
        query = """
        SELECT 
            br.waktu_mulai,
            br.waktu_selesai,
            br.durasi,
            br.kredit_terpakai,
            r.nama_ruangan,
            kr.nama_kategori,
            DATE_FORMAT(br.waktu_mulai, '%d %M %Y') as tanggal_formatted
        FROM booking_ruangan br
        JOIN ruangan r ON br.id_ruangan = r.id_ruangan
        JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
        JOIN memberships m ON br.id_memberships = m.id_memberships
        WHERE m.id_user = %s 
        AND br.kredit_terpakai > 0
        ORDER BY br.waktu_mulai DESC
        LIMIT 10
        """
        
        cursor.execute(query, (user_id,))
        history_data = cursor.fetchall()
        
        # Format data untuk frontend
        formatted_history = []
        for item in history_data:
            formatted_history.append({
                "tanggal": item['tanggal_formatted'],
                "deskripsi": f"Menggunakan {item['durasi']} menit {item['nama_ruangan']} ({item['nama_kategori']})",
                "kredit_terpakai": item['kredit_terpakai'],
                "waktu_mulai": item['waktu_mulai'].strftime('%H:%M'),
                "waktu_selesai": item['waktu_selesai'].strftime('%H:%M')
            })
        
        return jsonify({"message": "OK", "datas": formatted_history}), 200
        
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
            
@memberships_endpoints.route('/readMembershipsByUser/<int:user_id>', methods=['GET'])
@jwt_required()
def read_memberships_by_user(user_id):
    """Ambil info membership + riwayat penggunaan untuk user tertentu"""
    identity = get_jwt_identity()
    if identity['id_user'] != user_id:
        return jsonify({"msg": "Unauthorized"}), 401

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Data membership
        cursor.execute("""
            SELECT pm.id_paket_membership, pm.nama_paket, pm.harga, pm.durasi, pm.kuota, pm.deskripsi_benefit, kr.nama_kategori,
                   m.tanggal_mulai, m.tanggal_akhir, m.credits_used
            FROM memberships m
            JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership
            JOIN kategori_ruangan kr ON pm.id_kategori_ruangan = kr.id_kategori_ruangan
            WHERE m.id_user = %s
        """, (user_id,))
        membership = cursor.fetchone()

        # Riwayat penggunaan
        cursor.execute("""
            SELECT tanggal, deskripsi
            FROM riwayat_penggunaan
            WHERE id_user = %s
            ORDER BY tanggal DESC
        """, (user_id,))
        riwayat = cursor.fetchall()

        return jsonify({
            "membership": membership,
            "riwayat": riwayat
        }), 200

    except Exception as e:
        return jsonify({"msg": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()






@memberships_endpoints.route('/register', methods=['POST'])
def register_membership():
    """
    Proses pendaftaran membership:
    1. Buat transaksi pembelian paket
    2. Buat membership aktif
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        print("DEBUG DATA:", data)
        id_user = data.get("id_user")  # bisa NULL kalau guest
        phone = data.get("no_hp")
        id_paket = data.get("id_paket_membership")

        if not id_paket:
            return jsonify({"message": "ID paket membership wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # ambil detail paket membership
        cursor.execute("""
            SELECT harga, durasi, kuota 
            FROM paket_membership 
            WHERE id_paket_membership = %s
        """, (id_paket,))
        paket = cursor.fetchone()

        if not paket:
            return jsonify({"message": "Paket membership tidak ditemukan"}), 404

        # 1. Insert transaksi
        insert_transaksi = """
        INSERT INTO transaksi (id_user, tanggal_transaksi, total_harga_final, 
                               metode_pembayaran, status_pembayaran, status_order)
        VALUES (%s, NOW(), %s, %s, %s, %s)
        """
        cursor.execute(insert_transaksi, (
            id_user, paket["harga"], "Non-Tunai", "Lunas", "Baru",
        ))
        id_transaksi = cursor.lastrowid

        # 2. Hitung tanggal mulai & berakhir
        cursor.execute("SELECT CURDATE() as today")
        today = cursor.fetchone()["today"]
        cursor.execute("SELECT DATE_ADD(CURDATE(), INTERVAL %s DAY) as end_date", (paket["durasi"],))
        end_date = cursor.fetchone()["end_date"]

        # 3. Insert membership
        insert_membership = """
        INSERT INTO memberships (id_user, id_paket_membership, id_transaksi,
                                 tanggal_mulai, tanggal_berakhir,
                                 total_credit, sisa_credit, status_memberships)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
        """
        cursor.execute(insert_membership, (
            id_user, id_paket, id_transaksi, today, end_date,
            paket["kuota"], paket["kuota"]
        ))

        connection.commit()
        return jsonify({
            "message": "OK",
            "id_transaksi": id_transaksi
        }), 201

    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@memberships_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_memberships (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_memberships": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@memberships_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_memberships SET title=%s, description=%s WHERE id_memberships=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_memberships": product_id}
    return jsonify(data), 200


@memberships_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_memberships WHERE id_memberships = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_memberships": product_id}
    return jsonify(data)


@memberships_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@memberships_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list memberships"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_memberships WHERE id_memberships = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200