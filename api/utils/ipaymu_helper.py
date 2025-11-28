import os
import json
import hashlib
import hmac
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('.env.dev')

def create_ipaymu_payment(id_transaksi, amount, buyer_name, buyer_phone, buyer_email):
    
    va = os.getenv('IPAYMU_VA')
    secret = os.getenv('IPAYMU_API_KEY') 
    
    base_url = "https://sandbox.ipaymu.com/api/v2"
    url = f"{base_url}/payment"
    
    notify_url = "https://e89ea1c9dc76.ngrok-free.app/api/callback/ipaymu" 
    
    frontend_url = "http://localhost:5173" 
    return_url = f"{frontend_url}/riwayat-transaksi" 
    cancel_url = f"{frontend_url}/booking-ruangan"   

    # Payload Data
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
        
        # --- TAMBAHKAN BARIS INI ---
        "paymentMethod": "qris" 
        # ---------------------------
    }

    # Generate Signature (Otomatis akan menyertakan paymentMethod baru)
    body_json = json.dumps(body, separators=(',', ':'))
    body_hash = hashlib.sha256(body_json.encode('utf-8')).hexdigest().lower()
    string_to_sign = f"POST:{va}:{body_hash}:{secret}"
    signature = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'va': va,
        'signature': signature,
        'timestamp': datetime.now().strftime('%Y%m%d%H%M%S')
    }

    try:
        print(f"Mengirim request ke: {url}")
        response = requests.post(url, headers=headers, data=body_json)
        res_data = response.json()
        
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