"""Routes for module produk"""
import decimal
import json
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year

produk_endpoints = Blueprint('produk', __name__)
UPLOAD_FOLDER = "img"


@produk_endpoints.route('/kategori', methods=['GET'])
def read_kategori():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)

        id_tenant = request.args.get('id_tenant')
        if id_tenant:
            cursor.execute("SELECT * FROM kategori_produk WHERE id_tenant = %s", (id_tenant,))
        else:
            cursor.execute("SELECT * FROM kategori_produk")

        results = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "OK", "datas": results}), 200


@produk_endpoints.route('/readByKategori', methods=['GET'])
def readByKategori():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        id_kategori = request.args.get('id_kategori')

        # Query default, akan dimodifikasi jika ada id_kategori
        # Ambil SEMUA kolom yang relevan, terutama status_ketersediaan
        query = """
            SELECT
                p.id_produk, p.nama_produk, p.deskripsi_produk, p.harga,
                p.status_ketersediaan, p.foto_produk, p.id_kategori
            FROM produk_fnb p
            WHERE p.status_visibilitas = 'Aktif'
            ORDER BY p.nama_produk ASC
        """
        params = () # Tuple parameter kosong default

        if id_kategori:
            # --- PERBAIKAN DI SINI ---
            # Tambahkan filter id_kategori DAN pastikan filter visibilitas tetap ada
            query = """
                SELECT
                    p.id_produk, p.nama_produk, p.deskripsi_produk, p.harga,
                    p.status_ketersediaan, p.foto_produk, p.id_kategori
                FROM produk_fnb p
                WHERE p.id_kategori = %s
                  AND p.status_visibilitas = 'Aktif'
                ORDER BY p.nama_produk ASC
            """
            params = (id_kategori,) # Parameter untuk query
        # else:
            # Jika tidak ada id_kategori, mungkin lebih baik tidak mengembalikan apa-apa
            # atau kembalikan semua produk aktif (sesuai kebutuhan UI)
            # Jika ingin semua produk aktif:
            # query = """
            #     SELECT p.id_produk, p.nama_produk, p.deskripsi_produk, p.harga,
            #            p.status_ketersediaan, p.foto_produk, p.id_kategori
            #     FROM produk_fnb p
            #     WHERE p.status_visibilitas = 'Aktif'
            #     ORDER BY p.id_kategori, p.nama_produk ASC
            # """
            # params = ()
            # Jika tidak ingin mengembalikan apa-apa jika tidak ada id_kategori:
            # return jsonify({"message": "OK", "datas": []}), 200


        cursor.execute(query, params)
        results = cursor.fetchall()

    except Exception as e:
        print(f"Error reading products by category: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return jsonify({"message": "OK", "datas": results}), 200


# @produk_endpoints.route('/create', methods=['POST'])
# def create_transaksi_fnb():
#     """
#     Endpoint untuk membuat transaksi F&B baru.
#     Menyimpan data ke tabel 'transaksi' dan 'detail_order_fnb'.
#     """
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()

#         # Ekstrak data dari body request
#         fnb_type = data.get('fnb_type')
#         nama_guest = data.get('nama_guest')
#         lokasi_pemesanan = data.get('lokasi_pemesanan')
#         metode_pembayaran_raw = data.get('metode_pembayaran')
#         total_harga_final = data.get('total_harga_final')
#         detail_order = data.get('detail_order') # Ini adalah list of dictionaries

#         # 2. Buat mapping untuk menerjemahkan nilai
#         payment_map = {
#             "QRIS": "Non-Tunai",
#             "CASH": "Tunai"
#         }
#         # 3. Dapatkan nilai yang sesuai untuk database
#         metode_pembayaran_db = payment_map.get(metode_pembayaran_raw)
        
#         if not all([fnb_type, nama_guest, metode_pembayaran, total_harga_final, detail_order]):
#             return jsonify({"message": "ERROR", "error": "Data tidak lengkap"}), 400

#         connection = get_connection()
#         connection.start_transaction() # Mulai transaksi database
#         cursor = connection.cursor(dictionary=True)

#         # 1. Insert ke tabel master 'transaksi'
#         query_transaksi = """
#             INSERT INTO transaksi 
#             (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran, total_harga_final, status_pembayaran, status_order) 
#             VALUES (%s, %s, %s, %s, %s, 'Lunas', 'Baru')
#         """
#         values_transaksi = (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran, total_harga_final)
#         cursor.execute(query_transaksi, values_transaksi)
        
#         # Ambil ID dari transaksi yang baru saja dibuat
#         id_transaksi_baru = cursor.lastrowid

#         # 2. Insert ke tabel detail 'detail_order_fnb'
#         query_detail = """
#             INSERT INTO detail_order_fnb 
#             (id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan) 
#             VALUES (%s, %s, %s, %s, %s)
#         """
#         # Siapkan data untuk multi-insert
#         values_detail = [
#             (id_transaksi_baru, item['id_produk'], item['jumlah'], item['harga_saat_order'], item.get('catatan_pesanan'))
#             for item in detail_order
#         ]
        
#         cursor.executemany(query_detail, values_detail) # executemany lebih efisien untuk banyak data

#         connection.commit() # Jika semua berhasil, simpan perubahan
        
#         return jsonify({
#             "message": "OK", 
#             "datas": {
#                 "id_transaksi": id_transaksi_baru,
#                 "total_harga": total_harga_final,
#                 "nama_pemesan": nama_guest,
#                 "detail_order": detail_order,
#             }
#         }), 201 # 201 Created

#     except Exception as e:
#         if connection:
#             connection.rollback() # Jika ada error, batalkan semua perubahan
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
    
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
            
# @produk_endpoints.route('/create', methods=['POST'])
# def create_transaksi_fnb():
#     """
#     Endpoint untuk membuat transaksi F&B baru.
#     Menyimpan data ke tabel 'transaksi' dan 'detail_order_fnb'.
#     """
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()

#         # Ekstrak data dari body request
#         fnb_type = data.get('fnb_type')
#         nama_guest = data.get('nama_guest')
#         lokasi_pemesanan = data.get('lokasi_pemesanan')
#         # 1. Ambil nilai mentah dari frontend
#         metode_pembayaran_raw = data.get('metode_pembayaran') 
#         total_harga_final = data.get('total_harga_final')
#         detail_order = data.get('detail_order') 

#         # --- INI SOLUSINYA ---
#         # 2. Buat mapping untuk menerjemahkan nilai
#         payment_map = {
#             "QRIS": "Non-Tunai",
#             "CASH": "Tunai"
#         }
#         # 3. Dapatkan nilai yang sesuai untuk database
#         metode_pembayaran_db = payment_map.get(metode_pembayaran_raw)
#         # --- AKHIR SOLUSI ---

#         # 4. Validasi menggunakan nilai yang sudah di-map
#         if not all([fnb_type, nama_guest, metode_pembayaran_db, total_harga_final, detail_order]):
#             if not metode_pembayaran_db:
#                  return jsonify({"message": "ERROR", "error": f"Metode pembayaran '{metode_pembayaran_raw}' tidak valid."}), 400
#             return jsonify({"message": "ERROR", "error": "Data tidak lengkap"}), 400

#         connection = get_connection()
#         connection.start_transaction() 
#         cursor = connection.cursor(dictionary=True)

#         # 1. Insert ke tabel master 'transaksi'
#         query_transaksi = """
#             INSERT INTO transaksi 
#             (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran, total_harga_final, status_pembayaran, status_order) 
#             VALUES (%s, %s, %s, %s, %s, 'Lunas', 'Baru')
#         """
#         # 5. Gunakan variabel '_db' yang sudah bersih untuk query
#         values_transaksi = (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran_db, total_harga_final)
#         cursor.execute(query_transaksi, values_transaksi)
        
#         id_transaksi_baru = cursor.lastrowid

#         # 2. Insert ke tabel detail 'detail_order_fnb'
#         query_detail = """
#             INSERT INTO detail_order_fnb 
#             (id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan) 
#             VALUES (%s, %s, %s, %s, %s)
#         """
#         values_detail = [
#             (id_transaksi_baru, item['id_produk'], item['jumlah'], item['harga_saat_order'], item.get('catatan_pesanan'))
#             for item in detail_order
#         ]
        
#         cursor.executemany(query_detail, values_detail) 

#         connection.commit() 
        
#         return jsonify({
#             "message": "OK", 
#             "datas": {
#                 "id_transaksi": id_transaksi_baru,
#                 "total_harga": total_harga_final,
#                 "nama_pemesan": nama_guest,
#                 "detail_order": detail_order,
#             }
#         }), 201 

#     except Exception as e:
#         if connection:
#             connection.rollback() 
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
    
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()


@produk_endpoints.route('/create', methods=['POST'])
# @jwt_required() # Aktifkan jika perlu autentikasi
def create_transaksi_fnb_with_tax():
    """
    Endpoint untuk membuat transaksi F&B baru dari sistem_pembayaran.
    Menghitung pajak, memetakan metode pembayaran, dan menyimpan
    data ke tabel 'transaksi' dan 'detail_order_fnb'.
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "ERROR", "error": "Request body must be JSON."}), 400

        # 1. Ekstrak data dari body request
        fnb_type = data.get('fnb_type')
        nama_guest = data.get('nama_guest')
        lokasi_pemesanan = data.get('lokasi_pemesanan')
        metode_pembayaran_raw = data.get('metode_pembayaran')
        detail_order = data.get('detail_order')

        # (Opsional) Ambil nilai dari frontend untuk referensi
        # subtotal_frontend = data.get('subtotal')
        # pajak_nominal_frontend = data.get('pajak_nominal')
        # total_harga_final_frontend = data.get('total_harga_final')

        # 2. Validasi data dasar
        if not detail_order or not fnb_type or not nama_guest or not metode_pembayaran_raw:
            return jsonify({"message": "ERROR", "error": "Data tidak lengkap (detail_order, fnb_type, nama_guest, metode_pembayaran dibutuhkan)."}), 400
        if fnb_type == 'Dine In' and not lokasi_pemesanan:
            return jsonify({"message": "ERROR", "error": "Lokasi pemesanan dibutuhkan untuk Dine In."}), 400

        # 3. Pemetaan Metode Pembayaran
        payment_map = {"QRIS": "Non-Tunai", "CASH": "Tunai"}
        metode_pembayaran_db = payment_map.get(metode_pembayaran_raw)
        if not metode_pembayaran_db:
            return jsonify({"message": "ERROR", "error": f"Metode pembayaran '{metode_pembayaran_raw}' tidak valid. Gunakan 'QRIS' atau 'CASH'."}), 400

        # --- PERHITUNGAN ULANG DI BACKEND ---
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 4. Hitung Ulang Subtotal di Backend & Validasi Detail Order
        subtotal_backend = decimal.Decimal(0.00)
        valid_detail_order_items = []
        for item in detail_order:
            try:
                harga = decimal.Decimal(item['harga_saat_order'])
                jumlah = int(item['jumlah'])
                id_produk = int(item['id_produk'])
                catatan = item.get('catatan_pesanan')

                if jumlah > 0:
                    subtotal_backend += harga * jumlah
                    valid_detail_order_items.append({
                        'id_produk': id_produk, 'jumlah': jumlah,
                        'harga_saat_order': harga, 'catatan_pesanan': catatan
                    })
            except (KeyError, ValueError, TypeError, decimal.InvalidOperation) as e:
                return jsonify({"message": "ERROR", "error": f"Data tidak valid dalam detail_order: {str(e)}"}), 400

        if subtotal_backend <= 0:
            return jsonify({"message": "ERROR", "error": "Pesanan tidak boleh kosong atau totalnya nol."}), 400

        # 5. Ambil Persentase Pajak dari DB
        cursor.execute("SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
        setting_pajak = cursor.fetchone()
        pajak_persen_db = decimal.Decimal(10.00) # Default
        if setting_pajak and setting_pajak['value']:
            try:
                pajak_persen_db = decimal.Decimal(setting_pajak['value'])
            except decimal.InvalidOperation:
                print(f"Warning: Nilai pajak '{setting_pajak['value']}' di DB tidak valid. Menggunakan default 10%.")

        # 6. Hitung Ulang Pajak Nominal dan Total Final di Backend
        pajak_nominal_backend = (subtotal_backend * (pajak_persen_db / 100)).quantize(
            decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP
        )
        total_harga_final_backend = subtotal_backend + pajak_nominal_backend

        # --- PENYIMPANAN KE DATABASE ---
        # TIDAK PERLU connection.start_transaction() di sini

        # 7. Insert ke tabel master 'transaksi'
        query_transaksi = """
            INSERT INTO transaksi (
                fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran,
                subtotal, pajak_persen, pajak_nominal, total_harga_final,
                status_pembayaran, status_order, tanggal_transaksi
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        values_transaksi = (
            fnb_type, nama_guest,
            lokasi_pemesanan if fnb_type == 'Dine In' else None,
            metode_pembayaran_db, subtotal_backend, pajak_persen_db,
            pajak_nominal_backend, total_harga_final_backend,
            'Disimpan', 'Baru'
        )
        cursor.execute(query_transaksi, values_transaksi)
        id_transaksi_baru = cursor.lastrowid

        # 8. Insert ke tabel detail 'detail_order_fnb'
        if not valid_detail_order_items:
            # Jika tidak ada item valid setelah filter, rollback tidak diperlukan karena belum commit
            return jsonify({"message": "ERROR", "error": "Tidak ada item valid dalam pesanan."}), 400

        query_detail = """
            INSERT INTO detail_order_fnb
            (id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan)
            VALUES (%s, %s, %s, %s, %s)
        """
        values_detail = [
            (id_transaksi_baru, item['id_produk'], item['jumlah'],
             item['harga_saat_order'], item.get('catatan_pesanan'))
            for item in valid_detail_order_items
        ]
        cursor.executemany(query_detail, values_detail)

        # 9. Ambil data lengkap untuk respons
        cursor.execute("""
            SELECT
                t.id_transaksi, t.nama_guest, t.tanggal_transaksi,
                t.subtotal, t.pajak_persen, t.pajak_nominal, t.total_harga_final,
                GROUP_CONCAT(
                    JSON_OBJECT(
                        'id_produk', dof.id_produk, 'nama_produk', pf.nama_produk,
                        'jumlah', dof.jumlah, 'harga_saat_order', dof.harga_saat_order,
                        'catatan_pesanan', dof.catatan_pesanan
                    ) ORDER BY dof.id_detail_order ASC SEPARATOR ','
                ) AS detail_items
            FROM transaksi t
            LEFT JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
            LEFT JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            WHERE t.id_transaksi = %s
            GROUP BY t.id_transaksi
        """, (id_transaksi_baru,))
        transaksi_result_db = cursor.fetchone()

        # Konversi Decimal ke String & Parse JSON
        if transaksi_result_db:
             for key in ['subtotal', 'pajak_nominal', 'total_harga_final', 'pajak_persen']:
                  if key in transaksi_result_db and isinstance(transaksi_result_db[key], decimal.Decimal):
                       transaksi_result_db[key] = str(transaksi_result_db[key])
             if 'detail_items' in transaksi_result_db and transaksi_result_db['detail_items']:
                  try:
                       detail_str = f"[{transaksi_result_db['detail_items']}]"
                       parsed_details = json.loads(detail_str)
                       for item in parsed_details:
                           if 'harga_saat_order' in item and item['harga_saat_order'] is not None:
                               # Coba konversi ke Decimal dulu untuk validasi format
                               harga_dec = decimal.Decimal(item['harga_saat_order'])
                               item['harga_saat_order'] = str(harga_dec) # Simpan sebagai string
                       transaksi_result_db['detail_items'] = parsed_details
                  except (json.JSONDecodeError, decimal.InvalidOperation) as parse_error:
                       print(f"Warning: Gagal parse/konversi detail_items JSON untuk transaksi {id_transaksi_baru}: {parse_error}")
                       transaksi_result_db['detail_items'] = []
             else:
                  transaksi_result_db['detail_items'] = []

        # Simpan semua perubahan jika semua query berhasil
        connection.commit()

        # 10. Kembalikan data yang berhasil disimpan
        return jsonify({"message": "OK", "datas": transaksi_result_db}), 201

    except (decimal.InvalidOperation, ValueError, TypeError) as e:
        # Error konversi angka atau tipe data tidak valid
        if connection: connection.rollback()
        print(f"Data validation error: {str(e)}") # Log detail error
        return jsonify({"message": "ERROR", "error": f"Format data tidak valid: {str(e)}"}), 400
    except KeyError as e:
        # Key JSON tidak ditemukan
        if connection: connection.rollback()
        print(f"Missing key error: {str(e)}") # Log detail error
        return jsonify({"message": "ERROR", "error": f"Data JSON tidak lengkap, field '{str(e)}' tidak ditemukan."}), 400
    except Exception as e:
        # Error umum atau database
        if connection:
            connection.rollback()
        print(f"Error saat membuat transaksi F&B: {str(e)}")
        import traceback
        traceback.print_exc() # Cetak traceback lengkap ke log server
        return jsonify({"message": "ERROR", "error": "Terjadi kesalahan internal pada server."}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            

@produk_endpoints.route('/tenants', methods=['GET'])
def get_all_tenants():
    """Mengambil daftar semua tenant yang aktif."""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Di production, Anda mungkin ingin menambah "WHERE status = 'Active'"
        query = "SELECT id_tenant, nama_tenant, gambar_tenant FROM tenants WHERE status_tenant = 'Active'"
        cursor.execute(query)
        tenants = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": tenants}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()