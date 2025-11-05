"""Routes for module books"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, decode_token
from flask_bcrypt import Bcrypt
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity


from helper.db_helper import get_connection

bcrypt = Bcrypt()
auth_endpoints = Blueprint('auth', __name__)


# Di file auth_endpoints.py Anda

@auth_endpoints.route('/login', methods=['POST'])
def login():
    """Route for authentication"""
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    if not user or not bcrypt.check_password_hash(user.get('password'), password):
        return jsonify({"msg": "Bad email or password"}), 401

    access_token = create_access_token(
        identity={'email': email, 'id_user': user.get('id_user')}, 
        additional_claims={'roles': user.get('role'), 'id_user': user.get('id_user')}
    )
    decoded_token = decode_token(access_token)
    expires = decoded_token['exp']

    return jsonify({
        "access_token": access_token,
        "expires_in": expires,
        "type": "Bearer",
        # TAMBAHAN KUNCI: Kirim status first_login ke frontend
        "is_first_login": user.get('is_first_login'),
        "role": user.get('role') # Kirim role juga untuk mempermudah frontend
    })


# Di file auth_endpoints.py Anda (tambahkan di bawah)

@auth_endpoints.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Route for user to change their own password"""
    current_user_identity = get_jwt_identity()
    user_id = current_user_identity.get('id_user')

    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')

    if not old_password or not new_password:
        return jsonify({"msg": "Old password and new password are required"}), 400

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Dapatkan user dan password hash yang sekarang
        query_select = "SELECT password FROM users WHERE id_user = %s"
        cursor.execute(query_select, (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        # 2. Verifikasi password lama
        if not bcrypt.check_password_hash(user.get('password'), old_password):
            return jsonify({"msg": "Invalid old password"}), 401

        # 3. Hash password baru
        hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        # 4. Update password baru DAN set is_first_login = 0
        query_update = "UPDATE users SET password = %s, is_first_login = 0 WHERE id_user = %s"
        cursor.execute(query_update, (hashed_new_password, user_id))
        connection.commit()

        return jsonify({"msg": "Password updated successfully"}), 200

    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@auth_endpoints.route('/register', methods=['POST'])
def register():
    """Route for user registration"""
    nama = request.form.get('nama')
    email = request.form.get('email')
    password = request.form.get('password')

    if not nama or not email or not password:
        return jsonify({"msg": "Nama, email, and password are required"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        connection = get_connection()
        cursor = connection.cursor()
        insert_query = "INSERT INTO users (nama, email, password) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (nama, email, hashed_password))
        connection.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    if new_id:
        return jsonify({
            "message": "OK",
            "description": "User created",
            "email": email
        }), 201

    return jsonify({"message": "Failed, can't register user"}), 501


# Di file auth_endpoints.py Anda

@auth_endpoints.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    """Route for getting user profile info"""
    identity = get_jwt_identity()  # -> { "email": "...", "id_user": ... }
    roles = get_jwt().get("roles")
    user_id = identity.get("id_user")

    # --- INI ADALAH PERBAIKAN ---
    # Kita perlu mengambil status is_first_login terbaru dari DB
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT is_first_login FROM users WHERE id_user = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    if not user:
        return jsonify({"msg": "User not found"}), 404
    # --- AKHIR PERBAIKAN ---

    return jsonify({
        "user_logged": True,
        "id_user": user_id,
        "email": identity.get("email"),
        "roles": roles,
        # --- TAMBAHKAN 'is_first_login' DARI HASIL QUERY DB ---
        "is_first_login": user.get('is_first_login')
    })
    