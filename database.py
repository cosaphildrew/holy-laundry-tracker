"""
Holy Laundry - Database Module (tracker-site copy)

This is the SAME database module used by the main Holy Laundry app,
pointed at the SAME Postgres database via DATABASE_URL. It's duplicated
here (rather than imported across projects) so this tracker site can be
deployed completely independently from the staff app.

Only two functions were added at the bottom that don't exist in the main
app's copy: get_client_by_id() and get_service_by_id(). Both are simple
read-only lookups (no writes, no schema changes) added so the public
tracking page can show a client's name and a service's name without
pulling every client/service row. If you ever update the main app's
database.py, you can safely copy those two functions over here too - they
don't touch anything the main app relies on.

Driver: pg8000 (pure Python - no C extension required).
"""

import os
import json
import ssl
from datetime import datetime
from contextlib import contextmanager
from urllib.parse import urlparse, unquote

import pg8000


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
        ctx = ssl.create_default_context()
        ssl_context = ctx

    return {
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") if parsed.path else None,
        "ssl_context": ssl_context,
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


# ---------------------------------------------------------------- ORDERS
def get_order_by_tracking_number(tracking_number):
    """Look up a single order by its printed tracking number. Returns None
    if no order matches. This is the only lookup the tracker site needs
    for the order itself."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT id, client_id, service_id, items, drop_off_date, due_date, price, notes,
                      status, is_rush, tracking_number, created_at
               FROM orders WHERE tracking_number = %s""",
            (tracking_number,),
        )
        row = c.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "client_id": row[1],
        "service_id": row[2],
        "items": json.loads(row[3]) if isinstance(row[3], str) else row[3],
        "drop_off_date": row[4],
        "due_date": row[5],
        "price": float(row[6]) if row[6] else 0,
        "notes": row[7],
        "status": row[8],
        "is_rush": row[9] if len(row) > 9 else False,
        "tracking_number": row[10] if len(row) > 10 else None,
        "created_at": row[11],
    }


# ---------------------------------------------------------- ADDED HELPERS
def get_client_by_id(client_id):
    """Read-only lookup of a single client's public-safe fields (name
    only - phone/address are deliberately left out since this is called
    from a public, unauthenticated page)."""
    if not client_id:
        return None
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM clients WHERE id = %s", (client_id,))
        row = c.fetchone()
    if not row:
        return None
    return {"name": row[0]}


def get_service_by_id(service_id):
    """Read-only lookup of a single service's name/unit (used only as a
    fallback label; order items already store their own type/qty)."""
    if not service_id:
        return None
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT name, unit FROM services WHERE id = %s", (service_id,))
        row = c.fetchone()
    if not row:
        return None
    return {"name": row[0], "unit": row[1]}
