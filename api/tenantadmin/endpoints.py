"""Routes for module tenantadmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename
import uuid # Untuk nama file unik

tenantadmin_endpoints = Blueprint("tenantadmin_endpoints", __name__)


# Definisikan folder untuk menyimpan file upload
UPLOAD_FOLDER = 'img' 



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
                    t.id_tenant, t.nama_tenant, t.deskripsi_tenant, 
                    t.gambar_tenant, 
                    t.status_tenant, -- TAMBAHKAN INI
                    u.nama as nama_owner, u.id_user
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

# ✅ CREATE a new Tenant (dengan upload gambar)
@tenantadmin_endpoints.route('/tenantCreate', methods=['POST'])
def create_tenant_with_image():
    connection = None
    cursor = None
    try:
        # Ambil data form teks
        nama_tenant = request.form.get("nama_tenant")
        deskripsi_tenant = request.form.get("deskripsi_tenant")
        id_user = request.form.get("id_user")

        if not nama_tenant or not id_user:
            return jsonify({"message": "ERROR", "error": "Nama tenant dan owner wajib diisi"}), 400

        gambar_filename = None
        if 'gambar_tenant' in request.files:
            file = request.files['gambar_tenant']
            if file.filename != '':
                # Buat nama file yang aman dan unik
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                gambar_filename = unique_filename

        connection = get_connection()
        cursor = connection.cursor()
        
        # Query 1: Membuat tenant baru dengan nama gambar
        query_insert = "INSERT INTO tenants (nama_tenant, deskripsi_tenant, id_user, gambar_tenant) VALUES (%s, %s, %s, %s)"
        cursor.execute(query_insert, (nama_tenant, deskripsi_tenant, id_user, gambar_filename))

        # Query 2: Mengubah role user
        query_update_role = "UPDATE users SET role = 'admin_tenant' WHERE id_user = %s"
        cursor.execute(query_update_role, (id_user,))
        
        connection.commit()
        return jsonify({"message": "Tenant berhasil ditambahkan"}), 201

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


# ✅ UPDATE a Tenant (dengan upload gambar opsional)
@tenantadmin_endpoints.route('/tenantUpdate/<int:id_tenant>', methods=['PUT'])
def update_tenant_with_image(id_tenant):
    connection = None
    cursor = None
    try:
        nama_tenant = request.form.get("nama_tenant")
        deskripsi_tenant = request.form.get("deskripsi_tenant")
        id_user = request.form.get("id_user")

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Dapatkan nama file gambar lama
        cursor.execute("SELECT gambar_tenant FROM tenants WHERE id_tenant = %s", (id_tenant,))
        tenant = cursor.fetchone()
        if not tenant:
            return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404
        
        old_image = tenant['gambar_tenant']
        gambar_filename = old_image

        # Cek jika ada file baru yang diupload
        if 'gambar_tenant' in request.files:
            file = request.files['gambar_tenant']
            if file.filename != '':
                # Hapus gambar lama jika ada
                if old_image and os.path.exists(os.path.join(UPLOAD_FOLDER, old_image)):
                    os.remove(os.path.join(UPLOAD_FOLDER, old_image))
                
                # Simpan gambar baru
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                gambar_filename = unique_filename
        
        # Update database
        query_update = "UPDATE tenants SET nama_tenant = %s, deskripsi_tenant = %s, id_user = %s, gambar_tenant = %s WHERE id_tenant = %s"
        cursor.execute(query_update, (nama_tenant, deskripsi_tenant, id_user, gambar_filename, id_tenant))
        connection.commit()

        return jsonify({"message": "Tenant berhasil diperbarui"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()


@tenantadmin_endpoints.route('/tenantUpdateStatus/<int:id_tenant>', methods=['PUT'])
def update_tenant_status(id_tenant):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        new_status = data.get('status_tenant')

        if not new_status or new_status not in ['Active', 'Inactive']:
            return jsonify({"message": "ERROR", "error": "Status tidak valid"}), 400

        connection = get_connection()
        cursor = connection.cursor()
        query = "UPDATE tenants SET status_tenant = %s WHERE id_tenant = %s"
        cursor.execute(query, (new_status, id_tenant))
        connection.commit()

        return jsonify({"message": f"Status tenant berhasil diubah ke {new_status}"}), 200

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE a Tenant (beserta file gambarnya)
@tenantadmin_endpoints.route('/tenantDelete/<int:id_tenant>', methods=['DELETE'])
def delete_tenant_with_image(id_tenant):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Dapatkan nama file gambar sebelum dihapus dari DB
        cursor.execute("SELECT gambar_tenant FROM tenants WHERE id_tenant = %s", (id_tenant,))
        tenant = cursor.fetchone()
        if not tenant:
            return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404
        
        # 2. Hapus data tenant dari database
        cursor.execute("DELETE FROM tenants WHERE id_tenant = %s", (id_tenant,))
        connection.commit()

        # 3. Hapus file gambar dari server
        image_to_delete = tenant['gambar_tenant']
        if image_to_delete and os.path.exists(os.path.join(UPLOAD_FOLDER, image_to_delete)):
            os.remove(os.path.join(UPLOAD_FOLDER, image_to_delete))

        return jsonify({"message": "Tenant berhasil dihapus"}), 200
        
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ Endpoint BARU untuk menyajikan

# # ✅ READ All Tenants (dengan join ke tabel users untuk mendapatkan nama owner)
# @tenantadmin_endpoints.route('/tenantRead', methods=['GET'])
# def get_all_tenants():
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)
#         # Query ini mengambil data tenant beserta nama owner dari tabel users
#         query = """
#             SELECT 
#                 t.id_tenant, 
#                 t.nama_tenant, 
#                 t.deskripsi_tenant, 
#                 u.nama as nama_owner,
#                 u.id_user
#             FROM tenants t
#             LEFT JOIN users u ON t.id_user = u.id_user
#             ORDER BY t.id_tenant DESC
#         """
#         cursor.execute(query)
#         tenants = cursor.fetchall()
#         return jsonify({"message": "OK", "datas": tenants}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# # ✅ CREATE a new Tenant
# @tenantadmin_endpoints.route('/tenantCreate', methods=['POST'])
# def create_tenant():
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         nama_tenant = data.get("nama_tenant")
#         deskripsi_tenant = data.get("deskripsi_tenant")
#         id_user = data.get("id_user")

