
import decimal
import traceback
from flask import Blueprint, jsonify, request
from helper.db_helper import get_connection
from flask_jwt_extended import jwt_required
from datetime import date, datetime, timedelta
import json

owner_endpoints = Blueprint('owner_endpoints', __name__)

@owner_endpoints.route('/laporan-pajak-data', methods=['GET'])
@jwt_required()
def get_laporan_pajak_data():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify({"message": "ERROR", "error": "Parameter start_date dan end_date diperlukan."}), 400

    try:
        # Konversi tanggal (Kode ini sudah benar)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        end_date_for_query = end_date + timedelta(days=1)

    except ValueError:
        return jsonify({"message": "ERROR", "error": "Format tanggal tidak valid (YYYY-MM-DD)."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # === PERUBAHAN QUERY PENDAPATAN ===
        # Hitung Total Pendapatan HANYA dari transaksi F&B yang Lunas
        cursor.execute("""
            SELECT SUM(t.total_harga_final) as total_pendapatan_fnb
            FROM transaksi t
            WHERE t.status_pembayaran = 'Lunas'
              AND t.tanggal_transaksi >= %s AND t.tanggal_transaksi < %s
              AND EXISTS ( -- Pastikan transaksi ini punya detail F&B
                  SELECT 1
                  FROM detail_order_fnb dof
                  WHERE dof.id_transaksi = t.id_transaksi
              )
        """, (start_date, end_date_for_query))
        pendapatan_result = cursor.fetchone()
        # Ganti nama variabel agar lebih jelas
        total_pendapatan_fnb = pendapatan_result['total_pendapatan_fnb'] or decimal.Decimal(0.00)
        # === AKHIR PERUBAHAN QUERY PENDAPATAN ===


        # (Query pengeluaran - sudah benar)
        cursor.execute("""
            SELECT id_pengeluaran, kategori, jumlah, tanggal_pengeluaran
            FROM pengeluaran_operasional
            WHERE tanggal_pengeluaran BETWEEN %s AND %s
            ORDER BY tanggal_pengeluaran DESC
        """, (start_date, end_date))
        pengeluaran_list = cursor.fetchall()

        # (Query data pajak - sudah benar)
        latest_tax_payment = { "paidAmount": 0.0, "paymentDate": None }
        try:
            cursor.execute("""
                SELECT jumlah_dibayar, tanggal_bayar
                FROM pembayaran_pajak
                WHERE periode_mulai = %s AND periode_selesai = %s
                ORDER BY timestamp_catat DESC
                LIMIT 1
            """, (start_date, end_date))
            tax_payment_db = cursor.fetchone()
            if tax_payment_db:
                 latest_tax_payment["paidAmount"] = float(tax_payment_db['jumlah_dibayar'])
                 if isinstance(tax_payment_db.get('tanggal_bayar'), (datetime, date)):
                     latest_tax_payment["paymentDate"] = tax_payment_db['tanggal_bayar'].isoformat()
        except Exception as tax_err:
             print(f"Warning: Could not fetch tax payment data - {tax_err}")


        # (Formatting pengeluaran - sudah benar)
        safe_pengeluaran = []
        for p in pengeluaran_list:
             tanggal_pengeluaran = p.get("tanggal_pengeluaran")
             tanggal_iso = None
             if isinstance(tanggal_pengeluaran, (datetime, date)):
                 tanggal_iso = tanggal_pengeluaran.isoformat()

             safe_pengeluaran.append({
                 "id": p.get("id_pengeluaran"),
                 "kategori": p.get("kategori"),
                 "jumlah": float(p.get("jumlah", 0)),
                 "tanggal": tanggal_iso
             })

        # === PERUBAHAN NAMA VARIABEL DI RETURN ===
        return jsonify({
            "message": "OK",
            # Kirim pendapatan F&B sebagai field terpisah (atau ganti nama field lama)
            "total_pendapatan_fnb": float(total_pendapatan_fnb),
            # Anda mungkin masih ingin mengirim total pendapatan kotor *semua* transaksi?
            # Jika iya, tambahkan query lain untuk menghitungnya tanpa filter EXISTS
            # "total_pendapatan_kotor_all": float(total_semua_pendapatan),
            "pengeluaran_list": safe_pengeluaran,
            "tax_payment_status": latest_tax_payment
        }), 200
        # === AKHIR PERUBAHAN NAMA VARIABEL ===

    except Exception as e:
        print(f"Error fetching laporan pajak data: {e}")
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()
        
# B. (REKOMENDASI) Endpoint untuk Menyimpan Data Pembayaran Pajak
# Anda perlu tabel baru `pembayaran_pajak` (id, periode_mulai, periode_selesai, jumlah_dibayar, tanggal_bayar, timestamp_catat)
@owner_endpoints.route('/catat-pajak', methods=['POST'])
@jwt_required()
def catat_pembayaran_pajak():
    # (Pastikan hanya Owner)
    
    data = request.get_json()
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    paid_amount = data.get('paidAmount')
    payment_date_str = data.get('paymentDate') # Akan dalam format ISO dari frontend

    # (Validasi input: tanggal, amount)
    if not all([start_date_str, end_date_str, paid_amount, payment_date_str]):
         return jsonify({"message": "ERROR", "error": "Data tidak lengkap."}), 400
    try:
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        payment_date = datetime.datetime.fromisoformat(payment_date_str.replace('Z', '+00:00')).date() # Konversi ISO ke date
        paid_amount_dec = decimal.Decimal(paid_amount)
    except (ValueError, TypeError):
         return jsonify({"message": "ERROR", "error": "Format data tidak valid."}), 400


    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Simpan ke tabel pembayaran_pajak (sesuaikan nama tabel/kolom)
        query = """
            INSERT INTO pembayaran_pajak 
            (periode_mulai, periode_selesai, jumlah_dibayar, tanggal_bayar, timestamp_catat) 
            VALUES (%s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (start_date, end_date, paid_amount_dec, payment_date))
        connection.commit()

        return jsonify({"message": "OK", "info": "Pembayaran pajak berhasil dicatat."}), 201

    except Exception as e:
        if connection: connection.rollback()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

















# Catatan: Fungsi close_db_resources telah dihapus, 
# penutupan cursor dan connection dilakukan di blok finally setiap endpoint.


# ==========================
# Helpers
# ==========================
def _parse_date(v):
    """Parse tanggal dari string (YYYY-MM-DD atau DD-MM-YYYY) -> datetime.date | None."""
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except Exception:
            pass
    return None


def _req_range():
    """Ambil start_date & end_date dari query string, hasil date | None."""
    return _parse_date(request.args.get("start_date")), _parse_date(request.args.get("end_date"))


def _bad_request(msg):
    """Helper respon 400 JSON standar."""
    return jsonify({"message": "Error", "error": msg}), 400


# # ============================================================
# # 1) DASHBOARD SUMMARY / LAPORAN DASHBOARD  (GET /dashboard/summary)
# # ============================================================
# @owner_endpoints.route('/dashboard/summary', methods=['GET'])
# def dashboard_summary():
#     start_date, end_date = _req_range()
#     if not start_date or not end_date:
#         return jsonify({"message": "Error", "error": "Parameter start_date & end_date wajib (YYYY-MM-DD)."}), 400

#     connection = None
#     cursor = None
#     try:
#         connection = get_connection()
#         cursor = connection.cursor(dictionary=True)

#         # ---------- 1) TOTALS ----------
#         cursor.execute(
#             """
#             SELECT COALESCE(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total_fnb
#             FROM detail_order_fnb dof
#             JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
#             WHERE t.status_pembayaran = 'Lunas'
#               AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             """,
#             (start_date, end_date),
#         )
#         total_fnb = float((cursor.fetchone() or {}).get("total_fnb", 0))

#         cursor.execute(
#             """
#             SELECT COALESCE(SUM(x.total_transaksi), 0) AS total_ws
#             FROM (
#                 SELECT t.id_transaksi, MAX(t.total_harga_final) AS total_transaksi
#                 FROM booking_ruangan br
#                 JOIN transaksi t ON t.id_transaksi = br.id_transaksi
#                 WHERE t.status_pembayaran = 'Lunas'
#                   AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#                 GROUP BY t.id_transaksi
#             ) x
#             """,
#             (start_date, end_date),
#         )
#         total_ws = float((cursor.fetchone() or {}).get("total_ws", 0))

#         total_sales = total_fnb + total_ws

#         cursor.execute(
#             """
#             SELECT COUNT(*) AS total_transactions
#             FROM transaksi t
#             WHERE t.status_pembayaran = 'Lunas'
#               AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             """,
#             (start_date, end_date),
#         )
#         total_transactions = int((cursor.fetchone() or {}).get("total_transactions", 0))

#         total_days = max((end_date - start_date).days + 1, 1)
#         totals = {
#             "total_fnb": total_fnb,
#             "total_ws": total_ws,
#             "total_sales": total_sales,
#             "total_transactions": total_transactions,
#             "avg_daily": (total_sales / total_days) if total_days else 0,
#             "total_days": total_days,
#         }

#         # ---------- 2) DAILY SALES (FNB vs WS) ----------
#         cursor.execute(
#             """
#             SELECT DATE(t.tanggal_transaksi) AS tanggal,
#                    SUM(dof.jumlah * dof.harga_saat_order) AS fnb
#             FROM transaksi t
#             JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
#             WHERE t.status_pembayaran = 'Lunas'
#               AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             GROUP BY DATE(t.tanggal_transaksi)
#             """,
#             (start_date, end_date),
#         )
#         fnb_map = {r["tanggal"]: float(r.get("fnb") or 0) for r in (cursor.fetchall() or [])}

#         cursor.execute(
#             """
#             SELECT dt.tanggal, SUM(dt.total_transaksi) AS ws
#             FROM (
#                 SELECT DATE(t.tanggal_transaksi) AS tanggal,
#                        t.id_transaksi,
#                        MAX(t.total_harga_final) AS total_transaksi
#                 FROM booking_ruangan br
#                 JOIN transaksi t ON t.id_transaksi = br.id_transaksi
#                 WHERE t.status_pembayaran = 'Lunas'
#                   AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#                 GROUP BY DATE(t.tanggal_transaksi), t.id_transaksi
#             ) dt
#             GROUP BY dt.tanggal
#             """,
#             (start_date, end_date),
#         )
#         ws_map = {r["tanggal"]: float(r.get("ws") or 0) for r in (cursor.fetchall() or [])}

#         daily_sales = []
#         it = start_date
#         while it <= end_date:
#             f = fnb_map.get(it, 0.0)
#             w = ws_map.get(it, 0.0)
#             daily_sales.append({"tanggal": it.isoformat(), "fnb": f, "ws": w, "all": f + w})
#             it += timedelta(days=1)

#         # ---------- 3) VISITORS BY HOUR ----------
#         cursor.execute(
#             """
#             SELECT HOUR(t.tanggal_transaksi) AS hour, COUNT(*) AS count
#             FROM transaksi t
#             WHERE t.status_pembayaran = 'Lunas'
#               AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             GROUP BY HOUR(t.tanggal_transaksi)
#             ORDER BY hour
#             """,
#             (start_date, end_date),
#         )
#         visitors_by_hour = [{"hour": int(r["hour"]), "count": int(r["count"])} for r in (cursor.fetchall() or [])]

#         # ---------- 4) BOOKINGS BY HOUR ----------
#         cursor.execute(
#             """
#             SELECT HOUR(t.tanggal_transaksi) AS hour, COUNT(*) AS count
#             FROM booking_ruangan br
#             JOIN transaksi t ON t.id_transaksi = br.id_transaksi
#             WHERE t.status_pembayaran = 'Lunas'
#               AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             GROUP BY HOUR(t.tanggal_transaksi)
#             ORDER BY hour
#             """,
#             (start_date, end_date),
#         )
#         bookings_by_hour = [{"hour": int(r["hour"]), "count": int(r["count"])} for r in (cursor.fetchall() or [])]

#         # ---------- 5) TOP FNB (munculkan nama tenant) & TOP WS ----------
#         q_top_fnb = """
#             SELECT 
#                 pf.nama_produk AS item,
#                 COALESCE(tn.nama_tenant, 'Tanpa Tenant') AS tenant,
#                 SUM(dof.jumlah) AS qty,
#                 -- total kotor per produk (akumulasi)
#                 SUM(dof.jumlah * dof.harga_saat_order) AS gross,
#                 -- distribusi diskon transaksi proporsional ke item
#                 SUM(
#                     CASE 
#                         WHEN tg.trans_gross > 0 THEN
#                             (dof.jumlah * dof.harga_saat_order) / tg.trans_gross
#                             * GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0)
#                         ELSE 0
#                     END
#                 ) AS discount,
#                 -- nett = gross - discount
#                 ( SUM(dof.jumlah * dof.harga_saat_order)
#                 - SUM(
#                     CASE 
#                         WHEN tg.trans_gross > 0 THEN
#                             (dof.jumlah * dof.harga_saat_order) / tg.trans_gross
#                             * GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0)
#                         ELSE 0
#                     END
#                   )
#                 ) AS nett
#             FROM detail_order_fnb dof
#             JOIN transaksi t         ON t.id_transaksi = dof.id_transaksi
#                                     AND t.status_pembayaran = 'Lunas'
#             JOIN produk_fnb pf       ON pf.id_produk = dof.id_produk
#             LEFT JOIN kategori_produk kp ON kp.id_kategori = pf.id_kategori
#             LEFT JOIN tenants tn     ON tn.id_tenant = kp.id_tenant
#             -- gross per transaksi untuk membagi diskon proporsional
#             JOIN (
#                 SELECT dof2.id_transaksi,
#                        SUM(dof2.jumlah * dof2.harga_saat_order) AS trans_gross
#                 FROM detail_order_fnb dof2
#                 JOIN transaksi t2 ON t2.id_transaksi = dof2.id_transaksi
#                 WHERE t2.status_pembayaran = 'Lunas'
#                   AND DATE(t2.tanggal_transaksi) BETWEEN %s AND %s
#                 GROUP BY dof2.id_transaksi
#             ) tg ON tg.id_transaksi = dof.id_transaksi
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#             GROUP BY pf.id_produk, pf.nama_produk, tn.nama_tenant
#             ORDER BY qty DESC
#             LIMIT 10
#         """
#         cursor.execute(q_top_fnb, (start_date, end_date, start_date, end_date))
#         top_fnb = [
#             {
#                 "item":     r["item"],
#                 "tenant":   r["tenant"],
#                 "qty":      float(r["qty"] or 0),
#                 "total":    float(r["gross"] or 0),     # kompatibel dengan front-end lama
#                 "gross":    float(r["gross"] or 0),
#                 "discount": float(r["discount"] or 0),
#                 "nett":     float(r["nett"] or 0),
#             }
#             for r in (cursor.fetchall() or [])
#         ]

#         cursor.execute(
#             """
#             SELECT 
#                 r.nama_ruangan AS item,
#                 COUNT(DISTINCT br.id_booking) AS qty,
#                 SUM(x.total_transaksi) AS total
#             FROM booking_ruangan br
#             JOIN ruangan r ON r.id_ruangan = br.id_ruangan
#             JOIN (
#                 SELECT t.id_transaksi, MAX(t.total_harga_final) AS total_transaksi
#                 FROM transaksi t
#                 WHERE t.status_pembayaran = 'Lunas'
#                   AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#                 GROUP BY t.id_transaksi
#             ) x ON x.id_transaksi = br.id_transaksi
#             GROUP BY r.nama_ruangan
#             ORDER BY qty DESC
#             LIMIT 5
#             """,
#             (start_date, end_date),
#         )
#         top_ws = [
#             {"item": r["item"], "qty": int(r["qty"] or 0), "total": float(r["total"] or 0)}
#             for r in (cursor.fetchall() or [])
#         ]

#         return jsonify(
#             {
#                 "message": "OK",
#                 "datas": {
#                     "totals": totals,
#                     "daily_sales": daily_sales,
#                     "visitors_by_hour": visitors_by_hour,
#                     "bookings_by_hour": bookings_by_hour,
#                     "top_fnb": top_fnb,
#                     "top_ws": top_ws,
#                 },
#             }
#         ), 200

#     except Exception as e:
#         print("[dashboard_summary] error:", e)
#         return jsonify({"message": "Error", "error": str(e)}), 500
#     finally:
#         if cursor:
#             try:
#                 cursor.close()
#             except Exception:
#                 pass
#         if connection:
#             try:
#                 connection.close()
#             except Exception:
#                 pass


# # ============================================================
# # 2) OWNER FNB DASHBOARD  (GET /ownerfnb)  — FNB only
# # ============================================================
# @owner_endpoints.route("/ownerfnb", methods=["GET", "OPTIONS"])
# def ownerfnb_dashboard():
#     # Preflight (CORS)
#     if request.method == "OPTIONS":
#         return ("", 204)

#     # Ambil parameter & validasi tanggal
#     start_date_raw = request.args.get("start_date")
#     end_date_raw = request.args.get("end_date")
#     start_date = _parse_date(start_date_raw)
#     end_date = _parse_date(end_date_raw)
#     if not start_date or not end_date:
#         return _bad_request("start_date & end_date wajib (YYYY-MM-DD atau DD-MM-YYYY).")

#     conn = None
#     cur = None
#     try:
#         conn = get_connection()
#         cur = conn.cursor(dictionary=True)

#         # ---------- 1) TOTALS (FNB saja) ----------
#         totals_sql = """
#             SELECT
#                 COALESCE(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total_fnb,
#                 COUNT(DISTINCT t.id_transaksi) AS total_transactions,
#                 DATEDIFF(%s, %s) + 1 AS total_days
#             FROM detail_order_fnb dof
#             JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#               AND t.status_pembayaran = 'Lunas';
#         """
#         cur.execute(totals_sql, (end_date, start_date, start_date, end_date))
#         tr = cur.fetchone() or {}
#         total_fnb = int(tr.get("total_fnb") or 0)
#         total_tx = int(tr.get("total_transactions") or 0)
#         total_days = int(tr.get("total_days") or 1)
#         avg_daily = round(total_fnb / max(1, total_days))

#         # ---------- 2) DAILY SELLING PER TENANT ----------
#         daily_sql = """
#             SELECT
#                 DATE(t.tanggal_transaksi) AS tanggal,
#                 kp.id_tenant,
#                 SUM(dof.jumlah * dof.harga_saat_order) AS total_harian
#             FROM detail_order_fnb dof
#             JOIN transaksi t   ON t.id_transaksi = dof.id_transaksi
#             JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
#             JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#               AND t.status_pembayaran = 'Lunas'
#             GROUP BY tanggal, kp.id_tenant
#             ORDER BY tanggal ASC;
#         """
#         cur.execute(daily_sql, (start_date, end_date))
#         rows = cur.fetchall() or []

#         daily_map = {}
#         for r in rows:
#             key = r["tanggal"].isoformat() if hasattr(r["tanggal"], "isoformat") else str(r["tanggal"])
#             if key not in daily_map:
#                 daily_map[key] = {"tanggal": key, "dapoerms": 0, "homebro": 0}
#             if int(r["id_tenant"]) == TENANT_DAPOER_MS:
#                 daily_map[key]["dapoerms"] = int(r["total_harian"] or 0)
#             elif int(r["id_tenant"]) == TENANT_HOME_BRO:
#                 daily_map[key]["homebro"] = int(r["total_harian"] or 0)
#         daily_selling = sorted(daily_map.values(), key=lambda x: x["tanggal"])

#         # ---------- 3) VISITORS BY HOUR (trafik kunjungan) ----------
#         visitors_sql = """
#             SELECT
#                 HOUR(t.tanggal_transaksi) AS hour,
#                 COUNT(DISTINCT t.id_transaksi) AS cnt
#             FROM transaksi t
#             JOIN detail_order_fnb dof ON dof.id_transaksi = t.id_transaksi
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#               AND t.status_pembayaran = 'Lunas'
#             GROUP BY hour
#             ORDER BY hour;
#         """
#         cur.execute(visitors_sql, (start_date, end_date))
#         visitors_by_hour = [
#             {"hour": int(r["hour"]), "count": int(r["cnt"])}
#             for r in (cur.fetchall() or [])
#         ]

#         # ---------- 4) PEAK HOURS (banyak menu dipesan per jam) ----------
#         peak_sql = """
#             SELECT
#                 HOUR(t.tanggal_transaksi) AS hour,
#                 SUM(dof.jumlah) AS item_count
#             FROM detail_order_fnb dof
#             JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#               AND t.status_pembayaran = 'Lunas'
#             GROUP BY hour
#             ORDER BY hour;
#         """
#         cur.execute(peak_sql, (start_date, end_date))
#         peak_by_hour = [
#             {"hour": int(r["hour"]), "count": int(r["item_count"] or 0)}
#             for r in (cur.fetchall() or [])
#         ]

#         # ---------- 5) TOP 5 PRODUCT PER TENANT ----------
#         top_sql = """
#             SELECT
#                 pf.nama_produk AS item,
#                 SUM(dof.jumlah) AS qty,
#                 SUM(dof.jumlah * dof.harga_saat_order) AS total
#             FROM detail_order_fnb dof
#             JOIN transaksi t   ON t.id_transaksi = dof.id_transaksi
#             JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
#             JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
#             WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
#               AND t.status_pembayaran = 'Lunas'
#               AND kp.id_tenant = %s
#             GROUP BY pf.nama_produk
#             ORDER BY total DESC
#             LIMIT 5;
#         """
#         # Dapoer M.S
#         cur.execute(top_sql, (start_date, end_date, TENANT_DAPOER_MS))
#         top_dapoer = [
#             {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
#             for r in (cur.fetchall() or [])
#         ]
#         # HomeBro
#         cur.execute(top_sql, (start_date, end_date, TENANT_HOME_BRO))
#         top_home = [
#             {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
#             for r in (cur.fetchall() or [])
#         ]

#         # ---------- Response ----------
#         return jsonify(
#             {
#                 "message": "OK",
#                 "datas": {
#                     "totals": {
#                         "total_fnb": total_fnb,
#                         "total_ws": 0,                  # FNB-only dashboard
#                         "total_sales": total_fnb,       # sama dengan total_fnb
#                         "total_transactions": total_tx, # jumlah transaksi FNB berhasil
#                         "avg_daily": avg_daily,         # rata-rata harian FNB
#                         "total_days": total_days,
#                     },
#                     "daily_selling_per_tenant": daily_selling,  # line chart per tenant
#                     "visitors_by_hour": visitors_by_hour,       # transaksi per jam
#                     "peak_by_hour": peak_by_hour,               # item/menu per jam
#                     "top_fnb": {
#                         "dapoer": top_dapoer,                   # Top 5 DapoerMS
#                         "home": top_home,                       # Top 5 HomeBro
#                     },
#                 },
#             }
#         ), 200

#     except Exception as e:
#         print("ownerfnb_dashboard error:", e)
#         return jsonify({"message": "Error", "error": str(e)}), 500
#     finally:
#         if cur:
#             try:
#                 cur.close()
#             except Exception:
#                 pass
#         if conn:
#             try:
#                 conn.close()
#             except Exception:
#                 pass







# --- 1. Total Pendapatan per Kategori ---
@owner_endpoints.route('/totalPendapatan', methods=['GET'])
def getTotalPendapatan():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Kueri untuk menghitung total pendapatan dari 5 kategori utama.
        # Menggunakan kolom t.total_harga_final.
        query = """
        -- 1. Total Pendapatan dari F&B
        SELECT 'F&B' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 2. Total Pendapatan dari Booking Ruangan / Working Space (Non-Membership Credit)
        SELECT 'Working Space' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN booking_ruangan br ON t.id_transaksi = br.id_transaksi
        -- Hanya hitung transaksi pembayaran ruangan (bukan penggunaan kredit dari membership yang totalnya 0)
        WHERE br.id_memberships IS NULL OR t.total_harga_final > 0
        GROUP BY kategori

        UNION ALL

        -- 3. Total Pendapatan dari Event Booking
        SELECT 'Event Booking' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN booking_event be ON t.id_transaksi = be.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 4. Total Pendapatan dari Pembelian Membership
        SELECT 'Membership' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN memberships m ON t.id_transaksi = m.id_transaksi
        GROUP BY kategori

        UNION ALL

        -- 5. Total Pendapatan dari Pembelian Virtual Office
        SELECT 'Virtual Office' AS kategori, SUM(t.total_harga_final) AS total
        FROM transaksi t
        JOIN client_virtual_office cvo ON t.id_transaksi = cvo.id_transaksi
        GROUP BY kategori

        HAVING total IS NOT NULL AND total > 0; -- Memastikan hanya kategori dengan total pendapatan > 0 yang ditampilkan
        """

        cursor.execute(query)
        results = cursor.fetchall()

        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTotalPendapatan: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass


# --- 2. Top 10 FNB Terlaris ---
@owner_endpoints.route('/topFNB', methods=['GET'])
def getTopFNB():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk mencari Top 10 FNB berdasarkan kuantitas terjual
        query = """
        SELECT 
            COALESCE(pf.nama_produk, 'Produk Tidak Ditemukan') AS item,
            SUM(dof.jumlah) AS qty,
            SUM(dof.jumlah * dof.harga_saat_order) AS total
        FROM detail_order_fnb dof
        LEFT JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
        GROUP BY pf.nama_produk
        ORDER BY qty DESC
        LIMIT 10;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTopFNB: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 3. Top 5 Working Space Terlaris ---
@owner_endpoints.route('/topWorking', methods=['GET'])
def getTopWorking():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk mencari Top 5 Ruangan/Working Space berdasarkan pendapatan.
        # Menggunakan t.total_harga_final
        query = """
        SELECT 
            r.nama_ruangan AS item, -- Asumsi item adalah nama ruangan
            COUNT(br.id_booking) AS qty, -- Jumlah booking
            SUM(t.total_harga_final) AS total -- Mengambil total dari tabel transaksi yang terhubung
        FROM booking_ruangan br
        JOIN ruangan r ON br.id_ruangan = r.id_ruangan
        JOIN transaksi t ON br.id_transaksi = t.id_transaksi
        GROUP BY r.nama_ruangan
        ORDER BY total DESC
        LIMIT 5;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getTopWorking: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 4. Penjualan Harian Bulanan (Daily Selling) ---
@owner_endpoints.route('/dailySelling', methods=['GET'])
def getDailySelling():
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not month or not year:
        return jsonify({"message": "Parameter month dan year wajib."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Query untuk menghitung total transaksi per hari di bulan dan tahun yang ditentukan
        # Menggunakan total_harga_final
        query = """
        SELECT
            DAY(tanggal_transaksi) AS day,
            SUM(total_harga_final) AS total
        FROM transaksi
        WHERE MONTH(tanggal_transaksi) = %s AND YEAR(tanggal_transaksi) = %s
        GROUP BY DAY(tanggal_transaksi)
        ORDER BY DAY(tanggal_transaksi);
        """
        cursor.execute(query, (month, year))
        results = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getDailySelling: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

# --- 5. Ringkasan Profit Bulanan (Profit Summary) ---
@owner_endpoints.route('/profitSummary', methods=['GET'])
def getProfitSummary():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        # Mengambil data 6 bulan terakhir
        # Menggunakan total_harga_final
        query = """
        SELECT
            DATE_FORMAT(tanggal_transaksi, '%%Y-%%m') AS sort_date,
            DATE_FORMAT(tanggal_transaksi, '%%M') AS bulan, -- Bulan dalam bahasa Inggris default MySQL
            SUM(total_harga_final) AS total
        FROM transaksi
        WHERE tanggal_transaksi >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY sort_date, bulan
        ORDER BY sort_date ASC;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        return jsonify({"message": "OK", "datas": results}), 200
    except Exception as e:
        print(f"Error executing getProfitSummary: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        # Penutupan sumber daya secara defensif di sini
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass



@owner_endpoints.route('/fnb-dashboard-data', methods=['GET'])
def getFnBDashboardData():
    # Ambil parameter tanggal dari query string
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"message": "Error", "error": "Parameter start_date dan end_date wajib."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query Utama: Menarik semua data FNB yang dibutuhkan dalam satu kali panggil.
        query = """
        SELECT
            DATE(t.tanggal_transaksi) AS tanggal,
            SUM(t.total_harga_final) AS daily_sales,
            
            -- Order Type Aggregation (Doughnut Chart 1) - Menggunakan kolom fnb_type
            SUM(CASE WHEN t.fnb_type = 'Dine In' THEN 1 ELSE 0 END) AS dine_in_count,
            SUM(CASE WHEN t.fnb_type = 'Takeaway' THEN 1 ELSE 0 END) AS take_away_count,
            
            -- Payment Type Aggregation (Doughnut Chart 2)
            SUM(CASE WHEN t.metode_pembayaran = 'Cash' THEN 1 ELSE 0 END) AS cash_count,
            SUM(CASE WHEN t.metode_pembayaran != 'Cash' THEN 1 ELSE 0 END) AS non_cash_count,
            
            -- Sales per Tenant (for Progress Bar) - Menggunakan kp.id_tenant dan dof.jumlah
            SUM(CASE 
                WHEN kp.id_tenant = 1 THEN dof.harga_saat_order * dof.jumlah
                ELSE 0 
            END) AS homebro_sales,
            SUM(CASE 
                WHEN kp.id_tenant = 2 THEN dof.harga_saat_order * dof.jumlah
                ELSE 0 
            END) AS dapoerms_sales
            
        FROM 
            transaksi t
        JOIN 
            detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
        JOIN
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN 
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            DATE(t.tanggal_transaksi) BETWEEN %s AND %s 
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            DATE(t.tanggal_transaksi)
        ORDER BY
            tanggal;
        """
        
        # Query untuk Top 5 Product (DapoerMS - id_tenant = 2)
        top_product_dapoerms_query = """
        SELECT 
            pf.nama_produk AS item,
            SUM(dof.jumlah) AS qty, -- Kuantitas diubah menjadi jumlah
            SUM(dof.harga_saat_order * dof.jumlah) AS total -- Kuantitas diubah menjadi jumlah
        FROM 
            detail_order_fnb dof
        JOIN 
            transaksi t ON dof.id_transaksi = t.id_transaksi
        JOIN 
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            kp.id_tenant = 2 
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            pf.nama_produk
        ORDER BY 
            total DESC
        LIMIT 5;
        """

        # Query untuk Top 5 Product (HomeBro - id_tenant = 1)
        top_product_homebro_query = """
        SELECT 
            pf.nama_produk AS item,
            SUM(dof.jumlah) AS qty, -- Kuantitas diubah menjadi jumlah
            SUM(dof.harga_saat_order * dof.jumlah) AS total -- Kuantitas diubah menjadi jumlah
        FROM 
            detail_order_fnb dof
        JOIN 
            transaksi t ON dof.id_transaksi = t.id_transaksi
        JOIN 
            produk_fnb pf ON dof.id_produk_fnb = pf.id_produk
        JOIN
            kategori_produk kp ON pf.id_kategori = kp.id_kategori 
        WHERE 
            kp.id_tenant = 1 
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_transaksi IN ('Selesai', 'Lunas')
        GROUP BY 
            pf.nama_produk
        ORDER BY 
            total DESC
        LIMIT 5;
        """
        
        # Eksekusi Query Utama
        cursor.execute(query, (start_date, end_date))
        daily_sales_data = cursor.fetchall()
        
        # Eksekusi Top 5 DapoerMS
        cursor.execute(top_product_dapoerms_query, (start_date, end_date))
        dapoerms_top_products = cursor.fetchall()
        
        # Eksekusi Top 5 HomeBro
        cursor.execute(top_product_homebro_query, (start_date, end_date))
        homebro_top_products = cursor.fetchall()

        # Gabungkan semua hasil ke dalam satu JSON
        response_data = {
            "daily_sales_data": daily_sales_data,
            "dapoerms_top_products": dapoerms_top_products,
            "homebro_top_products": homebro_top_products
        }

        return jsonify({"message": "OK", "datas": response_data}), 200

    except Exception as e:
        print(f"Error executing getFnBDashboardData: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if connection: connection.close()



# ---------------- helpers ----------------
def _parse_date(v):
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except Exception:
            pass
    return None

def _req_range():
    """
    Ambil start_date & end_date dari query string.
    Wajib ada, format fleksibel (YYYY-MM-DD atau DD-MM-YYYY).
    """
    start = _parse_date(request.args.get("start_date"))
    end   = _parse_date(request.args.get("end_date"))
    return start, end

# -------------- DASHBOARD SUMMARY (endpoint utama) ----------------
@owner_endpoints.route('/dashboard/summary', methods=['GET'])
def dashboard_summary():
    start_date, end_date = _req_range()
    if not start_date or not end_date:
        return jsonify({"message": "Error", "error": "Parameter start_date & end_date wajib (YYYY-MM-DD)."}), 400

    connection, cursor = None, None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # ===================== 1) TOTALS =====================
        # a) Total F&B (sum detail) dalam range
        q_total_fnb = """
            SELECT COALESCE(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total_fnb
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
        """
        cursor.execute(q_total_fnb, (start_date, end_date))
        total_fnb = float(cursor.fetchone()["total_fnb"])

        # b) Total Working Space (agregasi per transaksi untuk hindari duplikasi)
        q_total_ws = """
            SELECT COALESCE(SUM(x.total_transaksi), 0) AS total_ws
            FROM (
                SELECT t.id_transaksi, MAX(t.total_harga_final) AS total_transaksi
                FROM booking_ruangan br
                JOIN transaksi t ON t.id_transaksi = br.id_transaksi
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY t.id_transaksi
            ) x
        """
        cursor.execute(q_total_ws, (start_date, end_date))
        total_ws = float(cursor.fetchone()["total_ws"])

        total_sales = total_fnb + total_ws

        # c) Jumlah transaksi (lunas) dalam range (pengunjung ≈ transaksi)
        q_total_trans = """
            SELECT COUNT(*) AS total_transactions
            FROM transaksi t
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
        """
        cursor.execute(q_total_trans, (start_date, end_date))
        total_transactions = int(cursor.fetchone()["total_transactions"])

        # d) total days & avg harian
        total_days = (end_date - start_date).days + 1
        total_days = max(total_days, 1)
        avg_daily = total_sales / total_days if total_days else 0

        totals = {
            "total_fnb": total_fnb,
            "total_ws": total_ws,
            "total_sales": total_sales,
            "total_transactions": total_transactions,
            "avg_daily": avg_daily,
            "total_days": total_days
        }

        # =============== 2) DAILY SALES (FNB vs WS) ===============
        # FNB per hari
        q_fnb_daily = """
            SELECT DATE(t.tanggal_transaksi) AS tanggal,
                   SUM(dof.jumlah * dof.harga_saat_order) AS fnb
            FROM transaksi t
            JOIN detail_order_fnb dof ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY DATE(t.tanggal_transaksi)
        """
        cursor.execute(q_fnb_daily, (start_date, end_date))
        fnb_rows = cursor.fetchall()
        fnb_map = { r["tanggal"]: float(r["fnb"] or 0) for r in fnb_rows }

        # WS per hari (agregasi per transaksi)
        q_ws_daily = """
            SELECT dt.tanggal, SUM(dt.total_transaksi) AS ws
            FROM (
                SELECT DATE(t.tanggal_transaksi) AS tanggal,
                       t.id_transaksi,
                       MAX(t.total_harga_final) AS total_transaksi
                FROM booking_ruangan br
                JOIN transaksi t ON t.id_transaksi = br.id_transaksi
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY DATE(t.tanggal_transaksi), t.id_transaksi
            ) dt
            GROUP BY dt.tanggal
        """
        cursor.execute(q_ws_daily, (start_date, end_date))
        ws_rows = cursor.fetchall()
        ws_map = { r["tanggal"]: float(r["ws"] or 0) for r in ws_rows }

        # gabungkan jadi list lengkap setiap hari di range
        daily_sales = []
        it = start_date
        while it <= end_date:
            f = fnb_map.get(it, 0.0)
            w = ws_map.get(it, 0.0)
            daily_sales.append({
                "tanggal": it.isoformat(),
                "fnb": f,
                "ws": w,
                "all": f + w
            })
            it += timedelta(days=1)

        # ======= 3) VISITORS BY HOUR (jumlah transaksi per jam) =======
        q_visitors_by_hour = """
            SELECT HOUR(t.tanggal_transaksi) AS hour, COUNT(*) AS count
            FROM transaksi t
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY HOUR(t.tanggal_transaksi)
            ORDER BY hour
        """
        cursor.execute(q_visitors_by_hour, (start_date, end_date))
        visitors_by_hour = [
            {"hour": int(r["hour"]), "count": int(r["count"])}
            for r in cursor.fetchall()
        ]

        # ======= 4) BOOKINGS BY HOUR (estimasi: pakai jam transaksi booking) =======
        # Jika kamu punya kolom jam_mulai/jam_selesai di booking_ruangan, ganti agregasi ini
        q_bookings_by_hour = """
            SELECT HOUR(t.tanggal_transaksi) AS hour, COUNT(*) AS count
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY HOUR(t.tanggal_transaksi)
            ORDER BY hour
        """
        cursor.execute(q_bookings_by_hour, (start_date, end_date))
        bookings_by_hour = [
            {"hour": int(r["hour"]), "count": int(r["count"])}
            for r in cursor.fetchall()
        ]

        # ================= 5) TOP FNB & TOP WS =================
        q_top_fnb = """
            SELECT 
                COALESCE(pf.nama_produk, 'Produk Tidak Ditemukan') AS item,
                SUM(dof.jumlah) AS qty,
                SUM(dof.jumlah * dof.harga_saat_order) AS total
            FROM detail_order_fnb dof
            LEFT JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY pf.nama_produk
            ORDER BY qty DESC
            LIMIT 10
        """
        cursor.execute(q_top_fnb, (start_date, end_date))
        top_fnb = [
            {"item": r["item"], "qty": float(r["qty"] or 0), "total": float(r["total"] or 0)}
            for r in cursor.fetchall()
        ]

        q_top_ws = """
            SELECT 
                r.nama_ruangan AS item,
                COUNT(DISTINCT br.id_booking) AS qty,
                SUM(x.total_transaksi) AS total
            FROM booking_ruangan br
            JOIN ruangan r ON br.id_ruangan = r.id_ruangan
            JOIN (
                SELECT t.id_transaksi, MAX(t.total_harga_final) AS total_transaksi
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY t.id_transaksi
            ) x ON x.id_transaksi = br.id_transaksi
            GROUP BY r.nama_ruangan
            ORDER BY total DESC
            LIMIT 5
        """
        cursor.execute(q_top_ws, (start_date, end_date))
        top_ws = [
            {"item": r["item"], "qty": float(r["qty"] or 0), "total": float(r["total"] or 0)}
            for r in cursor.fetchall()
        ]

        # ================== RESPON ==================
        return jsonify({
            "message": "OK",
            "datas": {
                "totals": totals,
                "daily_sales": daily_sales,
                "visitors_by_hour": visitors_by_hour,
                "bookings_by_hour": bookings_by_hour,
                "top_fnb": top_fnb,
                "top_ws": top_ws
            }
        }), 200

    except Exception as e:
        print(f"[dashboard_summary] error: {e}")
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if connection:
            try: connection.close()
            except: pass
            


TENANT_HOME_BRO = 3
TENANT_DAPOER_MS = 4

# ⬇️ TANPA leading slash + tambahkan OPTIONS
@owner_endpoints.route("/ownerfnb", methods=["GET", "OPTIONS"])
def ownerfnb_dashboard():
    # ⬇️ balas dulu preflight
    if request.method == "OPTIONS":
        return ("", 204)

    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')
    if not start_date or not end_date:
        return jsonify({"message": "Error", "error": "start_date & end_date wajib (YYYY-MM-DD)."}), 400

    conn = None
    cur  = None
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)

        # ---------- 1) TOTALS ----------
        totals_sql = """
        SELECT
            COALESCE(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total_fnb,
            COUNT(DISTINCT t.id_transaksi) AS total_transactions,
            DATEDIFF(%s, %s) + 1 AS total_days
        FROM detail_order_fnb dof
        JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
        WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
          AND t.status_pembayaran = 'Lunas';
        """
        cur.execute(totals_sql, (end_date, start_date, start_date, end_date))
        tr = cur.fetchone() or {}
        total_fnb  = int(tr.get("total_fnb") or 0)
        total_tx   = int(tr.get("total_transactions") or 0)
        total_days = int(tr.get("total_days") or 1)
        avg_daily  = round(total_fnb / max(1, total_days))

        # ---------- 2) DAILY SELLING PER TENANT ----------
        daily_sql = """
        SELECT
            DATE(t.tanggal_transaksi) AS tanggal,
            kp.id_tenant,
            SUM(dof.jumlah * dof.harga_saat_order) AS total_harian
        FROM detail_order_fnb dof
        JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
        JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
        JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
        WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
          AND t.status_pembayaran = 'Lunas'
        GROUP BY tanggal, kp.id_tenant
        ORDER BY tanggal ASC;
        """
        cur.execute(daily_sql, (start_date, end_date))
        rows = cur.fetchall() or []
        daily_map = {}
        for r in rows:
            key = r['tanggal'].isoformat() if hasattr(r['tanggal'], 'isoformat') else str(r['tanggal'])
            if key not in daily_map:
                daily_map[key] = {"tanggal": key, "dapoerms": 0, "homebro": 0}
            if r['id_tenant'] == TENANT_DAPOER_MS:
                daily_map[key]["dapoerms"] = int(r['total_harian'] or 0)
            elif r['id_tenant'] == TENANT_HOME_BRO:
                daily_map[key]["homebro"] = int(r['total_harian'] or 0)
        daily_selling = sorted(daily_map.values(), key=lambda x: x["tanggal"])

        # ---------- 3) VISITORS PER HOUR ----------
        visitors_sql = """
        SELECT
            HOUR(t.tanggal_transaksi) AS hour,
            COUNT(DISTINCT t.id_transaksi) AS cnt
        FROM transaksi t
        JOIN detail_order_fnb dof ON dof.id_transaksi = t.id_transaksi
        WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
          AND t.status_pembayaran = 'Lunas'
        GROUP BY hour
        ORDER BY hour;
        """
        cur.execute(visitors_sql, (start_date, end_date))
        vrows = cur.fetchall() or []
        visitors_by_hour = [{"hour": int(r["hour"]), "count": int(r["cnt"])} for r in vrows]

        # ---------- 4) PEAK HOURS ----------
        peak_by_hour = visitors_by_hour

        # ---------- 5) TOP 5 PRODUCT per TENANT ----------
        top_sql = """
        SELECT
            pf.nama_produk AS item,
            SUM(dof.jumlah) AS qty,
            SUM(dof.jumlah * dof.harga_saat_order) AS total
        FROM detail_order_fnb dof
        JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
        JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
        JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
        WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
          AND t.status_pembayaran = 'Lunas'
          AND kp.id_tenant = %s
        GROUP BY pf.nama_produk
        ORDER BY total DESC
        LIMIT 5;
        """
        cur.execute(top_sql, (start_date, end_date, TENANT_DAPOER_MS))
        top_dapoer = [{"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)} for r in (cur.fetchall() or [])]
        cur.execute(top_sql, (start_date, end_date, TENANT_HOME_BRO))
        top_home = [{"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)} for r in (cur.fetchall() or [])]

        return jsonify({
            "message": "OK",
            "datas": {
                "totals": {
                    "total_fnb": total_fnb,
                    "total_ws": 0,
                    "total_sales": total_fnb,
                    "total_transactions": total_tx,
                    "avg_daily": avg_daily,
                    "total_days": total_days
                },
                "daily_selling_per_tenant": daily_selling,
                "visitors_by_hour": visitors_by_hour,
                "peak_by_hour": peak_by_hour,
                "top_fnb": { "dapoer": top_dapoer, "home": top_home }
            }
        }), 200

    except Exception as e:
        print("ownerfnb_dashboard error:", e)
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cur:
            try: cur.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass
            
