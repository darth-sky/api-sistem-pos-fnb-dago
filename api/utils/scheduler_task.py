from helper.db_helper import get_connection
from datetime import datetime, timedelta

def cancel_expired_transactions():
    """
    Cron job untuk membatalkan transaksi yang menggantung (Pending > 60 menit).
    Penting untuk melepas slot booking ruangan agar bisa dipesan orang lain.
    """
    print(f"\n--- [SCHEDULER] Menjalankan pembersihan transaksi expired: {datetime.now()} ---")
    
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # 1. Tentukan batas waktu (misal: transaksi yang dibuat > 60 menit lalu)
        expiry_limit = datetime.now() - timedelta(minutes=1440)
        expiry_str = expiry_limit.strftime('%Y-%m-%d %H:%M:%S')

        # 2. Cari ID Transaksi yang 'Belum Lunas' dan sudah kadaluarsa
        # Kita perlu ID-nya untuk update tabel anak (booking, event, vo, fnb)
        query_get_ids = """
            SELECT id_transaksi FROM transaksi 
            WHERE status_pembayaran = 'Belum Lunas' 
            AND tanggal_transaksi < %s
        """
        cursor.execute(query_get_ids, (expiry_str,))
        expired_transactions = cursor.fetchall()
        
        if not expired_transactions:
            print("--- [SCHEDULER] Tidak ditemukan transaksi expired. System bersih. ---")
            return

        # Konversi hasil tuple ke list ID: ['101', '102']
        expired_ids = [str(x[0]) for x in expired_transactions]
        ids_placeholder = ', '.join(['%s'] * len(expired_ids))
        
        print(f"--- [SCHEDULER] Ditemukan {len(expired_ids)} transaksi expired. IDs: {expired_ids}")

        # 3. HAPUS Booking Ruangan (CRITICAL: Agar slot jam kembali kosong/available)
        query_delete_booking = f"DELETE FROM booking_ruangan WHERE id_transaksi IN ({ids_placeholder})"
        cursor.execute(query_delete_booking, tuple(expired_ids))
        print(f"--- [SCHEDULER] {cursor.rowcount} slot booking ruangan telah dilepas.")

        # 4. Update Booking Event -> 'Dibatalkan'
        query_cancel_event = f"""
            UPDATE booking_event 
            SET status_booking = 'Dibatalkan', alasan_pembatalan = 'System: Payment Expired'
            WHERE id_transaksi IN ({ids_placeholder})
        """
        cursor.execute(query_cancel_event, tuple(expired_ids))

        # 5. Update Virtual Office -> 'Kadaluarsa'
        query_cancel_vo = f"""
            UPDATE client_virtual_office 
            SET status_client_vo = 'Kadaluarsa' 
            WHERE id_transaksi IN ({ids_placeholder})
        """
        cursor.execute(query_cancel_vo, tuple(expired_ids))

        # 6. Update F&B Order -> 'Batal'
        query_cancel_fnb = f"""
            UPDATE detail_order_fnb 
            SET status_pesanan = 'Batal' 
            WHERE id_transaksi IN ({ids_placeholder})
        """
        cursor.execute(query_cancel_fnb, tuple(expired_ids))

        # 7. Update Transaksi Induk -> 'Dibatalkan'
        query_cancel_transaksi = f"""
            UPDATE transaksi 
            SET status_pembayaran = 'Dibatalkan', status_order = 'Batal'
            WHERE id_transaksi IN ({ids_placeholder})
        """
        cursor.execute(query_cancel_transaksi, tuple(expired_ids))
        
        connection.commit()
        print("--- [SCHEDULER] Pembersihan Selesai. Data berhasil diupdate. ---")

    except Exception as e:
        print(f"--- [SCHEDULER ERROR] : {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor: cursor.close()
        if connection: connection.close()