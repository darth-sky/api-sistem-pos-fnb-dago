"""Routes for module admin"""
import decimal
import os
from flask import Blueprint, Response, json, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import get_jwt_identity, jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename
import traceback
from datetime import datetime, date, timedelta
from mysql.connector import Error as DbError
import traceback
import io
import csv


admin_endpoints = Blueprint("admin_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@admin_endpoints.route('/non-fnb-transactions', methods=['GET'])
# @jwt_required()
def get_non_fnb_transactions():
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    if not start_date or not end_date:
        return jsonify({"message": "ERROR", "error": "startDate and endDate are required"}), 400

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query ini sama dengan query /transactions Anda,
        # TAPI DENGAN TAMBAHAN "fnb.id_transaksi IS NULL" untuk memfilter
        query = """
            SELECT 
                t.id_transaksi,
                t.tanggal_transaksi,
                COALESCE(u.nama, t.nama_guest, 'Guest') as name,
                t.total_harga_final as total,
                COALESCE(p.nilai_diskon, 0) as discount,
                (t.total_harga_final + COALESCE(p.nilai_diskon, 0)) as subtotal,
                CASE
                    WHEN br.id_transaksi IS NOT NULL THEN CONCAT('Sewa Ruangan (', r.nama_ruangan, ')')
                    WHEN be.id_transaksi IS NOT NULL THEN CONCAT('Sewa Event (', es.nama_event_space, ')')
                    WHEN m.id_transaksi IS NOT NULL THEN 'Pembelian Membership'
                    WHEN vo.id_transaksi IS NOT NULL THEN 'Pembelian Virtual Office'
                    ELSE 'Lainnya (Non-F&B)'
                END as category
            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            LEFT JOIN promo p ON t.id_promo = p.id_promo
            
            -- Join untuk filter F&B
            LEFT JOIN (SELECT DISTINCT id_transaksi FROM detail_order_fnb) fnb ON t.id_transaksi = fnb.id_transaksi
            
            -- Join untuk kategori Non-F&B
            LEFT JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
            LEFT JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            LEFT JOIN booking_event be ON t.id_transaksi = be.id_transaksi
            LEFT JOIN event_spaces es ON be.id_event_space = es.id_event_space
            LEFT JOIN memberships m ON t.id_transaksi = m.id_transaksi
            LEFT JOIN client_virtual_office vo ON t.id_transaksi = vo.id_transaksi
            WHERE 
                DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                AND t.status_pembayaran = 'Lunas'
                AND fnb.id_transaksi IS NULL -- <-- INI FILTER UTAMANYA
            ORDER BY t.tanggal_transaksi DESC;
        """
        
        cursor.execute(query, (start_date, end_date))
        transactions = cursor.fetchall()
        
        total_transaction_value = sum(item['total'] for item in transactions)

        return jsonify({
            "message": "OK",
            "datas": {
                "transactions": transactions,
                "summary": {
                    "totalTransaction": int(total_transaction_value)
                }
            }
        })

    except Exception as e:
        print(f"Error in /admin/non-fnb-transactions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            if cursor: cursor.close()
            connection.close()


@admin_endpoints.route('/fnb-sales-detail', methods=['GET'])
# @jwt_required()
def get_fnb_sales_detail():
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    if not start_date or not end_date:
        return jsonify({"message": "ERROR", "error": "startDate and endDate are required"}), 400

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Query ini mengambil setiap item F&B dan mengalokasikan pajak/diskon
        query = """
                WITH trans_details AS (
                    SELECT
                        t.id_transaksi, t.tanggal_transaksi, t.metode_pembayaran, t.pajak_nominal,
                        COALESCE(p.nilai_diskon, 0) as diskon_transaksi,
                        COALESCE(u.nama, t.nama_guest, 'Guest') as nama_pelanggan, -- Data sudah ada di sini
                        (SELECT SUM(dof_inner.jumlah * dof_inner.harga_saat_order) 
                        FROM detail_order_fnb dof_inner 
                        WHERE dof_inner.id_transaksi = t.id_transaksi) AS subtotal_fnb_transaksi
                    FROM transaksi t
                    LEFT JOIN users u ON t.id_user = u.id_user
                    LEFT JOIN promo p ON t.id_promo = p.id_promo
                    WHERE t.status_pembayaran = 'Lunas'
                    AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                    AND EXISTS (SELECT 1 FROM detail_order_fnb dof_ex WHERE dof_ex.id_transaksi = t.id_transaksi)
                )
                SELECT 
                    td.id_transaksi, td.tanggal_transaksi,
                    td.nama_pelanggan, -- ✅ TAMBAHKAN BARIS INI
                    tn.nama_tenant AS merchant, kp.nama_kategori AS category_product,
                    pf.nama_produk AS product, dof.jumlah AS quantity,
                    dof.harga_saat_order AS price,
                    (dof.jumlah * dof.harga_saat_order) AS sub_total_item,
                    CASE 
                        WHEN td.subtotal_fnb_transaksi > 0 
                        THEN (dof.jumlah * dof.harga_saat_order) / td.subtotal_fnb_transaksi * td.pajak_nominal
                        ELSE 0 
                    END AS tax_item,
                    CASE 
                        WHEN td.subtotal_fnb_transaksi > 0 
                        THEN (dof.jumlah * dof.harga_saat_order) / td.subtotal_fnb_transaksi * td.diskon_transaksi
                        ELSE 0 
                    END AS discount_item,
                    ( (dof.jumlah * dof.harga_saat_order) 
                    + CASE WHEN td.subtotal_fnb_transaksi > 0 THEN (dof.jumlah * dof.harga_saat_order) / td.subtotal_fnb_transaksi * td.pajak_nominal ELSE 0 END
                    - CASE WHEN td.subtotal_fnb_transaksi > 0 THEN (dof.jumlah * dof.harga_saat_order) / td.subtotal_fnb_transaksi * td.diskon_transaksi ELSE 0 END
                    ) AS total_item,
                    dof.catatan_pesanan AS note,
                    td.metode_pembayaran AS payment
                FROM detail_order_fnb dof
                JOIN trans_details td ON dof.id_transaksi = td.id_transaksi
                JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                JOIN tenants tn ON kp.id_tenant = tn.id_tenant
                ORDER BY td.tanggal_transaksi DESC;
        """
        cursor.execute(query, (start_date, end_date))
        items = cursor.fetchall()
        
        # Kirim kembali dalam format yang diharapkan
        return jsonify({"message": "OK", "datas": items})

    except Exception as e:
        print(f"Error in /admin/fnb-sales-detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            if cursor: cursor.close()
            connection.close()



def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)): # <-- TAMBAHKAN INI
        return obj.isoformat() # Konversi tanggal/waktu ke string ISO (cth: '2025-11-07')
    
    # Tampilkan error yang lebih jelas jika ada tipe data lain
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
# routes/admin_routes.py

@admin_endpoints.route('/export-bagi-hasil-detail', methods=['GET'])
@jwt_required()
def get_export_bagi_hasil_detail():
    connection = None
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({
                "message": "ERROR",
                "error": "Parameter 'start_date' dan 'end_date' diperlukan"
            }), 400

        # Pastikan end_date mencakup akhir hari
        end_date_str_inclusive = f"{end_date_str} 23:59:59"

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua tenant aktif
        cursor.execute("""
            SELECT id_tenant, nama_tenant 
            FROM tenants 
            WHERE status_tenant = 'Active'
        """)
        tenants = cursor.fetchall()

        export_data = {}

        for tenant in tenants:
            id_tenant = tenant['id_tenant']
            tenant_name = tenant['nama_tenant']

            # 2. Ambil Rincian Sales (DENGAN TOTAL DISCOUNT)
            # Perubahan ada di baris SELECT ke-5: menghitung diskon dari persentase
            query_sales_detail = """
                SELECT 
                    DATE(t.tanggal_transaksi) AS tanggal,
                    pf.nama_produk,
                    SUM(dof.jumlah) AS jumlah_qty,
                    
                    -- Total Kotor (Gross)
                    SUM(dof.harga_saat_order * dof.jumlah) AS total_penjualan_gross,
                    
                    -- Total Diskon
                    SUM(
                        (dof.harga_saat_order * dof.jumlah) * (COALESCE(t.discount_percentage, 0) / 100)
                    ) AS total_discount,

                    -- (BARU) Total Pajak
                    -- Dihitung dari (Harga x Qty) dikali Persen Pajak Transaksi
                    SUM(
                        (dof.harga_saat_order * dof.jumlah) * (COALESCE(t.pajak_persen, 0) / 100)
                    ) AS total_pajak

                FROM transaksi t
                JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
                JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                WHERE kp.id_tenant = %s
                  AND t.status_pembayaran = 'Lunas'
                  AND t.tanggal_transaksi BETWEEN %s AND %s
                GROUP BY DATE(t.tanggal_transaksi), pf.nama_produk
                ORDER BY tanggal, pf.nama_produk;
            """
            cursor.execute(query_sales_detail, (id_tenant, start_date_str, end_date_str_inclusive))
            sales_details = cursor.fetchall()

            # 3. Ambil Rincian Utang (Tidak berubah)
            query_debt_detail = """
                SELECT 
                    tanggal_utang,
                    deskripsi,
                    jumlah
                FROM utang_tenant
                WHERE id_tenant = %s
                  AND status_lunas = 0
                  AND tanggal_utang <= %s
                ORDER BY tanggal_utang;
            """
            cursor.execute(query_debt_detail, (id_tenant, end_date_str))
            debt_details = cursor.fetchall()

            # Masukkan hasil ke export_data
            export_data[tenant_name] = {
                "sales": sales_details,
                "debts": debt_details
            }

        # Gunakan json.dumps dengan helper decimal_default
        response_body = json.dumps({
            "message": "OK",
            "datas": export_data
        }, default=decimal_default)

        return response_body, 200, {'Content-Type': 'application/json'}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "message": "ERROR",
            "error": str(e)
        }), 500

    finally:
        if connection:
            connection.close()
            
# Helper untuk JSON
# Helper untuk JSON
# def decimal_default(obj):
#     if isinstance(obj, decimal.Decimal):
#         return float(obj)
#     raise TypeError

