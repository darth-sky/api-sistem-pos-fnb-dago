"""Routes for module kasir"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from flask import jsonify
from datetime import datetime, time

kasir_endpoints = Blueprint('kasir', __name__)
UPLOAD_FOLDER = "img"


# Fungsi helper untuk menentukan level warna berdasarkan sisa waktu
# def get_time_level(time_left_seconds):
#     if time_left_seconds is None:
#         return "gray" # Selesai
#     elif time_left_seconds > 3600: # Lebih dari 1 jam
#         return "green"
#     elif time_left_seconds > 900: # Lebih dari 15 menit
#         return "yellow"
#     else: # Kurang dari 15 menit
#         return "red"

@kasir_endpoints.route('/dashboard-data', methods=['GET'])
def get_kasir_dashboard_data():
    """
    Endpoint untuk mengambil semua data yang dibutuhkan oleh dasbor kasir.
    - Ringkasan transaksi, sewa aktif, dan ruangan tersedia.
    - Agregasi tipe ruangan (total & tersedia).
    - Daftar unit ruangan yang tersedia saat ini.
    - Daftar sewa yang aktif dan yang sudah selesai pada hari ini.
    """
    connection = None  # Inisialisasi di luar try block
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # --- 1. Data Ringkasan Atas ---
        # Today's Transaction
        query_today_transaction = """
        SELECT SUM(total_harga_final) as total 
        FROM transaksi 
        WHERE DATE(tanggal_transaksi) = CURDATE() AND status_pembayaran = 'Lunas';
        """
        cursor.execute(query_today_transaction)
        today_transaction = cursor.fetchone()['total'] or 0

        # Active Space Rental
        query_active_rentals = """
        SELECT COUNT(id_booking) as count FROM booking_ruangan 
        WHERE NOW() BETWEEN waktu_mulai AND waktu_selesai;
        """
        cursor.execute(query_active_rentals)
        active_rentals_count = cursor.fetchone()['count'] or 0
        
        # Total Rooms and Available Rooms
        query_total_rooms = "SELECT COUNT(id_ruangan) as count FROM ruangan WHERE status_ketersediaan = 'Active';"
        cursor.execute(query_total_rooms)
        total_rooms = cursor.fetchone()['count'] or 0
        available_rooms_count = total_rooms - active_rentals_count

        summary_data = {
            "todayTransaction": int(today_transaction),
            "spaceRental": active_rentals_count,
            "spaceAvailable": available_rooms_count
        }
        
        # --- 2. Data Tipe Unit Ruangan ---
        query_space_types = """
            SELECT 
                kr.nama_kategori as name, 
                COUNT(r.id_ruangan) as total,
                (COUNT(r.id_ruangan) - (
                    SELECT COUNT(br.id_booking) 
                    FROM booking_ruangan br
                    JOIN ruangan r_inner ON br.id_ruangan = r_inner.id_ruangan
                    WHERE r_inner.id_kategori_ruangan = kr.id_kategori_ruangan AND NOW() BETWEEN br.waktu_mulai AND br.waktu_selesai
                )) as available
            FROM ruangan r
            JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
            WHERE r.status_ketersediaan = 'Active'
            GROUP BY kr.id_kategori_ruangan, kr.nama_kategori;
        """
        cursor.execute(query_space_types)
        space_types_data = cursor.fetchall()

        # --- 3. Data Unit yang Tersedia ---
        query_available_units = """
            SELECT nama_ruangan FROM ruangan 
            WHERE status_ketersediaan = 'Active' AND id_ruangan NOT IN (
                SELECT id_ruangan FROM booking_ruangan WHERE NOW() BETWEEN waktu_mulai AND waktu_selesai
            );
        """
        cursor.execute(query_available_units)
        available_units_data = [row['nama_ruangan'] for row in cursor.fetchall()]

        # --- 4. Data Sewa (Aktif & Selesai Hari Ini) ---
        query_rentals = """
            SELECT 
                br.id_booking as id,
                COALESCE(u.nama, t.nama_guest) as client,
                r.nama_ruangan as unit,
                t.total_harga_final as price,
                br.waktu_mulai,
                br.waktu_selesai
            FROM booking_ruangan br
            JOIN transaksi t ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            LEFT JOIN users u ON t.id_user = u.id_user
            WHERE DATE(br.waktu_mulai) = CURDATE()
            ORDER BY br.waktu_mulai DESC;
        """
        cursor.execute(query_rentals)
        all_rentals_today = cursor.fetchall()
        
        rentals_active = []
        rentals_finish = []
        
        now = datetime.now()
        for rental in all_rentals_today:
            # Format data dasar
            rental['price'] = int(rental['price'])
            # 'date' untuk ditampilkan di UI, formatnya bisa disesuaikan
            rental['date'] = rental['waktu_mulai'].strftime('%d/%m/%Y %H:%M')

            # PERUBAHAN UTAMA:
            # Kirim waktu mulai dan selesai sebagai string ISO 8601.
            # Ini adalah format standar yang mudah diparsing oleh JavaScript.
            waktu_mulai_obj = rental['waktu_mulai']
            waktu_selesai_obj = rental['waktu_selesai']
            
            rental['waktu_mulai'] = waktu_mulai_obj.isoformat()
            rental['waktu_selesai'] = waktu_selesai_obj.isoformat()

            # Hapus kalkulasi 'time' dan 'level' dari sini
            
            # Pisahkan antara yang aktif dan yang sudah selesai
            if now >= waktu_mulai_obj and now <= waktu_selesai_obj:
                rentals_active.append(rental)
            elif now > waktu_selesai_obj:
                rentals_finish.append(rental)

        return jsonify({
            "message": "OK",
            "datas": {
                "summary": summary_data,
                "spaceTypes": space_types_data,
                "availableUnits": available_units_data,
                "rentals": {
                    "active": rentals_active,
                    "finish": rentals_finish
                }
            }
        })

    except Exception as e:
        # Log error untuk debugging di sisi server jika perlu
        print(f"Error in /dashboard-data: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        # Pastikan koneksi ditutup dengan aman
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# @kasir_endpoints.route('/dashboard-data', methods=['GET'])
# def get_kasir_dashboard_data():
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
        
#         # --- 1. Data Ringkasan Atas ---
#         # Today's Transaction
#         query_today_transaction = """
#         SELECT SUM(total_harga_final) as total 
#         FROM transaksi 
#         WHERE DATE(tanggal_transaksi) = CURDATE() AND status_pembayaran = 'Lunas';
#         """
#         cursor.execute(query_today_transaction)
#         today_transaction = cursor.fetchone()['total'] or 0

