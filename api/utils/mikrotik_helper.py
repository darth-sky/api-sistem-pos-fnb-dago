import os
from dotenv import load_dotenv
import routeros_api
import random
import string

load_dotenv('.env.dev')

# Ambil value dari environment variable
MIKROTIK_HOST = os.getenv('MIKROTIK_HOST')
MIKROTIK_USER = os.getenv('MIKROTIK_USER')
MIKROTIK_PASS = os.getenv('MIKROTIK_PASS')

def generate_voucher_mikrotik(durasi_jam, profile_name="default", comment="POS"):
    """
    Membuat user hotspot di Mikrotik dengan profil spesifik.
    Mengembalikan tuple (username, password).
    
    MODIFIED: Menggunakan sistem Single Code (Username = Password).
    """
    connection = None
    try:
        # 1. Buat Koneksi
        connection = routeros_api.RouterOsApiPool(
            MIKROTIK_HOST, 
            username=MIKROTIK_USER, 
            password=MIKROTIK_PASS, 
            plaintext_login=True
        )
        api = connection.get_api()

        # 2. Generate Single Code (Username = Password)
        # Format: 8 karakter huruf kecil & angka (contoh: s25kjr9f)
        # Ini lebih mudah diketik pelanggan daripada campuran huruf besar/kecil
        kode_voucher = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        username = kode_voucher
        password = kode_voucher # <--- PENTING: Password disamakan dengan Username
        
        # 3. Hitung Limit Uptime
        # Format Mikrotik: "2h", "4h", "1d", dll.
        limit_uptime = f"{durasi_jam}h"

        # 4. Tambahkan User ke Mikrotik
        users_resource = api.get_resource('/ip/hotspot/user')
        users_resource.add(
            name=username,
            password=password,
            limit_uptime=limit_uptime,
            profile=profile_name, # Profil dinamis dari parameter
            comment=f"{comment} [{profile_name}]"
        )
        
        print(f"Sukses generate voucher Mikrotik: {username} ({profile_name})")
        
        # Tetap mengembalikan dua nilai agar kompatibel dengan kode pemanggil (endpoints.py)
        return username, password

    except Exception as e:
        print(f"Mikrotik Error: {str(e)}")
        return None, None

    finally:
        # 5. Selalu tutup koneksi
        if connection:
            connection.disconnect()