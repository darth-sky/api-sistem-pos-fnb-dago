"""Routes for module books"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, decode_token
from flask_bcrypt import Bcrypt
from flask_jwt_extended import jwt_required

from helper.db_helper import get_connection

bcrypt = Bcrypt()
auth_endpoints = Blueprint('auth', __name__)


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
        identity={'email': email, 'id_user': user.get('id_user')}, additional_claims={'roles': user.get('role'), 'id_user': user.get('id_user')})
    decoded_token = decode_token(access_token)
    expires = decoded_token['exp']

    return jsonify({
        "access_token": access_token,
        "expires_in": expires,
        "type": "Bearer"
    })


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


@auth_endpoints.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    identity = get_jwt_identity()  # -> { "email": "...", "id_user": ... }
    roles = get_jwt().get("roles")

    return jsonify({
        "user_logged": True,
        "id_user": identity.get("id_user"),
        "email": identity.get("email"),
        "roles": roles
    })