"""Routes for module kasir"""
import decimal
from functools import wraps
import os
import shlex
import subprocess
from flask import Blueprint, Response, jsonify, request, send_file
import mysql
from helper.db_helper import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER, get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import get_jwt_identity, jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from flask import jsonify
from datetime import datetime, time, date
import traceback
from collections import defaultdict


kasir_endpoints = Blueprint('kasir', __name__)
UPLOAD_FOLDER = "img"


@kasir_endpoints.route('/transaksi/session/<int:id_sesi>', methods=['GET'])
@jwt_required()
def read_transaksi_by_session_id(id_sesi):
    """
    Ambil daftar transaksi berdasarkan ID SESI SPESIFIK (Baik buka maupun tutup).
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Validasi apakah sesi tersebut ada (Opsional, tapi baik untuk keamanan)
        cursor.execute("SELECT id_sesi FROM sesi_kasir WHERE id_sesi = %s", (id_sesi,))
        sesi = cursor.fetchone()
        if not sesi:
            return jsonify({"message": "ERROR", "error": "Sesi tidak ditemukan"}), 404

        # 2. Query utama (Sama persis dengan readTransaksiKasirs, tapi WHERE t.id_sesi = %s)
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
            t.subtotal,
            t.pajak_nominal,
            t.pajak_persen,
            t.uang_diterima,
            t.kembalian,
            
            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan,
            d.status_pesanan AS status_item, 
            tnt.nama_tenant,
            
            b.id_booking,
            r.nama_ruangan,
            r.harga_per_jam,
            b.harga_saat_booking,
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
        LEFT JOIN kategori_produk k_prod ON p.id_kategori = k_prod.id_kategori
        LEFT JOIN tenants tnt ON k_prod.id_tenant = tnt.id_tenant
        LEFT JOIN booking_ruangan b ON t.id_transaksi = b.id_transaksi
        LEFT JOIN ruangan r ON b.id_ruangan = r.id_ruangan
        LEFT JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
        
        -- PERUBAHAN UTAMA DI SINI: Filter by ID SESI yang dikirim frontend
        WHERE t.id_sesi = %s
            
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """

        cursor.execute(query, (id_sesi,))
        rows = cursor.fetchall()

        # --- LOGIKA GROUPING (COPY PASTE DARI KODE SEBELUMNYA) ---
        from collections import defaultdict
        grouped_data = defaultdict(list)
        for row in rows:
            grouped_data[row["id_transaksi"]].append(row)

        final_data = []
        for trx_id, trx_rows in grouped_data.items():
            first_row = trx_rows[0]
            
            if first_row["jenis_transaksi"] not in ("fnb", "booking"):
                continue
                
            # ... (Logika status order sama seperti sebelumnya) ...
            fnb_items = [r for r in trx_rows if r['id_detail_order'] is not None]
            overall_status = first_row["status_order"]
            # (Sederhanakan logika status untuk ringkasan)
            
            order_type = "Booking"
            if first_row["jenis_transaksi"] == "fnb":
                order_type = first_row["fnb_type"] or "Takeout"

            transaction_entry = {
                "id": trx_id,
                "customer": first_row["customer_name"],
                "location": first_row["lokasi_pemesanan"],
                "status_pesanan": overall_status, 
                "payment_status": first_row["status_pembayaran"],
                "payment_method": first_row["metode_pembayaran"],
                "total": float(first_row["total_harga_final"]),
                "time": first_row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                "type": order_type,
                "subtotal": float(first_row.get("subtotal") or 0),
                "tax_nominal": float(first_row.get("pajak_nominal") or 0),
                "tax_percent": float(first_row.get("pajak_persen") or 0),
                "uang_diterima": float(first_row.get("uang_diterima") or 0),
                "kembalian": float(first_row.get("kembalian") or 0),
                "items": [],
                "bookings": []
            }
            
            processed_bookings = set()
            for row in trx_rows:
                if row["id_detail_order"]:
                    transaction_entry["items"].append({
                        "id_detail_order": row["id_detail_order"],
                        "product": row["nama_produk"],
                        "qty": row["jumlah"],
                        "price": float(row["harga_saat_order"]),
                        "note": row["catatan_pesanan"],
                        "status": row["status_item"],
                        "tenant_name": row["nama_tenant"] or "Lainnya"
                    })
                if row["id_booking"] and row["id_booking"] not in processed_bookings:
                    transaction_entry["bookings"].append({
                        "id_booking": row["id_booking"],
                        "room_name": row["nama_ruangan"],
                        "room_category": row["kategori_ruangan"],
                        "booked_price": float(row["harga_saat_booking"] or 0), 
                        "start_time": row["waktu_mulai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_mulai"] else None,
                        "end_time": row["waktu_selesai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_selesai"] else None,
                        "duration": row["durasi"]
                    })
                    processed_bookings.add(row["id_booking"])
            
            final_data.append(transaction_entry)

        return jsonify({
            "message": "OK",
            "datas": final_data
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@kasir_endpoints.route('/export-database', methods=['GET'])
@jwt_required()
def export_database():
    try:
        # 1. Tentukan nama file backup
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"backup_db_pos_{timestamp}.sql"
        filepath = os.path.join(os.getcwd(), 'temp', filename) # Simpan di folder temp

        # Pastikan folder temp ada
        if not os.path.exists('temp'):
            os.makedirs('temp')

        # 2. Jalankan mysqldump (Sesuaikan path mysqldump jika di Windows dan tidak di PATH)
        # Contoh command: mysqldump -u root -p --host localhost db_name > file.sql
        
        # PERHATIAN: Ganti variabel di bawah sesuai config database Anda
        DB_USER = 'root'
        DB_PASS = '' # Kosongkan jika tidak ada, atau isi password
        DB_NAME = 'db_sistem_pos_v30'
        DB_HOST = 'localhost'

        cmd = [
            'mysqldump',
            f'-h{DB_HOST}',
            f'-u{DB_USER}',
            f'--password={DB_PASS}' if DB_PASS else '', # Handle password kosong
            DB_NAME
        ]
        
        # Hapus elemen kosong jika password kosong
        cmd = [x for x in cmd if x] 

        with open(filepath, 'w') as output_file:
            process = subprocess.Popen(cmd, stdout=output_file, stderr=subprocess.PIPE)
            stderr = process.communicate()[1]

            if process.returncode != 0:
                raise Exception(f"Error dumping database: {stderr.decode('utf-8')}")

        # 3. Kirim file ke frontend
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/sql'
        )

    except Exception as e:
        print(f"Export Error: {e}")
        return jsonify({"message": "Gagal membackup database", "error": str(e)}), 500




# Helper decorator untuk memeriksa peran (Anda mungkin sudah punya)
def role_required(role_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            jwt_identity = get_jwt_identity()
            role = jwt_identity.get('role')
            if role != role_name:
                return jsonify({"message": "ERROR", "error": "Akses ditolak: Peran tidak diizinkan."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator



# --- PERUBAHAN: HELPER FUNCTION BARU UNTUK VALIDASI BENTROK ---
def check_booking_conflicts(cursor, items_to_check, id_transaksi_to_exclude=None):
    """
    Memvalidasi semua item ruangan dalam keranjang agar tidak bentrok.
    Mengembalikan pesan error jika bentrok, atau None jika aman.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    for item in items_to_check:
        if item.get('type') != 'room' or not item.get('bookingData'):
            continue
            
        booking_data = item.get('bookingData')
        try:
            id_ruangan = int(booking_data['id_ruangan'])
            start_hour = int(booking_data['waktu_mulai_jam'])
            durasi_jam = int(booking_data['durasi_jam'])
            end_hour = start_hour + durasi_jam
            
            waktu_mulai = f"{today_str} {start_hour:02d}:00:00"
            waktu_selesai = f"{today_str} {end_hour:02d}:00:00"

        except (KeyError, ValueError, TypeError) as e:
            return f"Data booking ruangan tidak valid: {str(e)}"

        # Query untuk cek bentrok
        query_check = """
            SELECT COUNT(*) as count FROM booking_ruangan
            WHERE id_ruangan = %s AND (%s < waktu_selesai AND %s > waktu_mulai)
        """
        params_check = [id_ruangan, waktu_mulai, waktu_selesai]
        
        # Jika sedang mengupdate (paySavedOrder), jangan cek bentrok dengan diri sendiri
        if id_transaksi_to_exclude:
            query_check += " AND id_transaksi != %s"
            params_check.append(id_transaksi_to_exclude)
            
        cursor.execute(query_check, tuple(params_check))
        
        if cursor.fetchone()['count'] > 0:
            return f"Jadwal untuk '{item.get('name')}' ({start_hour:02d}:00 - {end_hour:02d}:00) sudah terisi."

    return None # Tidak ada konflik


def calculate_order_totals(cursor, items, discount_percentage_str, discount_nominal_input=0):
    """
    Menghitung semua total berdasarkan keranjang campuran (F&B + Ruangan).
    Pajak HANYA dikenakan pada F&B.
    
    PRIORITAS DISKON:
    1. Jika discount_nominal_input ada (> 0), gunakan itu (agar akurat/tidak ada selisih pembulatan).
    2. Jika tidak, hitung manual dari discount_percentage_str.
    
    Mengembalikan (subtotal, diskon_nominal, pajak_nominal, total_final, pajak_persen_db)
    """
    subtotal_fnb = decimal.Decimal(0.00)
    subtotal_room = decimal.Decimal(0.00)
    
    # 1. Hitung Subtotal Item
    for item in items:
        try:
            harga = decimal.Decimal(item['price'])
            jumlah = int(item['qty'])
            
            if item.get('type') == 'fnb':
                subtotal_fnb += harga * jumlah
            elif item.get('type') == 'room':
                subtotal_room += harga * jumlah
        except (KeyError, ValueError, TypeError, decimal.InvalidOperation) as e:
            raise ValueError(f"Data item tidak valid: {str(e)}")

    subtotal_backend = subtotal_fnb + subtotal_room
    
    # 2. Tentukan Nominal Diskon (MODIFIED)
    # Prioritaskan input nominal langsung dari Frontend untuk menghindari rounding error
    if discount_nominal_input is not None and float(discount_nominal_input) > 0:
        discount_nominal_backend = decimal.Decimal(discount_nominal_input).quantize(
            decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP
        )
    else:
        # Fallback: Hitung dari persentase jika nominal tidak dikirim/nol
        discount_percentage = decimal.Decimal(discount_percentage_str)
        discount_nominal_backend = (subtotal_backend * (discount_percentage / 100)).quantize(
            decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP
        )
    
    # 3. Ambil Pajak F&B dari Settings
    cursor.execute("SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
    setting_pajak = cursor.fetchone()
    pajak_persen_db = decimal.Decimal(10.00)
    if setting_pajak and setting_pajak['value']:
        try: 
            pajak_persen_db = decimal.Decimal(setting_pajak['value'])
        except decimal.InvalidOperation: 
            print(f"Warning: Pajak '{setting_pajak['value']}' di DB tidak valid.")

    # 4. Hitung Pajak HANYA dari F&B
    # Kita perlu mengalokasikan diskon secara proporsional ke F&B
    fnb_taxable_amount = subtotal_fnb
    
    if subtotal_backend > 0 and discount_nominal_backend > 0:
        # Rumus: (Subtotal F&B / Total Subtotal) * Total Diskon Nominal
        fnb_discount_portion = (subtotal_fnb / subtotal_backend) * discount_nominal_backend
        fnb_taxable_amount = (subtotal_fnb - fnb_discount_portion)

    # Pastikan taxable amount tidak negatif
    if fnb_taxable_amount < 0:
        fnb_taxable_amount = decimal.Decimal(0.00)

    pajak_nominal_backend = (fnb_taxable_amount * (pajak_persen_db / 100)).quantize(
        decimal.Decimal('0.01'), rounding=decimal.ROUND_HALF_UP
    )
    
    # 5. Total Final
    # Total Final = Subtotal - Diskon + Pajak
    total_harga_final_backend = (subtotal_backend - discount_nominal_backend) + pajak_nominal_backend

    # Validasi akhir agar tidak negatif
    if pajak_nominal_backend < 0: pajak_nominal_backend = decimal.Decimal('0.00')
    if total_harga_final_backend < 0: total_harga_final_backend = decimal.Decimal('0.00')

    return subtotal_backend, discount_nominal_backend, pajak_nominal_backend, total_harga_final_backend, pajak_persen_db


# --- PERUBAHAN: HELPER FUNCTION BARU UNTUK MEMPROSES ITEMS ---
# Asumsi Anda punya helper untuk import: from datetime import datetime, date

def process_order_items(cursor, id_transaksi, items_frontend):
    """
    Memproses keranjang campuran, memisahkan item F&B dan Ruangan,
    dan menyimpannya ke tabel yang sesuai.
    """
    today_date = date.today().strftime('%Y-%m-%d')

    for item in items_frontend:
        item_type = item.get('type')
        
        if item_type == 'fnb':
            # --- Logika F&B (Sudah benar) ---
            query_fnb = """
                INSERT INTO detail_order_fnb 
                    (id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan, status_pesanan)
                VALUES (%s, %s, %s, %s, %s, 'Baru')
            """
            values_fnb = (
                id_transaksi,
                item.get('id'),
                item.get('qty'),
                item.get('price'),
                item.get('note')
            )
            cursor.execute(query_fnb, values_fnb)
            
        elif item_type == 'room':
            # --- Logika Ruangan (INI YANG PERLU DIPERBAIKI) ---
            booking_data = item.get('bookingData', {})
            
            # 1. Ambil data dari payload
            id_ruangan = booking_data.get('id_ruangan')
            durasi_jam = booking_data.get('durasi_jam')
            waktu_mulai_jam = booking_data.get('waktu_mulai_jam')
            
            # --- PERBAIKAN: Ambil harga dari item, BUKAN dari bookingData ---
            # item['price'] adalah harga paket yang benar.
            harga_ruangan = item.get('price', 0) 
            # --- AKHIR PERBAIKAN ---

            # 2. Buat objek datetime
            waktu_mulai_dt = datetime.strptime(f"{today_date} {waktu_mulai_jam}:00:00", '%Y-%m-%d %H:%M:%S')
            waktu_selesai_dt = datetime.strptime(f"{today_date} {waktu_mulai_jam + durasi_jam}:00:00", '%Y-%m-%d %H:%M:%S')
            
            # 3. Insert ke DB (Termasuk kolom `harga_saat_booking`)
            query_room = """
                INSERT INTO booking_ruangan
                    (id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi, harga_saat_booking)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            values_room = (
                id_transaksi,
                id_ruangan,
                waktu_mulai_dt,
                waktu_selesai_dt,
                durasi_jam * 60,  # Simpan sebagai menit (sesuai DB Anda)
                harga_ruangan     # <-- Simpan harga ruangan di sini
            )
            cursor.execute(query_room, values_room)

    return True # Selesai

# --- PASTIKAN HELPER FUNCTION INI ADA ---
# (Fungsi ini mengubah tipe data (seperti tanggal/decimal) menjadi string)
def serialize_db_row(row):
    if not row:
        return None
    serialized = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            serialized[key] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value
    return serialized
# --- AKHIR HELPER FUNCTION ---


# ... (Pastikan semua import Anda ada di atas)

@kasir_endpoints.route('/sesi/history', methods=['GET'])
@jwt_required()
def get_history_for_current_session():
    # 1. Dapatkan ID kasir dari token (Misal: Rose, ID 71)
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 2. Cari Sesi Aktif GLOBAL (Logika ini sudah benar)
        cursor.execute("""
            SELECT id_sesi, saldo_awal 
            FROM sesi_kasir 
            WHERE status_sesi = 'Dibuka' 
            LIMIT 1
        """)
        sesi_aktif = cursor.fetchone()

        # 3. Jika tidak ada sesi aktif GLOBAL, kembalikan data kosong
        if not sesi_aktif:
            return jsonify({
                "message": "OK", 
                "transactions": [],
                "open_balance": 0,
                "current_balance": 0
            }), 200

        id_sesi_aktif = sesi_aktif['id_sesi'] 
        open_balance = sesi_aktif['saldo_awal'] or decimal.Decimal(0.00) 

        # 4. Ambil semua transaksi UNTUK ID SESI GLOBAL DAN ID KASIR INI (Logika ini sudah benar)
        query = """
            SELECT
                t.id_transaksi,
                t.tanggal_transaksi,
                COALESCE(u.nama, t.nama_guest) AS nama_pelanggan,
                t.metode_pembayaran,
                t.subtotal,
                t.pajak_nominal,
                t.lokasi_pemesanan,
                t.total_harga_final,
                t.status_order,
                (SELECT GROUP_CONCAT(pf.nama_produk SEPARATOR ', ')
                    FROM detail_order_fnb dof
                    JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                    WHERE dof.id_transaksi = t.id_transaksi
                ) AS fnb_items,
                (SELECT GROUP_CONCAT(r.nama_ruangan SEPARATOR ', ')
                    FROM booking_ruangan br
                    JOIN ruangan r ON br.id_ruangan = r.id_ruangan
                    WHERE br.id_transaksi = t.id_transaksi
                ) AS room_items
            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            WHERE 
                t.id_sesi = %s AND t.id_kasir_pembuat = %s 
            ORDER BY t.tanggal_transaksi DESC;
        """
        
        cursor.execute(query, (id_sesi_aktif, id_user_kasir))
        transaksi_list_raw = cursor.fetchall()
        
        safe_transaksi = [serialize_db_row(trx) for trx in transaksi_list_raw]

        # 5. Hitung total tunai UNTUK ID SESI GLOBAL DAN ID KASIR INI (Logika ini sudah benar)
        cursor.execute("""
            SELECT SUM(total_harga_final) as total_tunai_sesi
            FROM transaksi
            WHERE 
                id_sesi = %s AND id_kasir_pembuat = %s 
                AND metode_pembayaran = 'Tunai'
        """, (id_sesi_aktif, id_user_kasir))
        
        total_tunai_result = cursor.fetchone()
        
        # --- PERUBAHAN DI SINI ---
        
        # Ini adalah total tunai yang HANYA disetor oleh KASIR INI
        total_tunai_kasir_ini = total_tunai_result['total_tunai_sesi'] or decimal.Decimal(0.00) 
        
        # Hapus kueri untuk total_tunai_global
        
        # 6. Hitung current_balance berdasarkan permintaan Anda:
        # Saldo saat ini = Saldo Awal Sesi (Global) + Total Tunai DARI KASIR INI
        current_balance = open_balance + total_tunai_kasir_ini
        
        # --- AKHIR PERUBAHAN ---
        
        # 7. Modifikasi return JSON
        return jsonify({
            "message": "OK", 
            "transactions": safe_transaksi, # Transaksi milik kasir ini
            "open_balance": float(open_balance), # Saldo awal global
            "current_balance": float(current_balance) # Saldo (Saldo Awal + Tunai Kasir Ini)
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

                
# Di file endpoint kasir Anda (misal: .../routes/kasir_endpoints.py)

@kasir_endpoints.route('/sesi/buka', methods=['POST'])
@jwt_required()
def buka_sesi_kasir():
    # 1. Dapatkan ID kasir (tetap penting untuk mencatat SIAPA yang BUKA)
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity

    data = request.get_json()
    nama_sesi = data.get('nama_sesi')
    saldo_awal = data.get('saldo_awal')

    if saldo_awal is None:
        return jsonify({"message": "ERROR", "error": "Saldo awal wajib diisi."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERUBAHAN 1: Cek apakah ADA SESI AKTIF GLOBAL ---
        # Bukan lagi "WHERE id_user_kasir = %s"
        cursor.execute(
            "SELECT id_sesi FROM sesi_kasir WHERE status_sesi = 'Dibuka' LIMIT 1"
        )
        sesi_aktif = cursor.fetchone()
        
        # Jika ada sesi aktif, jangan biarkan buat baru
        if sesi_aktif:
            return jsonify({
                "message": "ERROR", 
                "error": "Sesi sudah dibuka oleh kasir lain. Silakan gabung sesi yang ada di daftar."
            }), 400
        # --- AKHIR PERUBAHAN 1 ---

        # Buat sesi baru (INSERT sudah benar, mencatat ID kasir pembuat)
        query = """
            INSERT INTO sesi_kasir (id_user_kasir, nama_sesi, saldo_awal, status_sesi, waktu_mulai)
            VALUES (%s, %s, %s, 'Dibuka', NOW())
        """
        cursor.execute(query, (id_user_kasir, nama_sesi,
                          decimal.Decimal(saldo_awal)))
        
        new_session_id = cursor.lastrowid
        connection.commit()

        # --- PERUBAHAN 2: Kembalikan data sesi lengkap, bukan cuma ID ---
        # AuthProvider.joinSession() membutuhkan objek sesi yang lengkap.
        
        # Query data sesi yang baru dibuat beserta nama kasirnya
        cursor.execute("""
            SELECT 
                s.id_sesi, 
                s.nama_sesi, 
                s.saldo_awal, 
                s.waktu_mulai, 
                u.nama AS nama_kasir
            FROM sesi_kasir s
            JOIN users u ON s.id_user_kasir = u.id_user
            WHERE s.id_sesi = %s
        """, (new_session_id,))
        
        new_session_data = cursor.fetchone()
        
        if not new_session_data:
            # Ini seharusnya tidak terjadi, tapi sebagai pengaman
            return jsonify({"message": "ERROR", "error": "Gagal mengambil data sesi yang baru dibuat."}), 500

        # Serialisasi Decimal dan Datetime
        new_session_data['saldo_awal'] = float(new_session_data['saldo_awal'])
        new_session_data['waktu_mulai'] = new_session_data['waktu_mulai'].isoformat()

        return jsonify({
            "message": "OK", 
            "info": "Sesi kasir berhasil dibuka", 
            "session": new_session_data  # <-- Kirim objek 'session'
        }), 201
        # --- AKHIR PERUBAHAN 2 ---

    except Exception as e:
        if connection:
            connection.rollback()
        # Cetak traceback untuk debugging di server
        traceback.print_exc() 
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# # --- 2. ENDPOINT UNTUK MENUTUP SESI ---
# @kasir_endpoints.route('/sesi/tutup', methods=['POST'])
# @jwt_required()
# def tutup_sesi_kasir():
#     # (Ekstrak ID Kasir - Kode ini sudah benar)
#     jwt_identity = get_jwt_identity()
#     try:
#         id_user_kasir = jwt_identity.get('id_user')
#         if not id_user_kasir:
#             return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
#     except AttributeError:
#         id_user_kasir = jwt_identity

#     data = request.get_json()
#     saldo_akhir_aktual = data.get('saldo_akhir_aktual')

#     if saldo_akhir_aktual is None:
#         return jsonify({"message": "ERROR", "error": "Saldo akhir aktual wajib diisi."}), 400

#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # (Cari sesi aktif - Kode ini sudah benar)
#         cursor.execute("SELECT id_sesi, saldo_awal FROM sesi_kasir WHERE id_user_kasir = %s AND status_sesi = 'Dibuka' LIMIT 1", (id_user_kasir,))
#         sesi_aktif = cursor.fetchone()
#         if not sesi_aktif:
#             return jsonify({"message": "ERROR", "error": "Tidak ada sesi aktif untuk ditutup."}), 404

#         id_sesi = sesi_aktif['id_sesi']
#         saldo_awal_sesi = sesi_aktif['saldo_awal']

#         # (Hitung total tunai - Kode ini sudah benar)
#         cursor.execute("SELECT SUM(total_harga_final) as total_tunai FROM transaksi WHERE id_sesi = %s AND metode_pembayaran = 'Tunai'", (id_sesi,))
#         result_tunai = cursor.fetchone()
#         total_tunai = result_tunai['total_tunai'] or 0
#         saldo_akhir_tercatat = saldo_awal_sesi + total_tunai

#         # (Update sesi kasir - Kode ini sudah benar)
#         query_update_sesi = """
#             UPDATE sesi_kasir SET saldo_akhir_tercatat = %s, saldo_akhir_aktual = %s, status_sesi = 'Ditutup', waktu_selesai = NOW()
#             WHERE id_sesi = %s
#         """
#         cursor.execute(query_update_sesi, (saldo_akhir_tercatat, decimal.Decimal(saldo_akhir_aktual), id_sesi))

        # # === PERUBAHAN DI SINI: Update status semua produk F&B ===
        # query_update_produk = "UPDATE produk_fnb SET status_ketersediaan = 'Inactive'"
        # cursor.execute(query_update_produk)
        # # === AKHIR PERUBAHAN ===

        # # Commit SEMUA perubahan (update sesi DAN update produk)
        # connection.commit()

#         return jsonify({"message": "OK", "info": "Sesi kasir berhasil ditutup, status produk diperbarui"}), 200 # Pesan bisa disesuaikan

#     except Exception as e:
#         if connection: connection.rollback() # Rollback jika salah satu query gagal
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


@kasir_endpoints.route('/sesi/tutup', methods=['POST'])
@jwt_required()
def tutup_sesi_kasir():
    # (Ekstrak ID Kasir - Kode ini tetap dipakai untuk otorisasi)
    jwt_identity = get_jwt_identity()
    try:
        # Kita tetap periksa siapa yang login, tapi tidak untuk query
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity  # fallback jika format token beda

    data = request.get_json()

    # --- PERUBAHAN 1: Ambil id_sesi dari JSON ---
    id_sesi_dari_frontend = data.get('id_sesi')
    # --- AKHIR PERUBAHAN 1 ---

    saldo_akhir_aktual = data.get('saldo_akhir_aktual')
    nama_kasir_penutup = data.get('nama_kasir_penutup')

    if saldo_akhir_aktual is None:
        return jsonify({"message": "ERROR", "error": "Saldo akhir aktual wajib diisi."}), 400
    if not nama_kasir_penutup:
        return jsonify({"message": "ERROR", "error": "Nama kasir penutup wajib diisi."}), 400

    # --- PERUBAHAN 2: Validasi id_sesi_dari_frontend ---
    if not id_sesi_dari_frontend:
        return jsonify({"message": "ERROR", "error": "ID Sesi tidak diterima oleh server."}), 400
    # --- AKHIR PERUBAHAN 2 ---

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERUBAHAN 3: Ubah Query SQL ---
        # Cari sesi berdasarkan ID SESI, bukan ID USER KASIR
        cursor.execute(
            "SELECT id_sesi, saldo_awal FROM sesi_kasir WHERE id_sesi = %s AND status_sesi = 'Dibuka' LIMIT 1",
            (id_sesi_dari_frontend,)
        )
        # --- AKHIR PERUBAHAN 3 ---

        sesi_aktif = cursor.fetchone()

        if not sesi_aktif:
            # Error ini sekarang berarti sesi-nya tidak ada ATAU sudah ditutup
            return jsonify({
                "message": "ERROR",
                "error": f"Sesi aktif tidak ditemukan (ID: {id_sesi_dari_frontend}). Mungkin sudah ditutup."
            }), 404

        id_sesi = sesi_aktif['id_sesi']
        saldo_awal_sesi = sesi_aktif['saldo_awal']

        # (Hitung total tunai - Kode ini sudah benar)
        cursor.execute("""
            SELECT SUM(total_harga_final) AS total_tunai
            FROM transaksi
            WHERE id_sesi = %s AND metode_pembayaran = 'Tunai'
        """, (id_sesi,))
        result_tunai = cursor.fetchone()
        total_tunai = result_tunai['total_tunai'] or 0

        saldo_akhir_tercatat = saldo_awal_sesi + total_tunai

        # (Query Update - Kode ini sudah benar)
        query_update = """
            UPDATE sesi_kasir
            SET saldo_akhir_tercatat = %s,
                saldo_akhir_aktual = %s,
                nama_kasir_penutup = %s,
                status_sesi = 'Ditutup',
                waktu_selesai = NOW()
            WHERE id_sesi = %s
        """
        cursor.execute(
            query_update,
            (saldo_akhir_tercatat, decimal.Decimal(saldo_akhir_aktual), nama_kasir_penutup, id_sesi)
        )

        # (Update produk F&B - Kode ini sudah benar)
        query_update_produk = "UPDATE produk_fnb SET status_ketersediaan = 'Inactive'"
        cursor.execute(query_update_produk)

        connection.commit()

        return jsonify({"message": "OK", "info": "Sesi kasir berhasil ditutup"}), 200

    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --- PERBAIKI HELPER FUNCTION INI ---
def serialize_session(session_dict):
    if not session_dict:
        return None

    serialized = {}
    for key, value in session_dict.items():
        # --- PERUBAHAN DI SINI ---
        # Kita tidak lagi menggunakan 'datetime.datetime' atau 'datetime.date'
        # Cukup 'datetime' dan 'date' karena kita mengimpornya langsung
        if isinstance(value, (datetime, date)):
            # --- AKHIR PERUBAHAN ---
            serialized[key] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value
    return serialized
# --- AKHIR PERBAIKAN ---


# (Asumsi Anda punya endpoint ini di backend)

@kasir_endpoints.route('/sesi/all-open', methods=['GET'])
@jwt_required()
def get_all_open_sessions():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # --- PERBAIKAN DI SINI ---
        # Pastikan 's.id_sesi' ada di dalam SELECT
        query = """
            SELECT 
                s.id_sesi, -- <-- PASTIKAN INI ADA
                s.nama_sesi, 
                s.waktu_mulai, 
                s.saldo_awal, 
                u.nama as nama_kasir 
            FROM sesi_kasir s
            JOIN users u ON s.id_user_kasir = u.id_user
            WHERE s.status_sesi = 'Dibuka'
            ORDER BY s.waktu_mulai DESC
        """
        # --- AKHIR PERBAIKAN ---
        
        cursor.execute(query)
        sessions = cursor.fetchall()
        
        # (Pastikan Anda menggunakan 'serialize_session' untuk menangani datetime/decimal)
        safe_sessions = [serialize_session(s) for s in sessions] 
        
        return jsonify({"message": "OK", "sessions": safe_sessions}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# --- ENDPOINT BARU 2: Mendapatkan sesi yang baru ditutup (LIMIT 10) ---
@kasir_endpoints.route('/sesi/recent-closed', methods=['GET'])
@jwt_required()
def get_recent_closed_sessions():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT s.*, u.nama as nama_kasir
            FROM sesi_kasir s
            JOIN users u ON s.id_user_kasir = u.id_user
            WHERE s.status_sesi = 'Ditutup'
            ORDER BY s.waktu_selesai DESC
            LIMIT 10
        """
        cursor.execute(query)
        sessions = cursor.fetchall()
        safe_sessions = [serialize_session(s) for s in sessions]
        return jsonify({"message": "OK", "sessions": safe_sessions}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --- ENDPOINT BARU 3: Untuk "Mengambil Alih" sesi yang terbuka ---
@kasir_endpoints.route('/sesi/takeover', methods=['POST'])
@jwt_required()
def takeover_session():
    # Dapatkan ID kasir BARU (yang sedang login)
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir_baru = jwt_identity.get('id_user')
        if not id_user_kasir_baru:
            return jsonify({"message": "ERROR", "error": "Token tidak valid."}), 401
    except AttributeError:
        id_user_kasir_baru = jwt_identity

    data = request.get_json()
    id_sesi_ambil_alih = data.get('id_sesi')
    if not id_sesi_ambil_alih:
        return jsonify({"message": "ERROR", "error": "ID Sesi diperlukan."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Cek apakah kasir BARU ini sudah punya sesi aktif
        cursor.execute(
            "SELECT id_sesi FROM sesi_kasir WHERE id_user_kasir = %s AND status_sesi = 'Dibuka'", (id_user_kasir_baru,))
        sesi_aktif_sendiri = cursor.fetchone()
        if sesi_aktif_sendiri:
            return jsonify({"message": "ERROR", "error": "Anda sudah memiliki sesi aktif. Tutup sesi Anda saat ini terlebih dahulu."}), 400

        # Update sesi yang dituju dengan ID kasir BARU
        query = """
            UPDATE sesi_kasir
            SET id_user_kasir = %s
            WHERE id_sesi = %s AND status_sesi = 'Dibuka'
        """
        cursor.execute(query, (id_user_kasir_baru, id_sesi_ambil_alih))

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Sesi tidak ditemukan atau sudah ditutup."}), 404

        connection.commit()
        return jsonify({"message": "OK", "info": "Sesi berhasil diambil alih."}), 200
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --- PERBAIKI ENDPOINT INI ---
@kasir_endpoints.route('/sesi/aktif', methods=['GET'])
@jwt_required()
def get_sesi_aktif():
    # Ekstrak ID user (Kode ini sudah benar dari perbaikan sebelumnya)
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERUBAHAN DI SINI: Tambahkan JOIN ke tabel users ---
        query = """
            SELECT s.*, u.nama as nama_kasir 
            FROM sesi_kasir s
            JOIN users u ON s.id_user_kasir = u.id_user 
            WHERE s.id_user_kasir = %s AND s.status_sesi = 'Dibuka' 
            LIMIT 1
        """
        cursor.execute(query, (id_user_kasir,))
        # --- AKHIR PERUBAHAN ---

        sesi_aktif_raw = cursor.fetchone()

        if sesi_aktif_raw:
            # Serialisasi hasil (Kode ini sudah benar)
            sesi_aktif_safe = serialize_session(sesi_aktif_raw)
            return jsonify({"message": "OK", "session": sesi_aktif_safe}), 200
        else:
            return jsonify({"message": "OK", "session": None}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --- 4. ENDPOINT UNTUK DAPATKAN REKOMENDASI SALDO AWAL ---
@kasir_endpoints.route('/sesi/saldo-terakhir', methods=['GET'])
@jwt_required()
def get_saldo_terakhir():
    # Mengambil 'saldo_akhir_aktual' dari sesi YANG PALING TERAKHIR DITUTUP
    # Ini sesuai deskripsi "sesuai uang dari shift 3"
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT saldo_akhir_aktual FROM sesi_kasir 
            WHERE status_sesi = 'Ditutup' 
            ORDER BY waktu_selesai DESC 
            LIMIT 1
        """)
        last_session = cursor.fetchone()

        saldo = 0.00
        if last_session:
            saldo = last_session['saldo_akhir_aktual']

        return jsonify({"message": "OK", "saldo_terakhir": saldo}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def calculate_totals_and_validate_items(items_frontend):
    """
    Helper untuk menghitung subtotal dan memvalidasi item dari data frontend.
    Mengembalikan subtotal (Decimal), daftar item valid untuk DB, atau error.
    """
    subtotal_backend = decimal.Decimal('0.00')
    valid_detail_items_for_db = []

    for item in items_frontend:
        try:
            # Gunakan get() untuk default value jika kunci tidak ada
            harga_str = item.get('price')
            jumlah_str = item.get('qty')
            id_produk_str = item.get('id')

            if harga_str is None or jumlah_str is None or id_produk_str is None:
                raise ValueError(f"Data item tidak lengkap: {item}")

            harga = decimal.Decimal(harga_str)
            jumlah = int(jumlah_str)
            id_produk = int(id_produk_str)
            catatan = item.get('note')  # Note bisa None/kosong

            if jumlah <= 0:
                # Abaikan item dengan qty 0 atau negatif, atau lemparkan error jika perlu
                # raise ValueError(f"Jumlah item tidak valid: {jumlah} untuk produk ID {id_produk}")
                continue  # Lewati item ini

            # Validasi tambahan (opsional): Cek apakah harga sesuai dengan DB?
            # cursor.execute("SELECT harga FROM produk_fnb WHERE id_produk = %s", (id_produk,))
            # db_product = cursor.fetchone()
            # if not db_product or decimal.Decimal(db_product['harga']) != harga:
            #     raise ValueError(f"Harga produk ID {id_produk} tidak cocok.")

            subtotal_backend += harga * jumlah
            valid_detail_items_for_db.append({
                'id_produk': id_produk,
                'jumlah': jumlah,
                'harga_saat_order': harga,  # Simpan sebagai Decimal dulu
                'catatan_pesanan': catatan
            })
        except (KeyError, ValueError, TypeError, decimal.InvalidOperation) as e:
            # Kembalikan pesan error yang jelas
            return None, None, f"Data item tidak valid: {str(e)} pada item {item}"
        except Exception as e:
            # Tangkap error tak terduga lainnya
            return None, None, f"Error validasi item: {str(e)}"

    if not valid_detail_items_for_db:
        return None, None, "Tidak ada item valid dalam pesanan."
    if subtotal_backend <= 0:
        return None, None, "Subtotal pesanan tidak valid (<= 0)."

    return subtotal_backend, valid_detail_items_for_db, None  # Sukses


def get_tax_percentage(cursor):
    """Helper untuk mengambil persentase pajak dari tabel settings."""
    try:
        cursor.execute(
            "SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
        setting_pajak = cursor.fetchone()
        if setting_pajak and setting_pajak.get('value'):
            return decimal.Decimal(setting_pajak['value'])
        else:
            print(
                "Warning: Setting PAJAK_FNB_PERSEN tidak ditemukan atau kosong. Menggunakan default 10%.")
            return decimal.Decimal('10.00')
    except (mysql.connector.Error, decimal.InvalidOperation) as e:
        print(
            f"Error mengambil atau parsing pajak dari DB: {e}. Menggunakan default 10%.")
        return decimal.Decimal('10.00')

# --- ENDPOINT SIMPAN ORDER ---


@kasir_endpoints.route('/save-order', methods=['POST'])
@jwt_required()
def save_kasir_order():
    """
    Menyimpan order F&B + Ruangan dari Kasir dengan status 'Disimpan'.
    Memvalidasi sesi DAN jadwal ruangan.
    MODIFIED: Sekarang menyimpan discount_percentage DAN discount_nominal.
    """
    
    # 1. Dapatkan ID Kasir
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity

    connection = None
    cursor = None
    try:
        data = request.get_json()
        if not data or 'items' not in data or not isinstance(data['items'], list):
            return jsonify({"message": "ERROR", "error": "Format data order tidak valid."}), 400

        # 2. Ambil & Validasi Sesi
        id_sesi_aktif = data.get('id_sesi')
        if not id_sesi_aktif:
            return jsonify({"message": "ERROR", "error": "ID Sesi (id_sesi) tidak ada dalam request body."}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT id_sesi FROM sesi_kasir WHERE id_sesi = %s AND status_sesi = 'Dibuka' LIMIT 1", (id_sesi_aktif,))
        if not cursor.fetchone():
            return jsonify({"message": "ERROR", "error": "Sesi yang Anda ikuti sudah ditutup atau tidak valid."}), 403

        # 3. Ekstrak data
        customer_name = data.get('customerName', 'Guest')
        order_type_frontend = data.get('orderType')
        room = data.get('room') if order_type_frontend == 'dinein' else None
        items_frontend = data.get('items', [])
        
        # --- PERUBAHAN 1: Ambil data diskon lengkap ---
        discount_percentage_frontend = data.get('discountPercentage', 0)
        discount_nominal_frontend = data.get('discountNominal', 0) # <-- Tambahkan ini
        # ----------------------------------------------

        fnb_type_map = {'dinein': 'Dine In', 'takeaway': 'Takeaway', 'pickup': 'Pick Up'}
        fnb_type_db = fnb_type_map.get(order_type_frontend)
        if not fnb_type_db:
            return jsonify({"message": "ERROR", "error": f"Tipe order '{order_type_frontend}' tidak valid."}), 400

        # 4. Cek bentrok jadwal SEBELUM menghitung/menyimpan
        conflict_error = check_booking_conflicts(cursor, items_frontend)
        if conflict_error:
            return jsonify({"message": "ERROR", "error": conflict_error}), 409 # 409 Conflict

        # 5. Gunakan helper kalkulasi baru
        # Pastikan helper calculate_order_totals menerima parameter nominal
        subtotal_backend, discount_nominal_backend, \
        pajak_nominal_backend, total_harga_final_backend, \
        pajak_persen_db = calculate_order_totals(
            cursor, 
            items_frontend, 
            discount_percentage_frontend, 
            discount_nominal_frontend # <-- Kirim ke helper
        )

        # 6. Insert ke tabel 'transaksi' dengan status 'Disimpan'
        # --- PERUBAHAN 2: Tambahkan discount_nominal di Query ---
        booking_source = data.get('booking_source', 'KasirWalkIn')
        query_transaksi = """
            INSERT INTO transaksi (
                id_sesi, id_kasir_pembuat, nama_guest, lokasi_pemesanan, fnb_type,
                subtotal, 
                discount_percentage, discount_nominal,
                pajak_persen, pajak_nominal, total_harga_final,
                status_pembayaran, status_order, tanggal_transaksi, id_promo,
                booking_source  -- <--- TAMBAH KOLOM INI
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Disimpan', 'Baru', NOW(), %s, %s)
        """
        values_transaksi = (
            id_sesi_aktif, id_user_kasir,
            customer_name, room, fnb_type_db,
            subtotal_backend, 
            discount_percentage_frontend, discount_nominal_backend,
            pajak_persen_db, pajak_nominal_backend, total_harga_final_backend,
            None, # id_promo
            booking_source # <--- MASUKKAN VALUE
        )
        # -------------------------------------------------------
        
        cursor.execute(query_transaksi, values_transaksi)
        id_transaksi_baru = cursor.lastrowid

        # 7. Gunakan helper pemroses item baru
        process_order_items(cursor, id_transaksi_baru, items_frontend)

        connection.commit() 

        return jsonify({
            "message": "OK",
            "info": "Order berhasil disimpan",
            "id_transaksi": id_transaksi_baru
        }), 201

    except (decimal.InvalidOperation, ValueError, TypeError) as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": f"Format data tidak valid: {str(e)}"}), 400
    except mysql.connector.Error as db_err:
        if connection: connection.rollback()
        print(f"Database error saat menyimpan order: {db_err}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": f"Database error: {db_err.msg}"}), 500
    except Exception as e:
        if connection: connection.rollback()
        print(f"Error saat menyimpan order kasir: {str(e)}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": "Terjadi kesalahan internal pada server."}), 500
    finally:
        if cursor: cursor.close()
        if connection and connection.is_connected():
            connection.close()
            

@kasir_endpoints.route('/saved-order/<int:id_transaksi>', methods=['GET'])
# @jwt_required() 
def get_saved_order_detail(id_transaksi):
    """
    Mengambil detail transaksi dan SEMUA item (F&B dan Ruangan)
    untuk order yang disimpan.
    FIXED: Mengambil discount_nominal dan discount_percentage.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil Data Header Transaksi
        cursor.execute("""
            SELECT
                id_transaksi, nama_guest, lokasi_pemesanan, fnb_type,
                subtotal, 
                discount_percentage, 
                discount_nominal, -- ✅ FIX: Wajib ambil kolom ini
                pajak_persen, pajak_nominal, total_harga_final,
                status_pembayaran, status_order, tanggal_transaksi
            FROM transaksi
            WHERE id_transaksi = %s AND status_pembayaran = 'Disimpan'
        """, (id_transaksi,))
        
        transaksi_data = cursor.fetchone()

        if not transaksi_data:
            return jsonify({"message": "ERROR", "error": "Order tersimpan tidak ditemukan atau statusnya bukan 'Disimpan'."}), 404

        # 2. Ambil detail item F&B (Tidak berubah)
        cursor.execute("""
            SELECT
                dof.id_detail_order, dof.id_produk, pf.nama_produk,
                dof.jumlah, dof.harga_saat_order, dof.catatan_pesanan,
                dof.status_pesanan,
                k.id_tenant AS merchantId, k.nama_kategori AS category,
                pf.status_ketersediaan
            FROM detail_order_fnb dof
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk k ON pf.id_kategori = k.id_kategori
            WHERE dof.id_transaksi = %s
            ORDER BY dof.id_detail_order ASC
        """, (id_transaksi,))
        detail_items_fnb = cursor.fetchall()
        
        # 3. Ambil detail item Ruangan (Tidak berubah)
        cursor.execute("""
            SELECT 
                br.id_booking, br.id_ruangan, r.nama_ruangan,
                br.waktu_mulai, br.waktu_selesai, br.durasi,
                (br.durasi / 60) AS durasi_jam,
                HOUR(br.waktu_mulai) AS waktu_mulai_jam,
                br.harga_saat_booking AS harga_paket 
            FROM booking_ruangan br
            JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            WHERE br.id_transaksi = %s
        """, (id_transaksi,))
        detail_items_room = cursor.fetchall()
        
        # 4. Format Items (Mapping Data)
        response_items = []
        
        for item in detail_items_fnb:
            response_items.append({
                "id": item['id_produk'],
                "cartId": f"fnb_{item['id_produk']}_{item.get('catatan_pesanan') or 'no-note'}",
                "type": "fnb",
                "name": item['nama_produk'],
                "price": float(item['harga_saat_order']),
                "qty": item['jumlah'],
                "note": item['catatan_pesanan'],
                "merchantId": item['merchantId'],
                "category": item['category'],
                "available": item['status_ketersediaan'] == 'Active'
            })
            
        for item in detail_items_room:
            start_hour = item['waktu_mulai'].hour
            end_hour = item['waktu_selesai'].hour
            response_items.append({
                "id": item['id_ruangan'],
                "cartId": f"room_{item['id_ruangan']}_{start_hour}",
                "type": "room",
                "name": item['nama_ruangan'],
                "price": float(item['harga_paket']),
                "qty": 1,
                "note": f"Booking {start_hour:02d}:00 - {end_hour:02d}:00",
                "bookingData": {
                    "id_ruangan": item['id_ruangan'],
                    "durasi_jam": int(item['durasi_jam']),
                    "waktu_mulai_jam": start_hour,
                    "total_harga_final": float(item['harga_paket'])
                }
            })

        # 5. Susun Response Akhir
        response_data = {
            "id_transaksi": transaksi_data['id_transaksi'],
            "customerName": transaksi_data['nama_guest'],
            "orderType": transaksi_data['fnb_type'].lower().replace(" ", "") if transaksi_data['fnb_type'] else "dinein",
            "room": transaksi_data['lokasi_pemesanan'],
            
            "subtotal": float(transaksi_data['subtotal'] or 0),
            "taxPercentage": float(transaksi_data['pajak_persen'] or 0),
            "taxNominal": float(transaksi_data['pajak_nominal'] or 0),
            "totalAmount": float(transaksi_data['total_harga_final'] or 0),
            
            "tanggal_transaksi": transaksi_data['tanggal_transaksi'].isoformat() if transaksi_data['tanggal_transaksi'] else None,
            
            # ✅ FIX: Pastikan kedua field ini terkirim
            "discountPercentage": float(transaksi_data.get('discount_percentage', 0.0) or 0), 
            "discountNominal": float(transaksi_data.get('discount_nominal', 0.0) or 0), 
            
            "items": response_items
        }

        return jsonify(response_data), 200

    except mysql.connector.Error as db_err:
        print(f"Database error: {db_err}")
        return jsonify({"message": "ERROR", "error": f"Database error: {db_err.msg}"}), 500
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
                    

@kasir_endpoints.route('/pay-saved-order/<int:id_transaksi>', methods=['POST'])
@jwt_required()
def pay_saved_order(id_transaksi):
    # 1. Dapatkan ID Kasir
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
    except AttributeError:
        id_user_kasir = jwt_identity

    connection = None
    cursor = None
    try:
        data = request.get_json()
        if not data: return jsonify({"message": "ERROR", "error": "Data invalid"}), 400

        # 2. Validasi Sesi
        id_sesi_aktif = data.get('id_sesi')
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT id_sesi FROM sesi_kasir WHERE id_sesi = %s AND status_sesi = 'Dibuka' LIMIT 1", (id_sesi_aktif,))
        if not cursor.fetchone():
            return jsonify({"message": "ERROR", "error": "Sesi tidak valid."}), 403
        
        # 3. Ekstrak Data & Validasi (Sama seperti create order)
        # ... (Kode ekstraksi data Anda sebelumnya) ...
        customer_name = data.get('customerName', 'Guest')
        order_type_frontend = data.get('orderType')
        room = data.get('room')
        payment_method_raw = data.get('paymentMethod')
        items_frontend_updated = data.get('items', [])
        discount_percentage_frontend = data.get('discountPercentage', 0)
        discount_nominal_frontend = data.get('discountNominal', 0)

        payment_map = {"QRIS": "Non-Tunai", "CASH": "Tunai", "DEBIT": "Non-Tunai"}
        metode_pembayaran_db = payment_map.get(payment_method_raw)
        
        uang_diterima_fe = data.get('uang_diterima', None)
        kembalian_fe = data.get('kembalian', None)
        uang_diterima_db = uang_diterima_fe if metode_pembayaran_db == 'Tunai' else None
        kembalian_db = kembalian_fe if metode_pembayaran_db == 'Tunai' else None

        # 4. Cek Status Order
        cursor.execute("SELECT status_pembayaran FROM transaksi WHERE id_transaksi = %s", (id_transaksi,))
        existing_order = cursor.fetchone()
        if not existing_order or existing_order['status_pembayaran'] != 'Disimpan':
            return jsonify({"message": "ERROR", "error": "Order tidak valid/sudah dibayar."}), 400
            
        # 5. Cek Konflik
        conflict_error = check_booking_conflicts(cursor, items_frontend_updated, id_transaksi_to_exclude=id_transaksi)
        if conflict_error:
             return jsonify({"message": "ERROR", "error": conflict_error}), 409

        # 6. Kalkulasi Ulang
        subtotal_backend, discount_nominal_backend, \
        pajak_nominal_backend, total_harga_final_backend, \
        pajak_persen_db = calculate_order_totals(
            cursor, items_frontend_updated, discount_percentage_frontend, discount_nominal_frontend
        )

        booking_source = data.get('booking_source', 'KasirWalkIn')

        query_update = """
            UPDATE transaksi SET
                nama_guest=%s, lokasi_pemesanan=%s, metode_pembayaran=%s,
                subtotal=%s, discount_percentage=%s, discount_nominal=%s,
                pajak_persen=%s, pajak_nominal=%s, total_harga_final=%s,
                status_pembayaran='Lunas', tanggal_transaksi=NOW(),
                id_sesi=%s, id_kasir_pembuat=%s, uang_diterima=%s, kembalian=%s,
                booking_source=%s  -- <--- UPDATE KOLOM INI
            WHERE id_transaksi=%s
        """
        values = (
            customer_name, room, metode_pembayaran_db,
            subtotal_backend, discount_percentage_frontend, discount_nominal_backend,
            pajak_persen_db, pajak_nominal_backend, total_harga_final_backend,
            id_sesi_aktif, id_user_kasir, uang_diterima_db, kembalian_db,
            booking_source,
            id_transaksi,
        )
        cursor.execute(query_update, values)

        # 8. Update Detail Items
        cursor.execute("DELETE FROM detail_order_fnb WHERE id_transaksi = %s", (id_transaksi,))
        cursor.execute("DELETE FROM booking_ruangan WHERE id_transaksi = %s", (id_transaksi,))
        process_order_items(cursor, id_transaksi, items_frontend_updated)

        # --- 9. LOGIKA VOUCHER OTOMATIS (NEW) ---
        voucher_response = None
        
        # Cek apakah voucher sudah pernah dibuat sebelumnya untuk transaksi ini?
        cursor.execute("SELECT id_voucher FROM transaksi_voucher WHERE id_transaksi = %s", (id_transaksi,))
        existing_voucher = cursor.fetchone()
        
        # Jika belum ada voucher DAN total > 0, generate baru
        if not existing_voucher and total_harga_final_backend > 0:
            durasi = get_voucher_duration_by_price(total_harga_final_backend)
            
            if durasi > 0:
                profile_name = f"shop-{durasi}H"
                user_mikrotik, pass_mikrotik = generate_voucher_mikrotik(
                    durasi, 
                    profile_name=profile_name, 
                    comment=f"Pay-Saved Trx #{id_transaksi}"
                )
                
                if user_mikrotik:
                    cursor.execute("""
                        INSERT INTO transaksi_voucher 
                        (id_transaksi, mikrotik_user, mikrotik_pass, mikrotik_profile, durasi_jam)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_transaksi, user_mikrotik, pass_mikrotik, profile_name, durasi))
                    
                    voucher_response = {
                        "code": user_mikrotik,
                        "profile": profile_name,
                        "duration": durasi
                    }
        # ----------------------------------------

        connection.commit()

        return jsonify({
            "message": "OK",
            "info": f"Order #{id_transaksi} berhasil dibayar.",
            "id_transaksi": id_transaksi,
            "voucher": voucher_response # <-- Kirim voucher ke frontend
        }), 200

    except Exception as e:
        if connection: connection.rollback()
        print(f"Error pay saved order: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
            
@kasir_endpoints.route('/updatePaymentStatus/<int:trx_id>', methods=['PUT'])
# @jwt_required() # 💎 Uncomment ini jika Anda menggunakan otentikasi JWT
def update_payment_status(trx_id):
    """Mengubah status pembayaran transaksi menjadi 'Lunas'."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
        UPDATE transaksi 
        SET status_pembayaran = 'Lunas'
        WHERE id_transaksi = %s
        """
        # Catatan: Saya mengasumsikan 'Non-Tunai' sebagai default saat kasir menekan tombol.
        # Anda bisa juga menerima 'metode_pembayaran' dari body request jika perlu.

        cursor.execute(query, (trx_id,))

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Transaksi tidak ditemukan"}), 404

        connection.commit()

        return jsonify({
            "message": "OK",
            "data": {"id_transaksi": trx_id, "status_pembayaran": "Lunas"}
        }), 200

    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@kasir_endpoints.route('/updateBatalStatus/<int:trx_id>', methods=['PUT'])
# @jwt_required() # 💎 Uncomment ini jika Anda menggunakan otentikasi JWT
def update_batal_status(trx_id):
    """Mengubah status pembayaran transaksi menjadi 'Lunas'."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
        UPDATE transaksi 
        SET status_pembayaran = 'Dibatalkan'
        WHERE id_transaksi = %s
        """
        # Catatan: Saya mengasumsikan 'Non-Tunai' sebagai default saat kasir menekan tombol.
        # Anda bisa juga menerima 'metode_pembayaran' dari body request jika perlu.

        cursor.execute(query, (trx_id,))

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Transaksi tidak ditemukan"}), 404

        connection.commit()

        return jsonify({
            "message": "OK",
            "data": {"id_transaksi": trx_id, "status_pembayaran": "Lunas"}
        }), 200

    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =========================================================================================
# ENDPOINT 3: (BARU) Mengambil data semua ruangan & jadwalnya untuk hari ini
# =========================================================================================
@kasir_endpoints.route('/rooms-todays', methods=['GET'])
def get_rooms_for_today():
    """
    Mengambil daftar semua ruangan beserta paket harganya dan
    jadwal jam yang sudah dibooking untuk hari ini saja.
    (Logika ini tidak berubah, sudah benar)
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua data ruangan
        query_rooms = """
            SELECT
                r.id_ruangan, r.nama_ruangan, r.harga_per_jam,
                r.kapasitas, kr.nama_kategori
            FROM ruangan r
            JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
            WHERE r.status_ketersediaan = 'Active'
            ORDER BY r.nama_ruangan;
        """
        cursor.execute(query_rooms)
        rooms = cursor.fetchall()

        # Ambil semua paket harga
        cursor.execute(
            "SELECT id_ruangan, durasi_jam, harga_paket FROM paket_harga_ruangan;")
        all_packages = cursor.fetchall()

        # 2. Ambil semua jam yang sudah dibooking HARI INI
        query_booked = """
            SELECT id_ruangan, waktu_mulai, waktu_selesai
            FROM booking_ruangan
            WHERE DATE(waktu_mulai) = CURDATE();
        """
        cursor.execute(query_booked)
        bookings_today = cursor.fetchall()

        # 3. Proses dan gabungkan data
        for room in rooms:
            room['paket_harga'] = [
                pkg for pkg in all_packages if pkg['id_ruangan'] == room['id_ruangan']]
            
            room['booked_hours'] = []
            room_bookings = [
                b for b in bookings_today if b['id_ruangan'] == room['id_ruangan']]
            for booking in room_bookings:
                start_hour = booking['waktu_mulai'].hour
                end_hour = booking['waktu_selesai'].hour
                for hour in range(start_hour, end_hour):
                    room['booked_hours'].append(hour)

        return jsonify({"message": "OK", "datas": rooms}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# =========================================================================================
# ENDPOINT 4: (BARU) Membuat booking ruangan baru dari kasir
# =========================================================================================
@kasir_endpoints.route('/book-room', methods=['POST'])
@jwt_required()
def create_room_booking():
    """
    Menerima data booking ruangan dari kasir, memvalidasi sesi,
    dan menyimpan ID Kasir (pembuat) DAN ID Sesi (dari frontend).
    """
    
    # 1. Dapatkan ID KASIR PEMBUAT (dari token)
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity # Fallback

    connection = None
    cursor = None
    try:
        data = request.get_json()
        
        # --- PERBAIKAN UTAMA DIMULAI DI SINI ---

        # 2. Ambil 'id_sesi' DARI FRONTEND (bukan dicari)
        id_sesi_aktif = data.get('id_sesi')
        if not id_sesi_aktif:
            return jsonify({"message": "ERROR", "error": "ID Sesi (id_sesi) tidak ada dalam request body."}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True) 

        # 3. Validasi 'id_sesi' yang dikirim frontend
        cursor.execute("""
            SELECT id_sesi FROM sesi_kasir 
            WHERE id_sesi = %s AND status_sesi = 'Dibuka' 
            LIMIT 1
        """, (id_sesi_aktif,))
        sesi_valid = cursor.fetchone()

        if not sesi_valid:
            return jsonify({"message": "ERROR", "error": "Sesi yang Anda ikuti sudah ditutup atau tidak valid."}), 403
        
        # --- AKHIR PERBAIKAN UTAMA ---

        # 4. Validasi data (SAMA)
        required_fields = ['id_ruangan', 'durasi_jam', 'waktu_mulai_jam', 'nama_guest', 'metode_pembayaran', 'total_harga_final']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "ERROR", "error": "Data tidak lengkap"}), 400

        # 5. Siapkan waktu mulai dan selesai (SAMA)
        today_str = datetime.now().strftime('%Y-%m-%d')
        start_hour = int(data['waktu_mulai_jam'])
        end_hour = start_hour + int(data['durasi_jam'])
        waktu_mulai = f"{today_str} {start_hour:02d}:00:00"
        waktu_selesai = f"{today_str} {end_hour:02d}:00:00"
        
        booking_source = data.get("booking_source", "KasirWalkIn")

        # 6. Validasi jadwal bentrok (SAMA)
        query_check = """
            SELECT COUNT(*) as count FROM booking_ruangan
            WHERE id_ruangan = %s AND (%s < waktu_selesai AND %s > waktu_mulai)
        """
        cursor.execute(query_check, (data['id_ruangan'], waktu_mulai, waktu_selesai))
        
        if cursor.fetchone()['count'] > 0:
            return jsonify({"message": "ERROR", "error": f"Jadwal pada jam {start_hour:02d}:00 - {end_hour:02d}:00 sudah terisi."}), 409

        # 7. Insert ke tabel 'transaksi' (SAMA, ini sudah benar)
        query_transaksi = """
            INSERT INTO transaksi (
                id_user, id_sesi, id_kasir_pembuat, 
                nama_guest, metode_pembayaran, total_harga_final, 
                status_pembayaran, status_order, booking_source,
                tanggal_transaksi
            ) VALUES (%s, %s, %s, %s, %s, %s, 'Lunas', 'Selesai', %s, NOW());
        """
        transaksi_values = (
            None,                 # id_user (Pelanggan)
            id_sesi_aktif,        # id_sesi (DARI REQUEST BODY)
            id_user_kasir,        # id_kasir_pembuat (DARI TOKEN)
            data['nama_guest'],
            data['metode_pembayaran'].capitalize(),
            data['total_harga_final'],
            booking_source
        )
        
        cursor.execute(query_transaksi, transaksi_values)
        id_transaksi_baru = cursor.lastrowid

        # 8. Insert ke tabel 'booking_ruangan' (SAMA, ini sudah benar)
        query_booking = """
            INSERT INTO booking_ruangan (
                id_transaksi, id_ruangan, waktu_mulai, waktu_selesai, durasi
            ) VALUES (%s, %s, %s, %s, %s);
        """
        durasi_dalam_menit = int(data['durasi_jam']) * 60 
        booking_values = (
            id_transaksi_baru,
            data['id_ruangan'],
            waktu_mulai,
            waktu_selesai,
            durasi_dalam_menit 
        )
        
        cursor.execute(query_booking, booking_values)

        connection.commit() 

        return jsonify({
            "message": "OK",
            "info": "Booking ruangan berhasil dibuat",
            "id_transaksi": id_transaksi_baru
        }), 201

    except mysql.connector.Error as db_err: 
        if connection: connection.rollback()
        traceback.print_exc()
        if 'id_kasir_pembuat' in str(db_err):
            return jsonify({"message": "ERROR", "error": "Database error. Pastikan kolom 'id_kasir_pembuat' sudah ditambahkan ke tabel 'transaksi'."}), 500
        return jsonify({"message": "ERROR", "error": f"Database error: {db_err}"}), 500
    except Exception as e:
        if connection:
            connection.rollback() 
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
                 

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
        available_units_data = [row['nama_ruangan']
                                for row in cursor.fetchall()]

        # --- 4. Data Sewa (Aktif, Selesai, & Akan Datang Hari Ini) ---
        query_rentals = """
            SELECT 
                br.id_booking AS id,
                COALESCE(u.nama, t.nama_guest) AS client,
                r.nama_ruangan AS unit,
                t.total_harga_final AS price,
                br.waktu_mulai,
                br.waktu_selesai,
                t.booking_source  -- <-- Tambahkan baris ini
            FROM booking_ruangan br
            JOIN transaksi t ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            LEFT JOIN users u ON t.id_user = u.id_user
            WHERE DATE(br.waktu_mulai) = CURDATE()
            ORDER BY br.waktu_mulai ASC;
        """
        cursor.execute(query_rentals)
        all_rentals_today = cursor.fetchall()
        # MODIFIKASI: Buat 3 list untuk menampung status yang berbeda
        rentals_upcoming = []
        rentals_active = []
        rentals_finish = []

        now = datetime.now()
        for rental in all_rentals_today:
            # Format data dasar
            rental['price'] = int(rental['price'])
            rental['date'] = rental['waktu_mulai'].strftime('%d/%m/%Y %H:%M')

            waktu_mulai_obj = rental['waktu_mulai']
            waktu_selesai_obj = rental['waktu_selesai']

            rental['waktu_mulai'] = waktu_mulai_obj.isoformat()
            rental['waktu_selesai'] = waktu_selesai_obj.isoformat()

            # MODIFIKASI: Logika untuk memisahkan booking
            if now < waktu_mulai_obj:
                # Jika waktu sekarang masih sebelum waktu mulai
                rentals_upcoming.append(rental)
            elif now >= waktu_mulai_obj and now <= waktu_selesai_obj:
                # Jika waktu sekarang berada di antara waktu mulai dan selesai
                rentals_active.append(rental)
            else:
                # Jika waktu sekarang sudah melewati waktu selesai
                rentals_finish.append(rental)

        return jsonify({
            "message": "OK",
            "datas": {
                "summary": summary_data,
                "spaceTypes": space_types_data,
                "availableUnits": available_units_data,
                "rentals": {
                    # MODIFIKASI: Kirim ketiga list ke frontend
                    "upcoming": rentals_upcoming,
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
    (Logika ini tidak berubah, sudah benar)
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua produk F&B (aktif dan inaktif)
        query_products = """
            SELECT
                p.id_produk AS id,
                p.nama_produk AS name,
                p.harga AS price,
                p.status_ketersediaan,
                p.status_visibilitas,
                k.id_tenant AS merchantId,
                k.nama_kategori AS category
            FROM produk_fnb p
            JOIN kategori_produk k ON p.id_kategori = k.id_kategori
            ORDER BY p.nama_produk;
        """
        cursor.execute(query_products)
        products_raw = cursor.fetchall()
        products = [
            {**p, "available": p.pop('status_ketersediaan') == 'Active'}
            for p in products_raw
        ]

        # 2. Ambil kategori tenant (merchant)
        query_merchants = "SELECT id_tenant AS id, nama_tenant AS name FROM tenants ORDER BY name;"
        cursor.execute(query_merchants)
        merchant_categories = cursor.fetchall()
        merchant_categories.insert(
            0, {'id': 'all_merchants', 'name': 'All Merchants'})

        # 3. Ambil kategori produk (tipe)
        query_product_types = "SELECT DISTINCT nama_kategori AS name FROM kategori_produk ORDER BY name;"
        cursor.execute(query_product_types)
        product_types_raw = cursor.fetchall()
        product_type_categories = [{'id': 'all_types', 'name': 'All Types'}]
        product_type_categories.extend(
            [{'id': pt['name'], 'name': pt['name']} for pt in product_types_raw])

        # 4. Data tipe order
        order_types = [
            {'id': 'dinein', 'name': 'Dine In'},
            {'id': 'takeaway', 'name': 'Take Away'},
            {'id': 'pickup', 'name': 'Pick Up'}
        ]

        # 5. Ambil Persentase Pajak F&B
        cursor.execute(
            "SELECT `value` FROM `settings` WHERE `key` = 'PAJAK_FNB_PERSEN'")
        setting_pajak = cursor.fetchone()
        pajak_fnb_persen = 10.0
        if setting_pajak and setting_pajak['value']:
            try:
                pajak_fnb_persen = float(setting_pajak['value'])
            except ValueError:
                print(
                    f"Warning: Nilai PAJAK_FNB_PERSEN ('{setting_pajak['value']}') di DB tidak valid. Menggunakan default {pajak_fnb_persen}%.")

        init_data = {
            "products": products,
            "merchantCategories": merchant_categories,
            "productTypeCategories": product_type_categories,
            "orderTypes": order_types,
            "taxRateFnbPercent": pajak_fnb_persen
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

# =========================================================================================
# ENDPOINT 2: Membuat order baru dari kasir
# =========================================================================================


# @kasir_endpoints.route('/order', methods=['POST'])
# def create_order():
#     """
#     Menerima data order dari frontend dan menyimpannya ke database.
#     Menggunakan transaksi untuk memastikan integritas data.
#     """
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         if not data or 'items' not in data or not data['items']:
#             return jsonify({"message": "ERROR", "error": "Invalid order data"}), 400

#         connection = get_connection()
#         cursor = connection.cursor()

#         # Mulai transaksi database
#         connection.start_transaction()

#         # 1. Insert ke tabel 'transaksi'
#         # Mapping tipe F&B dari frontend ke ENUM di DB
#         fnb_type_map = {
#             'dinein': 'Dine In',
#             'takeaway': 'Takeaway',
#             'pickup': 'Pick Up'
#         }
#         fnb_type = fnb_type_map.get(data.get('orderType'), 'Takeaway')

#         query_transaksi = """
#             INSERT INTO transaksi (
#                 nama_guest, lokasi_pemesanan, fnb_type, metode_pembayaran,
#                 total_harga_final, status_pembayaran, status_order
#             ) VALUES (%s, %s, %s, %s, %s, 'Lunas', 'Baru');
#         """
#         transaksi_values = (
#             data.get('customerName'),
#             data.get('room'),
#             fnb_type,
#             data.get('paymentMethod'),
#             data.get('totalAmount')
#         )
#         cursor.execute(query_transaksi, transaksi_values)

#         # Ambil ID dari transaksi yang baru saja dibuat
#         id_transaksi_baru = cursor.lastrowid

#         # 2. Insert setiap item ke tabel 'detail_order_fnb'
#         query_detail = """
#             INSERT INTO detail_order_fnb (
#                 id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan
#             ) VALUES (%s, %s, %s, %s, %s);
#         """
#         for item in data['items']:
#             detail_values = (
#                 id_transaksi_baru,
#                 item['id'],
#                 item['qty'],
#                 item['price'],
#                 item.get('note')
#             )
#             cursor.execute(query_detail, detail_values)

#         # Jika semua berhasil, commit transaksi
#         connection.commit()

#         return jsonify({
#             "message": "OK",
#             "info": "Order created successfully",
#             "id_transaksi": id_transaksi_baru
#         }), 201

#     except Exception as e:
#         # Jika terjadi error, batalkan semua perubahan
#         if connection:
#             connection.rollback()
#         traceback.print_exc()
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()
def get_voucher_duration_by_price(total_amount):
    """
    Menentukan durasi voucher berdasarkan total belanja.
    """
    if total_amount <= 0:
        return 0
    elif total_amount <= 50000:
        return 2
    elif total_amount <= 100000:
        return 4
    elif total_amount <= 150000:
        return 6
    else:
        return 8 # Maksimal 8 Jam untuk belanja > 150rb


# --- ENDPOINT 1: BUAT ORDER BARU ---
@kasir_endpoints.route('/order', methods=['POST'])
@jwt_required()
def create_kasir_order_with_tax():
    # 1. Dapatkan ID KASIR PEMBUAT
    jwt_identity = get_jwt_identity()
    try:
        id_user_kasir = jwt_identity.get('id_user')
        if not id_user_kasir:
            return jsonify({"message": "ERROR", "error": "Format token tidak valid."}), 401
    except AttributeError:
        id_user_kasir = jwt_identity 

    connection = None
    cursor = None
    try:
        data = request.get_json()
        # Validasi data standar
        if not data or 'items' not in data:
             return jsonify({"message": "ERROR", "error": "Data invalid"}), 400

        # 2. Ambil & Validasi Sesi
        id_sesi_aktif = data.get('id_sesi')
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT id_sesi FROM sesi_kasir WHERE id_sesi = %s AND status_sesi = 'Dibuka' LIMIT 1", (id_sesi_aktif,))
        if not cursor.fetchone():
            return jsonify({"message": "ERROR", "error": "Sesi tidak valid atau ditutup."}), 403

        # 3. Ekstrak Data
        customer_name = data.get('customerName', 'Guest')
        order_type_frontend = data.get('orderType')
        room = data.get('room')
        payment_method_raw = data.get('paymentMethod')
        items_frontend = data.get('items', [])
        discount_percentage_frontend = data.get('discountPercentage', 0)
        discount_nominal_frontend = data.get('discountNominal', 0)
        
        # Mapping Payment & F&B Type
        fnb_type_map = {'dinein': 'Dine In', 'takeaway': 'Takeaway', 'pickup': 'Pick Up'}
        fnb_type_db = fnb_type_map.get(order_type_frontend)
        
        payment_map = {"QRIS": "Non-Tunai", "CASH": "Tunai", "DEBIT": "Non-Tunai"}
        metode_pembayaran_db = payment_map.get(payment_method_raw)
        
        uang_diterima_fe = data.get('uang_diterima', None)
        kembalian_fe = data.get('kembalian', None)
        uang_diterima_db = uang_diterima_fe if metode_pembayaran_db == 'Tunai' else None
        kembalian_db = kembalian_fe if metode_pembayaran_db == 'Tunai' else None

        # 4. Cek Konflik Booking
        conflict_error = check_booking_conflicts(cursor, items_frontend)
        if conflict_error:
             return jsonify({"message": "ERROR", "error": conflict_error}), 409

        # 5. Kalkulasi Total
        subtotal_backend, discount_nominal_backend, \
        pajak_nominal_backend, total_harga_final_backend, \
        pajak_persen_db = calculate_order_totals(
            cursor, items_frontend, discount_percentage_frontend, discount_nominal_frontend
        )

        # 6. Insert Transaksi
        booking_source = data.get('booking_source', 'KasirWalkIn')

        # ... (kode validasi & kalkulasi) ...

        # 6. Insert Transaksi
        # PERBAIKAN: Tambahkan kolom booking_source
        # 6. Insert Transaksi
        query_transaksi = """
            INSERT INTO transaksi (
                id_user, id_sesi, id_kasir_pembuat, nama_guest, lokasi_pemesanan, 
                fnb_type, metode_pembayaran, uang_diterima, kembalian,
                subtotal, discount_percentage, discount_nominal,
                pajak_persen, pajak_nominal, total_harga_final,
                status_pembayaran, status_order, tanggal_transaksi,
                booking_source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Lunas', 'Baru', NOW(), %s)
        """
        # Perhatikan: Bagian akhir string di atas bersih, hanya "... NOW(), %s)"
        
        values = (
            data.get('id_user_pelanggan'), id_sesi_aktif, id_user_kasir, customer_name, room,
            fnb_type_db, metode_pembayaran_db, uang_diterima_db, kembalian_db,
            subtotal_backend, discount_percentage_frontend, discount_nominal_backend,
            pajak_persen_db, pajak_nominal_backend, total_harga_final_backend,
            booking_source
        )
        
        cursor.execute(query_transaksi, values)
        id_transaksi_baru = cursor.lastrowid

        # 7. Proses Item
        process_order_items(cursor, id_transaksi_baru, items_frontend)

        # --- 8. LOGIKA VOUCHER OTOMATIS (NEW) ---
        voucher_response = None
        
        # Hanya generate jika ada pembayaran (total > 0)
        if total_harga_final_backend > 0:
            # 1. Tentukan durasi berdasarkan total belanja
            durasi = get_voucher_duration_by_price(total_harga_final_backend)
            
            if durasi > 0:
                # PERBAIKAN: Gunakan huruf kecil 'shop-Xh'
                profile_name = f"shop-{durasi}h" 
                
                # 2. Panggil Mikrotik
                user_mikrotik, pass_mikrotik = generate_voucher_mikrotik(
                    durasi, 
                    profile_name=profile_name, 
                    comment=f"Trx #{id_transaksi_baru}"
                )
                
                if user_mikrotik:
                    # 3. Simpan ke Database
                    cursor.execute("""
                        INSERT INTO transaksi_voucher 
                        (id_transaksi, mikrotik_user, mikrotik_pass, mikrotik_profile, durasi_jam)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_transaksi_baru, user_mikrotik, pass_mikrotik, profile_name, durasi))
                    
                    # 4. Siapkan Data untuk Frontend
                    voucher_response = {
                        "code": user_mikrotik,
                        "profile": profile_name,
                        "duration": durasi
                    }
        # ----------------------------------------

        connection.commit()

        return jsonify({
            "message": "OK", 
            "info": "Order berhasil dibuat", 
            "id_transaksi": id_transaksi_baru,
            "voucher": voucher_response # <-- Kirim voucher ke frontend
        }), 201
    
    except Exception as e:
        if connection: connection.rollback()
        print(f"Error create order: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

        
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
        if cursor:
            cursor.close()
        if connection:
            connection.close()


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
                    # default jika null
                    order_type = row["fnb_type"] or "Takeaway"
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
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@kasir_endpoints.route('/readTransaksiKasirs', methods=['GET'])
@jwt_required()
def readTransaksiKasirs():
    """
    Ambil daftar transaksi UNTUK KASIR YANG LOGIN
    DI DALAM SESI GLOBAL YANG SEDANG AKTIF.
    MODIFIED: Mengambil data Voucher Wifi untuk keperluan Reprint.
    """
    connection = None
    cursor = None
    try:
        # 1. Dapatkan ID kasir dari token
        identity = get_jwt_identity() 
        current_kasir_id = identity['id_user'] 

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 2. Cari Sesi Aktif GLOBAL
        cursor.execute("""
            SELECT id_sesi 
            FROM sesi_kasir 
            WHERE status_sesi = 'Dibuka' 
            LIMIT 1
        """)
        sesi_aktif = cursor.fetchone()

        # 3. Jika tidak ada sesi aktif GLOBAL, kembalikan data kosong
        if not sesi_aktif:
            return jsonify({"message": "OK", "datas": []}), 200

        id_sesi_aktif = sesi_aktif['id_sesi'] 

        # 4. Query utama (Ambil Transaksi, F&B, dan Booking)
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

            -- Rincian Harga
            t.subtotal,
            t.pajak_nominal,
            t.pajak_persen,
            
            -- Rincian Kembalian
            t.uang_diterima,
            t.kembalian,
            
            -- Detail F&B
            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan,
            d.status_pesanan AS status_item, 
            tnt.nama_tenant,
            
            -- Detail Booking Ruangan
            b.id_booking,
            r.nama_ruangan,
            r.harga_per_jam,
            b.harga_saat_booking,
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
        LEFT JOIN kategori_produk k_prod ON p.id_kategori = k_prod.id_kategori
        LEFT JOIN tenants tnt ON k_prod.id_tenant = tnt.id_tenant
        LEFT JOIN booking_ruangan b ON t.id_transaksi = b.id_transaksi
        LEFT JOIN ruangan r ON b.id_ruangan = r.id_ruangan
        LEFT JOIN kategori_ruangan k ON r.id_kategori_ruangan = k.id_kategori_ruangan
        
        WHERE 
            t.id_sesi = %s AND t.id_kasir_pembuat = %s
            
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """

        # 5. Eksekusi query utama
        cursor.execute(query, (id_sesi_aktif, current_kasir_id)) 
        rows = cursor.fetchall()

        # --- PERUBAHAN BARU: AMBIL DATA VOUCHER ---
        # Kita ambil semua voucher yang terkait dengan transaksi yang ditemukan
        voucher_map = defaultdict(list)
        if rows:
            # Ambil semua ID Transaksi unik dari hasil query
            trx_ids = list(set(row['id_transaksi'] for row in rows))
            
            if trx_ids:
                # Buat placeholder untuk query IN (%s, %s, ...)
                format_strings = ','.join(['%s'] * len(trx_ids))
                
                # Query ke tabel transaksi_voucher
                cursor.execute(f"""
                    SELECT id_transaksi, mikrotik_user, mikrotik_profile, durasi_jam
                    FROM transaksi_voucher
                    WHERE id_transaksi IN ({format_strings})
                """, tuple(trx_ids))
                
                voucher_rows = cursor.fetchall()
                
                # Masukkan ke dictionary biar mudah dipacking
                for v in voucher_rows:
                    voucher_map[v['id_transaksi']].append(v)
        # ------------------------------------------

        # 6. Grouping data
        grouped_data = defaultdict(list)
        for row in rows:
            grouped_data[row["id_transaksi"]].append(row)

        final_data = []
        
        # 7. Proses penyusunan JSON akhir
        for trx_id, trx_rows in grouped_data.items():
            first_row = trx_rows[0]
            
            if first_row["jenis_transaksi"] not in ("fnb", "booking"):
                continue
                
            # Logika Status Order
            fnb_items = [r for r in trx_rows if r['id_detail_order'] is not None]
            overall_status = first_row["status_order"]
            if fnb_items:
                item_statuses = {item['status_item'] for item in fnb_items}
                if all(s == 'Selesai' for s in item_statuses):
                    overall_status = 'Selesai'
                elif all(s == 'Diproses' for s in item_statuses):
                    overall_status = 'Diproses'
                elif 'Selesai' in item_statuses and len(item_statuses) > 1:
                    overall_status = 'Sebagian Diproses'
                elif 'Diproses' in item_statuses:
                    overall_status = 'Diproses'
                elif all(s == 'Baru' for s in item_statuses):
                    overall_status = 'Baru'
            
            order_type = "Booking"
            if first_row["jenis_transaksi"] == "fnb":
                order_type = first_row["fnb_type"] or "Takeout"

            transaction_entry = {
                "id": trx_id,
                "customer": first_row["customer_name"],
                "location": first_row["lokasi_pemesanan"],
                "status_pesanan": overall_status, 
                "payment_status": first_row["status_pembayaran"],
                "payment_method": first_row["metode_pembayaran"],
                "total": float(first_row["total_harga_final"]),
                "time": first_row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                "type": order_type,
                
                # Rincian Harga
                "subtotal": float(first_row.get("subtotal") or 0),
                "tax_nominal": float(first_row.get("pajak_nominal") or 0),
                "tax_percent": float(first_row.get("pajak_persen") or 0),
                
                # Rincian Kembalian
                "uang_diterima": float(first_row.get("uang_diterima") or 0),
                "kembalian": float(first_row.get("kembalian") or 0),
                
                "items": [],
                "bookings": [],
                "vouchers": [] # <-- Field Baru untuk Voucher
            }
            
            # --- MASUKKAN DATA VOUCHER ---
            if trx_id in voucher_map:
                for v in voucher_map[trx_id]:
                    transaction_entry["vouchers"].append({
                        "code": v['mikrotik_user'],
                        "profile": v['mikrotik_profile'],
                        "duration": v['durasi_jam']
                    })
            # -----------------------------
            
            # Logika append items dan bookings
            processed_bookings = set()
            for row in trx_rows:
                if row["id_detail_order"]:
                    transaction_entry["items"].append({
                        "id_detail_order": row["id_detail_order"],
                        "product": row["nama_produk"],
                        "qty": row["jumlah"],
                        "price": float(row["harga_saat_order"]),
                        "note": row["catatan_pesanan"],
                        "status": row["status_item"],
                        "tenant_name": row["nama_tenant"] or "Lainnya"
                    })
                if row["id_booking"] and row["id_booking"] not in processed_bookings:
                    transaction_entry["bookings"].append({
                        "id_booking": row["id_booking"],
                        "room_name": row["nama_ruangan"],
                        "room_category": row["kategori_ruangan"],
                        "booked_price": float(row["harga_saat_booking"] or 0), 
                        "start_time": row["waktu_mulai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_mulai"] else None,
                        "end_time": row["waktu_selesai"].strftime("%Y-%m-%d %H:%M:%S") if row["waktu_selesai"] else None,
                        "duration": row["durasi"]
                    })
                    processed_bookings.add(row["id_booking"])
            
            final_data.append(transaction_entry)

        return jsonify({
            "message": "OK",
            "datas": final_data
        }), 200

    except Exception as e:
        traceback.print_exc() 
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
@kasir_endpoints.route('/merchantOrders', methods=['GET'])
def readMerchantOrders():
    """Ambil daftar order khusus F&B (merchant kasir)"""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. PERBARUI QUERY: Tambahkan 'd.status_pesanan'
        query = """
        SELECT 
            t.id_transaksi,
            COALESCE(u.nama, t.nama_guest) AS customer_name,
            t.status_pembayaran,
            t.metode_pembayaran,
            t.total_harga_final,
            t.tanggal_transaksi,
            t.fnb_type,

            d.id_detail_order,
            p.nama_produk,
            d.jumlah,
            d.harga_saat_order,
            d.catatan_pesanan,
            d.status_pesanan  -- ✅ PASTIKAN FIELD INI ADA
        FROM transaksi t
        LEFT JOIN users u ON t.id_user = u.id_user
        INNER JOIN detail_order_fnb d ON t.id_transaksi = d.id_transaksi
        LEFT JOIN produk_fnb p ON d.id_produk = p.id_produk
        ORDER BY t.tanggal_transaksi DESC, t.id_transaksi;
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # 2. PERBARUI LOGIKA: Agregasi data dulu, baru hitung status
        data = {}
        item_statuses = {} # Kamus untuk melacak status semua item

        for row in rows:
            trx_id = row["id_transaksi"]

            if trx_id not in data:
                data[trx_id] = {
                    "id": trx_id,
                    "name": row["customer_name"],
                    "code": f"INV-{trx_id:05d}",
                    # Status akan diisi nanti
                    "type": "FNB",
                    "fnb_type": row["fnb_type"], 
                    "payment_status": row["status_pembayaran"],
                    "payment_method": row["metode_pembayaran"],
                    "total": float(row["total_harga_final"]),
                    "time": row["tanggal_transaksi"].strftime("%Y-%m-%d %H:%M:%S"),
                    "items": []
                }
                item_statuses[trx_id] = [] # Buat list status untuk trx ini

            # Tambahkan item
            data[trx_id]["items"].append({
                "id": row["id_detail_order"],
                "name": row["nama_produk"],
                "qty": row["jumlah"],
                "price": float(row["harga_saat_order"]),
                "note": row["catatan_pesanan"],
                "item_status": row["status_pesanan"]
            })
            
            # Catat status item ini
            item_statuses[trx_id].append(row["status_pesanan"])

        # 3. Hitung Status Final setelah loop selesai
        final_data = []
        for trx_id, order_data in data.items():
            statuses_set = set(item_statuses[trx_id]) # Ambil status unik

            # Terapkan logika status baru
            if "Diproses" in statuses_set:
                order_data["status"] = "In Progress"
            elif "Baru" in statuses_set and "Selesai" in statuses_set: # Kasus campuran
                order_data["status"] = "In Progress"
            elif all(s == "Selesai" for s in statuses_set):
                order_data["status"] = "Finish"
            elif all(s == "Baru" for s in statuses_set):
                order_data["status"] = "Waiting"
            elif all(s == "Batal" for s in statuses_set):
                order_data["status"] = "Canceled"
            else:
                # Default jika hanya 'Baru' atau kasus aneh lainnya
                order_data["status"] = "Waiting" 

            final_data.append(order_data)
            
        return jsonify({
            "message": "OK",
            "datas": final_data # Kembalikan data yang sudah dihitung
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

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
        }), 201  # 201 Created
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
    """Endpoint untuk mendapatkan daftar transaksi yang sudah diformat,
       TERMASUK detail booking ruangan beserta kategorinya."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # === PERUBAHAN UTAMA DI DALAM QUERY ===
        query = """
            SELECT
                t.id_transaksi AS id,
                COALESCE(u.nama, t.nama_guest) AS name,
                t.lokasi_pemesanan AS type, -- Mungkin perlu penyesuaian logika 'type'
                CASE
                    WHEN t.status_pembayaran = 'Lunas' THEN 'SUCCESS'
                    WHEN t.status_pembayaran = 'Belum Lunas' THEN 'WAITING'
                    ELSE 'FAILED' -- Menambah case Gagal
                END AS status,
                t.total_harga_final AS price,

                -- Subquery untuk produk F&B (tetap sama)
                (SELECT GROUP_CONCAT(pf.nama_produk SEPARATOR ', ')
                    FROM detail_order_fnb dof
                    JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                    WHERE dof.id_transaksi = t.id_transaksi
                ) AS product,

                -- === SUBQUERY BARU UNTUK BOOKING RUANGAN ===
                (SELECT GROUP_CONCAT(
                            CONCAT(r.nama_ruangan, ' (', kr.nama_kategori, ')') 
                            SEPARATOR ', '
                        )
                    FROM booking_ruangan br
                    JOIN ruangan r ON br.id_ruangan = r.id_ruangan
                    JOIN kategori_ruangan kr ON r.id_kategori_ruangan = kr.id_kategori_ruangan
                    WHERE br.id_transaksi = t.id_transaksi
                ) AS booked_rooms
                -- === AKHIR SUBQUERY BARU ===

            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            ORDER BY t.tanggal_transaksi DESC;
        """
        # === AKHIR PERUBAHAN QUERY ===

        cursor.execute(query)
        results = cursor.fetchall()

        # Mengganti nilai None pada product dan booked_rooms
        for row in results:
            if row['product'] is None:
                row['product'] = '-'
            # --- TAMBAHKAN INI ---
            if row['booked_rooms'] is None:
                row['booked_rooms'] = '-'
            # --- AKHIR TAMBAHAN ---

        return jsonify({"message": "OK", "datas": results}), 200

    except Exception as e:
        # Sebaiknya log error di sini juga
        print(f"Error fetching transactions: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# @kasir_endpoints.route('/transaksi', methods=['GET'])
# def get_all_transaksi():
#     """Endpoint untuk mendapatkan daftar transaksi yang sudah diformat."""
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # Query ini telah diperbaiki sesuai skema database final kita
#         query = """
#             SELECT
#                 t.id_transaksi AS id,
#                 COALESCE(u.nama, t.nama_guest) AS name,
#                 t.lokasi_pemesanan AS type,
#                 CASE
#                     WHEN t.status_pembayaran = 'Lunas' THEN 'SUCCESS'
#                     ELSE 'WAITING'
#                 END AS status,
#                 t.total_harga_final AS price,
#                 (SELECT GROUP_CONCAT(p.nama_produk SEPARATOR ', ')
#                     FROM detail_order_fnb do
#                     JOIN produk_fnb p ON do.id_produk = p.id_produk
#                     WHERE do.id_transaksi = t.id_transaksi
#                 ) AS product
#             FROM transaksi t
#             LEFT JOIN users u ON t.id_user = u.id_user
#             ORDER BY t.tanggal_transaksi DESC;
#         """

#         cursor.execute(query)
#         results = cursor.fetchall()

#         # Mengganti nilai None pada product menjadi string kosong agar tidak error di frontend
#         for row in results:
#             if row['product'] is None:
#                 row['product'] = '-'

#         return jsonify({"message": "OK", "datas": results}), 200

#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()


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


@kasir_endpoints.route('/summary_by_payment', methods=['GET'])
@jwt_required()  # Pastikan hanya admin/owner yang bisa akses jika perlu
def get_payment_summary_by_date():
    """
    Mengambil ringkasan total pendapatan dan jumlah transaksi
    dikelompokkan berdasarkan metode pembayaran untuk tanggal tertentu.
    Hanya menghitung transaksi yang sudah 'Lunas'.
    """
    connection = None
    cursor = None
    try:
        # Ambil tanggal dari query parameter, default ke hari ini
        # Diharapkan format YYYY-MM-DD
        # --- PERBAIKAN DI SINI ---
        # Gunakan 'date.today()' secara langsung
        today_str = date.today().isoformat()
        target_date_str = request.args.get('tanggal', today_str)

        # Validasi format tanggal
        try:
            # Gunakan 'datetime.strptime()' secara langsung
            datetime.strptime(target_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"message": "ERROR", "error": "Format tanggal tidak valid. Gunakan YYYY-MM-DD."}), 400
        # --- AKHIR PERBAIKAN ---
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query ini hanya menghitung transaksi 'Lunas'
        query = """
        SELECT 
            metode_pembayaran,
            COUNT(id_transaksi) AS jumlah_transaksi,
            SUM(total_harga_final) AS total_pendapatan
        FROM 
            transaksi
        WHERE 
            status_pembayaran = 'Lunas' AND
            DATE(tanggal_transaksi) = %s
        GROUP BY 
            metode_pembayaran;
        """

        cursor.execute(query, (target_date_str,))
        results = cursor.fetchall()

        # Siapkan struktur data default untuk dikirim ke frontend
        summary = {
            'Tunai': {'jumlah_transaksi': 0, 'total_pendapatan': 0},
            'Non-Tunai': {'jumlah_transaksi': 0, 'total_pendapatan': 0},
            'tanggal_laporan': target_date_str,
            'total_keseluruhan': 0
        }

        total_all = 0

        # Isi data dari hasil query
        for row in results:
            if row['metode_pembayaran'] in summary:
                # Konversi Decimal ke float agar aman untuk JSON
                total_pendapatan_float = float(row['total_pendapatan'])

                summary[row['metode_pembayaran']] = {
                    'jumlah_transaksi': row['jumlah_transaksi'],
                    'total_pendapatan': total_pendapatan_float
                }
                total_all += total_pendapatan_float

        summary['total_keseluruhan'] = total_all

        return jsonify({
            "message": "OK",
            "data": summary
        }), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
# Pastikan import helper sudah ada
from api.utils.mikrotik_helper import generate_voucher_mikrotik


@kasir_endpoints.route('/test-voucher', methods=['POST'])
@jwt_required()
def test_generate_voucher():
    """
    Endpoint khusus untuk tombol Test Print di Settings.
    Membuat 1 voucher 2 jam (Single Code) untuk testing.
    """
    try:
        # PERBAIKAN: Gunakan 'shop-2h' (huruf kecil) sesuai settingan Mikrotik Anda
        user, password = generate_voucher_mikrotik(2, profile_name="shop-2h", comment="TEST-PRINTER")
        
        if user and password:
            return jsonify({
                "message": "OK",
                "voucher": {
                    "user": user,
                    "pass": password,
                    "duration": 2
                }
            }), 200
        else:
            return jsonify({"message": "ERROR", "error": "Gagal koneksi ke Mikrotik"}), 500
            
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500