#         # Active Space Rental
#         query_active_rentals = """
#         SELECT COUNT(id_booking) as count FROM booking_ruangan 
#         WHERE NOW() BETWEEN waktu_mulai AND waktu_selesai;
#         """
#         cursor.execute(query_active_rentals)
#         active_rentals_count = cursor.fetchone()['count'] or 0
        
#         # Total Rooms and Available Rooms
#         query_total_rooms = "SELECT COUNT(id_ruangan) as count FROM ruangan WHERE status_ketersediaan = 'Active';"
#         cursor.execute(query_total_rooms)
#         total_rooms = cursor.fetchone()['count'] or 0
#         available_rooms_count = total_rooms - active_rentals_count

#         summary_data = {
#             "todayTransaction": int(today_transaction),
#             "spaceRental": active_rentals_count,
#             "spaceAvailable": available_rooms_count
#         }
        
#         # --- 2. Data Tipe Unit Ruangan ---
#         query_space_types = """
#             SELECT 
#                 kr.nama_kategori as name, 
#                 COUNT(r.id_ruangan) as total,
#                 (COUNT(r.id_ruangan) - (
#                     SELECT COUNT(br.id_booking) 
#                     FROM booking_ruangan br
#                     JOIN ruangan r_inner ON br.id_ruangan = r_inner.id_ruangan
#                     WHERE r_inner.id_kategori_ruangan = kr.id_kategori_ruangan AND NOW() BETWEEN br.waktu_mulai AND br.waktu_selesai
#                 )) as available
#             FROM ruangan r
#             JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
#             WHERE r.status_ketersediaan = 'Active'
#             GROUP BY kr.id_kategori_ruangan, kr.nama_kategori;
#         """
#         cursor.execute(query_space_types)
#         space_types_data = cursor.fetchall()

#         # --- 3. Data Unit yang Tersedia ---
#         query_available_units = """
#             SELECT nama_ruangan FROM ruangan 
#             WHERE status_ketersediaan = 'Active' AND id_ruangan NOT IN (
#                 SELECT id_ruangan FROM booking_ruangan WHERE NOW() BETWEEN waktu_mulai AND waktu_selesai
#             );
#         """
#         cursor.execute(query_available_units)
#         # Mengubah format dari list of dict menjadi list of string
#         available_units_data = [row['nama_ruangan'] for row in cursor.fetchall()]

#         # --- 4. Data Sewa (Aktif & Selesai Hari Ini) ---
#         query_rentals = """
#             SELECT 
#                 br.id_booking as id,
#                 COALESCE(u.nama, t.nama_guest) as client,
#                 r.nama_ruangan as unit,
#                 t.tanggal_transaksi as date,
#                 t.total_harga_final as price,
#                 br.waktu_mulai,
#                 br.waktu_selesai
#             FROM booking_ruangan br
#             JOIN transaksi t ON br.id_transaksi = t.id_transaksi
#             JOIN ruangan r ON br.id_ruangan = r.id_ruangan
#             LEFT JOIN users u ON t.id_user = u.id_user
#             WHERE DATE(br.waktu_mulai) = CURDATE()
#             ORDER BY br.waktu_mulai DESC;
#         """
#         cursor.execute(query_rentals)
#         all_rentals_today = cursor.fetchall()
        
