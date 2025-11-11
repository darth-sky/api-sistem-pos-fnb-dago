# owner_endpoints.py
import decimal
import traceback
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from helper.db_helper import get_connection
from datetime import date, datetime, timedelta  # <-- tambahkan date

owner_endpoints = Blueprint('owner_endpoints', __name__)




@owner_endpoints.route('/ws-dashboard-data', methods=['GET'])
def ws_dashboard_data():
    """
    Data untuk Working Space Dashboard:
    - stats: totalRevenue, totalBookings, totalVisitors
    - dailyRevenue: labels -> ['1','2',...,'N'] (hari dalam range, berurutan TANPA loncat)
                    labelsPretty -> ['1 Okt','2 Okt', ...] untuk tooltip
                    datasets -> jumlah booking per kategori/hari
    - categoryContribution: [{name, value}] (revenue per kategori)
    - packageByDuration: sumbu-X = DISTINCT paket_harga_ruangan.durasi_jam (saja),
                         hitung booking yang MATCH paket pada RUANGAN yang sama
                         -> [{durasi_jam, total_booking, total_user, total_revenue}]
    - topSpaces: Top 10 ruang urut qty booking DESC, tie-break total DESC
    """
    conn = None
    cur = None
    try:
        # default ke bulan berjalan
        today = date.today()
        start_date_str = request.args.get('startDate', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date_str   = request.args.get('endDate',   today.strftime('%Y-%m-%d'))

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_date_str,   '%Y-%m-%d').date()
        if end_date < start_date:
            return jsonify({"message": "ERROR", "error": "endDate < startDate"}), 400

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # ---------- 1) STATS ----------
        cur.execute("""
            SELECT
              COALESCE(SUM(t.total_harga_final), 0)                           AS totalRevenue,
              COUNT(br.id_booking)                                            AS totalBookings,
              COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR))) AS totalVisitors
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        s = cur.fetchone() or {}
        stats = {
            "totalRevenue": int(s.get("totalRevenue") or 0),
            "totalBookings": int(s.get("totalBookings") or 0),
            "totalVisitors": int(s.get("totalVisitors") or 0),
        }

        # ---------- 2) DAILY BOOKING (labels = hari 1..N) ----------
        days_count = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(days_count)]
        pos_map = {(start_date + timedelta(days=i)).strftime('%Y-%m-%d'): i for i in range(days_count)}

        labels_days   = [str(d.day) for d in all_dates]  # "1".."N"
        # Hindari %-d (tidak portable di Windows)
        labels_pretty = [f"{int(d.strftime('%d'))} {d.strftime('%b')}" for d in all_dates]

        categories = ["Open Space", "Space Monitor", "Room Meeting Besar", "Room Meeting Kecil"]
        dataset_map_counts = {k: [0] * days_count for k in categories}

        cur.execute("""
            SELECT
              DATE(br.waktu_mulai) AS period_date,
              kr.nama_kategori     AS category,
              COUNT(*)             AS cnt
            FROM booking_ruangan br
            JOIN transaksi t            ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r              ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr    ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY period_date, category
            ORDER BY period_date ASC
        """, (start_date_str, end_date_str))
        for row in cur.fetchall() or []:
            key = row["period_date"].strftime('%Y-%m-%d')
            idx = pos_map.get(key)
            cat = row["category"]
            if idx is not None and cat in dataset_map_counts:
                dataset_map_counts[cat][idx] = int(row["cnt"] or 0)

        dailyRevenue = {
            "labels": labels_days,          # sumbu-X 1..N
            "labelsPretty": labels_pretty,  # tooltip "1 Okt", dst.
            "datasets": dataset_map_counts
        }

        # ---------- 3) CATEGORY CONTRIBUTION (DOUGHNUT) ----------
        cur.execute("""
            SELECT kr.nama_kategori AS name, SUM(t.total_harga_final) AS value
            FROM transaksi t
            JOIN booking_ruangan br  ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r           ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY name
        """, (start_date_str, end_date_str))
        categoryContribution = [
            {"name": r["name"], "value": int(r["value"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # ---------- 4) PACKAGE BY DURATION (HANYA dari paket_harga_ruangan) ----------
        # Sumbu-X durasi dari paket (distinct & urut)
        cur.execute("""
          SELECT DISTINCT durasi_jam
          FROM paket_harga_ruangan
          WHERE durasi_jam IS NOT NULL
          ORDER BY durasi_jam ASC
        """)
        durations = [int(r["durasi_jam"]) for r in (cur.fetchall() or [])]

        # Hitung booking yang MATCH paket (id_ruangan sama & durasi jam sama PERSIS)
        # TIMESTAMPDIFF(HOUR, ...) melakukan floor — cocok jika booking dibuat pas per jam.
        cur.execute("""
          SELECT
            p.durasi_jam AS durasi_jam,
            COUNT(*) AS total_booking,
            COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR))) AS total_user,
            COALESCE(SUM(t.total_harga_final), 0) AS total_revenue
          FROM booking_ruangan br
          JOIN transaksi t ON t.id_transaksi = br.id_transaksi
          JOIN paket_harga_ruangan p
            ON p.id_ruangan = br.id_ruangan
           AND p.durasi_jam = TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)
          WHERE t.status_pembayaran = 'Lunas'
            AND DATE(br.waktu_mulai) BETWEEN %s AND %s
          GROUP BY p.durasi_jam
        """, (start_date_str, end_date_str))
        agg = {
            int(r["durasi_jam"]): {
                "total_booking": int(r["total_booking"] or 0),
                "total_user":    int(r["total_user"] or 0),
                "total_revenue": int(r["total_revenue"] or 0),
            }
            for r in (cur.fetchall() or [])
        }

        packageByDuration = []
        for dj in durations:
            a = agg.get(dj, {"total_booking": 0, "total_user": 0, "total_revenue": 0})
            packageByDuration.append({
                "durasi_jam": dj,
                "total_booking": a["total_booking"],
                "total_user": a["total_user"],
                "total_revenue": a["total_revenue"],
            })

        # ---------- 5) TOP 10 WORKING SPACES ----------
        cur.execute("""
            SELECT
              r.nama_ruangan   AS item,
              kr.nama_kategori AS category,
              COUNT(br.id_booking)      AS qty,
              SUM(t.total_harga_final)  AS total
            FROM transaksi t
            JOIN booking_ruangan br  ON br.id_transaksi = t.id_transaksi
            JOIN ruangan r           ON r.id_ruangan     = br.id_ruangan
            JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY item, category
            ORDER BY qty DESC, total DESC
            LIMIT 10
        """, (start_date_str, end_date_str))
        topSpaces = [{
            "item": r["item"],
            "category": r["category"],
            "qty": int(r["qty"] or 0),
            "total": int(r["total"] or 0),
        } for r in (cur.fetchall() or [])]

        return jsonify({
            "message": "OK",
            "datas": {
                "stats": stats,
                "dailyRevenue": dailyRevenue,
                "categoryContribution": categoryContribution,
                "packageByDuration": packageByDuration,
                "topSpaces": topSpaces
            }
        }), 200

    except Exception as e:
        print("Error in /api/v1/admin/ws-dashboard-data:", e)
        traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        try:
            if cur: cur.close()
        finally:
            if conn: conn.close()
# ------------------- END WS DASHBOARD -------------------


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
      


# ==========================
# Konstanta (ikuti skema DB)
# ==========================
TENANT_HOME_BRO = 3
TENANT_DAPOER_MS = 4


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


# ============================================================
# 1) DASHBOARD SUMMARY / LAPORAN DASHBOARD  (GET /dashboard/summary)
# ============================================================
@owner_endpoints.route('/dashboard/summary', methods=['GET'])
def dashboard_summary():
    start_date, end_date = _req_range()
    if not start_date or not end_date:
        return jsonify({"message": "Error", "error": "Parameter start_date & end_date wajib (YYYY-MM-DD)."}), 400

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        # ------------- (A) TOTALS NETT (by pay date) -------------
        # Rule: diskon transaksi dibebankan ke FNB, sisa nett = WS
        cursor.execute(
            """
            WITH fnb_gross AS (
                SELECT dof.id_transaksi,
                       SUM(dof.jumlah * dof.harga_saat_order) AS gross_fnb
                FROM detail_order_fnb dof
                JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY dof.id_transaksi
            ),
            trans_disc AS (
                SELECT t.id_transaksi,
                       t.total_harga_final,
                       GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0) AS disc_trx
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            fnb_net AS (
                SELECT d.id_transaksi,
                       GREATEST(COALESCE(g.gross_fnb,0) - d.disc_trx, 0) AS net_fnb,
                       d.total_harga_final
                FROM trans_disc d
                LEFT JOIN fnb_gross g ON g.id_transaksi = d.id_transaksi
            ),
            ws_net AS (
                SELECT n.id_transaksi,
                       GREATEST(n.total_harga_final - COALESCE(n.net_fnb,0), 0) AS net_ws
                FROM fnb_net n
            )
            SELECT
              (SELECT COALESCE(SUM(net_fnb),0) FROM fnb_net) AS total_fnb,
              (SELECT COALESCE(SUM(net_ws),0)  FROM ws_net ) AS total_ws;
            """,
            (start_date, end_date, start_date, end_date),
        )
        row_tot = cursor.fetchone() or {}
        total_fnb = float(row_tot.get("total_fnb") or 0.0)
        total_ws  = float(row_tot.get("total_ws")  or 0.0)
        total_sales = total_fnb + total_ws

        # ------------- (B) COUNTS: TX FNB (by pay date) & BOOKING WS (by start date) -------------
        cursor.execute(
            """
            SELECT COUNT(DISTINCT dof.id_transaksi) AS tx_fnb
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            """,
            (start_date, end_date),
        )
        tx_fnb = int((cursor.fetchone() or {}).get("tx_fnb", 0))

        cursor.execute(
            """
            SELECT COUNT(DISTINCT br.id_booking) AS book_ws
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            """,
            (start_date, end_date),
        )
        book_ws = int((cursor.fetchone() or {}).get("book_ws", 0))

        total_units = tx_fnb + book_ws  # inilah “trafik” versi laporan

        # ------------- (C) TOTAL PENGUNJUNG: FNB + WS (tanpa dedup lintas channel) -------------
        # FNB: distinct person di tanggal BAYAR
        cursor.execute(
            """
            SELECT COUNT(DISTINCT COALESCE(CAST(t.id_user AS CHAR), NULLIF(t.nama_guest,''), CONCAT('TX#', t.id_transaksi))) AS c
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            """,
            (start_date, end_date),
        )
        visitors_fnb = int((cursor.fetchone() or {}).get("c", 0))

        # WS: distinct person di tanggal PAKAI (waktu_mulai)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT COALESCE(CAST(t.id_user AS CHAR), NULLIF(t.nama_guest,''), CONCAT('TX#', t.id_transaksi))) AS c
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            """,
            (start_date, end_date),
        )
        visitors_ws = int((cursor.fetchone() or {}).get("c", 0))

        # kalau suatu orang melakukan FNB & WS di periode yang sama, dia terhitung 2 (sesuai permintaan)
        total_visitors_sum = visitors_fnb + visitors_ws

        # opsional: angka unik gabungan (kalau suatu saat mau ditampilkan)
        cursor.execute(
            """
            WITH fnb_vis AS (
              SELECT COALESCE(CAST(t.id_user AS CHAR), NULLIF(t.nama_guest,''), CONCAT('TX#', t.id_transaksi)) AS vid
              FROM detail_order_fnb dof
              JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            ws_vis AS (
              SELECT COALESCE(CAST(t.id_user AS CHAR), NULLIF(t.nama_guest,''), CONCAT('TX#', t.id_transaksi)) AS vid
              FROM booking_ruangan br
              JOIN transaksi t ON t.id_transaksi = br.id_transaksi
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            )
            SELECT COUNT(DISTINCT vid) AS c FROM (
              SELECT vid FROM fnb_vis
              UNION ALL
              SELECT vid FROM ws_vis
            ) u;
            """,
            (start_date, end_date, start_date, end_date),
        )
        total_visitors_unique = int((cursor.fetchone() or {}).get("c", 0))

        total_days = max((end_date - start_date).days + 1, 1)
        totals = {
            "total_fnb": total_fnb,
            "total_ws": total_ws,
            "total_sales": total_sales,
            "total_transactions": total_units,   
            "total_visitors": total_visitors_sum,
            "visitors_fnb": visitors_fnb,
            "visitors_ws": visitors_ws,
            "total_visitors_unique": total_visitors_unique,
            "avg_daily": (total_sales / total_days) if total_days else 0.0,
            "total_days": total_days,
        }

        # ------------- (D) DAILY SALES NETT (by pay date) -------------
        cursor.execute(
            """
            WITH fnb_gross AS (
                SELECT dof.id_transaksi,
                       SUM(dof.jumlah * dof.harga_saat_order) AS gross_fnb
                FROM detail_order_fnb dof
                JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY dof.id_transaksi
            ),
            trans_disc AS (
                SELECT t.id_transaksi,
                       DATE(t.tanggal_transaksi) AS trx_date,
                       t.total_harga_final,
                       GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0) AS disc_trx
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas'
                  AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            fnb_net AS (
                SELECT d.id_transaksi, d.trx_date,
                       GREATEST(COALESCE(g.gross_fnb,0) - d.disc_trx, 0) AS net_fnb,
                       d.total_harga_final
                FROM trans_disc d
                LEFT JOIN fnb_gross g ON g.id_transaksi = d.id_transaksi
            ),
            ws_net AS (
                SELECT n.id_transaksi, n.trx_date,
                       GREATEST(n.total_harga_final - COALESCE(n.net_fnb,0), 0) AS net_ws
                FROM fnb_net n
            ),
            days AS (
              SELECT DATE(%s) AS d UNION ALL SELECT DATE(%s)
            )
            SELECT x.trx_date AS tanggal,
                   COALESCE(f.fnb,0) AS fnb,
                   COALESCE(w.ws,0)  AS ws
            FROM (
              SELECT trx_date FROM trans_disc GROUP BY trx_date
            ) x
            LEFT JOIN (SELECT trx_date, SUM(net_fnb) AS fnb FROM fnb_net GROUP BY trx_date) f
                   ON f.trx_date = x.trx_date
            LEFT JOIN (SELECT trx_date, SUM(net_ws)  AS ws  FROM ws_net  GROUP BY trx_date) w
                   ON w.trx_date = x.trx_date
            ORDER BY x.trx_date ASC;
            """,
            (start_date, end_date, start_date, end_date, start_date, end_date),
        )
        rows_daily = cursor.fetchall() or []
        fnb_map = {r["tanggal"]: float(r.get("fnb") or 0) for r in rows_daily}
        ws_map  = {r["tanggal"]: float(r.get("ws")  or 0) for r in rows_daily}

        daily_sales = []
        it = start_date
        while it <= end_date:
            f = fnb_map.get(it, 0.0)
            w = ws_map.get(it, 0.0)
            daily_sales.append({"tanggal": it.isoformat(), "fnb": f, "ws": w, "all": f + w})
            it += timedelta(days=1)

        # ------------- (E) TRAFFIC BY HOUR (UNIT) -------------
        # FNB = count distinct id_transaksi by pay hour
        cursor.execute(
            """
            SELECT HOUR(t.tanggal_transaksi) AS hour,
                   COUNT(DISTINCT t.id_transaksi) AS cnt
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY HOUR(t.tanggal_transaksi)
            ORDER BY hour
            """,
            (start_date, end_date),
        )
        rows_fnb_h = cursor.fetchall() or []

        # WS = count distinct id_booking by start hour
        cursor.execute(
            """
            SELECT HOUR(br.waktu_mulai) AS hour,
                   COUNT(DISTINCT br.id_booking) AS cnt
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY HOUR(br.waktu_mulai)
            ORDER BY hour
            """,
            (start_date, end_date),
        )
        rows_ws_h = cursor.fetchall() or []

        OPEN_HOUR, CLOSE_HOUR = 8, 22
        hour_map = {}
        for r in rows_fnb_h:
            h = int(r["hour"])
            if OPEN_HOUR <= h <= CLOSE_HOUR:
                hour_map[h] = hour_map.get(h, 0) + int(r["cnt"] or 0)
        for r in rows_ws_h:
            h = int(r["hour"])
            if OPEN_HOUR <= h <= CLOSE_HOUR:
                hour_map[h] = hour_map.get(h, 0) + int(r["cnt"] or 0)

        visitors_by_hour = [{"hour": h, "count": hour_map[h]} for h in sorted(hour_map.keys())]
        # (Nama field dipertahankan untuk kompatibilitas—isi = unit, bukan unique person.)

        # ------------- (F) TOP 10 FNB (pro-rata diskon per produk) -------------
        q_top_fnb = """
            SELECT 
                pf.nama_produk AS item,
                COALESCE(tn.nama_tenant, 'Tanpa Tenant') AS tenant,
                SUM(dof.jumlah) AS qty,
                SUM(dof.jumlah * dof.harga_saat_order) AS gross,
                SUM(
                    CASE 
                        WHEN tg.trans_gross > 0 THEN
                            (dof.jumlah * dof.harga_saat_order) / tg.trans_gross
                            * GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0)
                        ELSE 0
                    END
                ) AS discount,
                ( SUM(dof.jumlah * dof.harga_saat_order)
                  - SUM(
                      CASE 
                        WHEN tg.trans_gross > 0 THEN
                            (dof.jumlah * dof.harga_saat_order) / tg.trans_gross
                            * GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0)
                        ELSE 0
                      END
                    )
                ) AS nett
            FROM detail_order_fnb dof
            JOIN transaksi t         ON t.id_transaksi = dof.id_transaksi
                                    AND t.status_pembayaran = 'Lunas'
            JOIN produk_fnb pf       ON pf.id_produk = dof.id_produk
            LEFT JOIN kategori_produk kp ON kp.id_kategori = pf.id_kategori
            LEFT JOIN tenants tn     ON tn.id_tenant = kp.id_tenant
            JOIN (
                SELECT dof2.id_transaksi,
                       SUM(dof2.jumlah * dof2.harga_saat_order) AS trans_gross
                FROM detail_order_fnb dof2
                JOIN transaksi t2 ON t2.id_transaksi = dof2.id_transaksi
                WHERE t2.status_pembayaran = 'Lunas'
                  AND DATE(t2.tanggal_transaksi) BETWEEN %s AND %s
                GROUP BY dof2.id_transaksi
            ) tg ON tg.id_transaksi = dof.id_transaksi
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY pf.id_produk, pf.nama_produk, tn.nama_tenant
            ORDER BY qty DESC
            LIMIT 10
        """
        cursor.execute(q_top_fnb, (start_date, end_date, start_date, end_date))
        top_fnb = [
            {
                "item":     r["item"],
                "tenant":   r["tenant"],
                "qty":      float(r["qty"] or 0),
                "total":    float(r["gross"] or 0),  # tampilkan gross sebagai "Total Penjualan"
                "gross":    float(r["gross"] or 0),
                "discount": float(r["discount"] or 0),
                "nett":     float(r["nett"] or 0),
            }
            for r in (cursor.fetchall() or [])
        ]

        # ------------- (G) TOP 5 WORKING SPACE (Kategori - X Jam), alokasi nett WS per booking -------------
        cursor.execute(
            """
            WITH fnb_gross AS (
              SELECT dof.id_transaksi,
                     SUM(dof.jumlah * dof.harga_saat_order) AS gross_fnb
              FROM detail_order_fnb dof
              JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
              GROUP BY dof.id_transaksi
            ),
            trans_disc AS (
              SELECT t.id_transaksi, t.total_harga_final,
                     GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0) AS disc_trx
              FROM transaksi t
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            fnb_net AS (
              SELECT d.id_transaksi,
                     GREATEST(COALESCE(g.gross_fnb,0) - d.disc_trx, 0) AS net_fnb,
                     d.total_harga_final
              FROM trans_disc d
              LEFT JOIN fnb_gross g ON g.id_transaksi = d.id_transaksi
            ),
            ws_net AS (
              SELECT n.id_transaksi,
                     GREATEST(n.total_harga_final - COALESCE(n.net_fnb,0), 0) AS net_ws
              FROM fnb_net n
            ),
            booking_in_range AS (
              SELECT br.id_booking,
                     br.id_transaksi,
                     CONCAT(
                       CASE
                         WHEN kr.nama_kategori LIKE '%Meeting%' THEN 'Meeting Room'
                         ELSE kr.nama_kategori
                       END,
                       ' - ',
                       COALESCE(p.durasi_jam, TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)),
                       ' Jam'
                     ) AS item
              FROM booking_ruangan br
              JOIN transaksi t ON t.id_transaksi = br.id_transaksi
              JOIN ruangan r ON r.id_ruangan = br.id_ruangan
              JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
              LEFT JOIN paket_harga_ruangan p
                ON p.id_ruangan = br.id_ruangan
               AND p.durasi_jam = TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(br.waktu_mulai) BETWEEN %s AND %s
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            per_trx_booking_count AS (
              SELECT id_transaksi, COUNT(*) AS cnt
              FROM booking_in_range
              GROUP BY id_transaksi
            ),
            ws_alloc AS (
              SELECT b.item,
                     CASE WHEN c.cnt > 0 THEN (w.net_ws / c.cnt) ELSE 0 END AS ws_alloc_amt
              FROM booking_in_range b
              JOIN per_trx_booking_count c ON c.id_transaksi = b.id_transaksi
              JOIN ws_net w ON w.id_transaksi = b.id_transaksi
            )
            SELECT item, COUNT(*) AS qty, COALESCE(SUM(ws_alloc_amt), 0) AS total
            FROM ws_alloc
            GROUP BY item
            ORDER BY qty DESC, total DESC
            LIMIT 5;
            """,
            (start_date, end_date, start_date, end_date,  # untuk fnb_gross/trans_disc
             start_date, end_date,                         # pemakaian (waktu_mulai)
             start_date, end_date)                         # tanggal bayar (konsistensi nett)
        )
        top_ws = [
            {"item": r["item"], "qty": int(r["qty"] or 0), "total": float(r["total"] or 0)}
            for r in (cursor.fetchall() or [])
        ]

        return jsonify(
            {
                "message": "OK",
                "datas": {
                    "totals": totals,
                    "daily_sales": daily_sales,
                    "visitors_by_hour": visitors_by_hour,  # ini = unit/jam (FNB tx + WS booking)
                    "top_fnb": top_fnb,
                    "top_ws": top_ws,
                },
            }
        ), 200

    except Exception as e:
        print("[dashboard_summary] error:", e)
        import traceback; traceback.print_exc()
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            try:
                connection.close()
            except Exception:
                pass

