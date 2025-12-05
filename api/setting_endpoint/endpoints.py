"""Routes for module acara"""
import os
import uuid
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from flask import Blueprint, jsonify, request

settings_endpoints = Blueprint('settings_endpoints', __name__)

# ✅ GET All Settings
@settings_endpoints.route('/getSettings', methods=['GET'])
def get_settings():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Select semua kolom
        query = "SELECT `key`, `value`, `deskripsi` FROM settings ORDER BY `key` ASC"
        cursor.execute(query)
        results = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ CREATE Setting
@settings_endpoints.route('/createSetting', methods=['POST'])
def create_setting():
    connection = None
    cursor = None
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        deskripsi = data.get('deskripsi')

        if not key or not value:
            return jsonify({"message": "ERROR", "error": "Key dan Value wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        # Cek apakah Key sudah ada
        cursor.execute("SELECT `key` FROM settings WHERE `key` = %s", (key,))
        if cursor.fetchone():
             return jsonify({"message": "ERROR", "error": f"Key '{key}' sudah ada. Gunakan Key lain."}), 409

        query = "INSERT INTO settings (`key`, `value`, `deskripsi`) VALUES (%s, %s, %s)"
        cursor.execute(query, (key, value, deskripsi))
        connection.commit()

        return jsonify({"message": "Setting berhasil ditambahkan"}), 201
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ UPDATE Setting
@settings_endpoints.route('/updateSetting/<string:key_id>', methods=['PUT'])
def update_setting(key_id):
    connection = None
    cursor = None
    try:
        data = request.json
        value = data.get('value')
        deskripsi = data.get('deskripsi')

        if not value:
            return jsonify({"message": "ERROR", "error": "Value wajib diisi"}), 400

        connection = get_connection()
        cursor = connection.cursor()

        # Cek apakah data ada
        cursor.execute("SELECT `key` FROM settings WHERE `key` = %s", (key_id,))
        if not cursor.fetchone():
            return jsonify({"message": "ERROR", "error": "Setting tidak ditemukan"}), 404

        # Update (Key tidak boleh diubah karena Primary Key)
        query = "UPDATE settings SET `value` = %s, `deskripsi` = %s WHERE `key` = %s"
        cursor.execute(query, (value, deskripsi, key_id))
        connection.commit()

        return jsonify({"message": "Setting berhasil diperbarui"}), 200
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

# ✅ DELETE Setting
@settings_endpoints.route('/deleteSetting/<string:key_id>', methods=['DELETE'])
def delete_setting(key_id):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT `key` FROM settings WHERE `key` = %s", (key_id,))
        if not cursor.fetchone():
            return jsonify({"message": "ERROR", "error": "Setting tidak ditemukan"}), 404

        cursor.execute("DELETE FROM settings WHERE `key` = %s", (key_id,))
        connection.commit()

        return jsonify({"message": "Setting berhasil dihapus"}), 200
    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()