#         rentals_active = []
#         rentals_finish = []
        
#         now = datetime.now()
#         for rental in all_rentals_today:
#             # Format ulang data untuk frontend
#             rental['price'] = int(rental['price'])
#             rental['date'] = rental['waktu_mulai'].strftime('%d/%m/%Y %H:%M')
            
#             if now >= rental['waktu_mulai'] and now <= rental['waktu_selesai']:
#                 time_left = rental['waktu_selesai'] - now
#                 time_left_seconds = time_left.total_seconds()
#                 # Format sisa waktu menjadi HH:MM:SS
#                 hours, remainder = divmod(time_left_seconds, 3600)
#                 minutes, seconds = divmod(remainder, 60)
#                 rental['time'] = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
#                 rental['level'] = get_time_level(time_left_seconds)
#                 rentals_active.append(rental)
#             elif now > rental['waktu_selesai']:
#                 rental['time'] = "Finished"
#                 rental['level'] = "gray" # Warna untuk yang sudah selesai
#                 rentals_finish.append(rental)

#         return jsonify({
#             "message": "OK",
#             "datas": {
#                 "summary": summary_data,
#                 "spaceTypes": space_types_data,
#                 "availableUnits": available_units_data,
#                 "rentals": {
#                     "active": rentals_active,
#                     "finish": rentals_finish
#                 }
#             }
#         })

#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if 'connection' in locals() and connection.is_connected():
#             cursor.close()
#             connection.close()

