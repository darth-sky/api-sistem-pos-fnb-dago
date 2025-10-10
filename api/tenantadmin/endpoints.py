"""Routes for module tenantadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

tenantadmin_endpoints = Blueprint("tenantadmin_endpoints", __name__)

# ✅ READ All Tenants (dengan join ke tabel users untuk mendapatkan nama owner)
@tenantadmin_endpoints.route('/tenantRead', methods=['GET'])
def get_all_tenants():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query ini mengambil data tenant beserta nama owner dari tabel users
        query = """
            SELECT 
                t.id_tenant, 
                t.nama_tenant, 
                t.deskripsi_tenant, 
                u.nama as nama_owner,
                u.id_user
            FROM tenants t
            LEFT JOIN users u ON t.id_user = u.id_user
            ORDER BY t.id_tenant DESC
        """
        cursor.execute(query)
        tenants = cursor.fetchall()
        return jsonify({"message": "OK", "datas": tenants}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE a new Tenant
@tenantadmin_endpoints.route('/tenantCreate', methods=['POST'])
def create_tenant():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_tenant = data.get("nama_tenant")
        deskripsi_tenant = data.get("deskripsi_tenant")
        id_user = data.get("id_user")

        if not nama_tenant or not id_user:
            return jsonify({"message": "ERROR", "error": "Nama tenant dan owner wajib diisi"}), 400

        connection = get_connection()
        # Memulai transaksi (di banyak library, ini terjadi secara implisit)
        cursor = connection.cursor()

        # Query 1: Membuat tenant baru
        query_insert_tenant = "INSERT INTO tenants (nama_tenant, deskripsi_tenant, id_user) VALUES (%s, %s, %s)"
        cursor.execute(query_insert_tenant, (nama_tenant, deskripsi_tenant, id_user))

        # Query 2: Mengubah role user menjadi 'admin_tenant'
        query_update_user_role = "UPDATE users SET role = 'admin_tenant' WHERE id_user = %s"
        cursor.execute(query_update_user_role, (id_user,))
        
        # Jika kedua query berhasil, simpan semua perubahan
        connection.commit()

        return jsonify({"message": "Tenant berhasil ditambahkan dan role user telah diperbarui"}), 201

    except Exception as e:
        # Jika terjadi error di salah satu query, batalkan semua perubahan
        if connection:
            connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
        
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE a Tenant
@tenantadmin_endpoints.route('/tenantUpdate/<int:id_tenant>', methods=['PUT'])
def update_tenant(id_tenant):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama_tenant = data.get("nama_tenant")
        deskripsi_tenant = data.get("deskripsi_tenant")
        id_user = data.get("id_user")

        if not nama_tenant or not id_user:
            return jsonify({"message": "ERROR", "error": "Nama tenant dan owner wajib diisi"}), 400
        
        connection = get_connection()
        cursor = connection.cursor()
        query = """
            UPDATE tenants 
            SET nama_tenant = %s, deskripsi_tenant = %s, id_user = %s 
            WHERE id_tenant = %s
        """
        cursor.execute(query, (nama_tenant, deskripsi_tenant, id_user, id_tenant))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404

        return jsonify({"message": "Tenant berhasil diperbarui"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE a Tenant
@tenantadmin_endpoints.route('/tenantDelete/<int:id_tenant>', methods=['DELETE'])
def delete_tenant(id_tenant):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM tenants WHERE id_tenant = %s"
        cursor.execute(query, (id_tenant,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404

        return jsonify({"message": "Tenant berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
        
        
# ✅ Endpoint untuk membaca semua pengguna (hanya ID dan Nama)
@tenantadmin_endpoints.route('/users', methods=['GET'])
def get_all_users():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Ambil user dengan role yang relevan jika perlu, atau semua user
        query = "SELECT id_user, nama FROM users ORDER BY nama ASC"
        cursor.execute(query)
        users = cursor.fetchall()
        return jsonify({"message": "OK", "datas": users}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()