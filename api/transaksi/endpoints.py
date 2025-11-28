"""Routes for module transaksi"""
import decimal
import json
import os
from flask import Blueprint, jsonify, request
from api.utils.ipaymu_helper import create_ipaymu_payment
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

        # QUERY LENGKAP (JANGAN DISINGKAT)
        query = """
        SELECT 
            t.id_transaksi,
            t.tanggal_transaksi,
            t.total_harga_final,
            t.metode_pembayaran,
            t.status_pembayaran,
            t.status_order,
            
            -- 1. Booking Ruangan (Dengan gambar_ruangan)
            (SELECT CONCAT('[', 
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_ruangan', r.nama_ruangan,
                        'gambar_ruangan', r.gambar_ruangan,
                        'waktu_mulai', br.waktu_mulai,
                        'waktu_selesai', br.waktu_selesai,
                        'durasi', br.durasi
                    )
                ), 
            ']')
            FROM booking_ruangan br 
            JOIN ruangan r ON br.id_ruangan = r.id_ruangan 
            WHERE br.id_transaksi = t.id_transaksi) AS bookings,

            -- 2. Memberships (WAJIB ADA agar tidak error KeyError)
            (SELECT CONCAT('[', 
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_paket', pm.nama_paket,
                        'tanggal_mulai', m.tanggal_mulai,
                        'tanggal_berakhir', m.tanggal_berakhir
                    )
                ), 
            ']')
            FROM memberships m 
            JOIN paket_membership pm ON m.id_paket_membership = pm.id_paket_membership 
            WHERE m.id_transaksi = t.id_transaksi) AS memberships,
            
            -- 3. Virtual Offices (WAJIB ADA)
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
            FROM client_virtual_office vo 
            JOIN paket_virtual_office pvo ON vo.id_paket_vo = pvo.id_paket_vo 
            WHERE vo.id_transaksi = t.id_transaksi) AS virtual_offices,

            -- 4. Events (Dengan gambar_ruangan jika ada di tabel event_spaces)
            (SELECT CONCAT('[',
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'nama_event', bes.nama_acara,
                        'nama_space', es.nama_event_space,
                        'gambar_ruangan', es.gambar_ruangan, 
                        'tanggal_event', bes.tanggal_event,
                        'waktu_mulai', bes.waktu_mulai,
                        'waktu_selesai', bes.waktu_selesai
                    )
                ),
            ']')
            FROM booking_event bes 
            JOIN event_spaces es ON bes.id_event_space = es.id_event_space 
            WHERE bes.id_transaksi = t.id_transaksi) AS events
        
        FROM transaksi t
        WHERE t.id_user = %s
        GROUP BY t.id_transaksi
        ORDER BY t.tanggal_transaksi DESC
        """
        
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        
        # Parsing JSON string dari database ke objek Python
        import json
        for row in results:
            if row['bookings']: 
                try: row['bookings'] = json.loads(row['bookings'])
                except: row['bookings'] = []
            
            if row['memberships']: 
                try: row['memberships'] = json.loads(row['memberships'])
                except: row['memberships'] = []
                
            if row['virtual_offices']: 
                try: row['virtual_offices'] = json.loads(row['virtual_offices'])
                except: row['virtual_offices'] = []
                
            if row['events']: 
                try: row['events'] = json.loads(row['events'])
                except: row['events'] = []

        return jsonify({
            "message": "OK",
            "data": results
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc() # Print error lengkap ke terminal backend
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


# @transaksi_endpoints.route('/create', methods=['POST'])
# @jwt_required() # Pastikan endpoint ini terlindungi
# def create_fnb_order_with_tax():
#     """
#     Routes for creating a new F&B order including tax calculation.
#     Expects JSON data in the request body.
#     """
#     connection = None
#     cursor = None
#     try:
#         # 1. Dapatkan data JSON dari request
#         data = request.json
#         if not data:
#             return jsonify({"message": "ERROR", "error": "Request body must be JSON."}), 400

#         # Ambil data yang diperlukan dari JSON
#         detail_order = data.get('detail_order')
#         fnb_type = data.get('fnb_type')
#         nama_guest = data.get('nama_guest')
#         lokasi_pemesanan = data.get('lokasi_pemesanan') # Bisa None untuk Takeaway
#         metode_pembayaran = data.get('metode_pembayaran')
#         # id_user = get_jwt_identity() # Jika Anda ingin mengambil ID user dari token JWT

#         # Validasi data dasar
#         if not detail_order or not fnb_type or not nama_guest or not metode_pembayaran:
#             return jsonify({"message": "ERROR", "error": "Missing required fields (detail_order, fnb_type, nama_guest, metode_pembayaran)."}), 400

#         # --- PERHITUNGAN PAJAK ---

#         # 2. Hitung Subtotal (hanya dari item F&B)
#         subtotal = decimal.Decimal(0.00)
#         for item in detail_order:
#             try:
#                 # Validasi dan konversi tipe data
#                 harga = decimal.Decimal(item['harga_saat_order'])
#                 jumlah = int(item['jumlah'])
#                 if jumlah <= 0: # Abaikan item dengan jumlah 0 atau negatif
#                     continue
#                 subtotal += harga * jumlah
#             except (KeyError, ValueError, TypeError) as e:
#                 return jsonify({"message": "ERROR", "error": f"Invalid data in detail_order: {str(e)}"}), 400

#         # Jika subtotal 0 (misalnya semua item 0 jumlahnya), mungkin batalkan
#         if subtotal <= 0:
#              return jsonify({"message": "ERROR", "error": "Order cannot be empty or have zero total."}), 400

#         # 3. Ambil Persentase Pajak dari DB
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True) # Gunakan dictionary=True agar hasil seperti objek
#         cursor.execute("SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
#         setting_pajak = cursor.fetchone()

#         pajak_persen = decimal.Decimal(10.00)  # Default fallback 10%
#         if setting_pajak and setting_pajak['value']:
#             try:
#                 pajak_persen = decimal.Decimal(setting_pajak['value'])
#             except decimal.InvalidOperation:
#                 # Log error jika nilai di DB tidak valid, tapi tetap pakai default
#                 print(f"Warning: Invalid tax percentage '{setting_pajak['value']}' in settings table. Using default 10%.")


#         # 4. Hitung Pajak Nominal dan Total Final
#         # Gunakan pembulatan standar (half-up) untuk 2 desimal
#         pajak_nominal = (subtotal * (pajak_persen / decimal.Decimal(100))).quantize(decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP)
#         total_harga_final = subtotal + pajak_nominal

#         # --- AKHIR PERHITUNGAN PAJAK ---

#         # 5. Simpan ke tabel 'transaksi'
#         insert_transaksi_query = """
#             INSERT INTO transaksi (
#                  fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran,
#                 subtotal, pajak_persen, pajak_nominal, total_harga_final,
#                 status_pembayaran, status_order, tanggal_transaksi
#                 -- Tambahkan id_user jika perlu: , id_user
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
#                 -- Tambahkan %s lagi jika ada id_user: , %s
#         """
#         transaksi_values = (
#             fnb_type,
#             nama_guest,
#             lokasi_pemesanan if fnb_type == 'Dine In' else None, # Pastikan lokasi null jika takeaway
#             metode_pembayaran,
#             subtotal,
#             pajak_persen,
#             pajak_nominal,
#             total_harga_final,
#             'Pending', # Status pembayaran awal
#             'Pending'  # Status order awal
#             # id_user # tambahkan jika perlu
#         )
#         cursor.execute(insert_transaksi_query, transaksi_values)
#         id_transaksi_baru = cursor.lastrowid # Dapatkan ID transaksi yang baru saja dibuat

#         # 6. Simpan detail order ke 'detail_order_fnb'
#         insert_detail_query = """
#             INSERT INTO detail_order_fnb (
#                 id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan, status_item
#             ) VALUES (%s, %s, %s, %s, %s, %s)
#         """
#         detail_values_list = []
#         for item in detail_order:
#              if int(item['jumlah']) > 0: # Hanya simpan item yang jumlahnya > 0
#                 detail_values_list.append((
#                     id_transaksi_baru,
#                     item['id_produk'],
#                     int(item['jumlah']),
#                     decimal.Decimal(item['harga_saat_order']),
#                     item.get('catatan_pesanan'), # Gunakan .get() untuk handle jika key tidak ada
#                     'Pending' # Status item awal
#                 ))

#         if detail_values_list: # Pastikan ada item yang valid untuk disimpan
#             cursor.executemany(insert_detail_query, detail_values_list)
#         else:
#             # Jika tidak ada item valid, batalkan transaksi utama
#             connection.rollback()
#             return jsonify({"message": "ERROR", "error": "No valid items found in the order."}), 400


#         # 7. Ambil data transaksi lengkap untuk dikirim balik (Opsional tapi bagus)
#         cursor.execute("""
#             SELECT t.*, 
#                    GROUP_CONCAT(
#                        JSON_OBJECT(
#                            'id_produk', dof.id_produk, 
#                            'nama_produk', pf.nama_produk,  -- Ambil nama produk dari join
#                            'jumlah', dof.jumlah, 
#                            'harga_saat_order', dof.harga_saat_order, 
#                            'catatan_pesanan', dof.catatan_pesanan
#                        )
#                    ) AS detail_items
#             FROM transaksi t
#             LEFT JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
#             LEFT JOIN produk_fnb pf ON dof.id_produk = pf.id_produk -- Join untuk nama produk
#             WHERE t.id_transaksi = %s
#             GROUP BY t.id_transaksi 
#         """, (id_transaksi_baru,))
#         transaksi_baru = cursor.fetchone()

#         # Konversi tipe data Decimal ke string agar bisa di-JSON-kan
#         if transaksi_baru:
#              for key in ['subtotal', 'pajak_nominal', 'total_harga_final', 'pajak_persen']:
#                   if key in transaksi_baru and isinstance(transaksi_baru[key], decimal.Decimal):
#                        transaksi_baru[key] = str(transaksi_baru[key])
#              # Parse detail_items JSON string jika perlu
#              if 'detail_items' in transaksi_baru and transaksi_baru['detail_items']:
#                   # Perlu penanganan khusus karena GROUP_CONCAT bisa menghasilkan satu string besar
#                   # Mungkin lebih baik mengambil detail terpisah jika GROUP_CONCAT rumit
#                   try:
#                        # Coba parse jika formatnya array JSON valid
#                        transaksi_baru['detail_items'] = json.loads(f"[{transaksi_baru['detail_items']}]")
#                        # Konversi Decimal di dalam detail_items juga
#                        for item in transaksi_baru['detail_items']:
#                            if 'harga_saat_order' in item and isinstance(item['harga_saat_order'], decimal.Decimal):
#                                item['harga_saat_order'] = str(item['harga_saat_order'])
#                   except json.JSONDecodeError:
#                        print(f"Warning: Could not parse detail_items JSON for transaction {id_transaksi_baru}")
#                        transaksi_baru['detail_items'] = [] # Atau handle error lain


#         connection.commit() # Simpan semua perubahan ke database

#         return jsonify({"message": "Order successfully created", "datas": transaksi_baru}), 201

#     except decimal.InvalidOperation as e:
#          if connection:
#              connection.rollback()
#          return jsonify({"message": "ERROR", "error": f"Invalid number format in request data: {str(e)}"}), 400
#     except KeyError as e:
#          if connection:
#              connection.rollback()
#          return jsonify({"message": "ERROR", "error": f"Missing key in request data: {str(e)}"}), 400
#     except Exception as e:
#         if connection:
#             connection.rollback() # Batalkan semua jika ada error
#         # Log error sebenarnya di sini untuk debugging
#         print(f"Error creating order: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"message": "ERROR", "error": f"An internal server error occurred: {str(e)}"}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()



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




@transaksi_endpoints.route('/settings/tax-fnb', methods=['GET'])
def get_fnb_tax_rate():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
        setting_pajak = cursor.fetchone()

        pajak_fnb_persen = 10.0 # Default fallback
        if setting_pajak and setting_pajak['value']:
            try:
                pajak_fnb_persen = float(setting_pajak['value'])
            except ValueError:
                print("Warning: Nilai PAJAK_FNB_PERSEN di DB tidak valid.")

        return jsonify({"message": "OK", "taxRate": pajak_fnb_persen}), 200

    except Exception as e:
        print(f"Error getting FNB tax rate: {str(e)}")
        # Kembalikan default jika error, tapi log errornya
        return jsonify({"message": "ERROR", "error": str(e), "taxRate": 10.0}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        

@transaksi_endpoints.route('/repay/<int:id_transaksi>', methods=['GET'])
@jwt_required()
def get_repayment_link(id_transaksi):
    """
    Mengambil ulang URL pembayaran iPaymu untuk transaksi APAPUN yang belum lunas.
    """
    connection = None
    cursor = None
    try:
        identity = get_jwt_identity()
        user_id = identity.get("id_user")

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil detail transaksi (Pastikan milik user yang login)
        cursor.execute("""
            SELECT t.total_harga_final, t.status_pembayaran, 
                   u.nama, u.email, u.no_telepon
            FROM transaksi t
            JOIN users u ON t.id_user = u.id_user
            WHERE t.id_transaksi = %s AND t.id_user = %s
        """, (id_transaksi, user_id))
        trx = cursor.fetchone()

        if not trx:
            return jsonify({"message": "Transaksi tidak ditemukan atau akses ditolak"}), 404
        
        if trx['status_pembayaran'] == 'Lunas':
            return jsonify({"message": "Transaksi sudah lunas"}), 400

        # 2. Request Link Baru ke iPaymu
        ipaymu_res = create_ipaymu_payment(
            id_transaksi=id_transaksi,
            amount=trx['total_harga_final'],
            buyer_name=trx['nama'] or "Guest",
            buyer_phone=trx['no_telepon'] or "08123456789",
            buyer_email=trx['email'] or "guest@dago.com"
        )

        if ipaymu_res['success']:
            return jsonify({
                "message": "OK",
                "payment_url": ipaymu_res['url']
            }), 200
        else:
            return jsonify({"message": "ERROR", "error": ipaymu_res.get('message')}), 500

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()