@kasir_endpoints.route("/historyKasir", methods=["GET"])
def get_history_kasir():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        # format tanggal langsung ditulis di SQL string agar tidak kena parsing %
        base_query = (
            "SELECT "
            "t.id_transaksi, "
            "CONCAT(DAY(t.tanggal_transaksi), ' ', MONTHNAME(t.tanggal_transaksi), ' ', YEAR(t.tanggal_transaksi), ' ', LPAD(HOUR(t.tanggal_transaksi), 2, '0'), ':', LPAD(MINUTE(t.tanggal_transaksi), 2, '0'), ':', LPAD(SECOND(t.tanggal_transaksi), 2, '0')) AS datetime, "
            "COALESCE(t.nama_guest, 'Guest') AS name, "
            "t.metode_pembayaran AS payment, "
            "COALESCE(t.lokasi_pemesanan, '-') AS table_name, "
            "t.total_harga_final AS total, "
            "0 AS discount, "
            "0 AS tax, "
            "t.total_harga_final AS subtotal "
            "FROM transaksi t "
            "WHERE t.status_pembayaran = 'Lunas' AND ("
            "  EXISTS (SELECT 1 FROM detail_order_fnb dof WHERE dof.id_transaksi = t.id_transaksi) OR "
            "  EXISTS (SELECT 1 FROM booking_ruangan br WHERE br.id_transaksi = t.id_transaksi)"
            ")"
        )

        params = ()

        if start_date and end_date:
            # Perhatikan ada 't.' sebelum tanggal_transaksi untuk menyesuaikan alias tabel
            base_query += " AND t.tanggal_transaksi BETWEEN %s AND %s"
            params = (start_date, end_date)

        base_query += " ORDER BY t.tanggal_transaksi DESC"

        print("🧩 QUERY:", base_query)
        print("📅 PARAMS:", params)

        cursor.execute(base_query, params)
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200

    except Exception as e:
        print("🔥 ERROR get_history_kasir:", str(e))
        return jsonify({"message": "ERROR", "error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@kasir_endpoints.route("/readProdukKasir", methods=["GET"])
def read_produk_kasir():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT 
            p.id_produk,
            p.nama_produk AS product,
            p.deskripsi_produk AS deskripsi,
            p.harga AS price,
            p.status_ketersediaan AS status,
            p.foto_produk AS foto,
            k.nama_kategori AS category,
            t.nama_tenant AS merchant,
            NOW() AS updated
        FROM produk_fnb p
        JOIN kategori_produk k ON p.id_kategori = k.id_kategori
        LEFT JOIN tenants t ON k.id_tenant = t.id_tenant
        ORDER BY p.id_produk DESC
        """

        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# Di file endpoint kasir Anda
@kasir_endpoints.route('/pos-init', methods=['GET'])
def get_pos_init_data():
    """
    Satu endpoint untuk mengambil semua data yang diperlukan
    oleh halaman kasir (POS) saat pertama kali dimuat.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua produk F&B (aktif dan inaktif)
        # --- PERBAIKAN DI SINI --- Hapus 'WHERE p.status_ketersediaan = 'Active''
        query_products = """
            SELECT
                p.id_produk AS id,
                p.nama_produk AS name,
                p.harga AS price,
                p.status_ketersediaan,
                k.id_tenant AS merchantId,
                k.nama_kategori AS category
            FROM produk_fnb p
            JOIN kategori_produk k ON p.id_kategori = k.id_kategori
            ORDER BY p.nama_produk;
        """
        cursor.execute(query_products)
        products_raw = cursor.fetchall()
        
        # Logika ini sudah benar, akan mengubah status menjadi true/false
        products = [
            {**p, "available": p.pop('status_ketersediaan') == 'Active'}
            for p in products_raw
        ]

        # 2. Ambil kategori tenant (merchant) - (Tidak ada perubahan)
        query_merchants = "SELECT id_tenant AS id, nama_tenant AS name FROM tenants ORDER BY name;"
        cursor.execute(query_merchants)
        merchant_categories = cursor.fetchall()
        merchant_categories.insert(0, {'id': 'all_merchants', 'name': 'All Merchants'})

        # 3. Ambil kategori produk (tipe) - (Tidak ada perubahan)
        query_product_types = "SELECT DISTINCT nama_kategori AS name FROM kategori_produk ORDER BY name;"
        cursor.execute(query_product_types)
        product_types_raw = cursor.fetchall()
        product_type_categories = [{'id': 'all_types', 'name': 'All Types'}]
        product_type_categories.extend([{'id': pt['name'], 'name': pt['name']} for pt in product_types_raw])

        # 4. Data tipe order - (Tidak ada perubahan)
        order_types = [
            {'id': 'dinein', 'name': 'Dine In'},
            {'id': 'takeaway', 'name': 'Take Away'},
            {'id': 'pickup', 'name': 'Pick Up'}
        ]

        # Gabungkan semua data menjadi satu respons - (Tidak ada perubahan)
        init_data = {
            "products": products,
            "merchantCategories": merchant_categories,
            "productTypeCategories": product_type_categories,
            "orderTypes": order_types
        }

        return jsonify({"message": "OK", "datas": init_data}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


#=========================================================================================
# ENDPOINT 2: Membuat order baru dari kasir
#=========================================================================================
@kasir_endpoints.route('/order', methods=['POST'])
def create_order():
    """
    Menerima data order dari frontend dan menyimpannya ke database.
    Menggunakan transaksi untuk memastikan integritas data.
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        if not data or 'items' not in data or not data['items']:
            return jsonify({"message": "ERROR", "error": "Invalid order data"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # Mulai transaksi database
        connection.start_transaction()

        # 1. Insert ke tabel 'transaksi'
        # Mapping tipe F&B dari frontend ke ENUM di DB
        fnb_type_map = {
            'dinein': 'Dine In',
            'takeaway': 'Takeaway',
            'pickup': 'Pick Up'
        }
        fnb_type = fnb_type_map.get(data.get('orderType'), 'Takeaway')

        query_transaksi = """
            INSERT INTO transaksi (
                nama_guest, lokasi_pemesanan, fnb_type, metode_pembayaran,
                total_harga_final, status_pembayaran, status_order
            ) VALUES (%s, %s, %s, %s, %s, 'Lunas', 'Baru');
        """
        transaksi_values = (
            data.get('customerName'),
            data.get('room'),
            fnb_type,
            data.get('paymentMethod'),
            data.get('totalAmount')
        )
        cursor.execute(query_transaksi, transaksi_values)
        
        # Ambil ID dari transaksi yang baru saja dibuat
        id_transaksi_baru = cursor.lastrowid

        # 2. Insert setiap item ke tabel 'detail_order_fnb'
        query_detail = """
            INSERT INTO detail_order_fnb (
                id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan
            ) VALUES (%s, %s, %s, %s, %s);
        """
        for item in data['items']:
            detail_values = (
                id_transaksi_baru,
                item['id'],
                item['qty'],
                item['price'],
                item.get('note')
            )
            cursor.execute(query_detail, detail_values)

        # Jika semua berhasil, commit transaksi
        connection.commit()

        return jsonify({
            "message": "OK",
            "info": "Order created successfully",
            "id_transaksi": id_transaksi_baru
        }), 201

    except Exception as e:
        # Jika terjadi error, batalkan semua perubahan
        if connection:
            connection.rollback()
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


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
            t.fnb_type,

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
                    "fnb_type": row["fnb_type"],  # 🆕 Tambahkan baris ini
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