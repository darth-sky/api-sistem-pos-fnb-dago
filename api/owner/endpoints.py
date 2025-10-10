
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from flask_jwt_extended import jwt_required
from datetime import datetime
import json

owner_endpoints = Blueprint('owner_endpoints', __name__)

# Catatan: Fungsi close_db_resources telah dihapus, 
# penutupan cursor dan connection dilakukan di blok finally setiap endpoint.

# --- 1. Total Pendapatan per Kategori ---
@owner_endpoints.route('/totalPendapatan', methods=['GET'])
def getTotalPendapatan():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Kueri untuk menghitung total pendapatan dari 5 kategori utama.
        # Menggunakan kolom t.total_harga_final.
        query = """
        -- 1. Total Pendapatan dari F&B
        SELECT 'F&B' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 2. Total Pendapatan dari Booking Ruangan / Working Space (Non-Membership Credit)
        SELECT 'Working Space' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
        -- Hanya hitung transaksi pembayaran ruangan (bukan penggunaan kredit dari membership yang totalnya 0)
        WHERE br.id_memberships IS NULL OR t.total_harga_final > 0
        GROUP BY kategori

        UNION ALL

        -- 3. Total Pendapatan dari Event Booking
        SELECT 'Event Booking' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN booking_event be ON t.id_transaksi = be.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 4. Total Pendapatan dari Pembelian Membership
        SELECT 'Membership' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN memberships m ON t.id_transaksi = m.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 5. Total Pendapatan dari Pembelian Virtual Office
        SELECT 'Virtual Office' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN client_virtual_office cvo ON t.id_transaksi = cvo.id_transaksi
        GROUP BY kategori

        HAVING total IS NOT NULL AND total > 0; -- Memastikan hanya kategori dengan total pendapatan > 0 yang ditampilkan
        """

        cursor.execute(query)
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTotalPendapatan: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


# --- 2. Top 10 FNB Terlaris ---
@owner_endpoints.route('/topFNB', methods=['GET'])
def getTopFNB():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk mencari Top 10 FNB berdasarkan kuantitas terjual
        query = """
        SELECT 
            COALESCE(pf.nama_produk, 'Produk Tidak Ditemukan') AS item,
            SUM(dof.jumlah) AS qty,
            SUM(dof.jumlah * dof.harga_saat_order) AS total
        FROM detail_order_fnb dof
        LEFT JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
        GROUP BY pf.nama_produk
        ORDER BY qty DESC
        LIMIT 10;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTopFNB: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 3. Top 5 Working Space Terlaris ---
@owner_endpoints.route('/topWorking', methods=['GET'])
def getTopWorking():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk mencari Top 5 Ruangan/Working Space berdasarkan pendapatan.
        # Menggunakan t.total_harga_final
        query = """
        SELECT 
            r.nama_ruangan AS item, -- Asumsi item adalah nama ruangan
            COUNT(br.id_booking) AS qty, -- Jumlah booking
            SUM(t.total_harga_final) AS total -- Mengambil total dari tabel transaksi yang terhubung
        FROM booking_ruangan br
        JOIN ruangan r ON br.id_ruangan = r.id_ruangan
        JOIN transaksi t ON br.id_transaksi = t.id_transaksi
        GROUP BY r.nama_ruangan
        ORDER BY total DESC
        LIMIT 5;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTopWorking: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 4. Penjualan Harian Bulanan (Daily Selling) ---
