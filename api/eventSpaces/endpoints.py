"""Routes for module eventspaces (customer side) with Email notif"""
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from flask_jwt_extended import jwt_required
import datetime
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

eventspaces_endpoints = Blueprint("eventspaces_endpoints", __name__)

# Konfigurasi Email
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")  # default Gmail
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_SENDER = os.getenv("EMAIL_SENDER",
                         "dagocreativehub@gmail.com")  # email sistem pengirim
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD",
                           "xhxs podr zrxk tlay")  # app password
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL",
                        "mohamedizzykilian@gmail.com")  # email tujuan admin


def send_email_notification(subject,
                            body,
                            customer_email,
                            recipient=ADMIN_EMAIL):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = recipient
        msg["Subject"] = subject
        msg["Reply-To"] = customer_email  # kalau admin klik reply, akan ke customer

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
        server.quit()
        print(f"[EMAIL] Notifikasi terkirim ke {recipient}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


# Endpoint untuk pelanggan mengajukan booking event
@eventspaces_endpoints.route('/bookingEvent', methods=['POST'])
@jwt_required()  # hanya user login yang bisa booking
def create_booking():
    try:
        data = request.get_json()
        
        # 🔹 Debug log
        print("📥 Data diterima dari frontend:", data)

        required_fields = [
            "id_event_space", "id_user", "nama_acara", "tanggal_event",
            "waktu_mulai", "waktu_selesai", "jumlah_peserta", "email_customer"
        ]

        # Validasi data
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "message": f"Field {field} wajib diisi"
                }), 400

        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # 1. Buat transaksi baru
        insert_transaksi = """
            INSERT INTO transaksi (id_user, total_harga_final, tanggal_transaksi, status_pembayaran, status_order)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_transaksi,
                        (data["id_user"], 0, datetime.datetime.now(), 'Belum Lunas', 'Baru'))
        connection.commit()
        transaksi_id = cursor.lastrowid

        # 2. Insert booking_event
        insert_booking = """
            INSERT INTO booking_event
            (id_event_space, id_user, id_transaksi, tanggal_event, waktu_mulai, waktu_selesai,
             status_booking, nama_acara, deskripsi, jumlah_peserta, kebutuhan_tambahan)
            VALUES (%s,%s,%s,%s,%s,%s,'Baru',%s,%s,%s,%s)
        """
        cursor.execute(
            insert_booking,
            (data["id_event_space"], data["id_user"], transaksi_id,
             data["tanggal_event"], data["waktu_mulai"], data["waktu_selesai"],
             data["nama_acara"], data.get("deskripsi"), data["jumlah_peserta"],
             data.get("kebutuhan_tambahan")))
        connection.commit()
        booking_id = cursor.lastrowid

        # 3. Kirim notifikasi Email ke Admin
        subject = f"📢 Booking Baru #{booking_id} Diajukan"
        body = (f"📢 Booking Baru Diajukan!\n\n"
                f"ID Booking: {booking_id}\n"
                f"User ID: {data['id_user']}\n"
                f"Email Customer: {data['email_customer']}\n"
                f"Acara: {data['nama_acara']}\n"
                f"Tanggal: {data['tanggal_event']}\n"
                f"Waktu: {data['waktu_mulai']} - {data['waktu_selesai']}\n"
                f"Peserta: {data['jumlah_peserta']}\n"
                f"Tambahan: {data.get('kebutuhan_tambahan', '-')}\n\n"
                f"👉 Mohon segera diproses di dashboard admin.")

        send_email_notification(subject, body, data["email_customer"],
                                ADMIN_EMAIL)

        return jsonify({
            "success": True,
            "message":
            "Booking berhasil diajukan dan notifikasi email terkirim ke admin.",
            "booking_id": booking_id
        }), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            
