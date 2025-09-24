"""Routes for module menu"""
import os
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from helper.form_validation import get_form_data
from flask_jwt_extended import jwt_required
from helper.year_operation import diff_year
from helper.year_operation import check_age_book

menu_endpoints = Blueprint('menu', __name__)
UPLOAD_FOLDER = "img"

# COBA - COBA DULU
@menu_endpoints.route('/kategori', methods=['GET'])
def read_kategori():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM kategori_menu")
        results = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "OK", "datas": results}), 200

@menu_endpoints.route('/readByKategori', methods=['GET'])
def readByKategori():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)

        id_kategori = request.args.get('id_kategori')
        if id_kategori:
            cursor.execute("SELECT * FROM menu WHERE id_kategori = %s", (id_kategori,))
        else:
            cursor.execute("SELECT * FROM menu")

        results = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "OK", "datas": results}), 200




# @menu_endpoints.route('/read', methods=['GET'])
# # @jwt_required()
# def read():
#     """Routes for module get list menu"""
#     connection = get_connection()
#     cursor = connection.cursor(dictionary=True)
#     select_query = "SELECT * FROM menu"
#     cursor.execute(select_query)
#     results = cursor.fetchall()
#     cursor.close()  # Close the cursor after query execution
#     return jsonify({"message": "OK", "datas": results}), 200

@menu_endpoints.route('/read', methods=['GET'])
def read():
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM menu")
        results = cursor.fetchall()
    finally:
        cursor.close()       # Tutup cursor
        connection.close()   # Kembalikan koneksi ke pool

    return jsonify({"message": "OK", "datas": results}), 200




@menu_endpoints.route('/create', methods=['POST'])
@jwt_required()
def create():
    """Routes for module create a book"""
    required = get_form_data(["title"])  # use only if the field required
    title = required["title"]
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()
    insert_query = "INSERT INTO tb_menu (title, description) VALUES (%s, %s)"
    request_insert = (title, description)
    cursor.execute(insert_query, request_insert)
    connection.commit()  # Commit changes to the database
    cursor.close()
    new_id = cursor.lastrowid  # Get the newly inserted book's ID\
    if new_id:
        return jsonify({"title": title, "message": "Inserted", "id_menu": new_id}), 201
    return jsonify({"message": "Cant Insert Data"}), 500


@menu_endpoints.route('/update/<product_id>', methods=['PUT'])
@jwt_required()
def update(product_id):
    """Routes for module update a book"""
    title = request.form['title']
    description = request.form['description']

    connection = get_connection()
    cursor = connection.cursor()

    update_query = "UPDATE tb_menu SET title=%s, description=%s WHERE id_menu=%s"
    update_request = (title, description, product_id)
    cursor.execute(update_query, update_request)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "updated", "id_menu": product_id}
    return jsonify(data), 200


@menu_endpoints.route('/delete/<product_id>', methods=['GET'])
@jwt_required()
def delete(product_id):
    """Routes for module to delete a book"""
    connection = get_connection()
    cursor = connection.cursor()

    delete_query = "DELETE FROM tb_menu WHERE id_menu = %s"
    delete_id = (product_id,)
    cursor.execute(delete_query, delete_id)
    if cursor.rowcount <= 0:
        return jsonify({"message": "Data not found"}), 400
    connection.commit()
    cursor.close()
    data = {"message": "Data deleted", "id_menu": product_id}
    return jsonify(data)


@menu_endpoints.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Routes for upload file"""
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        uploaded_file.save(file_path)
        return jsonify({"message": "ok", "data": "uploaded", "file_path": file_path}), 200
    return jsonify({"err_message": "Can't upload data"}), 400


@menu_endpoints.route("/read/age/<book_id>", methods=["GET"])
@jwt_required()
def read_age(book_id):
    """routes for module get list menu"""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    select_query = "SELECT title, publication_year FROM tb_menu WHERE id_menu = %s"
    parameter_request = (str(book_id), )
    cursor.execute(select_query, parameter_request)
    results = cursor.fetchone()
    publication_year = results["publication_year"]
    ages = diff_year(publication_year)
    category_age = check_age_book(ages)
    results["category_age"] = category_age

    cursor.close()  # Close the cursor after query execution
    return jsonify({"message": "OK", "datas": results}), 200