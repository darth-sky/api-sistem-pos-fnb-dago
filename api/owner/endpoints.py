# owner_endpoints.py
import decimal
import traceback
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from helper.db_helper import get_connection
from datetime import date, datetime, timedelta  # <-- tambahkan date

owner_endpoints = Blueprint('owner_endpoints', __name__)

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

# ------------- (F) PAYMENT BREAKDOWN (Tunai & Non-Tunai) ----------
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
                    t.metode_pembayaran,
                    t.total_harga_final,
                    GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0) AS disc_trx
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ),
            fnb_net AS (
                SELECT d.id_transaksi,
                    d.metode_pembayaran,
                    GREATEST(COALESCE(g.gross_fnb,0) - d.disc_trx, 0) AS net_fnb
                FROM trans_disc d
                LEFT JOIN fnb_gross g ON g.id_transaksi = d.id_transaksi
            ),
            ws_net AS (
                SELECT n.id_transaksi,
                    n.metode_pembayaran,
                    GREATEST(n.total_harga_final - COALESCE(nf.net_fnb,0), 0) AS net_ws
                FROM trans_disc n
                LEFT JOIN fnb_net nf ON nf.id_transaksi = n.id_transaksi
            )
            SELECT metode_pembayaran, SUM(net_fnb) AS fnb, 0 AS ws
            FROM fnb_net
            GROUP BY metode_pembayaran

            UNION ALL

            SELECT metode_pembayaran, 0 AS fnb, SUM(net_ws) AS ws
            FROM ws_net
            GROUP BY metode_pembayaran
            """,
            (start_date, end_date, start_date, end_date)
        )

        rows = cursor.fetchall() or []

        # 1️⃣ Inisialisasi payment breakdown
        payment_breakdown = {
            "tunai": 0.0,
            "non_tunai": 0.0,
            "fnb": 0.0,
            "ws": 0.0,
        }

        # 2️⃣ Proses data SQL → hitung tunai / non tunai
        for r in rows:
            method = (r["metode_pembayaran"] or "Non Tunai").lower()
            fnb = float(r["fnb"] or 0)
            ws  = float(r["ws"] or 0)

            payment_breakdown["fnb"] += fnb
            payment_breakdown["ws"] += ws

            if method in ["tunai", "cash"]:
                payment_breakdown["tunai"] += fnb + ws
            else:
                payment_breakdown["non_tunai"] += fnb + ws

        # 3️⃣ Hitung total keseluruhan
        payment_breakdown["grand_total"] = (
            payment_breakdown["tunai"] + payment_breakdown["non_tunai"]
        )

        # 4️⃣ Convert ke ARRAY untuk frontend
        payment_array = [
            { "method": "Tunai", "total": payment_breakdown["tunai"] },
            { "method": "Non Tunai", "total": payment_breakdown["non_tunai"] }
        ]


        # ------------- (G) TOP 10 FNB (pro-rata diskon per produk) -------------
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

        # ------------- (H) TOP 5 WORKING SPACE (Kategori - X Jam), alokasi nett WS per booking -------------
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

        # ------------- (NEW) KONTRIBUSI TENANT FNB (nett per tenant) -------------
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
                        GREATEST(COALESCE(g.gross_fnb,0) - d.disc_trx, 0) AS net_fnb
                  FROM trans_disc d
                  LEFT JOIN fnb_gross g ON g.id_transaksi = d.id_transaksi
              )
              SELECT 
                  COALESCE(tn.nama_tenant, 'Tanpa Tenant') AS tenant,
                  SUM(fn.net_fnb) AS nett
              FROM fnb_net fn
              JOIN detail_order_fnb dof ON dof.id_transaksi = fn.id_transaksi
              JOIN produk_fnb pf ON pf.id_produk = dof.id_produk
              LEFT JOIN kategori_produk kp ON kp.id_kategori = pf.id_kategori
              LEFT JOIN tenants tn ON tn.id_tenant = kp.id_tenant
              GROUP BY tenant
              ORDER BY nett DESC;
              """,
              (start_date, end_date, start_date, end_date)
          )

        tenant_contribution = [
              {"tenant": r["tenant"], "nett": float(r["nett"] or 0)}
              for r in (cursor.fetchall() or [])
          ]

          # Tambah Working Space sebagai satu row tersendiri
        tenant_contribution.append({
        "tenant": "Working Space",
        "nett": totals["total_ws"]
          })


        return jsonify(
            {
                "message": "OK",
                "datas": {
                    "totals": totals,
                    "daily_sales": daily_sales,
                    "visitors_by_hour": visitors_by_hour,  # ini = unit/jam (FNB tx + WS booking)
                    "top_fnb": top_fnb,
                    "top_ws": top_ws,
                    "payment_breakdown": payment_array,
                    "tenant_contribution": tenant_contribution,
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
    #  🔰 TRANSACTION LIST  (Sheet 1)
    # ============================================================
    @owner_endpoints.route("/transaction", methods=["GET"])
    def transaction_sheet():
        start_date = request.args.get("start_date")
        end_date   = request.args.get("end_date")

        s = _parse_date(start_date)
        e = _parse_date(end_date)
        if not s or not e:
            return _bad_request("start_date & end_date wajib")

        conn = None
        cur  = None
        try:
            conn = get_connection()
            cur = conn.cursor(dictionary=True)

            cur.execute("""
                SELECT 
                    t.id_transaksi,
                    DATE(t.tanggal_transaksi) AS tanggal,
                    TIME(t.tanggal_transaksi) AS waktu,
                    t.metode_pembayaran,
                    t.total_harga_final,
                    t.subtotal,
                    t.pajak_nominal,
                    t.status_pembayaran,
                    t.nama_guest,
                    t.fnb_type,
                    t.booking_source
                FROM transaksi t
                WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                ORDER BY t.tanggal_transaksi ASC
            """, (s, e))

            rows = cur.fetchall() or []

            return jsonify({"message":"OK", "datas": rows}), 200

        except Exception as e:
            print("transaction_sheet error:", e)
            return jsonify({"message":"Error","error":str(e)}), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()

    # ============================================================
    #  🔰 TRANSACTION DETAIL  (Sheet 2)
    # ============================================================
    @owner_endpoints.route("/transaction/detail", methods=["GET"])
    def transaction_detail_sheet():
        id_transaksi = request.args.get("id_transaksi")
        if not id_transaksi:
            return _bad_request("id_transaksi wajib")

        conn = None
        cur  = None
        try:
            conn = get_connection()
            cur  = conn.cursor(dictionary=True)

            # ============================
            #  DETAIL FNB
            # ============================
            cur.execute("""
                SELECT 
                    dof.id_detail_order,
                    pf.nama_produk,
                    dof.jumlah,
                    dof.harga_saat_order,
                    (dof.jumlah * dof.harga_saat_order) AS subtotal
                FROM detail_order_fnb dof
                JOIN produk_fnb pf ON pf.id_produk = dof.id_produk
                WHERE dof.id_transaksi = %s
            """, (id_transaksi,))
            fnb_detail = cur.fetchall() or []

            # ============================
            #  DETAIL WORKING SPACE
            # ============================
            cur.execute("""
                SELECT 
                    br.id_booking,
                    r.nama_ruangan,
                    br.waktu_mulai,
                    br.waktu_selesai,
                    TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam,
                FROM booking_ruangan br
                JOIN ruangan r ON r.id_ruangan = br.id_ruangan
                WHERE br.id_transaksi = %s
            """, (id_transaksi,))
            ws_detail = cur.fetchall() or []

            return jsonify({
                "message": "OK",
                "datas": {
                    "fnb": fnb_detail,
                    "ws": ws_detail
                }
            }), 200

        except Exception as e:
            print("transaction_detail_sheet error:", e)
            return jsonify({"message":"Error","error":str(e)}), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()

# ============================================================
# 2) OWNER FNB DASHBOARD  (GET /ownerfnb)
# ============================================================

TENANT_COLORS = ["#2563eb", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6"]

@owner_endpoints.route("/ownerfnb", methods=["GET", "OPTIONS"])
def ownerfnb_dashboard():
    if request.method == "OPTIONS":
        return ("", 204)

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

        # Ambil tenant aktif
        cur.execute("""
            SELECT id_tenant, nama_tenant 
            FROM tenants 
            WHERE status_tenant = 'Active'
            ORDER BY id_tenant
        """)
        tenants = cur.fetchall() or []

        tenant_info = []
        for i, t in enumerate(tenants):
            tenant_info.append({
                "id": t["id_tenant"],
                "name": t["nama_tenant"],
                "color": TENANT_COLORS[i % len(TENANT_COLORS)]
            })

        tenant_ids = [t["id"] for t in tenant_info]
        if not tenant_ids:
            return jsonify({
                "message": "OK",
                "datas": {
                    "totals": {"total_fnb": 0, "total_ws": 0, "total_sales": 0,
                               "total_transactions": 0, "avg_daily": 0, "total_days": 1},
                    "tenant_info": [],
                    "daily_selling_per_tenant": {},
                    "visitors_by_hour": [],
                    "peak_by_hour": [],
                    "payment_breakdown": [],
                    "top_fnb": {},
                    "unpopular_fnb": {},
                }
            }), 200

        placeholders = ", ".join(["%s"] * len(tenant_ids))

        # ==============================================================
        #  1) TOTALS – versi pajak & diskon (nett)
        # ==============================================================
        totals_sql = f"""
            WITH fnb_trx AS (
                SELECT DISTINCT t.id_transaksi
                FROM transaksi t
                JOIN detail_order_fnb dof ON dof.id_transaksi = t.id_transaksi
                JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                AND t.status_pembayaran = 'Lunas'
                AND kp.id_tenant IN ({placeholders})
            )
            SELECT
                -- Gross FNB
                COALESCE((
                    SELECT SUM(dof.jumlah * dof.harga_saat_order)
                    FROM detail_order_fnb dof
                    JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
                    JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
                    JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
                    WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
                    AND kp.id_tenant IN ({placeholders})
                    AND t.status_pembayaran = 'Lunas'
                ),0) AS gross_fnb,

                -- Pajak
                COALESCE((
                    SELECT SUM(t.pajak_nominal)
                    FROM transaksi t
                    JOIN fnb_trx ft ON ft.id_transaksi = t.id_transaksi
                ),0) AS total_tax,

                -- Diskon
                COALESCE((
                    SELECT SUM(GREATEST((t.subtotal + t.pajak_nominal) - t.total_harga_final, 0))
                    FROM transaksi t
                    JOIN fnb_trx ft ON ft.id_transaksi = t.id_transaksi
                ),0) AS total_discount,

                -- NETT
                COALESCE((
                    SELECT SUM(t.total_harga_final)
                    FROM transaksi t
                    JOIN fnb_trx ft ON ft.id_transaksi = t.id_transaksi
                ),0) AS total_nett,

                -- Jumlah Transaksi
                (SELECT COUNT(*) FROM fnb_trx) AS total_transactions,

                DATEDIFF(%s, %s) + 1 AS total_days
        """

        cur.execute(
            totals_sql,
            (
                start_date, end_date, *tenant_ids,     # untuk fnb_trx
                start_date, end_date, *tenant_ids,     # untuk gross
                end_date, start_date                   # total_days
            )
        )

        totals = cur.fetchone() or {}
        gross_fnb = int(totals["gross_fnb"] or 0)
        total_tax = int(totals["total_tax"] or 0)
        total_discount = int(totals["total_discount"] or 0)
        total_nett = int(totals["total_nett"] or 0)
        total_tx = int(totals["total_transactions"] or 0)
        total_days = int(totals["total_days"] or 1)
        avg_daily = round(total_nett / max(1, total_days))

        # ==============================================================
        # 2) DAILY SELLING PER TENANT (masih gross seperti sebelumnya)
        # ==============================================================

        daily_sql = f"""
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
            AND kp.id_tenant IN ({placeholders})
            GROUP BY tanggal, kp.id_tenant
            ORDER BY tanggal ASC;
        """

        cur.execute(daily_sql, (start_date, end_date, *tenant_ids))
        rows = cur.fetchall() or []

        daily_map = {}
        for r in rows:
            tgl = r["tanggal"].isoformat()
            if tgl not in daily_map:
                daily_map[tgl] = {}
            daily_map[tgl][str(r["id_tenant"])] = int(r["total_harian"] or 0)

        # ==============================================================
        # 3) VISITORS BY HOUR
        # ==============================================================
        visitors_sql = f"""
            SELECT HOUR(t.tanggal_transaksi) AS hour,
                   COUNT(DISTINCT t.id_transaksi) AS cnt
            FROM transaksi t
            JOIN detail_order_fnb dof ON dof.id_transaksi = t.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            AND kp.id_tenant IN ({placeholders})
            GROUP BY hour
            ORDER BY hour
        """
        cur.execute(visitors_sql, (start_date, end_date, *tenant_ids))
        visitors = [{"hour": int(r["hour"]), "count": int(r["cnt"])} for r in cur.fetchall() or []]

        # ==============================================================
        # 4) PEAK ITEM BY HOUR
        # ==============================================================
        peak_sql = f"""
            SELECT HOUR(t.tanggal_transaksi) AS hour,
                   SUM(dof.jumlah) AS item_count
            FROM detail_order_fnb dof
            JOIN transaksi t ON t.id_transaksi = dof.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            AND kp.id_tenant IN ({placeholders})
            GROUP BY hour
            ORDER BY hour
        """
        cur.execute(peak_sql, (start_date, end_date, *tenant_ids))
        peak = [{"hour": int(r["hour"]), "count": int(r["item_count"] or 0)} for r in cur.fetchall() or []]

        # ==============================================================
        # 5) PAYMENT BREAKDOWN (NETT)
        # ==============================================================
        payment_sql = f"""
            SELECT t.metode_pembayaran AS method,
                   SUM(t.total_harga_final) AS total
            FROM transaksi t
            JOIN detail_order_fnb dof ON dof.id_transaksi = t.id_transaksi
            JOIN produk_fnb pf ON dof.id_produk = pf.id_produk
            JOIN kategori_produk kp ON pf.id_kategori = kp.id_kategori
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            AND kp.id_tenant IN ({placeholders})
            GROUP BY t.metode_pembayaran
            ORDER BY total DESC
        """

        cur.execute(payment_sql, (start_date, end_date, *tenant_ids))
        payment_breakdown = [
            {"method": r["method"] or "Lainnya", "total": int(r["total"] or 0)}
            for r in cur.fetchall() or []
        ]

        # ==============================================================
        # 6) TOP & UNPOPULAR – masih versi gross (seperti sebelumnya)
        # ==============================================================

        top_sql = """
            SELECT pf.nama_produk AS item,
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
            ORDER BY qty DESC, total DESC
            LIMIT 5;
        """

        unpop_sql = """
            SELECT pf.nama_produk AS item,
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
            LIMIT 50;
        """

        top_map = {}
        unpop_map = {}

        for tid in tenant_ids:
            cur.execute(top_sql, (start_date, end_date, tid))
            top_map[str(tid)] = [
                {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
                for r in cur.fetchall() or []
            ]

            cur.execute(unpop_sql, (start_date, end_date, tid))
            unpop_map[str(tid)] = [
                {"item": r["item"], "qty": int(r["qty"] or 0), "total": int(r["total"] or 0)}
                for r in cur.fetchall() or []
            ]

        # ==============================================================
        # RESPONSE FINAL
        # ==============================================================

        return jsonify({
            "message": "OK",
            "datas": {
                "totals": {
                    "gross_fnb": gross_fnb,
                    "total_tax": total_tax,
                    "total_discount": total_discount,
                    "total_nett": total_nett,
                    "total_sales": total_nett,
                    "total_transactions": total_tx,
                    "avg_daily": avg_daily,
                    "total_days": total_days,
                },
                "tenant_info": tenant_info,
                "daily_selling_per_tenant": daily_map,
                "visitors_by_hour": visitors,
                "peak_by_hour": peak,
                "payment_breakdown": payment_breakdown,
                "top_fnb": top_map,
                "unpopular_fnb": unpop_map
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

# ============================================================
# 3) WS DASHBOARD — FINAL FIXED VERSION
# ============================================================
@owner_endpoints.route('/ws-dashboard-data', methods=['GET', 'OPTIONS'])
def ws_dashboard_data():
    """
    Data untuk Working Space Dashboard:
    - stats: totalRevenue, totalBookings, totalVisitors
    - dailyRevenue: labels ['1'..'N'], labelsPretty ['1 Okt',...], datasets -> amount per kategori/hari
    - categoryContribution: [{name, value}]
    - packageByDuration: [{durasi_jam, total_booking, total_user, total_revenue}]
    - packageByDurationByCategory: { "Open Space":[...], "Space Monitor":[...], "Meeting Room":[...] }
    - hourlyBookings: total per jam (start-only, hanya jam dengan transaksi)
    - hourlyBookingsByCategory: breakdown kategori per jam
    - hourlyBookingsByCategoryAndDuration: breakdown kategori+durasi per jam
    - top_ws: Top 5 ruang (kategori - X Jam)
    """
    # Preflight CORS (opsional jika pakai flask-cors global)
    if request.method == "OPTIONS":
        return ("", 204, {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        })

    conn = None
    cur = None
    try:
        # default: bulan berjalan
        today = date.today()
        start_date_str = request.args.get('startDate', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date_str   = request.args.get('endDate',   today.strftime('%Y-%m-%d'))
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        if end_date < start_date:
            return jsonify({"message": "ERROR", "error": "endDate < startDate"}), 400

        OPEN_HOUR, CLOSE_HOUR = 8, 22
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT
              COALESCE(SUM(t.total_harga_final), 0)                                   AS totalRevenue,
              
              -- TAMBAHKAN BARIS INI (Mengambil total diskon nominal)
              COALESCE(SUM(t.discount_nominal), 0)                                    AS totalDiscount, 
              
              COUNT(br.id_booking)                                                    AS totalBookings,
              COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR)))         AS totalVisitors
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        
        s = cur.fetchone() or {}
        
        stats = {
            "totalRevenue": int(s.get("totalRevenue") or 0),
            
            # TAMBAHKAN BARIS INI KE DALAM OBJECT STATS
            "totalDiscount": int(s.get("totalDiscount") or 0),
            
            "totalBookings": int(s.get("totalBookings") or 0),
            "totalVisitors": int(s.get("totalVisitors") or 0),
        }

        # ---------- 2) DAILY BOOKING/REVENUE PER KATEGORI ----------
        days_count = (end_date - start_date).days + 1
        all_dates = [start_date + timedelta(days=i) for i in range(days_count)]
        pos_map = {d.strftime('%Y-%m-%d'): i for i, d in enumerate(all_dates)}
        labels_days   = [str(d.day) for d in all_dates]
        labels_pretty = [f"{int(d.strftime('%d'))} {d.strftime('%b')}" for d in all_dates]

        categories = ["Open Space", "Space Monitor", "Room Meeting Besar", "Room Meeting Kecil"]
        dataset_map_counts = {k: [0]*days_count for k in categories}

        cur.execute("""
            SELECT
              DATE(br.waktu_mulai) AS period_date,
              kr.nama_kategori     AS category,
              SUM(t.total_harga_final) AS amt
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
                dataset_map_counts[cat][idx] = int(row["amt"] or 0)

        dailyRevenue = {"labels": labels_days, "labelsPretty": labels_pretty, "datasets": dataset_map_counts}

        # ---------- 3) CATEGORY CONTRIBUTION ----------
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

        # ---------- 3B) PRODUCT CONTRIBUTION ----------
        cur.execute("""
            SELECT COALESCE(SUM(t.total_harga_final), 0) AS total
            FROM memberships m
            JOIN transaksi t ON t.id_transaksi = m.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        membershipRevenue = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute("""
            SELECT COALESCE(SUM(t.total_harga_final), 0) AS total
            FROM client_virtual_office vo
            JOIN transaksi t ON t.id_transaksi = vo.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        voRevenue = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute("""
            SELECT COALESCE(SUM(t.total_harga_final), 0) AS total
            FROM transaksi t
            WHERE t.status_pembayaran = 'Lunas'
            AND (
                LOWER(t.booking_source) LIKE '%private%' 
                OR LOWER(t.booking_source) LIKE '%office%'
            )
            AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        poRevenue = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute("""
            SELECT COALESCE(SUM(t.total_harga_final), 0) AS total
            FROM booking_event be
            JOIN transaksi t ON t.id_transaksi = be.id_transaksi
            WHERE t.status_pembayaran = 'Lunas'
            AND DATE(be.tanggal_event) BETWEEN %s AND %s
        """, (start_date_str, end_date_str))
        eventRevenue = int((cur.fetchone() or {}).get("total") or 0)

        productContribution = [
            {"name": "Membership", "value": membershipRevenue},
            {"name": "Virtual Office", "value": voRevenue},
            {"name": "Private Office", "value": poRevenue},
            {"name": "Event Space", "value": eventRevenue},
        ]


        # ================================================
        # 4) TRAFIK BOOKING PER DURASI (FLEKSIBEL)
        # ================================================

        # 4A: ambil durasi unik dari booking, bukan dari paket
        cur.execute("""
            SELECT DISTINCT 
                TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE DATE(br.waktu_mulai) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            ORDER BY durasi_jam ASC
        """, (start_date_str, end_date_str))

        durations = [int(r["durasi_jam"]) for r in cur.fetchall() or []]

        # 4B: agregasi trafik booking per durasi (cash + kredit)
        cur.execute("""
            SELECT
                TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam,
                COUNT(*) AS total_booking,
                COUNT(DISTINCT COALESCE(t.nama_guest, CAST(t.id_user AS CHAR))) AS total_user,
                SUM(t.total_harga_final) AS total_revenue
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            WHERE DATE(br.waktu_mulai) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            GROUP BY durasi_jam
            ORDER BY durasi_jam ASC
        """, (start_date_str, end_date_str))

        agg = {int(r["durasi_jam"]): r for r in cur.fetchall() or []}

        packageByDuration = [{
            "durasi_jam": dj,
            "total_booking": int(agg.get(dj, {}).get("total_booking", 0)),
            "total_user": int(agg.get(dj, {}).get("total_user", 0)),
            "total_revenue": int(agg.get(dj, {}).get("total_revenue", 0)), # revenue cash, kredit = 0
        } for dj in durations]

        # ================================================
        # 4C) TRAFIK BOOKING PER DURASI PER KATEGORI (FLEKSIBEL)
        # ================================================

        cur.execute("""
            SELECT
                CASE
                    WHEN kr.nama_kategori IN ('Room Meeting Besar','Room Meeting Kecil')
                        THEN 'Meeting Room'
                    ELSE kr.nama_kategori
                END AS category,
                TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam,
                COUNT(*) AS total_booking
            FROM booking_ruangan br
            JOIN transaksi t ON t.id_transaksi = br.id_transaksi
            JOIN ruangan r ON r.id_ruangan = br.id_ruangan
            JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE DATE(br.waktu_mulai) BETWEEN %s AND %s
            AND t.status_pembayaran = 'Lunas'
            GROUP BY category, durasi_jam
            ORDER BY durasi_jam ASC
        """, (start_date_str, end_date_str))

        rows_cat = cur.fetchall() or []

        packageByDurationByCategory = {
            "Open Space": [],
            "Space Monitor": [],
            "Meeting Room": []
        }

        for cat in packageByDurationByCategory.keys():
            map_cat = {
                int(r["durasi_jam"]): int(r["total_booking"])
                for r in rows_cat if r["category"] == cat
            }
            packageByDurationByCategory[cat] = [
                {"durasi_jam": dj, "total_booking": map_cat.get(dj, 0)}
                for dj in durations
            ]

        # ---------- 5) HOURLY BOOKINGS (BY CATEGORY + DURATION) ----------
        cur.execute("""
          SELECT
            CASE
              WHEN kr.nama_kategori IN ('Room Meeting Besar','Room Meeting Kecil') THEN 'Meeting Room'
              ELSE kr.nama_kategori
            END AS category,
            HOUR(br.waktu_mulai) AS hh,
            TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam,
            COUNT(*) AS cnt
          FROM booking_ruangan br
          JOIN transaksi t         ON t.id_transaksi = br.id_transaksi
          JOIN ruangan r           ON r.id_ruangan = br.id_ruangan
          JOIN kategori_ruangan kr ON kr.id_kategori_ruangan = r.id_kategori_ruangan
          WHERE t.status_pembayaran = 'Lunas'
            AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            AND HOUR(br.waktu_mulai) BETWEEN %s AND %s
          GROUP BY category, hh, durasi_jam
          HAVING cnt > 0
          ORDER BY hh
        """, (start_date_str, end_date_str, OPEN_HOUR, CLOSE_HOUR))
        rows_h = cur.fetchall() or []

        hourlyBookingsByCategory = {}
        hourlyBookingsByCategoryAndDuration = {}
        for r in rows_h:
          hh  = str(int(r["hh"]))
          cat = r["category"]
          dur = str(int(r["durasi_jam"] or 0))
          cnt = int(r["cnt"] or 0)

          cat_map = hourlyBookingsByCategory.setdefault(hh, {"Open Space": 0, "Space Monitor": 0, "Meeting Room": 0})
          cat_map[cat] += cnt

          dur_map = hourlyBookingsByCategoryAndDuration.setdefault(hh, {"Open Space": {}, "Space Monitor": {}, "Meeting Room": {}})
          dur_map[cat][dur] = dur_map[cat].get(dur, 0) + cnt

        hourlyBookings = {hh: sum(cat_map.values()) for hh, cat_map in hourlyBookingsByCategory.items()}

        # ---------- 5B) POPULAR SPACE ----------
        cur.execute(
            """
            SELECT 
              CONCAT(
                CASE 
                  WHEN kr.nama_kategori LIKE '%Meeting%' THEN 'Meeting Room'
                  ELSE kr.nama_kategori
                END,
                ' ( ',
                COALESCE(p.durasi_jam, TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)),
                ' Jam)'
              ) AS item,
              COUNT(*) AS qty,
              SUM(x.total_transaksi) AS total
            FROM booking_ruangan br
            JOIN ruangan r            ON r.id_ruangan = br.id_ruangan
            JOIN kategori_ruangan kr  ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            JOIN (
              SELECT t.id_transaksi, MAX(t.total_harga_final) AS total_transaksi
              FROM transaksi t
              WHERE t.status_pembayaran = 'Lunas'
                AND DATE(t.tanggal_transaksi) BETWEEN %s AND %s
              GROUP BY t.id_transaksi
            ) x ON x.id_transaksi = br.id_transaksi
            LEFT JOIN paket_harga_ruangan p
              ON p.id_ruangan = br.id_ruangan
             AND p.durasi_jam = TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)
            WHERE DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY item
            ORDER BY qty DESC, total DESC
            LIMIT 5
            """,
            (start_date_str, end_date_str, start_date_str, end_date_str),
        )
        top_ws = [{"item": r["item"], "qty": int(r["qty"] or 0), "total": float(r["total"] or 0)} for r in (cur.fetchall() or [])]

        # ---------- 7) CATEGORY PERFORMANCE ----------
        cur.execute("""
          SELECT
            CASE
              WHEN kr.nama_kategori IN ('Room Meeting Besar','Room Meeting Kecil') THEN 'Meeting Room'
              ELSE kr.nama_kategori
            END AS category,
            COUNT(*) AS bookings,
            SUM(t.total_harga_final) AS revenue,
            AVG(TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai)) AS avg_duration_jam
          FROM booking_ruangan br
          JOIN transaksi t            ON t.id_transaksi = br.id_transaksi
          JOIN ruangan r              ON r.id_ruangan = br.id_ruangan
          JOIN kategori_ruangan kr    ON kr.id_kategori_ruangan = r.id_kategori_ruangan
          WHERE t.status_pembayaran = 'Lunas'
            AND DATE(br.waktu_mulai) BETWEEN %s AND %s
          GROUP BY category
        """, (start_date_str, end_date_str))
        categoryPerformance = [
          {
            "category": r["category"],
            "bookings": int(r["bookings"] or 0),
            "revenue": int(r["revenue"] or 0),
            "avg_duration_jam": float(r["avg_duration_jam"] or 0.0),
          }
          for r in (cur.fetchall() or [])
        ]

        # ---------- 8) BOOKINGS BY WEEKDAY ----------
        cur.execute("""
          SELECT WEEKDAY(br.waktu_mulai) AS wday, COUNT(*) AS cnt
          FROM booking_ruangan br
          JOIN transaksi t ON t.id_transaksi = br.id_transaksi
          WHERE t.status_pembayaran = 'Lunas'
            AND DATE(br.waktu_mulai) BETWEEN %s AND %s
          GROUP BY wday
          ORDER BY wday
        """, (start_date_str, end_date_str))
        rows_weekday = cur.fetchall() or []
        weekday_map = {int(r["wday"]): int(r["cnt"]) for r in rows_weekday}
        bookingsByWeekday = [{"wday": i, "count": weekday_map.get(i, 0)} for i in range(7)]

        # ---------- 9) BOOKINGS BY DATE DETAILED ----------
        cur.execute("""
            SELECT
              DATE(br.waktu_mulai) AS book_date,
              CASE
                WHEN kr.nama_kategori IN ('Room Meeting Besar','Room Meeting Kecil') THEN 'Meeting Room'
                ELSE kr.nama_kategori
              END AS category,
              TIMESTAMPDIFF(HOUR, br.waktu_mulai, br.waktu_selesai) AS durasi_jam,
              COUNT(*) AS cnt
            FROM booking_ruangan br
            JOIN transaksi t            ON t.id_transaksi = br.id_transaksi
            JOIN ruangan r              ON r.id_ruangan = br.id_ruangan
            JOIN kategori_ruangan kr    ON kr.id_kategori_ruangan = r.id_kategori_ruangan
            WHERE t.status_pembayaran = 'Lunas'
              AND DATE(br.waktu_mulai) BETWEEN %s AND %s
            GROUP BY book_date, category, durasi_jam
            ORDER BY book_date ASC
        """, (start_date_str, end_date_str))
        rows_detailed = cur.fetchall() or []

        bookingsByDateDetailed = {}
        for r in rows_detailed:
            dstr = r["book_date"].strftime("%Y-%m-%d")
            cat = r["category"]
            dur = int(r["durasi_jam"] or 0)
            cnt = int(r["cnt"] or 0)
            node = bookingsByDateDetailed.setdefault(dstr, {"total": 0, "breakdown": {}})
            node["total"] += cnt
            node["breakdown"].setdefault(cat, {})
            node["breakdown"][cat][str(dur)] = node["breakdown"][cat].get(str(dur), 0) + cnt

        payload = {
            "stats": stats,
            "dailyRevenue": dailyRevenue,
            "categoryContribution": categoryContribution,
            "productContribution": productContribution,
            "packageByDuration": packageByDuration,
            "packageByDurationByCategory": packageByDurationByCategory,
            "hourlyBookings": hourlyBookings,
            "hourlyBookingsByCategory": hourlyBookingsByCategory,
            "hourlyBookingsByCategoryAndDuration": hourlyBookingsByCategoryAndDuration,
            "top_ws": top_ws,
            "categoryPerformance": categoryPerformance,
            "bookingsByWeekday": bookingsByWeekday,
            "bookingsByDateDetailed": bookingsByDateDetailed,
        }


        resp = jsonify({"message": "OK", **payload, "datas": payload})
        # header CORS (jika tidak pakai flask-cors)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 200

    except Exception as e:
        print("Error in /ws-dashboard-data:", e)
        import traceback; traceback.print_exc()
        return jsonify({"message": "ERROR", "error": str(e)}), 500
    finally:
        try:
            if cur: cur.close()
        except Exception: pass
        try:
            if conn: conn.close()
        except Exception: pass


# ============================================================
# 4) PAJAK DASHBOARD (OWNER)
# ============================================================

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
      