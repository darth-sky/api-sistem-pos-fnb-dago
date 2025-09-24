"""Routes for module kasir"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from flask import jsonify

kasir_endpoints = Blueprint('kasir', __name__)
UPLOAD_FOLDER = "img"


@kasir_endpoints.route('/productsKasir', methods=['GET'])
def get_products():
    """Ambil daftar produk F&B untuk POS"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            id_produk AS id,
            nama_produk AS name,
            harga AS price,
            status_ketersediaan AS status
        FROM produk_fnb
        ORDER BY nama_produk
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Format ke frontend-friendly
        products = [
            {
                "id": r["id"],
                "name": r["name"],
                "price": float(r["price"]),
                "available": True if r["status"] == "Active" else False
            }
            for r in rows
        ]

        return jsonify({"message": "OK", "datas": products}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# halaman transaksiKasir start

@kasir_endpoints.route('/readTransaksiKasir', methods=['GET'])
def readTransaksiKasir():
    """Ambil daftar semua transaksi kasir (F&B + Booking Ruangan)"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query untuk mendapatkan semua transaksi hari ini
        query = """
        SELECT 
            t.id_transaksi,
            COALESCE(u.nama, t.nama_guest) AS customer_name,
            t.lokasi_pemesanan,
            t.status_order,
            t.total_harga_final,
            t.tanggal_transaksi,
            t.metode_pembayaran,
            t.status_pembayaran,
            t.fnb_type,  -- tipe F&B

            -- Detail F&B
            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan,
            
            -- Detail Booking Ruangan
            b.id_booking,
            r.nama_ruangan,
            r.harga_per_jam,
            b.waktu_mulai,
            b.waktu_selesai,
            b.durasi,
            k.nama_kategori AS kategori_ruangan,
            
            -- Flag untuk jenis transaksi
            CASE 
                WHEN d.id_detail_order IS NOT NULL THEN 'fnb'
                WHEN b.id_booking IS NOT NULL THEN 'booking'
                ELSE 'other'
            END AS jenis_transaksi

        FROM transaksi t
        LEFT JOIN users u ON t.id_user = u.id_user
        LEFT JOIN detail_order_fnb d ON t.id_transaksi = d.id_transaksi
        LEFT JOIN produk_fnb p ON d.id_produk = p.id_produk
        LEFT JOIN booking_ruangan b ON t.id_transaksi = b.id_transaksi
        LEFT JOIN ruangan r ON b.id_ruangan = r.id_ruangan
        LEFT JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
        WHERE DATE(t.tanggal_transaksi) = CURDATE()
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        # Susun ulang hasil agar per-transaksi ada array items dan bookings
        data = {}
        for row in rows:
            trx_id = row["id_transaksi"]
            
            if trx_id not in data:
                # Tentukan type
                if row["jenis_transaksi"] == "fnb":
                    order_type = row["fnb_type"] or "Takeaway"  # default jika null
                elif row["jenis_transaksi"] == "booking":
                    order_type = "Booking"
                else:
                    order_type = "Other"

                data[trx_id] = {
                    "id": trx_id,
                    "customer": row["customer_name"],
                    "location": row["lokasi_pemesanan"],
                    "status": row["status_order"],
                    "payment_status": row["status_pembayaran"],
                    "payment_method": row["metode_pembayaran"],
                    "total": float(row["total_harga_final"]),
                    "time": row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                    "type": order_type,
                    "items": [],
                    "bookings": []
                }
            
            # Tambahkan item F&B jika ada
            if row["id_detail_order"]:
                data[trx_id]["items"].append({
                    "id_detail_order": row["id_detail_order"],
                    "product": row["nama_produk"],
                    "qty": row["jumlah"],
                    "price": float(row["harga_saat_order"]),
                    "note": row["catatan_pesanan"],
                    "fnb_type": row["fnb_type"]  # simpan di item juga opsional
                })
            
            # Tambahkan booking ruangan jika ada
            if row["id_booking"]:
                booking_data = {
                    "id_booking": row["id_booking"],
                    "room_name": row["nama_ruangan"],
                    "room_category": row["kategori_ruangan"],
                    "price_per_hour": float(row["harga_per_jam"]),
                    "start_time": row["waktu_mulai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_mulai"] else None,
                    "end_time": row["waktu_selesai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_selesai"] else None,
                    "duration": row["durasi"]
                }
                # Cek duplikat booking
                if not any(b["id_booking"] == booking_data["id_booking"] for b in data[trx_id]["bookings"]):
                    data[trx_id]["bookings"].append(booking_data)

        return jsonify({
            "message": "OK",
            "datas": list(data.values())
        }), 200


    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
@kasir_endpoints.route('/readTransaksiKasirs', methods=['GET'])
def readTransaksiKasirs():
    """Ambil daftar transaksi kasir hanya untuk F&B dan Booking Ruangan"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            t.id_transaksi,
            COALESCE(u.nama, t.nama_guest) AS customer_name,
            t.lokasi_pemesanan,
            t.status_order,
            t.total_harga_final,
            t.tanggal_transaksi,
            t.metode_pembayaran,
            t.status_pembayaran,
            t.fnb_type,

            -- Detail F&B
            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan,
            
            -- Detail Booking Ruangan
            b.id_booking,
            r.nama_ruangan,
            r.harga_per_jam,
            b.waktu_mulai,
            b.waktu_selesai,
            b.durasi,
            k.nama_kategori AS kategori_ruangan,
            
            CASE 
                WHEN d.id_detail_order IS NOT NULL THEN 'fnb'
                WHEN b.id_booking IS NOT NULL THEN 'booking'
                ELSE 'other'
            END AS jenis_transaksi

        FROM transaksi t
        LEFT JOIN users u ON t.id_user = u.id_user
        LEFT JOIN detail_order_fnb d ON t.id_transaksi = d.id_transaksi
        LEFT JOIN produk_fnb p ON d.id_produk = p.id_produk
        LEFT JOIN booking_ruangan b ON t.id_transaksi = b.id_transaksi
        LEFT JOIN ruangan r ON b.id_ruangan = r.id_ruangan
        LEFT JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
        WHERE DATE(t.tanggal_transaksi) = CURDATE()
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        data = {}
        for row in rows:
            trx_id = row["id_transaksi"]

            # ❌ skip transaksi "other"
            if row["jenis_transaksi"] not in ("fnb", "booking"):
                continue
            
            if trx_id not in data:
                if row["jenis_transaksi"] == "fnb":
                    order_type = row["fnb_type"] or "Takeout"
                elif row["jenis_transaksi"] == "booking":
                    order_type = "Booking"
                else:
                    continue

                data[trx_id] = {
                    "id": trx_id,
                    "customer": row["customer_name"],
                    "location": row["lokasi_pemesanan"],
                    "status": row["status_order"],
                    "payment_status": row["status_pembayaran"],
                    "payment_method": row["metode_pembayaran"],
                    "total": float(row["total_harga_final"]),
                    "time": row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                    "type": order_type,
                    "items": [],
                    "bookings": []
                }

            # Tambahkan item F&B
            if row["id_detail_order"]:
                data[trx_id]["items"].append({
                    "id_detail_order": row["id_detail_order"],
                    "product": row["nama_produk"],
                    "qty": row["jumlah"],
                    "price": float(row["harga_saat_order"]),
                    "note": row["catatan_pesanan"],
                    "fnb_type": row["fnb_type"]
                })
            
            # Tambahkan booking
            if row["id_booking"]:
                booking_data = {
                    "id_booking": row["id_booking"],
                    "room_name": row["nama_ruangan"],
                    "room_category": row["kategori_ruangan"],
                    "price_per_hour": float(row["harga_per_jam"]),
                    "start_time": row["waktu_mulai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_mulai"] else None,
                    "end_time": row["waktu_selesai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_selesai"] else None,
                    "duration": row["durasi"]
                }
                if not any(b["id_booking"] == booking_data["id_booking"] for b in data[trx_id]["bookings"]):
                    data[trx_id]["bookings"].append(booking_data)

        return jsonify({
            "message": "OK",
            "datas": list(data.values())
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# halaman transaksiKasir end


# halaman merchantkasir start

@kasir_endpoints.route('/merchantOrders', methods=['GET'])
def readMerchantOrders():
    """Ambil daftar order khusus F&B (merchant kasir)"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT 
            t.id_transaksi,
            COALESCE(u.nama, t.nama_guest) AS customer_name,
            t.status_order,
            t.status_pembayaran,
            t.metode_pembayaran,
            t.total_harga_final,
            t.tanggal_transaksi,

            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan
        FROM transaksi t
        LEFT JOIN users u ON t.id_user = u.id_user
        INNER JOIN detail_order_fnb d ON t.id_transaksi = d.id_transaksi   -- ✅ hanya ambil yg ada detail F&B
        LEFT JOIN produk_fnb p ON d.id_produk = p.id_produk
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        data = {}
        for row in rows:
            trx_id = row["id_transaksi"]

            if trx_id not in data:
                data[trx_id] = {
                    "id": trx_id,
                    "name": row["customer_name"],
                    "code": f"INV-{trx_id:05d}",
                    "status": (
                        "Waiting" if row["status_order"] == "Baru"
                        else "In Progress" if row["status_order"] == "Diproses"
                        else "Finish" if row["status_order"] == "Selesai"
                        else "Canceled"
                    ),
                    "type": "FNB",
                    "payment_status": row["status_pembayaran"],
                    "payment_method": row["metode_pembayaran"],
                    "total": float(row["total_harga_final"]),
                    "time": row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                    "items": []
                }

            # isi items
            data[trx_id]["items"].append({
                "id": row["id_detail_order"],
                "name": row["nama_produk"],
                "qty": row["jumlah"],
                "price": float(row["harga_saat_order"]),
                "note": row["catatan_pesanan"]
            })

        return jsonify({
            "message": "OK",
            "datas": list(data.values())
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()





# halaman merchantkasir end

@kasir_endpoints.route('/readKasir', methods=['GET'])
@jwt_required()
def readKasir_transaksi():
    """Endpoint untuk membaca daftar transaksi yang sedang berjalan atau terbaru."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Query ini mengambil data transaksi dan menggabungkannya dengan nama pelanggan (baik dari tabel users maupun guest)
        query = """
            SELECT 
                t.id_transaksi, 
                t.status_pembayaran,
                t.status_order, 
                t.total_harga_final, 
                t.lokasi_pemesanan, 
                COALESCE(u.nama, t.nama_guest) AS nama_pelanggan, 
                t.tanggal_transaksi
            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            WHERE t.status_order NOT IN ('Selesai', 'Batal')
            ORDER BY t.tanggal_transaksi DESC;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@kasir_endpoints.route('/createKasir', methods=['POST'])
@jwt_required()
def createKasir_transaksi():
    """Endpoint untuk membuat transaksi baru dari kasir."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        
        # Validasi data input sederhana
        customer_name = data.get('name')
        lokasi = data.get('room')

        if not customer_name:
            return jsonify({"message": "Nama pelanggan tidak boleh kosong"}), 400

        query = """
            INSERT INTO transaksi 
                (nama_guest, lokasi_pemesanan, total_harga_final, status_pembayaran, status_order) 
            VALUES (%s, %s, 0, 'Belum Lunas', 'Baru');
        """
        cursor.execute(query, (customer_name, lokasi))
        conn.commit()
        
        return jsonify({
            "message": "Order baru berhasil dibuat", 
            "id_transaksi": cursor.lastrowid
        }), 201 # 201 Created
    except Exception as e:
        conn.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@kasir_endpoints.route('/read', methods=['GET'])
def read():
    """Routes for module get list kasir"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        select_query = "SELECT * FROM order_fdanb"
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

@kasir_endpoints.route('/transaksi', methods=['GET'])
def get_all_transaksi():
    """Endpoint untuk mendapatkan daftar transaksi yang sudah diformat."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query ini telah diperbaiki sesuai skema database final kita
        query = """
            SELECT
                t.id_transaksi AS id,
                COALESCE(u.nama, t.nama_guest) AS name,
                t.lokasi_pemesanan AS type,
                CASE
                    WHEN t.status_pembayaran = 'Lunas' THEN 'SUCCESS'
                    ELSE 'WAITING'
                END AS status,
                t.total_harga_final AS price,
                (SELECT GROUP_CONCAT(p.nama_produk SEPARATOR ', ')
                    FROM detail_order_fnb do
                    JOIN produk_fnb p ON do.id_produk = p.id_produk
                    WHERE do.id_transaksi = t.id_transaksi
                ) AS product
            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            ORDER BY t.tanggal_transaksi DESC;
        """

        cursor.execute(query)
        results = cursor.fetchall()
        
        # Mengganti nilai None pada product menjadi string kosong agar tidak error di frontend
        for row in results:
            if row['product'] is None:
                row['product'] = '-'

        return jsonify({"message": "OK", "datas": results}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@kasir_endpoints.route('/transaksi', methods=['POST'])
def create_transaksi():
    """Endpoint untuk membuat transaksi baru dari kasir."""
    data = request.get_json()
    customer_name = data.get('customerName')
    order_type = data.get('orderType')
    # room = data.get('room') # Anda bisa gunakan ini jika perlu disimpan

    if not order_type:
        return jsonify({"message": "ERROR", "error": "Order type is required"}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Buat transaksi baru dengan data minimal
        query = """
            INSERT INTO transaksi 
            (nama_guest, lokasi_pemesanan, total_harga_final, status_pembayaran, status_order)
            VALUES (%s, %s, %s, %s, %s)
        """
        # Harga awal 0, status belum lunas & baru
        values = (customer_name, order_type, 0, 'Belum Lunas', 'Baru')
        
        cursor.execute(query, values)
        new_transaksi_id = cursor.lastrowid
        connection.commit()

        return jsonify({
            "message": "Transaksi baru berhasil dibuat", 
            "id_transaksi": new_transaksi_id
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


@kasir_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_kasir (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_kasir": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@kasir_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_kasir SET title=%s, description=%s WHERE id_kasir=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_kasir": product_id}
    return jsonify(data), 200


@kasir_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_kasir WHERE id_kasir = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_kasir": product_id}
    return jsonify(data)


@kasir_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@kasir_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list kasir"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_kasir WHERE id_kasir = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200