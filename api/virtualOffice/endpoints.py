"""Routes for module virtualOffice"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
import traceback

virtualOffice_endpoints = Blueprint('virtualOffice', __name__)
UPLOAD_FOLDER = "img"


@virtualOffice_endpoints.route('/read', methods=['GET'])
@jwt_required()
def read():
    """Routes for module get list virtualOffice"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT * FROM tb_virtualOffice"
    cursor.execute(select_query)
    results = cursor.fetchall()
    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200


# halaman virtual office yang berisi paket paket vo start

@virtualOffice_endpoints.route('/paket_vo', methods=['GET'])
def get_paket_vo():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT id_paket_vo, nama_paket, harga, durasi, 
               benefit_jam_meeting_room_per_bulan, 
               benefit_jam_working_space_per_bulan, 
               deskripsi_layanan
        FROM paket_virtual_office
        """
        cursor.execute(query)
        result = cursor.fetchall()

        return jsonify({"message": "OK", "datas": result}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# halaman virutal office yang berisi paket paket vo end


# halaman cekmasavo start

@virtualOffice_endpoints.route('/cekMasaVO/<int:id_user>', methods=['GET'])
def get_vo_detail(id_user):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            cvo.id_client_vo,
            cvo.tanggal_mulai,
            cvo.tanggal_berakhir,
            cvo.status_client_vo,
            pvo.nama_paket,
            pvo.harga,
            pvo.durasi
        FROM client_virtual_office cvo
        JOIN paket_virtual_office pvo ON cvo.id_paket_vo = pvo.id_paket_vo
        WHERE cvo.id_user = %s
        ORDER BY cvo.tanggal_mulai DESC
        LIMIT 1
        """
        cursor.execute(query, (id_user,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"message": "Not Found"}), 404

        return jsonify({"message": "OK", "data": result})

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# halaman cekmasavo end

