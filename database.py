"""
Holy Laundry - Reports site database module (READ-ONLY)

Same Postgres database and same DATABASE_URL as the staff app, but this site
only ever reads. Nothing here inserts, updates or deletes.

Driver: pg8000 (pure Python - no C extension required).
"""

import os
import json
import ssl
from datetime import datetime, timedelta, timezone, date, time
from contextlib import contextmanager
from urllib.parse import urlparse, unquote

import pg8000

# Philippine time. Reports group days by Manila date, not UTC.
PH_TZ = timezone(timedelta(hours=8))


def _get_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point this at the SAME Postgres "
            "database your main Holy Laundry app uses."
        )
    return url


def _parse_connect_args(url):
    parsed = urlparse(url)

    ssl_context = None
    query = parsed.query or ""
    if "sslmode=disable" not in query:
        ssl_context = ssl.create_default_context()

    return {
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") if parsed.path else None,
        "ssl_context": ssl_context,
        "timeout": 30,
    }


@contextmanager
def get_conn():
    url = _get_database_url()
    args = _parse_connect_args(url)
    try:
        conn = pg8000.connect(**args)
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        raise RuntimeError(f"Database connection failed: {e}") from e

    try:
        yield conn
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[DB] Query failed: {e}")
        raise
    finally:
        conn.close()


def day_range_to_epoch(start_date, end_date):
    """Inclusive Manila dates -> (start_ts, end_ts) epoch seconds, where
    end_ts is the start of the day AFTER end_date."""
    start = datetime.combine(start_date, time.min, tzinfo=PH_TZ)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=PH_TZ)
    return int(start.timestamp()), int(end.timestamp())


def get_report_data(start_date, end_date, cash_limit=50):
    """Everything the reports need, over ONE connection.

    Sales/services use orders that were PAID (status Picked Up with a paid_at
    time) inside the date range. Status counts and the cashbox are not
    date-filtered: they show the situation right now.
    """
    start_ts, end_ts = day_range_to_epoch(start_date, end_date)
    out = {}

    with get_conn() as conn:
        c = conn.cursor()

        # --- sales per day per payment method ---
        c.execute(
            """SELECT (to_timestamp(paid_at) AT TIME ZONE 'Asia/Manila')::date AS d,
                      COALESCE(payment_method, 'Unknown') AS method,
                      COUNT(*) AS n,
                      COALESCE(SUM(price), 0) AS total
               FROM orders
               WHERE status = 'Picked Up' AND paid_at IS NOT NULL
                     AND paid_at >= %s AND paid_at < %s
               GROUP BY 1, 2
               ORDER BY 1 DESC, 2""",
            (start_ts, end_ts),
        )
        out["sales"] = [
            {"date": r[0], "method": r[1], "count": int(r[2]), "total": round(float(r[3]), 2)}
            for r in c.fetchall()
        ]

        # --- items of paid orders (for sales per service) ---
        c.execute(
            """SELECT items FROM orders
               WHERE status = 'Picked Up' AND paid_at IS NOT NULL
                     AND paid_at >= %s AND paid_at < %s""",
            (start_ts, end_ts),
        )
        paid_items = []
        for (raw,) in c.fetchall():
            try:
                items = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except ValueError:
                items = []
            paid_items.append(items)
        out["paid_items"] = paid_items

        c.execute("SELECT name, unit, price FROM services")
        out["services"] = {r[0]: {"unit": r[1], "price": float(r[2])} for r in c.fetchall()}

        # --- orders by status (right now) ---
        c.execute(
            """SELECT COALESCE(status, 'Unknown'), COUNT(*),
                      COUNT(*) FILTER (WHERE is_rush)
               FROM orders GROUP BY 1"""
        )
        out["status_counts"] = {r[0]: {"count": int(r[1]), "rush": int(r[2])} for r in c.fetchall()}

        # --- cashbox (right now). In a SAVEPOINT so that a missing
        # cash_ledger table can't break the other reports. ---
        out["cash_error"] = None
        out["cash_balance"] = 0.0
        out["cash_entries"] = []
        try:
            c.execute("SAVEPOINT cashbox")
            c.execute("SELECT COALESCE(SUM(amount), 0) FROM cash_ledger")
            out["cash_balance"] = float(c.fetchone()[0])
            c.execute(
                "SELECT created_at, entry_type, amount, tendered, change_given, note "
                "FROM cash_ledger ORDER BY id DESC LIMIT %s",
                (cash_limit,),
            )
            out["cash_entries"] = [
                {"created_at": r[0], "entry_type": r[1], "amount": float(r[2]),
                 "tendered": None if r[3] is None else float(r[3]),
                 "change_given": None if r[4] is None else float(r[4]),
                 "note": r[5] or ""}
                for r in c.fetchall()
            ]
            c.execute("RELEASE SAVEPOINT cashbox")
        except Exception as e:
            print(f"[DB] Could not read cash_ledger: {e}")
            out["cash_error"] = str(e)
            try:
                c.execute("ROLLBACK TO SAVEPOINT cashbox")
            except Exception:
                pass

    return out


def get_calendar_data(year, month):
    """Paid orders per day for one calendar month (Manila dates)."""
    first = date(year, month, 1)
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    start_ts, end_ts = day_range_to_epoch(first, nxt - timedelta(days=1))

    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT (to_timestamp(paid_at) AT TIME ZONE 'Asia/Manila')::date AS d,
                      COUNT(*) AS n,
                      COALESCE(SUM(price), 0) AS total
               FROM orders
               WHERE status = 'Picked Up' AND paid_at IS NOT NULL
                     AND paid_at >= %s AND paid_at < %s
               GROUP BY 1""",
            (start_ts, end_ts),
        )
        days = {r[0]: {"count": int(r[1]), "total": round(float(r[2]), 2)}
                for r in c.fetchall()}
    return {"days": days}