# === 1. ENDPOINT UTAMA (BARU): Laporan Live Berdasarkan Rentang Tanggal ===
@admin_endpoints.route('/rekap-live', methods=['GET'])
def get_rekap_live():
    connection = None
    try:
        # Ambil start_date dan end_date dari query params
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str or not end_date_str:
            return jsonify({"message": "ERROR", "error": "Parameter 'start_date' dan 'end_date' diperlukan (format YYYY-MM-DD)"}), 400

        # Tambahkan ' 23:59:59' ke end_date agar mencakup HARI ITU
        end_date_str_inclusive = f"{end_date_str} 23:59:59"

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Ambil semua tenant aktif
        cursor.execute("SELECT id_tenant, nama_tenant FROM tenants WHERE status_tenant = 'Active' ORDER BY nama_tenant")
        tenants = cursor.fetchall()

        rekap_data = []

        for tenant in tenants:
            id_tenant = tenant['id_tenant']
            
            # 2. Hitung Total Sales dalam rentang tanggal
            query_sales = """
                SELECT COALESCE(SUM(dof.harga_saat_order * dof.jumlah), 0) AS total
                FROM transaksi t
                JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
                JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                WHERE kp.id_tenant = %s
                  AND t.status_pembayaran = 'Lunas'
                  AND t.tanggal_transaksi BETWEEN %s AND %s;
            """
            cursor.execute(query_sales, (id_tenant, start_date_str, end_date_str_inclusive))
            total_sales = cursor.fetchone()['total']

            # 3. Hitung Utang Awal (Semua utang belum lunas SEBELUM start_date)
            query_utang_awal = """
                SELECT COALESCE(SUM(jumlah), 0) AS total
                FROM utang_tenant
                WHERE id_tenant = %s
                  AND status_lunas = 0
                  AND tanggal_utang < %s;
            """
            cursor.execute(query_utang_awal, (id_tenant, start_date_str))
            utang_awal = cursor.fetchone()['total']

            # 4. Hitung Utang Baru (Utang yang ditambahkan SELAMA rentang tanggal)
            query_utang_baru = """
                SELECT COALESCE(SUM(jumlah), 0) AS total
                FROM utang_tenant
                WHERE id_tenant = %s
                  AND status_lunas = 0
                  AND tanggal_utang BETWEEN %s AND %s;
            """
            cursor.execute(query_utang_baru, (id_tenant, start_date_str, end_date_str))
            utang_masuk_periode = cursor.fetchone()['total']

            # 5. (PENTING) Hitung pelunasan utang yang terjadi SELAMA rentang tanggal
            # Asumsi: 'utang_awal' di rekap_bagi_hasil adalah jumlah yg dipotong
            query_pelunasan = """
                SELECT COALESCE(SUM(utang_awal), 0) AS total
                FROM rekap_bagi_hasil
                WHERE id_tenant = %s
                  AND status_pembayaran_t1 = 1 -- (Kita anggap T1 = Lunas)
                  AND MAKEDATE(periode_tahun, 1) + INTERVAL (periode_bulan - 1) MONTH 
                      BETWEEN %s AND %s; 
            """
            # Ini asumsi kasar, logika pelunasan mungkin perlu disesuaikan
            # Untuk SAAT INI, kita anggap pelunasan = 0 agar sederhana
            pelunasan_periode = 0
            
            # Total Utang = Utang Awal + Utang Baru - Pelunasan
            total_utang = utang_awal + utang_masuk_periode - pelunasan_periode

            rekap_data.append({
                "id_tenant": id_tenant,
                "nama_tenant": tenant['nama_tenant'],
                "totalSales": total_sales,
                "utangAwal": utang_awal,
                "utangMasukPeriode": utang_masuk_periode,
                "totalUtang": total_utang # Utang Awal + Utang Baru
            })

        return jsonify({"message": "OK", "datas": rekap_data}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()

# === 2. Endpoint: Menambah Utang Ad-hoc (Form "Input Utang") ===
# Endpoint ini sudah benar, hanya perlu memastikan 'tanggal_utang' diterima
@admin_endpoints.route('/utang-tenant', methods=['POST'])
def add_utang_tenant():
    connection = None
    try:
        data = request.json
        id_tenant = data.get('id_tenant')
        jumlah = data.get('jumlah')
        deskripsi = data.get('deskripsi', 'Utang manual dari admin')
        tanggal_utang = data.get('tanggal_utang') # 'YYYY-MM-DD'

        if not id_tenant or not jumlah or not tanggal_utang:
            return jsonify({"message": "ERROR", "error": "id_tenant, jumlah, dan tanggal_utang diperlukan"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        query = """
            INSERT INTO utang_tenant (id_tenant, tanggal_utang, jumlah, deskripsi, status_lunas)
            VALUES (%s, %s, %s, %s, 0)
        """
        cursor.execute(query, (id_tenant, tanggal_utang, jumlah, deskripsi))
        connection.commit()

        return jsonify({"message": "Utang tenant berhasil ditambahkan"}), 201

    except Exception as e:
        if connection: connection.rollback()
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()

# === 3. Endpoint: Mengambil Daftar Tenant Aktif (Tetap sama) ===
@admin_endpoints.route('/tenants-active', methods=['GET'])
def get_active_tenants():
    # ... (Endpoint ini tidak berubah, sudah benar) ...
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id_tenant, nama_tenant FROM tenants WHERE status_tenant = 'Active' ORDER BY nama_tenant")
        tenants = cursor.fetchall()
        return jsonify({"message": "OK", "datas": tenants}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()


@admin_endpoints.route('/utang-log', methods=['GET'])
def get_utang_log():
    connection = None
    try:
        # Ambil parameter dari query URL
        tenant_id = request.args.get('tenant_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not tenant_id:
            return jsonify({"message": "ERROR", "error": "Parameter 'tenant_id' diperlukan"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query dasar untuk semua utang tenant
        query = """
            SELECT id_utang, id_tenant, tanggal_utang, jumlah, deskripsi, status_lunas
            FROM utang_tenant
            WHERE id_tenant = %s
        """
        params = [tenant_id]

        # Tambahkan filter tanggal jika ada
        if start_date_str and end_date_str:
            query += " AND tanggal_utang BETWEEN %s AND %s"
            params.extend([start_date_str, end_date_str])
        
        query += " ORDER BY tanggal_utang DESC"
        
        cursor.execute(query, tuple(params))
        utang_log = cursor.fetchall()

        # Konversi Decimal ke float/str untuk JSON
        for log in utang_log:
            log['jumlah'] = float(log['jumlah'])
            # Ubah tanggal ke format YYYY-MM-DD
            if isinstance(log['tanggal_utang'], datetime):
                log['tanggal_utang'] = log['tanggal_utang'].strftime('%Y-%m-%d')
            elif isinstance(log['tanggal_utang'], date): # Handle jika tipenya date
                 log['tanggal_utang'] = log['tanggal_utang'].strftime('%Y-%m-%d')


        return jsonify({"message": "OK", "datas": utang_log}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()

# === 8. (BARU) UPDATE Entri Utang (Modal Edit) ===
@admin_endpoints.route('/utang-log/<int:id_utang>', methods=['PUT'])
def update_utang_entry(id_utang):
    connection = None
    try:
        data = request.json
        jumlah = data.get('jumlah')
        deskripsi = data.get('deskripsi')
        tanggal_utang = data.get('tanggal_utang') # 'YYYY-MM-DD'
        status_lunas = data.get('status_lunas') # boolean

        if not all([jumlah, deskripsi, tanggal_utang, status_lunas is not None]):
            return jsonify({"message": "ERROR", "error": "Semua field (jumlah, deskripsi, tanggal_utang, status_lunas) diperlukan"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        query = """
            UPDATE utang_tenant
            SET tanggal_utang = %s,
                jumlah = %s,
                deskripsi = %s,
                status_lunas = %s
            WHERE id_utang = %s
        """
        params = (tanggal_utang, decimal.Decimal(jumlah), deskripsi, 1 if status_lunas else 0, id_utang)
        
        cursor.execute(query, params)
        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "ID Utang tidak ditemukan"}), 404

        connection.commit()
        return jsonify({"message": "Entri utang berhasil diperbarui"}), 200

    except Exception as e:
        if connection: connection.rollback()
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()

# === 9. (BARU) DELETE Entri Utang (Tombol Hapus) ===
@admin_endpoints.route('/utang-log/<int:id_utang>', methods=['DELETE'])
def delete_utang_entry(id_utang):
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        query = "DELETE FROM utang_tenant WHERE id_utang = %s"
        cursor.execute(query, (id_utang,))
        
        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "ID Utang tidak ditemukan"}), 404

        connection.commit()
        return jsonify({"message": "Entri utang berhasil dihapus"}), 200

    except Exception as e:
        if connection: connection.rollback()
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection:
            connection.close()

















# --- HELPER KALKULASI SALES ---
def calculate_tenant_sales(cursor, id_tenant, start_date, end_date):
    """Menghitung total sales lunas seorang tenant dalam rentang tanggal."""
    query = """
        SELECT SUM(dof.harga_saat_order * dof.jumlah) as total_sales
        FROM transaksi t
        JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
        JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
        WHERE kp.id_tenant = %s
          AND t.status_pembayaran = 'Lunas'
          AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
    """
    try:
        cursor.execute(query, (id_tenant, start_date, end_date))
        result = cursor.fetchone()
        return result['total_sales'] if result and result['total_sales'] else 0
    except Exception as e:
        print(f"Error calculating sales for tenant {id_tenant}: {e}")
        return 0

# --- HELPER EXPORT CSV ---
def generate_csv_response(headers, data, filename="export.csv"):
    """Membuat response CSV dari data."""
    si = io.StringIO()
    # Tambahkan BOM untuk Excel
    si.write('\uFEFF') 
    
    writer = csv.DictWriter(si, fieldnames=[h['key'] for h in headers])
    
    # Tulis header kustom
    writer.writerow({h['key']: h['label'] for h in headers})
    
    writer.writerows(data)
    
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

# --- ENDPOINT UTAMA ---

# @admin_endpoints.route('/rekap-bagi-hasil', methods=['GET'])
# def get_rekap_bagi_hasil():
#     """
#     Endpoint utama. Mengambil data rekap bulanan yang sudah dikalkulasi.
#     Menerima query params: tahun, bulan, p1_start, p1_end, p2_start, p2_end
#     """
#     connection = None
#     cursor = None
#     try:
#         # 1. Ambil Query Params
#         tahun = request.args.get('tahun', type=int)
#         bulan = request.args.get('bulan', type=int)
#         p1_start = request.args.get('p1_start')
#         p1_end = request.args.get('p1_end')
#         p2_start = request.args.get('p2_start')
#         p2_end = request.args.get('p2_end')

#         if not all([tahun, bulan, p1_start, p1_end, p2_start, p2_end]):
#             return jsonify({"error": "Parameter tidak lengkap."}), 400

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # 2. Get semua tenant aktif
#         cursor.execute("SELECT id_tenant, nama_tenant FROM tenants WHERE status_tenant = 'Active'")
#         tenants = cursor.fetchall()
        
#         response_data = []

#         # 3. Loop per tenant untuk kalkulasi data
#         for tenant in tenants:
#             id_tenant = tenant['id_tenant']
            
#             # 3a. Kalkulasi Sales P1 & P2 dari Transaksi
#             sales_p1_calc = calculate_tenant_sales(cursor, id_tenant, p1_start, p1_end)
#             sales_p2_calc = calculate_tenant_sales(cursor, id_tenant, p2_start, p2_end)

#             # 3b. Get data rekap dari DB (utang_awal dan override sales)
#             cursor.execute(
#                 """
#                 SELECT utang_awal, sales_p1, sales_p2 
#                 FROM rekap_bagi_hasil 
#                 WHERE id_tenant = %s AND periode_tahun = %s AND periode_bulan = %s
#                 """,
#                 (id_tenant, tahun, bulan)
#             )
#             rekap = cursor.fetchone()

#             utang_awal_db = 0
#             sales_p1_override = None
#             sales_p2_override = None

#             if rekap:
#                 utang_awal_db = rekap['utang_awal'] or 0
#                 sales_p1_override = rekap['sales_p1']
#                 sales_p2_override = rekap['sales_p2']

#             # 3c. Get riwayat utang baru (debtHistory) di bulan berjalan
#             cursor.execute(
#                 """
#                 SELECT id_utang, tanggal_utang, jumlah, deskripsi, status_lunas
#                 FROM utang_tenant 
#                 WHERE id_tenant = %s 
#                   AND YEAR(tanggal_utang) = %s 
#                   AND MONTH(tanggal_utang) = %s
#                   AND status_lunas = 0
#                 """, 
#                 (id_tenant, tahun, bulan)
#             )
#             utang_history_db = cursor.fetchall()
            
#             # Konversi data utang ke format yang disukai frontend
#             debt_history_frontend = [
#                 {
#                     "id": u['id_utang'],
#                     "date": u['tanggal_utang'].isoformat(), # Kirim sebagai ISO string
#                     "amount": float(u['jumlah']),
#                     "isPaidOut": bool(u['status_lunas'])
#                     # 'paymentPeriod' akan ditentukan oleh frontend
#                 } for u in utang_history_db
#             ]

#             # 4. Susun data
#             tenant_data = {
#                 "id": id_tenant,
#                 "name": tenant['nama_tenant'],
#                 "totalSales": {
#                     # Gunakan override JIKA ADA, jika tidak (NULL), gunakan hasil kalkulasi
#                     "p1": float(sales_p1_override if sales_p1_override is not None else sales_p1_calc),
#                     "p2": float(sales_p2_override if sales_p2_override is not None else sales_p2_calc)
#                 },
#                 "currentDebt": float(utang_awal_db),
#                 "debtHistory": debt_history_frontend
#             }
#             response_data.append(tenant_data)

#         return jsonify(response_data), 200

#     except DbError as db_err:
#         print(f"Database error in get_rekap_bagi_hasil: {db_err}")
#         return jsonify({"error": "Database error"}), 500
#     except Exception as e:
#         print(f"General error in get_rekap_bagi_hasil: {e}")
#         traceback.print_exc()
#         return jsonify({"error": "Internal server error"}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

@admin_endpoints.route('/rekap-bagi-hasil/update', methods=['PUT'])
def update_rekap_data():
    """
    Menyimpan data rekap (utang_awal dan override sales).
    Ini menggunakan "INSERT ... ON DUPLICATE KEY UPDATE" (upsert).
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()
        id_tenant = data.get('id_tenant')
        tahun = data.get('tahun')
        bulan = data.get('bulan')
        utang_awal = data.get('currentDebt')
        sales_p1 = data.get('totalSalesP1')
        sales_p2 = data.get('totalSalesP2')

        if not all([id_tenant, tahun, bulan]):
             return jsonify({"error": "Data tidak lengkap (tenant, tahun, bulan wajib)"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # 'Upsert' logic
        query = """
            INSERT INTO rekap_bagi_hasil 
                (id_tenant, periode_tahun, periode_bulan, utang_awal, sales_p1, sales_p2)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                utang_awal = VALUES(utang_awal),
                sales_p1 = VALUES(sales_p1),
                sales_p2 = VALUES(sales_p2)
        """
        cursor.execute(query, (id_tenant, tahun, bulan, utang_awal, sales_p1, sales_p2))
        connection.commit()
        
        return jsonify({"message": "OK", "info": "Data rekap berhasil diperbarui"}), 200

    except DbError as db_err:
        if connection: connection.rollback()
        print(f"Database error in update_rekap_data: {db_err}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        if connection: connection.rollback()
        print(f"General error in update_rekap_data: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# @admin_endpoints.route('/utang-tenant', methods=['POST'])
# def add_utang_tenant():
#     """Menambah catatan utang/kasbon baru."""
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         id_tenant = data.get('id_tenant')
#         tanggal_utang = data.get('date') # Harusnya format YYYY-MM-DD
#         jumlah = data.get('amount')

#         if not all([id_tenant, tanggal_utang, jumlah]):
#              return jsonify({"error": "Data utang tidak lengkap"}), 400

#         connection = get_connection()
#         cursor = connection.cursor()
        
#         query = "INSERT INTO utang_tenant (id_tenant, tanggal_utang, jumlah) VALUES (%s, %s, %s)"
#         cursor.execute(query, (id_tenant, tanggal_utang, jumlah))
#         new_id = cursor.lastrowid
#         connection.commit()
        
#         # Kembalikan data utang yang baru dibuat
#         return jsonify({
#             "message": "OK", 
#             "info": "Utang baru berhasil ditambahkan",
#             "newDebt": {
#                 "id": new_id,
#                 "date": tanggal_utang,
#                 "amount": float(jumlah),
#                 "isPaidOut": False
#             }
#         }), 201

#     except DbError as db_err:
#         if connection: connection.rollback()
#         return jsonify({"error": f"Database error: {db_err}"}), 500
#     except Exception as e:
#         if connection: connection.rollback()
#         return jsonify({"error": f"Internal server error: {e}"}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()


@admin_endpoints.route('/utang-tenant/<int:id_utang>', methods=['DELETE'])
def delete_utang_tenant(id_utang):
    """Menghapus catatan utang/kasbon."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        
        # Hapus hanya jika belum lunas
        query = "DELETE FROM utang_tenant WHERE id_utang = %s AND status_lunas = 0"
        cursor.execute(query, (id_utang,))
        
        if cursor.rowcount == 0:
            return jsonify({"error": "Utang tidak ditemukan atau sudah lunas"}), 404
            
        connection.commit()
        return jsonify({"message": "OK", "info": "Catatan utang berhasil dihapus"}), 200

    except DbError as db_err:
        if connection: connection.rollback()
        return jsonify({"error": f"Database error: {db_err}"}), 500
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"error": f"Internal server error: {e}"}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


def consume_unread_results(cursor):
    """
    Membaca dan membuang semua sisa result set dari cursor
    untuk menghindari error 'Unread result found'.
    """
    try:
        # Loop selama cursor.next_result() mengembalikan True (ada result set lain)
        while cursor.next_result():
            pass # Lewati (buang) result set tersebut
    except DbError as e:
        # Ini normal terjadi jika tidak ada sisa result set
        # atau jika konektor tidak mendukungnya (spt versi lama)
        if e.errno != 2055 and e.errno != 2014: # 2055 = unread, 2014 = commands out of sync
            print(f"Error saat consume_unread_results: {e}")
    except Exception as e:
        # Tangkap error umum lainnya
        print(f"General error saat consume_unread_results: {e}")

@admin_endpoints.route('/rekap-bagi-hasil/export/all', methods=['GET'])
def export_rekap_all():
    """Export semua data rekap dari semua bulan."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERBAIKAN 1: 'Unread result found' ---
        # Bersihkan sisa hasil dari connection pool (jika ada)
        consume_unread_results(cursor)
        # -------------------------------------------

        # 1. Get semua tenant
        cursor.execute("SELECT id_tenant, nama_tenant FROM tenants WHERE status_tenant = 'Active'")
        
        # --- PERBAIKAN 2: Bug 'NameError' ---
        # Anda harus fetchall() dulu sebelum bisa memproses hasilnya
        tenants_list = cursor.fetchall()
        tenants = {t['id_tenant']: t['nama_tenant'] for t in tenants_list}
        # -----------------------------------
        
        # 2. Get semua rekap
        cursor.execute("SELECT * FROM rekap_bagi_hasil ORDER BY periode_tahun, periode_bulan, id_tenant")
        all_rekaps = cursor.fetchall()
        
        # 3. Get semua utang
        cursor.execute("SELECT * FROM utang_tenant WHERE status_lunas = 0")
        all_utang = cursor.fetchall()
        
        data_to_export = []
        
        # Logika ini harus disesuaikan dengan `computeShares` di frontend
        # Ini adalah simplifikasi
        for rekap in all_rekaps:
            id_tenant = rekap['id_tenant']
            tahun = rekap['periode_tahun']
            bulan = rekap['periode_bulan']
            
            # (Simplifikasi - idealnya kalkulasi P1/P2 di-cache di DB saat GET)
            # Untuk export, kita gunakan saja data override jika ada
            sales_p1 = float(rekap['sales_p1'] or 0)
            sales_p2 = float(rekap['sales_p2'] or 0)
            total_sales = sales_p1 + sales_p2
            utang_awal = float(rekap['utang_awal'] or 0)
            
            # Hitung utang baru di bulan itu
            utang_baru_bulan_ini = sum(
                float(u['jumlah']) for u in all_utang 
                if u['id_tenant'] == id_tenant 
                and u['tanggal_utang'].year == tahun 
                and u['tanggal_utang'].month == bulan
            )
            
            total_utang_dipotong = utang_awal + utang_baru_bulan_ini
            
            owner_share = total_sales * 0.3
            tenant_raw_share = total_sales * 0.7
            net_tenant_payment = max(0, tenant_raw_share - total_utang_dipotong)
            remaining_debt = max(0, total_utang_dipotong - tenant_raw_share)

            data_to_export.append({
                "month": f"{tahun}-{str(bulan).zfill(2)}",
                "tenantName": tenants.get(id_tenant, f"ID: {id_tenant}"),
                "salesP1": sales_p1,
                "salesP2": sales_p2,
                "totalSales": total_sales,
                "ownerShare": round(owner_share),
                "tenantRawShare": round(tenant_raw_share),
                "initialDebt": utang_awal,
                "totalDebt": round(total_utang_dipotong),
                "netTenantPayment": round(net_tenant_payment),
                "remainingDebt": round(remaining_debt)
            })

        headers = [
            { "label": "Bulan", "key": "month" },
            { "label": "Tenant", "key": "tenantName" },
            { "label": "Sales P1", "key": "salesP1" },
            { "label": "Sales P2", "key": "salesP2" },
            { "label": "Total Sales", "key": "totalSales" },
            { "label": "Hak Owner (30%)", "key": "ownerShare" },
            { "label": "Hak Tenant (70%)", "key": "tenantRawShare" },
            { "label": "Utang Awal Bulan", "key": "initialDebt" },
            { "label": "Total Utang Dipotong", "key": "totalDebt" },
            { "label": "Pembayaran NET", "key": "netTenantPayment" },
            { "label": "Sisa Utang Bulan Ini", "key": "remainingDebt" },
        ]

        filename = f"rekap_bagi_hasil_semua_bulan_{datetime.date.today().isoformat()}.csv"
        return generate_csv_response(headers, data_to_export, filename)

    except Exception as e:
        print(f"Error exporting all rekap: {e}")
        traceback.print_exc()
        return jsonify({"error": "Gagal mengekspor data"}), 500
    finally:
        # Sekarang cursor.close() akan aman untuk dipanggil
        if cursor: cursor.close()
        if connection: connection.close()
        
        
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper untuk mengubah Decimal menjadi float untuk JSON
# def decimal_default(obj):
#     if isinstance(obj, decimal.Decimal):
#         return float(obj)
#     raise TypeError

# # --- ENDPOINT 1: GET DATA REKAP UNTUK HALAMAN HUTANG ---
# # Ini menggabungkan Laporan Bagi Hasil (sales) dengan data utang/pembayaran
# @admin_endpoints.route('/rekapBagiHasil', methods=['GET'])
# def get_rekap_bagi_hasil():
#     connection = None
#     cursor = None
#     try:
#         start_date_str = request.args.get('startDate')
#         end_date_str = request.args.get('endDate')
#         # Ambil bulan dan tahun dari startDate untuk query rekap
#         try:
#             period_date = datetime.strptime(start_date_str, '%Y-%m-%d')
#             p_bulan = period_date.month
#             p_tahun = period_date.year
#         except:
#             return jsonify({"message": "ERROR", "error": "Format startDate tidak valid (YYYY-MM-DD)"}), 400

#         if not start_date_str or not end_date_str:
#             return jsonify({"message": "ERROR", "error": "Parameter startDate dan endDate wajib diisi"}), 400

#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
        
#         # Query ini menggabungkan total sales (dari laporanBagiHasil)
#         # dengan data utang/pembayaran dari tabel baru 'rekap_bagi_hasil'
#         query = """
#             -- 1. Ambil Total Sales (mirip laporanBagiHasil)
#             WITH TenantSales AS (
#                 SELECT 
#                     t.id_tenant,
#                     t.nama_tenant,
#                     SUM(dof.harga_saat_order * dof.jumlah) AS totalSales
#                 FROM transaksi tr
#                 JOIN detail_order_fnb dof ON tr.id_transaksi = dof.id_transaksi
#                 JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
#                 JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
#                 JOIN tenants t ON kp.id_tenant = t.id_tenant
#                 WHERE 
#                     tr.status_pembayaran = 'Lunas' AND
#                     DATE(tr.tanggal_transaksi) BETWEEN %s AND %s
#                 GROUP BY t.id_tenant, t.nama_tenant
#             ),
#             -- 2. Ambil data utang/pembayaran dari tabel rekap
#             TenantRekap AS (
#                 SELECT
#                     id_tenant,
#                     utang_awal,
#                     status_pembayaran_t1,
#                     status_pembayaran_t2
#                 FROM rekap_bagi_hasil
#                 WHERE periode_bulan = %s AND periode_tahun = %s
#             )
#             -- 3. Gabungkan semua tenant, sales, dan rekap
#             SELECT
#                 t.id_tenant AS id,
#                 t.nama_tenant AS name,
#                 COALESCE(ts.totalSales, 0) AS totalSales,
#                 COALESCE(tr.utang_awal, 0) AS debt,
#                 JSON_OBJECT(
#                     'p1_paid', COALESCE(tr.status_pembayaran_t1, 0),
#                     'p2_paid', COALESCE(tr.status_pembayaran_t2, 0)
#                 ) AS payments
#             FROM tenants t
#             LEFT JOIN TenantSales ts ON t.id_tenant = ts.id_tenant
#             LEFT JOIN TenantRekap tr ON t.id_tenant = tr.id_tenant
#             -- Hanya tampilkan tenant yang terdaftar di tabel tenants
#             -- Anda bisa tambahkan WHERE jika hanya ingin tenant F&B
#             ORDER BY t.nama_tenant;
#         """
        
#         params = (start_date_str, end_date_str, p_bulan, p_tahun)
#         cursor.execute(query, params)
#         results = cursor.fetchall()
        
#         # Konversi data JSON string 'payments' menjadi objek Python
#         for row in results:
#             if isinstance(row['payments'], str):
#                 row['payments'] = json.loads(row['payments'])
#             else:
#                 # Handle jika JSON_OBJECT mengembalikan dict (tergantung versi MySQL)
#                 # atau jika COALESCE mengembalikan payments=NULL -> json.loads gagal
#                 if row['payments'] is None:
#                      row['payments'] = {'p1_paid': False, 'p2_paid': False}
#                 # Pastikan p1_paid/p2_paid adalah boolean
#                 row['payments']['p1_paid'] = bool(row['payments']['p1_paid'])
#                 row['payments']['p2_paid'] = bool(row['payments']['p2_paid'])


#         return jsonify(results), 200

#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

@admin_endpoints.route('/tenants', methods=['GET'])
def get_all_tenants_list():
    """
    Endpoint untuk mengambil daftar semua tenant (ID dan Nama).
    Digunakan untuk mengisi dropdown di frontend.
    """
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True) # Menggunakan dictionary=True agar hasil berupa dict

        query = "SELECT id_tenant, nama_tenant FROM tenants ORDER BY nama_tenant ASC"
        cursor.execute(query)
        tenants = cursor.fetchall()

        # Jika Anda ingin format { value, label } langsung dari backend:
        # formatted_tenants = [{"value": t['id_tenant'], "label": t['nama_tenant']} for t in tenants]
        # return jsonify(formatted_tenants), 200

        # Atau kembalikan list objek standar:
        return jsonify(tenants), 200

    except Exception as e:
        print(f"Error fetching tenants: {e}") # Logging error di backend
        return jsonify({"message": "ERROR", "error": f"Gagal mengambil data tenant: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# --- ENDPOINT 2: POST/UPDATE DATA UTANG AWAL ---
# Ini digunakan oleh form "Input Utang Tenant Baru"
@admin_endpoints.route('/rekapBagiHasil/utang', methods=['POST'])
def save_utang_tenant():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        id_tenant = data.get('id_tenant')
        p_bulan = data.get('periode_bulan')
        p_tahun = data.get('periode_tahun')
        utang_awal = data.get('utang_awal', 0)

        if not all([id_tenant, p_bulan, p_tahun]):
            return jsonify({"message": "ERROR", "error": "id_tenant, periode_bulan, dan periode_tahun wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # Gunakan INSERT... ON DUPLICATE KEY UPDATE untuk membuat atau memperbarui data
        query = """
            INSERT INTO rekap_bagi_hasil (id_tenant, periode_bulan, periode_tahun, utang_awal)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            utang_awal = VALUES(utang_awal);
        """
        params = (id_tenant, p_bulan, p_tahun, utang_awal)
        cursor.execute(query, params)
        connection.commit()
        
        return jsonify({"message": "SUCCESS", "data": "Utang tenant berhasil disimpan"}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# --- ENDPOINT 3: PUT UNTUK TOGGLE STATUS PEMBAYARAN ---
# Ini digunakan saat admin menekan tombol "Bayar" (di frontend Anda togglePaymentNet)
@admin_endpoints.route('/rekapBagiHasil/payment', methods=['PUT'])
def toggle_payment_status():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        id_tenant = data.get('id_tenant')
        p_bulan = data.get('periode_bulan')
        p_tahun = data.get('periode_tahun')
        # Frontend akan mengirim 'p1' atau 'p2' atau 'all'
        termin = data.get('termin') 

        if not all([id_tenant, p_bulan, p_tahun, termin]):
            return jsonify({"message": "ERROR", "error": "id_tenant, periode_bulan, periode_tahun, dan termin wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        
        # Tentukan kolom yang akan di-update
        if termin == 'all_paid':
            set_clause = "status_pembayaran_t1 = 1, status_pembayaran_t2 = 1"
        elif termin == 'all_unpaid':
            set_clause = "status_pembayaran_t1 = 0, status_pembayaran_t2 = 0"
        else:
            return jsonify({"message": "ERROR", "error": f"Nilai termin '{termin}' tidak valid"}), 400

        # Query untuk update atau insert jika belum ada
        query = f"""
            INSERT INTO rekap_bagi_hasil (id_tenant, periode_bulan, periode_tahun, {set_clause})
            VALUES (%s, %s, %s, {1 if termin == 'all_paid' else 0}, {1 if termin == 'all_paid' else 0})
            ON DUPLICATE KEY UPDATE {set_clause};
        """
        
        params = (id_tenant, p_bulan, p_tahun)
        cursor.execute(query, params)
        connection.commit()
        
        return jsonify({"message": "SUCCESS", "data": "Status pembayaran berhasil diupdate"}), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()



# Helper function untuk memproses data penjualan bulanan/harian
def process_chart_data(rows, date_format, num_periods, period_type):
    """
    Mengisi data chart dengan 0 jika tidak ada penjualan pada periode tertentu.
    period_type: 'days' or 'months'
    """
    sales_map = {row['period']: row['total'] for row in rows}
    labels = []
    data = []
    
    for i in range(num_periods - 1, -1, -1):
        if period_type == 'days':
            current_date = datetime.now() - timedelta(days=i)
            label = current_date.strftime('%a') # 'Mon', 'Tue'
            key = current_date.strftime('%Y-%m-%d')
        else: # months
            current_month = datetime.now() - timedelta(days=i*30) # Perkiraan
            # Logika yang lebih akurat mungkin diperlukan jika presisi tinggi dibutuhkan
            current_date = datetime.now() - timedelta(days=i * 30)
            label = current_date.strftime('%b') # 'Apr', 'May'
            key = current_date.strftime('%Y-%m')

        labels.append(label)
        data.append(int(sales_map.get(key, 0)))
        
    return {"labels": labels, "data": data}


def get_total_sales_for_tenant(cursor, id_tenant, periode_str):
    """
    Menjalankan query SQL untuk menghitung total penjualan lunas 
    seorang tenant pada periode YYYY-MM.
    """
    query = """
        SELECT IFNULL(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total_penjualan
        FROM tenants AS t
        LEFT JOIN kategori_produk AS kp ON t.id_tenant = kp.id_tenant
        LEFT JOIN produk_fnb AS pf ON kp.id_kategori = pf.id_kategori
        LEFT JOIN detail_order_fnb AS dof ON pf.id_produk = dof.id_produk
        LEFT JOIN transaksi AS tr ON dof.id_transaksi = tr.id_transaksi
        WHERE 
            t.id_tenant = %s AND
            tr.status_pembayaran = 'Lunas' AND
            DATE_FORMAT(tr.tanggal_transaksi, '%%Y-%%m') = %s
        GROUP BY t.id_tenant;
    """
    cursor.execute(query, (id_tenant, periode_str))
    result = cursor.fetchone()
    return result[0] if result else decimal.Decimal(0)

# ===================================================================
# FUNGSI YANG DIPERBARUI: Tidak lagi menggunakan dayjs
# ===================================================================


def get_previous_debt(cursor, id_tenant, periode_dt_str):
    """
    Mencari sisa utang dari periode sebelumnya.
    periode_dt_str format: "YYYY-MM-01"
    """
    try:
        # 1. Ubah string "YYYY-MM-01" menjadi objek date
        #    Pastikan kita memanggil method dari KELAS datetime.date
        current_date = datetime.date.fromisoformat(periode_dt_str)

        # 2. Kurangi 1 hari untuk mendapatkan hari terakhir bulan sebelumnya
        last_day_of_prev_month = current_date - datetime.timedelta(days=1)

        # 3. Format kembali ke "YYYY-MM-01" untuk query
        prev_month_dt_str = last_day_of_prev_month.strftime('%Y-%m-01')

        query = """
            SELECT sisa_utang
            FROM rekap_bagi_hasil
            WHERE id_tenant = %s AND periode = %s
        """
        cursor.execute(query, (id_tenant, prev_month_dt_str)) # Gunakan string format baru
        result = cursor.fetchone()
        return result[0] if result else decimal.Decimal(0)
    except ValueError as ve:
        # Menangkap error jika format periode_dt_str salah
        print(f"Error parsing date string '{periode_dt_str}': {ve}")
        # Kembalikan nilai default atau raise error lagi, tergantung kebutuhan
        return decimal.Decimal(0)
    except Exception as e:
        # Menangkap error lain
        print(f"Error in get_previous_debt: {e}")
        return decimal.Decimal(0)
    
    
def calculate_shares_logic(total_sales, utang_dibawa, utang_baru_manual):
    """
    Logika inti untuk menghitung bagi hasil.
    Semua input harus decimal.Decimal
    """
    total_sales = decimal.Decimal(total_sales)
    utang_dibawa = decimal.Decimal(utang_dibawa)
    utang_baru_manual = decimal.Decimal(utang_baru_manual)

    hak_owner_30 = total_sales * decimal.Decimal(0.3)
    hak_tenant_70 = total_sales * decimal.Decimal(0.7)
    
    total_utang = utang_dibawa + utang_baru_manual
    
    # Hitung net share dan sisa utang
    net_tenant_share = decimal.Decimal(0)
    sisa_utang = decimal.Decimal(0)
    
    if hak_tenant_70 > total_utang:
        net_tenant_share = hak_tenant_70 - total_utang
        sisa_utang = decimal.Decimal(0)
    else:
        net_tenant_share = decimal.Decimal(0)
        sisa_utang = total_utang - hak_tenant_70
        
    # Bagi pembayaran
    p1_nominal = net_tenant_share * decimal.Decimal(0.3)
    # P2 mengambil sisa untuk menghindari pembulatan
    p2_nominal = net_tenant_share - p1_nominal
    
    return {
        "hak_owner_30": hak_owner_30.quantize(decimal.Decimal('0.01')),
        "hak_tenant_70": hak_tenant_70.quantize(decimal.Decimal('0.01')),
        "total_utang": total_utang.quantize(decimal.Decimal('0.01')),
        "net_tenant_share": net_tenant_share.quantize(decimal.Decimal('0.01')),
        "sisa_utang": sisa_utang.quantize(decimal.Decimal('0.01')),
        "p1_nominal": p1_nominal.quantize(decimal.Decimal('0.01')),
        "p2_nominal": p2_nominal.quantize(decimal.Decimal('0.01')),
    }


# --- Endpoints ---

# ✅ KALKULASI: Hitung ulang rekap bulanan untuk semua tenant
@admin_endpoints.route('/kalkulasi', methods=['POST'])
def calculate_all_tenant_shares():
    connection = None
    cursor = None
    try:
        # Ambil data dari JSON body
        data = request.json
        periode_str = data.get('periode') # "YYYY-MM"
        
        if not periode_str:
            return jsonify({"message": "ERROR", "error": "Periode (YYYY-MM) wajib diisi"}), 400
        
        periode_dt_str = f"{periode_str}-01" # "YYYY-MM-01"
        
        connection = get_connection()
        cursor = connection.cursor()
        
        # 1. Dapatkan semua tenant
        cursor.execute("SELECT id_tenant FROM tenants")
        tenants = cursor.fetchall()
        
        processed_count = 0
        
        # 2. Loop setiap tenant
        for (id_tenant,) in tenants:
            # 3. Hitung total penjualan lunas
            total_sales = get_total_sales_for_tenant(cursor, id_tenant, periode_str)
            
            # 4. Ambil sisa utang dari bulan lalu
            utang_dibawa = get_previous_debt(cursor, id_tenant, periode_dt_str)
            
            # 5. Dapatkan utang manual (jika ada) agar tidak ter-reset
            cursor.execute("SELECT utang_baru_manual FROM rekap_bagi_hasil WHERE id_tenant = %s AND periode = %s", (id_tenant, periode_dt_str))
            existing_rekap = cursor.fetchone()
            utang_baru_manual = existing_rekap[0] if existing_rekap else decimal.Decimal(0)

            # 6. Hitung bagi hasil
            shares = calculate_shares_logic(total_sales, utang_dibawa, utang_baru_manual)

            # 7. Simpan (INSERT ... ON DUPLICATE KEY UPDATE)
            query = """
                INSERT INTO rekap_bagi_hasil (
                    id_tenant, periode, total_penjualan_kotor, utang_dibawa, 
                    total_utang, hak_owner_30, hak_tenant_70, net_tenant_share, 
                    sisa_utang, p1_nominal, p2_nominal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_penjualan_kotor = VALUES(total_penjualan_kotor),
                    utang_dibawa = VALUES(utang_dibawa),
                    total_utang = VALUES(total_utang),
                    hak_owner_30 = VALUES(hak_owner_30),
                    hak_tenant_70 = VALUES(hak_tenant_70),
                    net_tenant_share = VALUES(net_tenant_share),
                    sisa_utang = VALUES(sisa_utang),
                    p1_nominal = VALUES(p1_nominal),
                    p2_nominal = VALUES(p2_nominal);
            """
            cursor.execute(query, (
                id_tenant, periode_dt_str, total_sales, utang_dibawa,
                shares['total_utang'], shares['hak_owner_30'], shares['hak_tenant_70'],
                shares['net_tenant_share'], shares['sisa_utang'], 
                shares['p1_nominal'], shares['p2_nominal']
            ))
            processed_count += 1

        connection.commit()
        return jsonify({"message": f"Kalkulasi berhasil untuk {processed_count} tenant."}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ GET REKAP: Ambil data rekapitulasi by periode
@admin_endpoints.route('/rekap', methods=['GET'])
def get_rekap_by_period():
    connection = None
    cursor = None
    try:
        # Ambil data dari query params
        periode_str = request.args.get('periode') # "YYYY-MM"
        if not periode_str:
            return jsonify({"message": "ERROR", "error": "Query param 'periode' (YYYY-MM) wajib diisi"}), 400
        
        connection = get_connection()
        # Gunakan 'dictionary=True' untuk mendapatkan hasil sebagai dict, bukan tuple
        cursor = connection.cursor(dictionary=True) 

        # 1. Ambil data utama
        query_data = """
            SELECT r.*, t.nama_tenant 
            FROM rekap_bagi_hasil r 
            JOIN tenants t ON r.id_tenant = t.id_tenant 
            WHERE DATE_FORMAT(r.periode, '%%Y-%%m') = %s 
            ORDER BY t.nama_tenant
        """
        cursor.execute(query_data, (periode_str,))
        data_list = cursor.fetchall()
        
        # 2. Ambil data total
        query_totals = """
            SELECT 
                SUM(total_penjualan_kotor) AS totalGross,
                SUM(hak_tenant_70) AS totalTenantShare,
                SUM(hak_owner_30) AS totalOwnerShare
            FROM rekap_bagi_hasil 
            WHERE DATE_FORMAT(periode, '%%Y-%%m') = %s
        """
        cursor.execute(query_totals, (periode_str,))
        totals = cursor.fetchone()
        
        # Handle jika belum ada data sama sekali
        if totals['totalGross'] is None:
            totals = {'totalGross': 0, 'totalTenantShare': 0, 'totalOwnerShare': 0}

        # Commit tidak diperlukan untuk GET
        return jsonify({"totals": totals, "data": data_list}), 200

    except Exception as e:
        # Rollback tidak diperlukan untuk GET
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ UPDATE REKAP: Update utang manual atau status bayar
@admin_endpoints.route('/rekap/<int:id_rekap>', methods=['PUT'])
def update_rekap_record(id_rekap):
    connection = None
    cursor = None
    try:
        # Ambil data dari JSON body
        data = request.json
        
        connection = get_connection()
        cursor = connection.cursor()

        # Kasus 1: Update Utang Manual (Perlu kalkulasi ulang)
        if 'utang_baru_manual' in data:
            utang_baru_manual = decimal.Decimal(data['utang_baru_manual'])
            
            # 1. Ambil data saat ini
            cursor.execute("SELECT total_penjualan_kotor, utang_dibawa FROM rekap_bagi_hasil WHERE id_rekap = %s", (id_rekap,))
            rekap = cursor.fetchone()
            if not rekap:
                return jsonify({"message": "ERROR", "error": "ID Rekap tidak ditemukan"}), 404
            
            total_sales, utang_dibawa = rekap
            
            # 2. Hitung ulang
            shares = calculate_shares_logic(total_sales, utang_dibawa, utang_baru_manual)
            
            # 3. Update ke DB
            query = """
                UPDATE rekap_bagi_hasil SET
                    utang_baru_manual = %s,
                    total_utang = %s,
                    net_tenant_share = %s,
                    sisa_utang = %s,
                    p1_nominal = %s,
                    p2_nominal = %s
                WHERE id_rekap = %s
            """
            cursor.execute(query, (
                utang_baru_manual, shares['total_utang'], shares['net_tenant_share'],
                shares['sisa_utang'], shares['p1_nominal'], shares['p2_nominal'],
                id_rekap
            ))
            
        # Kasus 2: Update Status Bayar P1 (Simple update)
        elif 'p1_status_bayar' in data:
            status_bool = bool(data['p1_status_bayar'])
            query = "UPDATE rekap_bagi_hasil SET p1_status_bayar = %s WHERE id_rekap = %s"
            cursor.execute(query, (status_bool, id_rekap))
            
        # Kasus 3: Update Status Bayar P2 (Simple update)
        elif 'p2_status_bayar' in data:
            status_bool = bool(data['p2_status_bayar'])
            query = "UPDATE rekap_bagi_hasil SET p2_status_bayar = %s WHERE id_rekap = %s"
            cursor.execute(query, (status_bool, id_rekap))
            
        else:
            return jsonify({"message": "ERROR", "error": "Body JSON tidak valid"}), 400

        connection.commit()
        return jsonify({"message": "Rekap berhasil diperbarui"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

@admin_endpoints.route('/dashboard-data', methods=['GET'])
def get_admin_dashboard_data():
    """
    Mengambil semua data agregat untuk dasbor admin berdasarkan rentang tanggal.
    Menerima parameter opsional: ?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
    """
    connection = None
    cursor = None
    try:
        # PERBAIKAN: Ambil tanggal dari parameter. Jika tidak ada, gunakan bulan ini sebagai default.
        today = date.today()
        start_date_str = request.args.get('startDate', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date_str = request.args.get('endDate', today.strftime('%Y-%m-%d'))

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Top Sale & Penjualan per Tenant (Pie Chart) - DENGAN FILTER TANGGAL
        query_tenant_sales = """
            SELECT name, SUM(value) as value FROM (
                -- Penjualan F&B per Tenant
                SELECT ten.nama_tenant AS name, SUM(t.total_harga_final) AS value
                FROM transaksi t
                JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
                JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                JOIN tenants ten ON kp.id_tenant = ten.id_tenant
                WHERE t.status_pembayaran = 'Lunas' AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY ten.nama_tenant
                
                UNION ALL
                
                -- Penjualan Space (Ruangan, Event, Membership, VO)
                SELECT 'Dago Creative Space' AS name, SUM(t.total_harga_final) AS value
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas' AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s AND (
                    t.id_transaksi IN (SELECT id_transaksi FROM booking_ruangan) OR
                    t.id_transaksi IN (SELECT id_transaksi FROM booking_event) OR
                    t.id_transaksi IN (SELECT id_transaksi FROM memberships) OR
                    t.id_transaksi IN (SELECT id_transaksi FROM client_virtual_office)
                )
            ) as combined_sales
            WHERE value IS NOT NULL
            GROUP BY name;
        """
        cursor.execute(query_tenant_sales, (start_date_str, end_date_str, start_date_str, end_date_str))
        tenant_sales = cursor.fetchall()
        top_sale_total = sum(item['value'] for item in tenant_sales if item['value'])

        # 2. Penjualan per Kategori Produk (Pie Chart) - DENGAN FILTER TANGGAL
        query_category_sales = """
            SELECT 
                CONCAT(SUBSTRING(ten.nama_tenant, 1, 3), '_', kp.nama_kategori) as name, 
                SUM(dof.jumlah * dof.harga_saat_order) as value
            FROM detail_order_fnb dof
            JOIN transaksi t ON dof.id_transaksi = t.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            JOIN tenants ten ON kp.id_tenant = ten.id_tenant
            WHERE t.status_pembayaran = 'Lunas' AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY name ORDER BY value DESC;
        """
        cursor.execute(query_category_sales, (start_date_str, end_date_str))
        category_sales = cursor.fetchall()

        # 3. Top 10 Produk Terlaris (Tabel) - DENGAN FILTER TANGGAL
        query_top_products = """
            SELECT 
                ten.nama_tenant as merchant, pf.nama_produk as item,
                SUM(dof.jumlah) as qty, SUM(dof.jumlah * dof.harga_saat_order) as total
            FROM detail_order_fnb dof
            JOIN transaksi t ON dof.id_transaksi = t.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            JOIN tenants ten ON kp.id_tenant = ten.id_tenant
            WHERE t.status_pembayaran = 'Lunas' AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY merchant, item ORDER BY total DESC LIMIT 10;
        """
        cursor.execute(query_top_products, (start_date_str, end_date_str))
        top_products = cursor.fetchall()

        # 4. Penjualan Harian (Line Chart) - DENGAN FILTER TANGGAL & LOGIKA BARU
        query_daily_selling = """
            SELECT DATE_FORMAT(tanggal_transaksi, '%Y-%m-%d') as period, SUM(total_harga_final) as total
            FROM transaksi
            WHERE status_pembayaran = 'Lunas' AND DATE(tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY period ORDER BY period ASC;
        """
        cursor.execute(query_daily_selling, (start_date_str, end_date_str))
        daily_selling_rows = cursor.fetchall()
        
        # Logika baru untuk mengisi tanggal yang kosong
        sales_map = {row['period']: int(row['total']) for row in daily_selling_rows}
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        delta = end_date - start_date
        
        all_dates = [(start_date + timedelta(days=i)) for i in range(delta.days + 1)]
        daily_labels = [d.strftime('%a, %d %b') for d in all_dates]
        daily_data = [sales_map.get(d.strftime('%Y-%m-%d'), 0) for d in all_dates]
        daily_selling = {"labels": daily_labels, "data": daily_data}
        
        # 5. Penjualan Bulanan (6 bulan terakhir - Bar Chart) - Query ini tetap relatif terhadap HARI INI
        query_monthly_summary = """
            SELECT DATE_FORMAT(tanggal_transaksi, '%Y-%m') as period, SUM(total_harga_final) as total
            FROM transaksi
            WHERE status_pembayaran = 'Lunas' AND tanggal_transaksi >= DATE_FORMAT(NOW() - INTERVAL 5 MONTH, '%Y-%m-01')
            GROUP BY period ORDER BY period ASC;
        """
        cursor.execute(query_monthly_summary)
        monthly_summary_rows = cursor.fetchall()
        # Logika helper sederhana untuk mengisi bulan kosong
        monthly_sales_map = {row['period']: int(row['total']) for row in monthly_summary_rows}
        monthly_labels = []
        monthly_data = []
        for i in range(5, -1, -1):
            current_month = datetime.now().date().replace(day=1) - timedelta(days=i*30) # Perkiraan
            label = current_month.strftime('%b')
            key = current_month.strftime('%Y-%m')
            monthly_labels.append(label)
            monthly_data.append(monthly_sales_map.get(key, 0))
        monthly_summary = {"labels": monthly_labels, "data": monthly_data}

        return jsonify({
            "message": "OK",
            "datas": {
                "topSaleTotal": int(top_sale_total or 0),
                "tenantSales": tenant_sales,
                "categorySales": category_sales,
                "topProducts": top_products,
                "dailySelling": daily_selling,
                "monthlySummary": monthly_summary
            }
        })

    except Exception as e:
        print(f"Error in /admin/dashboard-data: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# Di dalam file blueprint/endpoint admin Anda

@admin_endpoints.route('/transactions', methods=['GET'])
# @admin_required
def get_transaction_history():
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')

    if not start_date or not end_date:
        return jsonify({"message": "ERROR", "error": "startDate and endDate parameters are required"}), 400

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # PERBAIKAN: Query yang lebih komprehensif untuk semua jenis transaksi
        query = """
            SELECT 
                t.id_transaksi,
                t.tanggal_transaksi,
                COALESCE(u.nama, t.nama_guest, 'Guest') as name,
                t.total_harga_final as total,
                COALESCE(p.nilai_diskon, 0) as discount,
                (t.total_harga_final + COALESCE(p.nilai_diskon, 0)) as subtotal,
                CASE
                    WHEN fnb.id_transaksi IS NOT NULL THEN 
                        CASE 
                            WHEN t.fnb_type = 'Dine In' AND t.lokasi_pemesanan IS NOT NULL THEN CONCAT('F&B (', t.lokasi_pemesanan, ')')
                            WHEN t.fnb_type IS NOT NULL THEN CONCAT('F&B (', t.fnb_type, ')')
                            ELSE 'F&B'
                        END
                    WHEN br.id_transaksi IS NOT NULL THEN CONCAT('Sewa Ruangan (', r.nama_ruangan, ')')
                    WHEN be.id_transaksi IS NOT NULL THEN CONCAT('Sewa Event (', es.nama_event_space, ')')
                    WHEN m.id_transaksi IS NOT NULL THEN 'Pembelian Membership'
                    WHEN vo.id_transaksi IS NOT NULL THEN 'Pembelian Virtual Office'
                    ELSE 'Lainnya'
                END as category
            FROM transaksi t
            LEFT JOIN users u ON t.id_user = u.id_user
            LEFT JOIN promo p ON t.id_promo = p.id_promo
            -- Join untuk identifikasi tipe transaksi
            LEFT JOIN (SELECT DISTINCT id_transaksi FROM detail_order_fnb) fnb ON t.id_transaksi = fnb.id_transaksi
            LEFT JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
            LEFT JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            LEFT JOIN booking_event be ON t.id_transaksi = be.id_transaksi
            LEFT JOIN event_spaces es ON be.id_event_space = es.id_event_space
            LEFT JOIN memberships m ON t.id_transaksi = m.id_transaksi
            LEFT JOIN client_virtual_office vo ON t.id_transaksi = vo.id_transaksi
            WHERE 
                DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                AND t.status_pembayaran = 'Lunas'
            ORDER BY t.tanggal_transaksi DESC;
        """
        cursor.execute(query, (start_date, end_date))
        transactions = cursor.fetchall()
        
        total_transaction_value = sum(item['total'] for item in transactions)

        return jsonify({
            "message": "OK",
            "datas": {
                "transactions": transactions,
                "summary": {
                    "totalTransaction": int(total_transaction_value),
                    "currentBalance": 0
                }
            }
        })

    except Exception as e:
        print(f"Error in /admin/transactions: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    

@admin_endpoints.route('/costBulananRead', methods=['GET'])
@jwt_required()
def get_all_pengeluaran():
    connection = None
    cursor = None
    try:
        # --- PERUBAHAN 1: Ambil startDate dan endDate ---
        start_date_str = request.args.get('startDate')
        end_date_str = request.args.get('endDate')

        if not start_date_str or not end_date_str:
            return jsonify({"message": "ERROR", "error": "Parameter startDate dan endDate wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # --- PERUBAHAN 2: Modifikasi Query SQL ---
        query = """
            SELECT 
                id_pengeluaran AS id, 
                tanggal_pengeluaran AS tanggal, 
                kategori, 
                deskripsi, 
                jumlah 
            FROM pengeluaran_operasional 
            WHERE tanggal_pengeluaran BETWEEN %s AND %s
            ORDER BY tanggal_pengeluaran DESC
        """
        # --- PERUBAHAN 3: Update Parameter ---
        cursor.execute(query, (start_date_str, end_date_str))
        results = cursor.fetchall()

        for row in results:
            if isinstance(row['tanggal'], date):
               row['tanggal'] = row['tanggal'].strftime('%Y-%m-%d')

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        

# ✅ POST: Membuat data pengeluaran baru
@admin_endpoints.route('/costBulananCreate', methods=['POST'])
@jwt_required()
def create_pengeluaran():
    connection = None
    cursor = None
    try:
        # --- PERBAIKAN DIMULAI DI SINI ---
        
        # 1. Dapatkan seluruh identity object (dictionary)
        jwt_identity = get_jwt_identity()
        
        # 2. Ekstrak 'id_user' dari dictionary tersebut
        try:
            dicatat_oleh = jwt_identity.get('id_user')
            if not dicatat_oleh:
                return jsonify({"message": "ERROR", "error": "Format token tidak valid atau tidak berisi id_user"}), 401
        except AttributeError:
            # Fallback jika token HANYA berisi ID (bukan dict)
            dicatat_oleh = jwt_identity
            
        # --- PERBAIKAN SELESAI ---

        data = request.get_json()
        tanggal = data.get('tanggal')
        kategori = data.get('kategori')
        deskripsi = data.get('deskripsi')
        jumlah = data.get('jumlah')
        
        if not all([tanggal, kategori, deskripsi, jumlah]):
            return jsonify({"message": "ERROR", "error": "Semua field wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            INSERT INTO pengeluaran_operasional 
            (tanggal_pengeluaran, kategori, deskripsi, jumlah, dicatat_oleh) 
            VALUES (%s, %s, %s, %s, %s)
        """
        
        # 'dicatat_oleh' sekarang adalah integer (misal: 1), bukan dictionary
        cursor.execute(query, (tanggal, kategori, deskripsi, jumlah, dicatat_oleh))
        connection.commit()

        return jsonify({"message": "Pengeluaran berhasil ditambahkan"}), 201

    except Exception as e:
        if connection: connection.rollback()
        # Mengirimkan error yang lebih spesifik ke konsol untuk debugging
        import traceback
        traceback.print_exc() 
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
# ✅ PUT: Memperbarui data pengeluaran berdasarkan ID
@admin_endpoints.route('costBulananUpdate/<int:id_pengeluaran>', methods=['PUT'])
@jwt_required()
def update_pengeluaran(id_pengeluaran):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        tanggal = data.get('tanggal')
        kategori = data.get('kategori')
        deskripsi = data.get('deskripsi')
        jumlah = data.get('jumlah')

        if not all([tanggal, kategori, deskripsi, jumlah]):
            return jsonify({"message": "ERROR", "error": "Semua field wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = """
            UPDATE pengeluaran_operasional SET 
            tanggal_pengeluaran = %s, 
            kategori = %s, 
            deskripsi = %s, 
            jumlah = %s 
            WHERE id_pengeluaran = %s
        """
        cursor.execute(query, (tanggal, kategori, deskripsi, jumlah, id_pengeluaran))
        connection.commit()
        
        if cursor.rowcount == 0:
             return jsonify({"message": "ERROR", "error": "Data pengeluaran tidak ditemukan"}), 404

        return jsonify({"message": "Pengeluaran berhasil diperbarui"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE: Menghapus data pengeluaran berdasarkan ID
@admin_endpoints.route('costBulananDelete/<int:id_pengeluaran>', methods=['DELETE'])
@jwt_required()
def delete_pengeluaran(id_pengeluaran):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM pengeluaran_operasional WHERE id_pengeluaran = %s"
        cursor.execute(query, (id_pengeluaran,))
        connection.commit()
        
        if cursor.rowcount == 0:
             return jsonify({"message": "ERROR", "error": "Data pengeluaran tidak ditemukan"}), 404

        return jsonify({"message": "Pengeluaran berhasil dihapus"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@admin_endpoints.route('/laporanBagiHasil', methods=['GET'])
@jwt_required()
def get_laporan_bagi_hasil():
    connection = None
    cursor = None
    try:
        start_date_str = request.args.get('startDate')
        end_date_str = request.args.get('endDate')

        if not start_date_str or not end_date_str:
            return jsonify({"message": "ERROR", "error": "Parameter startDate dan endDate wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # --- QUERY SQL DIPERBARUI ---
        # Menggunakan COALESCE dan NULLIF untuk menangani pembagian nol dan nilai null
        query = """
            -- BAGIAN 1: TENANT F&B (Menggunakan proporsi item terhadap total transaksi untuk split pajak/diskon)
            SELECT 
                t.id_tenant AS id,
                t.nama_tenant AS tenant,
                
                -- Subtotal Murni Barang
                SUM(dof.harga_saat_order * dof.jumlah) AS subtotal,
                
                -- Pajak (Proporsional: (Subtotal Item / Subtotal Transaksi) * Pajak Transaksi)
                SUM(tr.pajak_nominal * ((dof.harga_saat_order * dof.jumlah) / NULLIF(tr.subtotal, 0))) AS tax,
                
                -- Diskon (Proporsional)
                SUM(tr.discount_nominal * ((dof.harga_saat_order * dof.jumlah) / NULLIF(tr.subtotal, 0))) AS discount,
                
                -- Grand Total (Uang Masuk Riil per Item)
                SUM(
                    (dof.harga_saat_order * dof.jumlah) + 
                    (tr.pajak_nominal * ((dof.harga_saat_order * dof.jumlah) / NULLIF(tr.subtotal, 0))) - 
                    (tr.discount_nominal * ((dof.harga_saat_order * dof.jumlah) / NULLIF(tr.subtotal, 0)))
                ) AS grandTotal,
                
                -- Bagi Hasil (Basis perhitungan biasanya dari Subtotal atau Grand Total - Tax. Di sini kita pakai Gross Sales items * 0.7 sesuai kode lama)
                SUM(dof.harga_saat_order * dof.jumlah) * 0.7 AS tenantShare,
                SUM(dof.harga_saat_order * dof.jumlah) * 0.3 AS ownerShare,
                
                FALSE AS isInternal
            FROM transaksi tr
            JOIN detail_order_fnb dof ON tr.id_transaksi = dof.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            JOIN tenants t ON kp.id_tenant = t.id_tenant
            WHERE tr.status_pembayaran = 'Lunas' AND DATE(tr.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY t.id_tenant, t.nama_tenant

            UNION ALL

            -- BAGIAN 2: PENDAPATAN INTERNAL (Working Space, Event, dll)
            SELECT
                999 AS id,
                'Dago Creative Space (Internal)' AS tenant,
                SUM(tr.subtotal) AS subtotal,
                SUM(tr.pajak_nominal) AS tax,
                SUM(tr.discount_nominal) AS discount,
                SUM(tr.total_harga_final) AS grandTotal, -- Total uang masuk
                
                -- Bagi hasil 0 untuk internal, semua masuk Owner
                0 AS tenantShare,
                SUM(tr.total_harga_final) AS ownerShare, -- Owner dapat grand total (atau net tergantung kebijakan, disini grand total)
                
                TRUE AS isInternal
            FROM transaksi tr
            -- Left join ke semua tabel sumber internal untuk memastikan ini bukan transaksi F&B murni yang tidak tercatat
            LEFT JOIN booking_ruangan br ON tr.id_transaksi = br.id_transaksi
            LEFT JOIN booking_event be ON tr.id_transaksi = be.id_transaksi
            LEFT JOIN memberships m ON tr.id_transaksi = m.id_transaksi
            LEFT JOIN client_virtual_office cvo ON tr.id_transaksi = cvo.id_transaksi
            WHERE 
                tr.status_pembayaran = 'Lunas' 
                AND DATE(tr.tanggal_transaksi) BETWEEN %s AND %s
                -- Filter: Pastikan salah satu ID booking/member ada (menandakan ini internal)
                AND (br.id_booking IS NOT NULL OR be.id_booking_event IS NOT NULL OR m.id_memberships IS NOT NULL OR cvo.id_client_vo IS NOT NULL)
        """
        
        # Parameter tanggal (diulang 4 kali karena ada 4 placeholder %s)
        params = (start_date_str, end_date_str, start_date_str, end_date_str)
        cursor.execute(query, params)
        results = cursor.fetchall()

        final_results = []
        dago_exists = False
        
        # Pembersihan Data (Konversi Decimal ke Float untuk JSON)
        for row in results:
            if row['grandTotal'] is None and row['subtotal'] is None: 
                continue 
            
            # Helper function untuk safe float conversion
            def to_float(val): return float(val) if val is not None else 0.0

            row['subtotal'] = to_float(row['subtotal'])
            row['tax'] = to_float(row['tax'])
            row['discount'] = to_float(row['discount'])
            row['grandTotal'] = to_float(row['grandTotal'])
            row['tenantShare'] = to_float(row['tenantShare'])
            row['ownerShare'] = to_float(row['ownerShare'])
            
            if row['isInternal']: 
                dago_exists = True
            
            final_results.append(row)

        # Jika tidak ada transaksi internal, tetap tampilkan baris Dago (0 rupiah) agar tabel rapi
        if not dago_exists:
            final_results.append({
                'id': 999, 'tenant': 'Dago Creative Space (Internal)',
                'subtotal': 0.0, 'tax': 0.0, 'discount': 0.0, 'grandTotal': 0.0,
                'tenantShare': 0.0, 'ownerShare': 0.0, 'isInternal': True
            })

        return jsonify(final_results), 200

    except Exception as e:
        print(f"Error Report: {e}") # Log error di server console
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
# ------------------- WS DASHBOARD (sesuai brief) -------------------
# --- WS Dashboard: sesuai DB (durasi dari paket_harga_ruangan, daily=1..N) ---
@admin_endpoints.route('/ws-dashboard-data', methods=['GET'])
def ws_dashboard_data():
    """
    Data untuk Working Space Dashboard:
    - stats: totalRevenue, totalBookings, totalVisitors
    - dailyRevenue: labels -> ['1','2',...,'N'] (hari dalam range, berurutan TANPA loncat)
                    labelsPretty -> ['1 Okt','2 Okt', ...] untuk tooltip
                    datasets -> jumlah booking per kategori/hari
    - categoryContribution: [{name, value}] (revenue per kategori)
    - packageByDuration: sumbu-X = DISTINCT paket_harga_ruangan.durasi_jam (saja),
                         hitung booking yang MATCH paket pada RUANGAN yang sama
                         -> [{durasi_jam, total_booking, total_user, total_revenue}]
    - topSpaces: Top 10 ruang urut qty booking DESC, tie-break total DESC
    """
    conn = None
    cur = None
    try:
        # default ke bulan berjalan
        today = date.today()
        start_date_str = request.args.get('startDate', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date_str   = request.args.get('endDate',   today.strftime('%Y-%m-%d'))

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_date_str,   '%Y-%m-%d').date()
        if end_date < start_date:
            return jsonify({"message": "ERROR", "error": "endDate < startDate"}), 400

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # ---------- 1) STATS ----------
        cur.execute("""
            SELECT
              COALESCE(SUM(t.total_harga_final), 0)                           AS totalRevenue,
              COUNT(br.id_booking)                                            AS totalBookings,
              COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR))) AS totalVisitors
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        s = cur.fetchone() or {}
        stats = {
            "totalRevenue": int(s.get("totalRevenue") or 0),
            "totalBookings": int(s.get("totalBookings") or 0),
            "totalVisitors": int(s.get("totalVisitors") or 0),
        }

        # ---------- 2) DAILY BOOKING (labels = hari 1..N) ----------
        days_count = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(days_count)]
        pos_map = {(start_date + timedelta(days=i)).strftime('%Y-%m-%d'): i for i in range(days_count)}

        labels_days   = [str(d.day) for d in all_dates]  # "1".."N"
        # Hindari %-d (tidak portable di Windows)
        labels_pretty = [f"{int(d.strftime('%d'))} {d.strftime('%b')}" for d in all_dates]

        categories = ["Open Space", "Space Monitor", "Room Meeting Besar", "Room Meeting Kecil"]
        dataset_map_counts = {k: [0] * days_count for k in categories}

        cur.execute("""
            SELECT
              DATE(br.waktu_mulai) AS period_date,
              kr.nama_kategori     AS category,
              COUNT(*)             AS cnt
            FROM booking_ruangan br
            JOIN transaksi t            ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r              ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr    ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY period_date, category
            ORDER BY period_date ASC
        """, (start_date_str, end_date_str))
        for row in cur.fetchall() or []:
            key = row["period_date"].strftime('%Y-%m-%d')
            idx = pos_map.get(key)
            cat = row["category"]
            if idx is not None and cat in dataset_map_counts:
                dataset_map_counts[cat][idx] = int(row["cnt"] or 0)

        dailyRevenue = {
            "labels": labels_days,          # sumbu-X 1..N
            "labelsPretty": labels_pretty,  # tooltip "1 Okt", dst.
            "datasets": dataset_map_counts
        }

        # ---------- 3) CATEGORY CONTRIBUTION (DOUGHNUT) ----------
        cur.execute("""
            SELECT kr.nama_kategori AS name, SUM(t.total_harga_final) AS value
            FROM transaksi t
            JOIN booking_ruangan br  ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r           ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY name
        """, (start_date_str, end_date_str))
        categoryContribution = [
            {"name": r["name"], "value": int(r["value"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # ---------- 4) PACKAGE BY DURATION (HANYA dari paket_harga_ruangan) ----------
        # Sumbu-X durasi dari paket (distinct & urut)
        cur.execute("""
          SELECT DISTINCT durasi_jam
          FROM paket_harga_ruangan
          WHERE durasi_jam IS NOT NULL
          ORDER BY durasi_jam ASC
        """)
        durations = [int(r["durasi_jam"]) for r in (cur.fetchall() or [])]

        # Hitung booking yang MATCH paket (id_ruangan sama & durasi jam sama PERSIS)
        # TIMESTAMPDIFF(HOUR, ...) melakukan floor — cocok jika booking dibuat pas per jam.
        cur.execute("""
          SELECT
            p.durasi_jam AS durasi_jam,
            COUNT(*) AS total_booking,
            COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR))) AS total_user,
            COALESCE(SUM(t.total_harga_final), 0) AS total_revenue
          FROM booking_ruangan br
          JOIN transaksi t ON t.id_transaksi = br.id_transaksi
          JOIN paket_harga_ruangan p
            ON p.id_ruangan = br.id_ruangan
           AND p.durasi_jam = TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)
          WHERE t.status_pembayaran = 'Lunas'
            AND DATE(br.waktu_mulai) BETWEEN %s AND %s
          GROUP BY p.durasi_jam
        """, (start_date_str, end_date_str))
        agg = {
            int(r["durasi_jam"]): {
                "total_booking": int(r["total_booking"] or 0),
                "total_user":    int(r["total_user"] or 0),
                "total_revenue": int(r["total_revenue"] or 0),
            }
            for r in (cur.fetchall() or [])
        }

        packageByDuration = []
        for dj in durations:
            a = agg.get(dj, {"total_booking": 0, "total_user": 0, "total_revenue": 0})
            packageByDuration.append({
                "durasi_jam": dj,
                "total_booking": a["total_booking"],
                "total_user": a["total_user"],
                "total_revenue": a["total_revenue"],
            })

        # ---------- 5) TOP 10 WORKING SPACES ----------
        cur.execute("""
            SELECT
              r.nama_ruangan   AS item,
              kr.nama_kategori AS category,
              COUNT(br.id_booking)      AS qty,
              SUM(t.total_harga_final)  AS total
            FROM transaksi t
            JOIN booking_ruangan br  ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r           ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY item, category
            ORDER BY qty DESC, total DESC
            LIMIT 10
        """, (start_date_str, end_date_str))
        topSpaces = [{
            "item": r["item"],
            "category": r["category"],
            "qty": int(r["qty"] or 0),
            "total": int(r["total"] or 0),
        } for r in (cur.fetchall() or [])]

        return jsonify({
            "message": "OK",
            "datas": {
                "stats": stats,
                "dailyRevenue": dailyRevenue,
                "categoryContribution": categoryContribution,
                "packageByDuration": packageByDuration,
                "topSpaces": topSpaces
            }
        }), 200

    except Exception as e:
        print("Error in /api/v1/admin/ws-dashboard-data:", e)
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        try:
            if cur: cur.close()
        finally:
            if conn: conn.close()
# ------------------- END WS DASHBOARD -------------------