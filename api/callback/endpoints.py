from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
import traceback

callback_endpoints = Blueprint('callback', __name__)

@callback_endpoints.route('/ipaymu', methods=['POST'])
def ipaymu_callback():
    """
    Endpoint callback iPaymu untuk mengonfirmasi pembayaran otomatis.
    Menangani: Transaksi Umum, Membership, Virtual Office, dan Event Space.
    """
    # iPaymu mengirim data dalam format Form Data
    trx_id = request.form.get('reference_id') # ID Transaksi Lokal
    status_code = request.form.get('status_code') # '1' = Berhasil
    status_msg = request.form.get('status') 

    print(f"\n=== CALLBACK IPAYMU RECEIVED ===")
    print(f"Trx ID: {trx_id}, Status Code: {status_code}, Status: {status_msg}")

    if not trx_id:
        return jsonify({"message": "No reference ID"}), 400

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Status Code '1' artinya pembayaran sukses/lunas
        if str(status_code) == '1': 
            
            # ---------------------------------------------------------
            # 1. UPDATE TABEL UTAMA: TRANSAKSI (LUNAS)
            # ---------------------------------------------------------
            update_trx = """
                UPDATE transaksi 
                SET status_pembayaran = 'Lunas', 
                    status_order = 'Selesai' 
                WHERE id_transaksi = %s
            """
            cursor.execute(update_trx, (trx_id,))
            
            # ---------------------------------------------------------
            # 2. CEK & AKTIFKAN: MEMBERSHIP
            # ---------------------------------------------------------
            cursor.execute("SELECT id_memberships FROM memberships WHERE id_transaksi = %s", (trx_id,))
            member_data = cursor.fetchone()
            
            if member_data:
                update_member = "UPDATE memberships SET status_memberships = 'Active' WHERE id_transaksi = %s"
                cursor.execute(update_member, (trx_id,))
                print(f"✅ Membership (ID: {member_data['id_memberships']}) berhasil DIAKTIFKAN.")

            # ---------------------------------------------------------
            # 3. CEK & AKTIFKAN: VIRTUAL OFFICE
            # ---------------------------------------------------------
            cursor.execute("SELECT id_client_vo, id_paket_vo FROM client_virtual_office WHERE id_transaksi = %s", (trx_id,))
            vo_data = cursor.fetchone()
            
            if vo_data:
                # Ambil durasi paket untuk hitung ulang tanggal berakhir (opsional, biar akurat dari tgl bayar)
                cursor.execute("SELECT durasi FROM paket_virtual_office WHERE id_paket_vo = %s", (vo_data['id_paket_vo'],))
                paket = cursor.fetchone()
                durasi = paket['durasi'] if paket else 30

                # Set status Aktif, Tgl Mulai = Hari Ini, Tgl Akhir = Hari Ini + Durasi
                update_vo = f"""
                    UPDATE client_virtual_office 
                    SET status_client_vo = 'Aktif',
                        tanggal_mulai = CURDATE(),
                        tanggal_berakhir = DATE_ADD(CURDATE(), INTERVAL {durasi} DAY)
                    WHERE id_transaksi = %s
                """
                cursor.execute(update_vo, (trx_id,))
                print(f"✅ Virtual Office (ID: {vo_data['id_client_vo']}) berhasil DIAKTIFKAN.")

            # ---------------------------------------------------------
            # 4. CEK & AKTIFKAN: BOOKING EVENT SPACE (Tambahan Baru)
            # ---------------------------------------------------------
            cursor.execute("SELECT id_booking_event FROM booking_event WHERE id_transaksi = %s", (trx_id,))
            event_data = cursor.fetchone()
            
            if event_data:
                # Ubah status dari 'Menunggu Pembayaran' -> 'Confirmed'
                update_event = """
                    UPDATE booking_event 
                    SET status_booking = 'Confirmed' 
                    WHERE id_booking_event = %s
                """
                cursor.execute(update_event, (event_data['id_booking_event'],))
                print(f"✅ Booking Event (ID: {event_data['id_booking_event']}) status CONFIRMED.")

            # Simpan semua perubahan
            connection.commit()
            print(f"✅ Transaksi {trx_id} LUNAS & Layanan Terkait Aktif.")
            
        else:
            print(f"⚠️ Transaksi {trx_id} callback diterima tapi belum lunas (Status: {status_msg}).")

        return jsonify({"message": "OK"}), 200

    except Exception as e:
        print(f"❌ Error processing callback: {e}")
        traceback.print_exc()
        if connection:
            connection.rollback()
        return jsonify({"message": "Error"}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()