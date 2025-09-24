"""Routes for module protected endpoints"""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from helper.jwt_helper import get_roles
from helper.db_helper import get_connection

protected_endpoints = Blueprint('data_protected', __name__)


# @protected_endpoints.route('/data', methods=['GET'])
# @jwt_required()
# def get_data():
#     """
#     Route to demonstrate protected data endpoint,
#     requires JWT to access
#     """
#     current_user = get_jwt_identity()
#     roles = get_roles()
    

#     # Jika tidak ada query ke DB, koneksi tidak perlu dibuka
#     # Tapi jika tetap ingin membuka connection:
#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor()
#         # bisa digunakan untuk query DB jika diperlukan
#     except Exception as e:
#         return jsonify({"msg": f"Database error: {str(e)}"}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if connection:
#             connection.close()

#     return jsonify({
#         "message": "OK",
#         "user_logged": current_user['email'],
#         "roles": roles,
#         "id_user": current_user['id_user']
#     }), 200


@protected_endpoints.route('/data', methods=['GET'])
@jwt_required()
def get_data():
    """
    Route to demonstrate protected data endpoint,
    requires JWT to access
    """
    current_user = get_jwt_identity()
    roles = get_roles()
    id_user = current_user.get('id_user')

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Ambil detail user dari DB
        cursor.execute("SELECT id_user, nama, email, role FROM users WHERE id_user = %s", (id_user,))
        user_detail = cursor.fetchone()

    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return jsonify({
        "message": "OK",
        "user_logged": current_user['email'],
        "roles": roles,
        "id_user": id_user,
        "detail": user_detail   # <--- detail user dari DB
    }), 200