# ============================================================
# 2) OWNER FNB DASHBOARD  (GET /ownerfnb)
# ============================================================
@owner_endpoints.route("/ownerfnb", methods=["GET", "OPTIONS"])
def ownerfnb_dashboard():
    # Preflight (CORS)
    if request.method == "OPTIONS":
        return ("", 204)

    # Ambil parameter & validasi tanggal
    start_date_raw = request.args.get("start_date")
    end_date_raw = request.args.get("end_date")
    start_date = _parse_date(start_date_raw)
    end_date = _parse_date(end_date_raw)
    if not start_date or not end_date:
        return _bad_request("start_date & end_date wajib (YYYY-MM-DD atau DD-MM-YYYY).")

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # ---------- 1) TOTALS (FNB saja) ----------
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
        total_fnb = int(tr.get("total_fnb") or 0)
        total_tx = int(tr.get("total_transactions") or 0)
        total_days = int(tr.get("total_days") or 1)
        avg_daily = round(total_fnb / max(1, total_days))

        # ---------- 2) DAILY SELLING PER TENANT ----------
        daily_sql = """
            SELECT
                DATE(t.tanggal_transaksi) AS tanggal,
                kp.id_tenant,
                SUM(dof.jumlah * dof.harga_saat_order) AS total_harian
            FROM detail_order_fnb dof
            JOIN transaksi t   ON t.id_transaksi = dof.id_transaksi
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
            key = r["tanggal"].isoformat() if hasattr(r["tanggal"], "isoformat") else str(r["tanggal"])
            if key not in daily_map:
                daily_map[key] = {"tanggal": key, "dapoerms": 0, "homebro": 0}
            if int(r["id_tenant"]) == TENANT_DAPOER_MS:
                daily_map[key]["dapoerms"] = int(r["total_harian"] or 0)
            elif int(r["id_tenant"]) == TENANT_HOME_BRO:
                daily_map[key]["homebro"] = int(r["total_harian"] or 0)
        daily_selling = sorted(daily_map.values(), key=lambda x: x["tanggal"])

        # ---------- 3) VISITORS BY HOUR (trafik kunjungan) ----------
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
        visitors_by_hour = [
            {"hour": int(r["hour"]), "count": int(r["cnt"])}
            for r in (cur.fetchall() or [])
        ]

        # ---------- 4) PEAK HOURS (banyak menu dipesan per jam) ----------
        peak_sql = """
            SELECT
                HOUR(t.tanggal_transaksi) AS hour,
                SUM(dof.jumlah) AS item_count
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
              AND t.status_pembayaran = 'Lunas'
            GROUP BY hour
            ORDER BY hour;
        """
        cur.execute(peak_sql, (start_date, end_date))
        peak_by_hour = [
            {"hour": int(r["hour"]), "count": int(r["item_count"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # ---------- 5) TOP 5 PRODUCT PER TENANT ----------
        top_sql = """
            SELECT
                pf.nama_produk AS item,
                SUM(dof.jumlah) AS qty,
                SUM(dof.jumlah * dof.harga_saat_order) AS total
            FROM detail_order_fnb dof
            JOIN transaksi t   ON t.id_transaksi = dof.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
              AND t.status_pembayaran = 'Lunas'
              AND kp.id_tenant = %s
            GROUP BY pf.nama_produk
            ORDER BY total DESC
            LIMIT 5;
        """
        # Dapoer M.S
        cur.execute(top_sql, (start_date, end_date, TENANT_DAPOER_MS))
        top_dapoer = [
            {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
            for r in (cur.fetchall() or [])
        ]
        # HomeBro
        cur.execute(top_sql, (start_date, end_date, TENANT_HOME_BRO))
        top_home = [
            {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # ---------- 6) UNPOPULAR PRODUCT PER TENANT (ikutkan yang qty = 0) ----------
        unpopular_sql = """
            SELECT
                pf.nama_produk AS item,
                COALESCE(SUM(dof.jumlah), 0) AS qty,
                COALESCE(SUM(dof.jumlah * dof.harga_saat_order), 0) AS total
            FROM produk_fnb pf
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            LEFT JOIN detail_order_fnb dof ON dof.id_produk = pf.id_produk
            LEFT JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                AND t.status_pembayaran = 'Lunas'
            WHERE kp.id_tenant = %s
            GROUP BY pf.nama_produk
            ORDER BY qty ASC, total ASC, pf.nama_produk ASC
            LIMIT 50
        """
        # Dapoer M.S
        cur.execute(unpopular_sql, (start_date, end_date, TENANT_DAPOER_MS))
        unpop_dapoer = [
            {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
            for r in (cur.fetchall() or [])
        ]
        # HomeBro
        cur.execute(unpopular_sql, (start_date, end_date, TENANT_HOME_BRO))
        unpop_home = [
            {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # ---------- Response ----------
        return jsonify(
            {
                "message": "OK",
                "datas": {
                    "totals": {
                        "total_fnb": total_fnb,
                        "total_ws": 0,
                        "total_sales": total_fnb,
                        "total_transactions": total_tx,
                        "avg_daily": avg_daily,
                        "total_days": total_days,
                    },
                    "daily_selling_per_tenant": daily_selling,
                    "visitors_by_hour": visitors_by_hour,
                    "peak_by_hour": peak_by_hour,
                    "top_fnb": {"dapoer": top_dapoer, "home": top_home},
                    "unpopular_fnb": {"dapoer": unpop_dapoer, "home": unpop_home},
                },
            }
        ), 200

    except Exception as e:
        print("ownerfnb_dashboard error:", e)
        return jsonify({"message": "Error", "error": str(e)}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
# ============================================================