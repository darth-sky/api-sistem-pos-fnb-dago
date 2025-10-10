"""Routes for module useradmin"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename

useradmin_endpoints = Blueprint("useradmin_endpoints", __name__)


# ✅ READ All Users
@useradmin_endpoints.route('/userReads', methods=['GET'])
def get_all_users():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT id_user, nama, email, role FROM users ORDER BY id_user DESC"
        cursor.execute(query)
        users = cursor.fetchall()
        return jsonify({"message": "OK", "datas": users}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE a new User
@useradmin_endpoints.route('/userCreate', methods=['POST'])
def create_user():
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama = data.get("nama")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role")

        if not nama or not email or not password or not role:
            return jsonify({"message": "ERROR", "error": "Semua field wajib diisi"}), 400

        # HASH PASSWORD SEBELUM DISIMPAN!
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        connection = get_connection()
        cursor = connection.cursor()
        query = "INSERT INTO users (nama, email, password, role) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (nama, email, hashed_password, role))
        connection.commit()

        return jsonify({"message": "User berhasil ditambahkan"}), 201
    except Exception as e:
        # Menangani error jika email sudah terdaftar
        if 'Duplicate entry' in str(e) and 'for key \'email\'' in str(e):
            return jsonify({"message": "ERROR", "error": "Email sudah terdaftar"}), 409
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE a User (Tanpa mengubah password)
@useradmin_endpoints.route('/userUpdate/<int:id_user>', methods=['PUT'])
def update_user(id_user):
    connection = None
    cursor = None
    try:
        data = request.get_json()
        nama = data.get("nama")
        email = data.get("email")
        role = data.get("role")

        if not nama or not email or not role:
            return jsonify({"message": "ERROR", "error": "Nama, email, dan role wajib diisi"}), 400
        
        connection = get_connection()
        cursor = connection.cursor()
        query = "UPDATE users SET nama = %s, email = %s, role = %s WHERE id_user = %s"
        cursor.execute(query, (nama, email, role, id_user))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "User tidak ditemukan"}), 404

        return jsonify({"message": "User berhasil diperbarui"}), 200
    except Exception as e:
        if 'Duplicate entry' in str(e) and 'for key \'email\'' in str(e):
            return jsonify({"message": "ERROR", "error": "Email sudah digunakan oleh user lain"}), 409
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE a User
@useradmin_endpoints.route('/userDelete/<int:id_user>', methods=['DELETE'])
def delete_user(id_user):
    # Logika tambahan: Anda mungkin tidak ingin user menghapus dirinya sendiri
    # current_user_id = ... # dapatkan dari token JWT
    # if current_user_id == id_user:
    #    return jsonify({"error": "Anda tidak bisa menghapus akun Anda sendiri"}), 403
    
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        query = "DELETE FROM users WHERE id_user = %s"
        cursor.execute(query, (id_user,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"message": "ERROR", "error": "User tidak ditemukan"}), 404

        return jsonify({"message": "User berhasil dihapus"}), 200
    except Exception as e:
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()