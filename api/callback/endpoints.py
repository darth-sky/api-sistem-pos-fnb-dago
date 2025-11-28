from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection

callback_endpoints = Blueprint('callback', __name__)

@callback_endpoints.route('/ipaymu', methods=['POST'])
def ipaymu_callback():
    # iPaymu mengirim data dalam format Form Data
    trx_id = request.form.get('reference_id') # ID Transaksi Lokal
    status_code = request.form.get('status_code') # '1' = Berhasil
    status = request.form.get('status') # 'berhasil', 'pending', dll

    print(f"\n=== CALLBACK IPAYMU RECEIVED ===")
    print(f"Trx ID: {trx_id}, Status Code: {status_code}, Status: {status}")

    if not trx_id:
        return jsonify({"message": "No reference ID"}), 400

    connection = get_connection()
    cursor = connection.cursor(dictionary=True) # Gunakan dictionary=True agar hasil fetchone enak dibaca

    try:
        # Status Code '1' artinya pembayaran sukses/lunas
        if str(status_code) == '1': 
            
            # 1. Update Tabel Transaksi (Lunas)
            update_query = """
                UPDATE transaksi 
                SET status_pembayaran = 'Lunas' 
                WHERE id_transaksi = %s
            """
            cursor.execute(update_query, (trx_id,))
            
            # 2. Cek & Aktifkan MEMBERSHIP (Jika ada)
            cursor.execute("SELECT id_memberships FROM memberships WHERE id_transaksi = %s", (trx_id,))
            member_data = cursor.fetchone()
            
            if member_data:
                update_member = "UPDATE memberships SET status_memberships = 'Active' WHERE id_transaksi = %s"
                cursor.execute(update_member, (trx_id,))
                print(f"✅ Membership (ID: {member_data['id_memberships']}) berhasil DIAKTIFKAN.")

            # 3. Cek & Aktifkan VIRTUAL OFFICE (Jika ada - Opsional/Jaga-jaga)
            cursor.execute("SELECT id_client_vo FROM client_virtual_office WHERE id_transaksi = %s", (trx_id,))
            vo_data = cursor.fetchone()
            
            if vo_data:
                # Set status Aktif dan pastikan tanggal mulai dihitung dari hari bayar (opsional)
                update_vo = """
                    UPDATE client_virtual_office 
                    SET status_client_vo = 'Aktif',
                        tanggal_mulai = CURDATE(),
                        # Hitung ulang tanggal berakhir jika perlu, atau biarkan sesuai insert awal
                        tanggal_berakhir = DATE_ADD(CURDATE(), INTERVAL (
                            SELECT durasi FROM paket_virtual_office 
                            WHERE id_paket_vo = client_virtual_office.id_paket_vo
                        ) DAY)
                    WHERE id_transaksi = %s
                """
                cursor.execute(update_vo, (trx_id,))
                print(f"✅ Virtual Office (ID: {vo_data['id_client_vo']}) berhasil DIAKTIFKAN.")

            # Simpan semua perubahan
            connection.commit()
            print(f"✅ Transaksi {trx_id} LUNAS & Layanan Terkait Aktif.")
            
        else:
            print(f"⚠️ Transaksi {trx_id} callback diterima tapi belum lunas (Status: {status}).")

        return jsonify({"message": "OK"}), 200

    except Exception as e:
        print(f"❌ Error processing callback: {e}")
        if connection:
            connection.rollback()
        return jsonify({"message": "Error"}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()