#         if not nama_tenant or not id_user:
#             return jsonify({"message": "ERROR", "error": "Nama tenant dan owner wajib diisi"}), 400

#         connection = get_connection()
#         # Memulai transaksi (di banyak library, ini terjadi secara implisit)
#         cursor = connection.cursor()

#         # Query 1: Membuat tenant baru
#         query_insert_tenant = "INSERT INTO tenants (nama_tenant, deskripsi_tenant, id_user) VALUES (%s, %s, %s)"
#         cursor.execute(query_insert_tenant, (nama_tenant, deskripsi_tenant, id_user))

#         # Query 2: Mengubah role user menjadi 'admin_tenant'
#         query_update_user_role = "UPDATE users SET role = 'admin_tenant' WHERE id_user = %s"
#         cursor.execute(query_update_user_role, (id_user,))
        
#         # Jika kedua query berhasil, simpan semua perubahan
#         connection.commit()

#         return jsonify({"message": "Tenant berhasil ditambahkan dan role user telah diperbarui"}), 201

#     except Exception as e:
#         # Jika terjadi error di salah satu query, batalkan semua perubahan
#         if connection:
#             connection.rollback()
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
        
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# # ✅ UPDATE a Tenant
# @tenantadmin_endpoints.route('/tenantUpdate/<int:id_tenant>', methods=['PUT'])
# def update_tenant(id_tenant):
#     connection = None
#     cursor = None
#     try:
#         data = request.get_json()
#         nama_tenant = data.get("nama_tenant")
#         deskripsi_tenant = data.get("deskripsi_tenant")
#         id_user = data.get("id_user")

#         if not nama_tenant or not id_user:
#             return jsonify({"message": "ERROR", "error": "Nama tenant dan owner wajib diisi"}), 400
        
#         connection = get_connection()
#         cursor = connection.cursor()
#         query = """
#             UPDATE tenants 
#             SET nama_tenant = %s, deskripsi_tenant = %s, id_user = %s 
#             WHERE id_tenant = %s
#         """
#         cursor.execute(query, (nama_tenant, deskripsi_tenant, id_user, id_tenant))
#         connection.commit()

#         if cursor.rowcount == 0:
#             return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404

#         return jsonify({"message": "Tenant berhasil diperbarui"}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()

# # ✅ DELETE a Tenant
# @tenantadmin_endpoints.route('/tenantDelete/<int:id_tenant>', methods=['DELETE'])
# def delete_tenant(id_tenant):
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor()
#         query = "DELETE FROM tenants WHERE id_tenant = %s"
#         cursor.execute(query, (id_tenant,))
#         connection.commit()

#         if cursor.rowcount == 0:
#             return jsonify({"message": "ERROR", "error": "Tenant tidak ditemukan"}), 404

#         return jsonify({"message": "Tenant berhasil dihapus"}), 200
#     except Exception as e:
#         return jsonify({"message": "ERROR", "error": str(e)}), 500
#     finally:
#         if cursor: cursor.close()
#         if connection: connection.close()
        
        

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