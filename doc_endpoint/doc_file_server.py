# File: doc_endpoint/doc_file_server.py

import os
from flask import send_from_directory, Blueprint, jsonify

doc_file_server = Blueprint('doc_file_server', __name__)

# --- PERBAIKAN PATH ---

# 1. Ini adalah path ke folder saat ini (yaitu .../doc_endpoint)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# 2. Kita naik satu level untuk mendapatkan ROOT PROYEK (yaitu .../proyek_flask)
PROJECT_ROOT = os.path.abspath(os.path.join(APP_ROOT, '..'))

# 3. Tentukan folder upload dari ROOT PROYEK
VO_UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads', 'vo_documents')

# -----------------------

# Endpoint ini sekarang sudah benar
@doc_file_server.route('/uploads/vo_documents/<path:filename>')
def serve_vo_document(filename):
    """
    Menyajikan file statis dari folder upload VO.
    """
    try:
        return send_from_directory(VO_UPLOAD_FOLDER, filename)
    except FileNotFoundError:
        return jsonify({"message": "File tidak ditemukan"}), 404