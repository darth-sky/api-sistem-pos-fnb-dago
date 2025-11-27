"""Routes for module tenant"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from datetime import datetime, timedelta
import math
import traceback
from datetime import datetime # --- PERUBAHAN 1: Impor library datetime ---

tenant_endpoints = Blueprint('tenant', __name__)
UPLOAD_FOLDER = "img"


@tenant_endpoints.route('/orders/transaksi/<int:id_transaksi>/status', methods=['PUT'])
def update_transaction_status_by_tenant(id_transaksi):
    data = request.get_json()
    if not data or 'status' not in data or 'tenant_id' not in data:
        return jsonify({"message": "ERROR", "error": "Missing data"}), 400

    new_status_ui = data['status']
    id_tenant = data['tenant_id']
    
    status_map = {
        "ON PROSES": "Diproses",
        "FINISH": "Selesai",
        "NEW": "Baru" # Opsional, jarang dipakai update ke Baru
    }
    
    db_status = status_map.get(new_status_ui)
    if not db_status:
         return jsonify({"message": "ERROR", "error": "Invalid status"}), 400

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # --- PERBAIKAN LOGIKA: Penentuan Status Asal yang Valid ---
        valid_origins = []
        
        if db_status == "Diproses":
            # Hanya boleh dari Baru
            valid_origins = ["Baru"]
        elif db_status == "Selesai":
            # Boleh dari Baru ATAU Diproses (Lebih Fleksibel)
            valid_origins = ["Baru", "Diproses"]
        
        if not valid_origins:
             return jsonify({"message": "ERROR", "error": "Invalid transition"}), 400

        # Buat string placeholder dinamis untuk IN clause (contoh: "%s, %s")
        placeholders = ', '.join(['%s'] * len(valid_origins))

        query_aman = f"""
            UPDATE detail_order_fnb
            SET 
                status_pesanan = %s
            WHERE 
                id_transaksi = %s AND
                status_pesanan IN ({placeholders}) AND -- Menggunakan IN untuk banyak status
                id_produk IN (
                    SELECT p.id_produk
                    FROM produk_fnb p
                    JOIN kategori_produk kp ON p.id_kategori = kp.id_kategori
                    WHERE kp.id_tenant = %s
                );
        """
        
        # Susun parameter urut: [status_baru, id_transaksi, ...status_asal..., id_tenant]
        params = [db_status, id_transaksi] + valid_origins + [id_tenant]

        cursor.execute(query_aman, params)
        connection.commit()

        return jsonify({
            "message": "Update success",
            "rows_affected": cursor.rowcount
        }), 200

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}") 
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()            
            

@tenant_endpoints.route("/updateProdukStatus/<int:id_produk>", methods=["PUT"])
def update_produk_status(id_produk):
    conn = None
    cursor = None
    try:
        data = request.get_json()

        if 'available' not in data or not isinstance(data['available'], bool):
            return jsonify({"message": "ERROR", "error": "Field 'available' (boolean) diperlukan."}), 400

        status_value = 'Active' if data['available'] else 'Inactive'

        print(f"🟢 Update Produk ID: {id_produk}, Status Baru: {status_value}")

        conn = get_connection()
        cursor = conn.cursor()

        query = """
        UPDATE produk_fnb
        SET status_ketersediaan = %s
        WHERE id_produk = %s
        """
        cursor.execute(query, (status_value, id_produk))
        conn.commit()

        # Ganti 404 dengan notifikasi ringan
        if cursor.rowcount == 0:
            return jsonify({
                "message": "Tidak ada data yang diubah (mungkin status sudah sama)."
            }), 200

        return jsonify({
            "message": f"Status ketersediaan produk berhasil diperbarui menjadi '{status_value}'."
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({
            "message": "ERROR",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@tenant_endpoints.route('/orders/tenant/<int:id_tenant>', methods=['GET'])
def get_orders_by_tenant(id_tenant):
    connection = None
    try:
        # --- PERUBAHAN 1: Ambil sesi_id dari query param ---
        sesi_id = request.args.get('sesi_id')
        if not sesi_id:
            return jsonify({"message": "ERROR", "error": "Missing 'sesi_id' query parameter"}), 400
        # --- AKHIR PERUBAHAN 1 ---

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # --- PERUBAHAN 2: Tambahkan t.id_sesi ke query ---
        query = """
            SELECT 
                t.id_transaksi,
                COALESCE(u.nama, t.nama_guest, 'Guest') as customer_name,
                t.fnb_type,
                t.lokasi_pemesanan,
                t.total_harga_final,
                t.tanggal_transaksi,
                dof.id_detail_order,
                dof.jumlah,
                dof.catatan_pesanan,
                dof.status_pesanan,
                p.nama_produk
            FROM transaksi t
            JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
            JOIN produk_fnb p ON dof.id_produk = p.id_produk
            JOIN kategori_produk kp ON p.id_kategori = kp.id_kategori
            LEFT JOIN users u ON t.id_user = u.id_user
            WHERE 
                kp.id_tenant = %s AND
                t.id_sesi = %s AND  -- <-- FILTER SESI DITAMBAHKAN DI SINI
                t.status_pembayaran = 'Lunas' AND
                -- Filter status pesanan yang logis untuk "Dashboard Aktif"
                dof.status_pesanan IN ('Baru', 'Diproses', 'Selesai') 
            ORDER BY t.tanggal_transaksi DESC;
        """
        # --- AKHIR PERUBAHAN 2 ---

        # --- PERUBAHAN 3: Tambahkan sesi_id ke parameter execute ---
        cursor.execute(query, (id_tenant, sesi_id))
        # --- AKHIR PERUBAHAN 3 ---
        
        results = cursor.fetchall()
        
        # ... (Sisa logika pengelompokan data Anda sudah benar) ...
        orders_dict = {}
        for row in results:
            order_id = row['id_transaksi']
            if order_id not in orders_dict:
                orders_dict[order_id] = {
                    "id": order_id,
                    "id_detail_order": row['id_detail_order'],
                    "code": f"ORD-{str(order_id).zfill(4)}",
                    "name": row['customer_name'],
                    "status": row['status_pesanan'],
                    "type": row['fnb_type'],
                    "place": row['lokasi_pemesanan'],
                    "total": int(row['total_harga_final']),
                    "tanggal_transaksi": row['tanggal_transaksi'],
                    "items": []
                }
            
            orders_dict[order_id]['items'].append({
                "name": row['nama_produk'],
                "qty": row['jumlah'],
                "note": row['catatan_pesanan']
            })

        final_orders = list(orders_dict.values())
        return jsonify({"message": "OK", "datas": final_orders})

    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            


@tenant_endpoints.route("/readOrderTenant/<int:id_tenant>", methods=["GET"])
def read_order_tenant(id_tenant):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT 
            t.id_transaksi AS id,
            COALESCE(t.nama_guest, 'Guest') AS name,
            t.tanggal_transaksi,
            t.status_order AS status,
            t.lokasi_pemesanan AS place,
            t.fnb_type AS type,
            t.total_harga_final AS total,
            CONCAT('ORD-', LPAD(t.id_transaksi, 4, '0')) AS code
        FROM transaksi t
        JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        JOIN produk_fnb p ON dof.id_produk = p.id_produk
        JOIN kategori_produk kp ON p.id_kategori = kp.id_kategori
        WHERE kp.id_tenant = %s
        GROUP BY t.id_transaksi
        ORDER BY t.tanggal_transaksi DESC
        """

        cursor.execute(query, (id_tenant,))
        orders = cursor.fetchall()

        # Ambil detail item untuk tiap transaksi
        for order in orders:
            cursor.execute("""
                SELECT 
                    dof.id_detail_order AS id,
                    p.nama_produk AS name,
                    dof.jumlah AS qty,
                    dof.catatan_pesanan AS note
                FROM detail_order_fnb dof
                JOIN produk_fnb p ON dof.id_produk = p.id_produk
                WHERE dof.id_transaksi = %s
            """, (order["id"],))
            order["items"] = cursor.fetchall()

        return jsonify({"message": "OK", "datas": orders}), 200

    except Exception as e:
        print("🔥 ERROR read_order_tenant:", str(e))
        return jsonify({"message": "ERROR", "error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@tenant_endpoints.route("/readProduktenant/<int:id_tenant>", methods=["GET"])
def read_produk_tenant(id_tenant):
    conn = None # Inisialisasi
    cursor = None # Inisialisasi
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
            p.status_visibilitas, -- <-- Bisa ditambahkan jika frontend perlu info ini juga
            p.foto_produk AS foto,
            k.nama_kategori AS category,
            t.nama_tenant AS merchant,
            NOW() AS updated
        FROM produk_fnb p
        JOIN kategori_produk k ON p.id_kategori = k.id_kategori
        LEFT JOIN tenants t ON k.id_tenant = t.id_tenant
        WHERE t.id_tenant = %s
          AND p.status_visibilitas = 'Aktif' -- <-- TAMBAHKAN BARIS INI
        ORDER BY p.id_produk DESC
        """

        cursor.execute(query, (id_tenant,))
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200

    except Exception as e:
        print(f"Error reading tenant products: {e}") # Logging error
        import traceback
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        # Pastikan cursor dan koneksi ditutup
        if cursor:
            cursor.close()
        if conn:
            conn.close()