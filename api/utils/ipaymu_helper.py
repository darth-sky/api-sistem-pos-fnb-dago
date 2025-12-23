import os
import json
import hashlib
import hmac
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.dev')

def create_ipaymu_payment(id_transaksi, amount, buyer_name, buyer_phone, buyer_email):
    """
    Fungsi untuk meminta Payment URL ke iPaymu (Khusus QRIS)
    """
    
    # 1. Ambil Kredensial dari .env
    va = os.getenv('IPAYMU_VA')
    secret = os.getenv('IPAYMU_API_KEY')
    env = os.getenv('IPAYMU_ENV', 'sandbox') # Default ke sandbox jika tidak diset

    # Validasi sederhana
    if not va or not secret:
        return {"success": False, "message": "Kredensial iPaymu (VA/Key) tidak ditemukan di .env"}

    # 2. Tentukan Base URL (Sandbox vs Production)
    if env == 'production':
        base_url = "https://my.ipaymu.com/api/v2"
    else:
        base_url = "https://sandbox.ipaymu.com/api/v2"

    url = f"{base_url}/payment" # Menggunakan endpoint Redirect / Session

    # 3. Konfigurasi URL Callback & Redirect
    # PENTING: Ganti URL Ngrok ini setiap kali Anda restart Ngrok!
    # Cek terminal ngrok Anda untuk URL yang sedang aktif saat ini.
    notify_url = "https://fec2e81c79d0.ngrok-free.app/api/callback/ipaymu" 
    
    # URL Frontend (React)
    frontend_url = "http://localhost:5173" 
    return_url = f"{frontend_url}/riwayat-transaksi" # Redirect user ke sini setelah sukses
    cancel_url = f"{frontend_url}/booking-ruangan"   # Redirect user ke sini jika batal

    # 4. Susun Payload Data
    body = {
        "product": ["Booking Ruangan"],
        "qty": ["1"],
        "price": [int(amount)],
        "name": buyer_name,
        "phone": buyer_phone or "08123456789",
        "email": buyer_email or "guest@dago.com",
        "notifyUrl": notify_url, 
        "returnUrl": return_url, 
        "cancelUrl": cancel_url, 
        "expired": 24,
        "expiredType": "hours",
        "referenceId": str(id_transaksi),
        # --- FORCE QRIS ---
        # Ini akan membatasi metode pembayaran hanya ke QRIS di halaman redirect
        "paymentMethod": "qris" 
        # ------------------
    }

    # 5. Generate Signature (HMAC-SHA256)
    # separators=(',', ':') penting agar JSON rapat tanpa spasi (compact) untuk signature
    body_json = json.dumps(body, separators=(',', ':'))
    
    body_hash = hashlib.sha256(body_json.encode('utf-8')).hexdigest().lower()
    string_to_sign = f"POST:{va}:{body_hash}:{secret}"
    signature = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # 6. Susun Headers
    headers = {
        'Content-Type': 'application/json',
        'va': va,
        'signature': signature,
        'timestamp': datetime.now().strftime('%Y%m%d%H%M%S')
    }

    # 7. Kirim Request
    try:
        print(f"Mengirim request iPaymu ke: {url}")
        # print(f"Payload: {body_json}") # Uncomment jika ingin debug payload

        response = requests.post(url, headers=headers, data=body_json)
        res_data = response.json()
        
        # Cek Status Response
        if res_data.get('Status') == 200:
            return {
                "success": True,
                "url": res_data['Data']['Url'],
                "session_id": res_data['Data']['SessionID']
            }
        else:
            print(f"iPaymu Error: {res_data}")
            return {"success": False, "message": res_data.get('Message')}
            
    except Exception as e:
        print(f"Connection Error: {e}")
        return {"success": False, "message": str(e)}