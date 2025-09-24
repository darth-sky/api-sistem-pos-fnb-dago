"""Routes for module produk"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year

produk_endpoints = Blueprint('produk', __name__)
UPLOAD_FOLDER = "img"


@produk_endpoints.route('/kategori', methods=['GET'])
def read_kategori():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)

        id_tenant = request.args.get('id_tenant')
        if id_tenant:
            cursor.execute("SELECT * FROM kategori_produk WHERE id_tenant = %s", (id_tenant,))
        else:
            cursor.execute("SELECT * FROM kategori_produk")

        results = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "OK", "datas": results}), 200


@produk_endpoints.route('/readByKategori', methods=['GET'])
def readByKategori():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)

        id_kategori = request.args.get('id_kategori')
        if id_kategori:
            cursor.execute("SELECT * FROM produk_fnb WHERE id_kategori = %s", (id_kategori,))
        else:
            cursor.execute("SELECT * FROM produk_fnb")

        results = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "OK", "datas": results}), 200


@produk_endpoints.route('/create', methods=['POST'])
def create_transaksi_fnb():
    """
    Endpoint untuk membuat transaksi F&B baru.
    Menyimpan data ke tabel 'transaksi' dan 'detail_order_fnb'.
    """
    connection = None
    cursor = None
    try:
        data = request.get_json()

        # Ekstrak data dari body request
        fnb_type = data.get('fnb_type')
        nama_guest = data.get('nama_guest')
        lokasi_pemesanan = data.get('lokasi_pemesanan')
        metode_pembayaran = data.get('metode_pembayaran')
        total_harga_final = data.get('total_harga_final')
        detail_order = data.get('detail_order') # Ini adalah list of dictionaries

        if not all([fnb_type, nama_guest, metode_pembayaran, total_harga_final, detail_order]):
            return jsonify({"message": "ERROR", "error": "Data tidak lengkap"}), 400

        connection = get_connection()
        connection.start_transaction() # Mulai transaksi database
        cursor = connection.cursor(dictionary=True)

        # 1. Insert ke tabel master 'transaksi'
        query_transaksi = """
            INSERT INTO transaksi 
            (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran, total_harga_final, status_pembayaran, status_order) 
            VALUES (%s, %s, %s, %s, %s, 'Lunas', 'Baru')
        """
        values_transaksi = (fnb_type, nama_guest, lokasi_pemesanan, metode_pembayaran, total_harga_final)
        cursor.execute(query_transaksi, values_transaksi)
        
        # Ambil ID dari transaksi yang baru saja dibuat
        id_transaksi_baru = cursor.lastrowid

        # 2. Insert ke tabel detail 'detail_order_fnb'
        query_detail = """
            INSERT INTO detail_order_fnb 
            (id_transaksi, id_produk, jumlah, harga_saat_order, catatan_pesanan) 
            VALUES (%s, %s, %s, %s, %s)
        """
        # Siapkan data untuk multi-insert
        values_detail = [
            (id_transaksi_baru, item['id_produk'], item['jumlah'], item['harga_saat_order'], item.get('catatan_pesanan'))
            for item in detail_order
        ]
        
        cursor.executemany(query_detail, values_detail) # executemany lebih efisien untuk banyak data

        connection.commit() # Jika semua berhasil, simpan perubahan
        
        return jsonify({
            "message": "OK", 
            "datas": {
                "id_transaksi": id_transaksi_baru,
                "total_harga": total_harga_final,
                "nama_pemesan": nama_guest
            }
        }), 201 # 201 Created

    except Exception as e:
        if connection:
            connection.rollback() # Jika ada error, batalkan semua perubahan
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()