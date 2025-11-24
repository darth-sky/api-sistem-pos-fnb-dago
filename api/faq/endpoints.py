"""Routes for module faq"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import traceback

faq_endpoints = Blueprint("faq_endpoints", __name__)

# folder penyimpanan upload
UPLOAD_FOLDER = "img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Pastikan folder ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# 1. GET: Ambil semua FAQ yang aktif
@faq_endpoints.route('/read', methods=['GET'])
def get_faqs():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Ambil hanya yang ada jawabannya atau status Aktif
        query = "SELECT pertanyaan as question, jawaban as answer FROM faq WHERE status = 'Aktif' ORDER BY urutan ASC"
        cursor.execute(query)
        result = cursor.fetchall()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 2. POST: User kirim pertanyaan baru
@faq_endpoints.route('/post', methods=['POST'])
def add_faq():
    data = request.json
    pertanyaan = data.get('question')
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Default status 'Menunggu' agar admin bisa jawab dulu sebelum tampil
        query = "INSERT INTO faq (pertanyaan, jawaban, status) VALUES (%s, %s, 'Menunggu')"
        # Jawaban diisi pesan default atau NULL dulu
        pesan_default = "Terima kasih! Admin akan segera menjawab pertanyaan ini."
        cursor.execute(query, (pertanyaan, pesan_default))
        conn.commit()
        return jsonify({"message": "Pertanyaan terkirim"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        
        
        
# --- ADMIN ROUTES ---

# 1. GET ALL (Termasuk Menunggu & Arsip)
@faq_endpoints.route('/admin', methods=['GET'])
# @jwt_required() # Uncomment jika pakai JWT
def get_all_faqs_admin():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Urutkan berdasarkan status (Menunggu paling atas) lalu urutan
        query = """
            SELECT * FROM faq 
            ORDER BY 
            CASE WHEN status = 'Menunggu' THEN 1 ELSE 2 END,
            urutan ASC, created_at DESC
        """
        cursor.execute(query)
        result = cursor.fetchall()
        return jsonify({"datas": result}), 200
    finally:
        cursor.close()
        conn.close()
        
# ... imports yang sudah ada

# ✅ CREATE FAQ (Khusus Admin - Bisa set Status & Jawaban langsung)
@faq_endpoints.route('/admin/post', methods=['POST'])
# @jwt_required() # Uncomment jika menggunakan JWT
def create_faq_admin():
    data = request.json
    pertanyaan = data.get('pertanyaan')
    jawaban = data.get('jawaban')
    status = data.get('status', 'Aktif') # Default Aktif jika admin yang buat
    urutan = data.get('urutan', 0)

    if not pertanyaan or not jawaban:
        return jsonify({"message": "Pertanyaan dan Jawaban wajib diisi"}), 400

    conn = get_connection()
    if conn is None:
         return jsonify({"message": "Database connection failed"}), 500

    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO faq (pertanyaan, jawaban, status, urutan) 
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (pertanyaan, jawaban, status, urutan))
        conn.commit()
        return jsonify({"message": "FAQ berhasil ditambahkan oleh Admin"}), 201
    except Exception as e:
        print(f"Error creating FAQ: {e}")
        if conn: conn.rollback()
        return jsonify({"message": "Gagal menambahkan FAQ"}), 500
    finally:
        cursor.close()
        conn.close()

# 2. UPDATE FAQ Lengkap
@faq_endpoints.route('/update/<int:id_faq>', methods=['PUT'])
# @jwt_required()
def update_faq(id_faq):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            UPDATE faq 
            SET pertanyaan = %s, jawaban = %s, status = %s, urutan = %s 
            WHERE id_faq = %s
        """
        cursor.execute(query, (
            data.get('pertanyaan'), 
            data.get('jawaban'), 
            data.get('status'), 
            data.get('urutan', 0), 
            id_faq
        ))
        conn.commit()
        return jsonify({"message": "FAQ updated"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# 3. UPDATE Status Saja (Untuk Quick Action di Tabel)
@faq_endpoints.route('/update/<int:id_faq>/status', methods=['PUT'])
# @jwt_required()
def update_faq_status_only(id_faq):
    data = request.json
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE faq SET status = %s WHERE id_faq = %s", (data.get('status'), id_faq))
        conn.commit()
        return jsonify({"message": "Status updated"}), 200
    finally:
        cursor.close()
        conn.close()

# 4. DELETE FAQ
@faq_endpoints.route('/delete/<int:id_faq>', methods=['DELETE'])
# @jwt_required()
def delete_faq(id_faq):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM faq WHERE id_faq = %s", (id_faq,))
        conn.commit()
        return jsonify({"message": "FAQ deleted"}), 200
    finally:
        cursor.close()
        conn.close()