@virtualOffice_endpoints.route('/register', methods=['POST'])
def register_virtual_office():
    """
    Proses pendaftaran Virtual Office:
    1. Buat transaksi pembelian paket VO
    2. Simpan detail klien di client_virtual_office
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        print("DEBUG DATA VO:", data)
        
        id_user = data.get("id_user")  # bisa NULL kalau guest
        id_paket_vo = data.get("id_paket_vo")

        # Data tambahan
        nama = data.get("nama")
        jabatan = data.get("jabatan")
        nama_perusahaan_klien = data.get("nama_perusahaan_klien")
        bidang_perusahaan = data.get("bidang_perusahaan")
        alamat_perusahaan = data.get("alamat_perusahaan")
        email_perusahaan = data.get("email_perusahaan")
        alamat_domisili = data.get("alamat_domisili")
        nomor_telepon = data.get("nomor_telepon")

        if not id_paket_vo or not nama_perusahaan_klien:
            return jsonify({"message": "ID paket dan nama perusahaan wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 🔹 Ambil detail paket virtual office
        cursor.execute("""
            SELECT harga, durasi 
            FROM paket_virtual_office 
            WHERE id_paket_vo = %s
        """, (id_paket_vo,))
        paket = cursor.fetchone()

        if not paket:
            return jsonify({"message": "Paket Virtual Office tidak ditemukan"}), 404

        # 🔹 Insert transaksi
        insert_transaksi = """
        INSERT INTO transaksi (id_user, tanggal_transaksi, total_harga_final, 
                               metode_pembayaran, status_pembayaran, status_order)
        VALUES (%s, NOW(), %s, %s, %s, %s)
        """
        cursor.execute(insert_transaksi, (
            id_user, paket["harga"], "Non-Tunai", "Lunas", "Baru",
        ))
        id_transaksi = cursor.lastrowid

        # 🔹 Hitung tanggal mulai & berakhir
        cursor.execute("SELECT CURDATE() as today")
        today = cursor.fetchone()["today"]
        cursor.execute("SELECT DATE_ADD(CURDATE(), INTERVAL %s DAY) as end_date", (paket["durasi"],))
        end_date = cursor.fetchone()["end_date"]

        # 🔹 Insert ke client_virtual_office
        insert_vo = """
        INSERT INTO client_virtual_office (
            id_user, id_paket_vo, id_transaksi,
            nama, jabatan, nama_perusahaan_klien, bidang_perusahaan,
            alamat_perusahaan, email_perusahaan, alamat_domisili, nomor_telepon,
            tanggal_mulai, tanggal_berakhir, status_client_vo
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Aktif')
        """
        cursor.execute(insert_vo, (
            id_user, id_paket_vo, id_transaksi,
            nama, jabatan, nama_perusahaan_klien, bidang_perusahaan,
            alamat_perusahaan, email_perusahaan, alamat_domisili, nomor_telepon,
            today, end_date
        ))

        connection.commit()
        return jsonify({
            "message": "OK",
            "id_transaksi": id_transaksi
        }), 201

    except Exception as e:
        if connection:
            connection.rollback()
            print("ERROR REGISTER VO:", str(e))
            traceback.print_exc()  # tampilkan error detail di terminal
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@virtualOffice_endpoints.route('/readDetailPaketVirtualOffice/<int:id>', methods=['GET'])
def readDetailPaketVirtualOffice(id):
    """Routes for module get detail paket virtual office by ID"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = """
        SELECT 
            id_paket_vo,
            nama_paket,
            harga,
            durasi,
            benefit_jam_meeting_room_per_bulan,
            benefit_jam_working_space_per_bulan
        FROM paket_virtual_office
        WHERE id_paket_vo = %s
        """
        cursor.execute(select_query, (id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"message": "NOT FOUND"}), 404
        return jsonify({"message": "OK", "data": result}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@virtualOffice_endpoints.route('/readPaketVirtualOffice', methods=['GET'])
def readPaketVirtualOffice():
    """Routes for module get list paket virtual office"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = """
        SELECT 
            id_paket_vo,
            nama_paket,
            harga,
            durasi,
            benefit_jam_meeting_room_per_bulan,
            benefit_jam_working_space_per_bulan
        FROM paket_virtual_office
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



@virtualOffice_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_virtualOffice (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_virtualOffice": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@virtualOffice_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_virtualOffice SET title=%s, description=%s WHERE id_virtualOffice=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_virtualOffice": product_id}
    return jsonify(data), 200


@virtualOffice_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_virtualOffice WHERE id_virtualOffice = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_virtualOffice": product_id}
    return jsonify(data)


@virtualOffice_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@virtualOffice_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list virtualOffice"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_virtualOffice WHERE id_virtualOffice = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200

@virtualOffice_endpoints.route('/daftar-vo', methods=['POST'])
def daftar_vo():
    connection = None
    cursor = None
    try:
        data = request.json
        print("📥 Data diterima:", data)  # debug

        connection = get_connection()
        cursor = connection.cursor()

        insert_query = """
        INSERT INTO virtual_office (
            id_user, id_paket_vo, nama_perusahaan, bidang_usaha,
            alamat_perusahaan, email_perusahaan, jabatan,
            alamat_domisili, nomor_telepon,
            metode_pembayaran, tanggal_mulai, tanggal_selesai
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (
            data.get("id_user"),          # foreign key ke tabel users
            data.get("id_paket_vo"),      # foreign key ke tabel paket
            data.get("nama_perusahaan"),
            data.get("bidang_usaha"),
            data.get("alamat_perusahaan"),
            data.get("email_perusahaan"),
            data.get("jabatan"),
            data.get("alamat_domisili"),
            data.get("nomor_telepon"),
            data.get("metode_pembayaran"),
            data.get("tanggal_mulai"),
            data.get("tanggal_selesai"),
        )

        cursor.execute(insert_query, values)
        connection.commit()

        return jsonify({"message": "Pendaftaran berhasil"}), 201

    except Exception as e:
        print("❌ ERROR:", str(e))
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# Cek VO
@virtualOffice_endpoints.route("/cek-vo/<int:id_user>", methods=["GET"])
def cek_vo(id_user):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT v.*, p.nama_paket, p.harga, p.durasi
            FROM vo_subscriptions v
            JOIN paket_vo p ON v.id_paket_vo = p.id_paket_vo
            WHERE v.id_user = %s
            ORDER BY v.id DESC LIMIT 1
        """, (id_user,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"data": {"status": "notfound"}}), 200

        # Tentukan status aktif/expired
        today = datetime.date.today()
        tanggal_selesai = result["tanggal_selesai"]
        status = "aktif" if tanggal_selesai >= today else "expired"

        response = {
            "status": status,
            "paket": result["nama_paket"],
            "harga": result["harga"],
            "tanggalMulai": str(result["tanggal_mulai"]),
            "tanggalBerakhir": str(result["tanggal_selesai"]),
            "benefits": [
                {"nama": "Alamat bisnis untuk legalitas usaha", "included": True, "used": True},
                {"nama": "Penerimaan surat & paket", "included": True, "used": True},
                {"nama": "Free meeting room", "included": True, "quota": 4, "used": 1, "unit": "jam/bulan"},
                {"nama": "Free working space", "included": True, "quota": 8, "used": 3, "unit": "jam/bulan"},
                {"nama": "Nama/logo perusahaan di website", "included": True, "used": True},
                {"nama": "Free wifi member", "included": True, "used": True},
            ],
            "riwayatPenggunaan": [
                {"id": 1, "tanggal": "2025-09-10", "aktivitas": "Menggunakan meeting room", "durasi": "2 jam", "type": "meeting"},
                {"id": 2, "tanggal": "2025-09-11", "aktivitas": "Menerima paket", "type": "mail"}
            ]
        }

        return jsonify({"data": response}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()