@owner_endpoints.route('/dailySelling', methods=['GET'])
def getDailySelling():
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not month or not year:
        return jsonify({"message": "Parameter month dan year wajib."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk menghitung total transaksi per hari di bulan dan tahun yang ditentukan
        # Menggunakan total_harga_final
        query = """
        SELECT
            DAY(tanggal_transaksi) AS day,
            SUM(total_harga_final) AS total
        FROM transaksi
        WHERE MONTH(tanggal_transaksi) = %s AND YEAR(tanggal_transaksi) = %s
        GROUP BY DAY(tanggal_transaksi)
        ORDER BY DAY(tanggal_transaksi);
        """
        cursor.execute(query, (month, year))
        results = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getDailySelling: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 5. Ringkasan Profit Bulanan (Profit Summary) ---
@owner_endpoints.route('/profitSummary', methods=['GET'])
def getProfitSummary():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Mengambil data 6 bulan terakhir
        # Menggunakan total_harga_final
        query = """
        SELECT
            DATE_FORMAT(tanggal_transaksi, '%%Y-%%m') AS sort_date,
            DATE_FORMAT(tanggal_transaksi, '%%M') AS bulan, -- Bulan dalam bahasa Inggris default MySQL
            SUM(total_harga_final) AS total
        FROM transaksi
        WHERE tanggal_transaksi >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY sort_date, bulan
        ORDER BY sort_date ASC;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getProfitSummary: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass



@owner_endpoints.route('/fnb-dashboard-data', methods=['GET'])
def getFnBDashboardData():
    # Ambil parameter tanggal dari query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"message": "Error", "error": "Parameter start_date dan end_date wajib."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query Utama: Menarik semua data FNB yang dibutuhkan dalam satu kali panggil.
        query = """
        SELECT
            DATE(t.tanggal_transaksi) AS tanggal,
            SUM(t.total_harga_final) AS daily_sales,
            
            -- Order Type Aggregation (Doughnut Chart 1) - Menggunakan kolom fnb_type
            SUM(CASE WHEN t.fnb_type = 'Dine In' THEN 1 ELSE 0 END) AS dine_in_count,
            SUM(CASE WHEN t.fnb_type = 'Takeaway' THEN 1 ELSE 0 END) AS take_away_count,
            
            -- Payment Type Aggregation (Doughnut Chart 2)
            SUM(CASE WHEN t.metode_pembayaran = 'Cash' THEN 1 ELSE 0 END) AS cash_count,
            SUM(CASE WHEN t.metode_pembayaran != 'Cash' THEN 1 ELSE 0 END) AS non_cash_count,
            
            -- Sales per Tenant (for Progress Bar) - Menggunakan kp.id_tenant dan dof.jumlah
            SUM(CASE 
                WHEN kp.id_tenant = 1 THEN dof.harga_saat_order * dof.jumlah
                ELSE 0 
            END) AS homebro_sales,
            SUM(CASE 
                WHEN kp.id_tenant = 2 THEN dof.harga_saat_order * dof.jumlah
                ELSE 0 
            END) AS dapoerms_sales
            
        FROM 
            transaksi t
        JOIN 
            detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        JOIN
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN 
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            DATE(t.tanggal_transaksi) BETWEEN %s AND %s 
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            DATE(t.tanggal_transaksi)
        ORDER BY
            tanggal;
        """
        
        # Query untuk Top 5 Product (DapoerMS - id_tenant = 2)
        top_product_dapoerms_query = """
        SELECT 
            pf.nama_produk AS item,
            SUM(dof.jumlah) AS qty, -- Kuantitas diubah menjadi jumlah
            SUM(dof.harga_saat_order * dof.jumlah) AS total -- Kuantitas diubah menjadi jumlah
        FROM 
            detail_order_fnb dof
        JOIN 
            transaksi t ON dof.id_transaksi = t.id_transaksi
        JOIN 
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            kp.id_tenant = 2 
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            pf.nama_produk
        ORDER BY 
            total DESC
        LIMIT 5;
        """

        # Query untuk Top 5 Product (HomeBro - id_tenant = 1)
        top_product_homebro_query = """
        SELECT 
            pf.nama_produk AS item,
            SUM(dof.jumlah) AS qty, -- Kuantitas diubah menjadi jumlah
            SUM(dof.harga_saat_order * dof.jumlah) AS total -- Kuantitas diubah menjadi jumlah
        FROM 
            detail_order_fnb dof
        JOIN 
            transaksi t ON dof.id_transaksi = t.id_transaksi
        JOIN 
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            kp.id_tenant = 1 
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            pf.nama_produk
        ORDER BY 
            total DESC
        LIMIT 5;
        """
        
        # Eksekusi Query Utama
        cursor.execute(query, (start_date, end_date))
        daily_sales_data = cursor.fetchall()
        
        # Eksekusi Top 5 DapoerMS
        cursor.execute(top_product_dapoerms_query, (start_date, end_date))
        dapoerms_top_products = cursor.fetchall()
        
        # Eksekusi Top 5 HomeBro
        cursor.execute(top_product_homebro_query, (start_date, end_date))
        homebro_top_products = cursor.fetchall()

        # Gabungkan semua hasil ke dalam satu JSON
        response_data = {
            "daily_sales_data": daily_sales_data,
            "dapoerms_top_products": dapoerms_top_products,
            "homebro_top_products": homebro_top_products
        }

        return jsonify({"message": "OK", "datas": response_data}), 200

    except Exception as e:
        print(f"Error executing getFnBDashboardData: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


