"""
Holy Laundry - Reports (password-protected website)

Replaces the old public "track my order" page. Owner/manager types a
password, then can view:
  - Sales:     paid orders per day, split by payment method
  - Cashbox:   cash that should be in the box + recent movements
  - Orders:    how many orders are in each stage right now
  - Services:  quantity and estimated revenue per service

READ-ONLY: it reads the same Postgres database as the staff app (same
DATABASE_URL) and never writes to it.

Password: set the REPORTS_PASSWORD environment variable on Render. If it is
not set, the fallback below is used - change it, because this site is public.

Run locally:
    DATABASE_URL=postgres://... REPORTS_PASSWORD=yourpassword python main.py
    -> http://localhost:8000 (or $PORT, e.g. on Render)
"""

import hmac
import os
import time
import datetime
import flet as ft

import database as db

PH_TZ = db.PH_TZ
STAGES = ["Dropped Off", "Washing", "Ready", "Picked Up"]

# Used only when the REPORTS_PASSWORD environment variable is not set.
FALLBACK_PASSWORD = "55555"
REPORTS_PASSWORD = os.environ.get("REPORTS_PASSWORD") or FALLBACK_PASSWORD
if not os.environ.get("REPORTS_PASSWORD"):
    print("[reports] WARNING: REPORTS_PASSWORD is not set - using the fallback "
          "password. Set REPORTS_PASSWORD on Render.")

TEAL = "#1F7A78"
TEAL_DARK = "#13524F"
TEAL_SOFT = "#E2F0EE"
CORAL = "#FF6B55"
CORAL_SOFT = "#FFE7E2"
GREEN = "#1F7A41"
INK = "#16292B"
MUTED = "#6F8688"
BG = "#EFF5F5"
LINE = "#E2EBEC"

TABS = ["Sales", "Cashbox", "Orders", "Services"]
RANGES = [("today", "Today"), ("7d", "7 days"), ("month", "This month"), ("all", "All time")]


# Newer Flet versions removed ElevatedButton and ft.app(); these keep the
# file working on both old and new Flet.
Button = getattr(ft, "Button", None) or ft.ElevatedButton


def border_all(width, color):
    side = ft.BorderSide(width, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def money(x):
    return f"₱{x:,.2f}"


def ph_today():
    return datetime.datetime.now(PH_TZ).date()


def range_dates(key):
    t = ph_today()
    if key == "today":
        return t, t
    if key == "7d":
        return t - datetime.timedelta(days=6), t
    if key == "month":
        return t.replace(day=1), t
    return datetime.date(2000, 1, 1), t


def fmt_ledger_time(dt):
    try:
        if dt.tzinfo is not None:
            dt = dt.astimezone(PH_TZ)
        return dt.strftime("%b %d %I:%M %p")
    except Exception:
        return str(dt)


def main(page: ft.Page):
    page.title = "Holy Laundry - Reports"
    page.bgcolor = BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    state = {
        "unlocked": False,
        "pw_input": "",
        "pw_error": "",
        "tab": 0,
        "range": "today",
        "data": None,
        "error": "",
    }

    def content_width():
        w = page.width or 420
        return max(300, min(620, w - 24))

    # ---------------------------------------------------------- data
    def load_data():
        s, e = range_dates(state["range"])
        try:
            state["data"] = db.get_report_data(s, e)
            state["error"] = ""
        except Exception as err:
            state["data"] = None
            state["error"] = f"Could not load reports: {err}"

    def reload_and_render(e=None):
        show_loading()
        load_data()
        render()

    # ---------------------------------------------------------- UI helpers
    def card(children, bg="white", border=LINE, padding=14):
        return ft.Container(
            content=ft.Column(children, spacing=8),
            bgcolor=bg, border=border_all(1, border), border_radius=14, padding=padding,
        )

    def label(text):
        return ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=MUTED)

    def row_lr(left, right, bold=True, color=INK, size=13, left_color=INK):
        return ft.Row(
            [
                ft.Text(left, size=size, color=left_color),
                ft.Text(right, size=size, weight=ft.FontWeight.BOLD if bold else None, color=color),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def chip(text, selected, on_click, accent=TEAL):
        return ft.Container(
            content=ft.Text(text, size=12, weight=ft.FontWeight.BOLD,
                            color="white" if selected else MUTED,
                            text_align=ft.TextAlign.CENTER),
            bgcolor=accent if selected else "white",
            border=border_all(1, accent if selected else LINE),
            border_radius=9, padding=ft.Padding(8, 9, 8, 9),
            alignment=ft.Alignment(0, 0), expand=True,
            on_click=on_click,
        )

    def shell(children):
        """Header + the given children, centered in a fixed-width column."""
        header = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Holy Laundry", size=22, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Reports", size=13, color="white"),
                ],
                spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=TEAL, padding=ft.Padding(24, 28, 24, 24),
            alignment=ft.Alignment(0, 0), width=page.width,
        )
        page.controls.clear()
        page.add(
            ft.Column(
                [
                    header,
                    ft.Container(height=14),
                    ft.Container(content=ft.Column(children, spacing=12), width=content_width()),
                    ft.Container(height=32),
                ],
                spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    def show_loading():
        shell([ft.Text("Loading reports...", size=14, color=MUTED, text_align=ft.TextAlign.CENTER)])

    # ---------------------------------------------------------- password
    def show_login():
        def on_pw(e):
            state["pw_input"] = e.control.value

        def try_login(e=None):
            attempt = (state["pw_input"] or "").strip()
            if hmac.compare_digest(attempt.encode(), REPORTS_PASSWORD.encode()):
                state["unlocked"] = True
                state["pw_input"] = ""
                state["pw_error"] = ""
                reload_and_render()
            else:
                time.sleep(2)  # slows down password guessing
                state["pw_input"] = ""
                state["pw_error"] = "Wrong password."
                show_login()

        shell([
            card([
                label("OWNER / MANAGER ONLY"),
                ft.Text("Enter the password to view reports.", size=13, color=INK),
                ft.TextField(label="Password", password=True, can_reveal_password=True,
                             on_change=on_pw, on_submit=try_login, autofocus=True),
                ft.Text(state["pw_error"], size=12, color=CORAL, weight=ft.FontWeight.W_600),
                Button("Open reports", bgcolor=TEAL, color="white", on_click=try_login),
            ])
        ])

    # ---------------------------------------------------------- views
    def view_sales(d):
        rows = d["sales"]
        total_rev = round(sum(r["total"] for r in rows), 2)
        total_n = sum(r["count"] for r in rows)
        by_method = {}
        for r in rows:
            m = by_method.setdefault(r["method"], {"count": 0, "total": 0.0})
            m["count"] += r["count"]
            m["total"] = round(m["total"] + r["total"], 2)

        out = [
            card([
                label("TOTAL SALES (PAID ORDERS)"),
                ft.Text(money(total_rev), size=30, weight=ft.FontWeight.BOLD, color=TEAL),
                ft.Text(f"{total_n} paid order(s)", size=12, color=MUTED),
            ]),
        ]
        if by_method:
            out.append(card(
                [label("BY PAYMENT METHOD")]
                + [row_lr(f"{name}  ({v['count']})", money(v["total"]))
                   for name, v in sorted(by_method.items(), key=lambda kv: -kv[1]["total"])]
            ))

            days = {}
            for r in rows:
                days.setdefault(r["date"], []).append(r)
            out.append(label("PER DAY"))
            for day, items in days.items():
                day_total = round(sum(i["total"] for i in items), 2)
                out.append(card(
                    [row_lr(day.strftime("%a, %b %d"), money(day_total), size=14)]
                    + [row_lr(f"{i['method']}  ({i['count']})", money(i["total"]),
                              bold=False, size=12, left_color=MUTED) for i in items]
                ))
        else:
            out.append(card([ft.Text("No paid orders in this period.", size=13, color=MUTED)]))
        return out

    def view_cashbox(d):
        if d.get("cash_error"):
            return [card([ft.Text("The cashbox table could not be read. Open the staff app "
                                  "once so it is created.", size=13, color=CORAL)])]
        kind = {"opening": "Opening cash", "sale": "Cash sale", "deposit": "Cash added",
                "withdrawal": "Cash out", "adjustment": "Count adjustment"}
        rows = []
        for en in d["cash_entries"]:
            amt = en["amount"]
            sub = fmt_ledger_time(en["created_at"])
            if en["tendered"] is not None:
                sub += f" - received {money(en['tendered'])}, change {money(en['change_given'])}"
            if en["note"]:
                sub += f" - {en['note']}"
            rows.append(
                ft.Row(
                    [
                        ft.Column(
                            [ft.Text(kind.get(en["entry_type"], en["entry_type"]),
                                     size=13, weight=ft.FontWeight.BOLD),
                             ft.Text(sub, size=11, color=MUTED)],
                            spacing=1, expand=True,
                        ),
                        ft.Text(f"{'+' if amt >= 0 else '-'}{money(abs(amt))}", size=14,
                                weight=ft.FontWeight.BOLD, color=GREEN if amt >= 0 else CORAL),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )
        return [
            card([
                label("CASH IN THE BOX NOW"),
                ft.Text(money(d["cash_balance"]), size=32, weight=ft.FontWeight.BOLD, color=TEAL),
            ]),
            label("RECENT MOVEMENTS"),
            card(rows or [ft.Text("No entries yet.", size=13, color=MUTED)]),
        ]

    def view_orders(d):
        counts = d["status_counts"]
        total = sum(v["count"] for v in counts.values())
        rows = []
        for st in STAGES + [s for s in counts if s not in STAGES]:
            v = counts.get(st, {"count": 0, "rush": 0})
            extra = f"  ({v['rush']} rush)" if v["rush"] else ""
            rows.append(row_lr(st + extra, str(v["count"])))
        return [
            card([
                label("ALL ORDERS"),
                ft.Text(str(total), size=30, weight=ft.FontWeight.BOLD, color=TEAL),
            ]),
            label("BY STATUS (RIGHT NOW)"),
            card(rows),
        ]

    def view_services(d):
        prices = d["services"]
        agg = {}
        for items in d["paid_items"]:
            for it in items:
                name = it.get("type") or "Item"
                qty = float(it.get("qty") or 0)
                a = agg.setdefault(name, {"qty": 0.0, "revenue": 0.0})
                a["qty"] += qty
                a["revenue"] += qty * prices.get(name, {}).get("price", 0.0)
        rows = []
        for name, a in sorted(agg.items(), key=lambda kv: -kv[1]["revenue"]):
            unit = prices.get(name, {}).get("unit", "")
            rows.append(
                ft.Row(
                    [
                        ft.Column(
                            [ft.Text(name, size=13, weight=ft.FontWeight.BOLD),
                             ft.Text(f"{a['qty']:g} {unit}", size=11, color=MUTED)],
                            spacing=1, expand=True,
                        ),
                        ft.Text(money(a["revenue"]), size=14, weight=ft.FontWeight.BOLD, color=TEAL),
                    ]
                )
            )
        return [
            label("SALES PER SERVICE (PAID ORDERS)"),
            card(rows or [ft.Text("No paid orders in this period.", size=13, color=MUTED)]),
            ft.Text("Revenue is estimated from today's service prices, before rush fees and discounts.",
                    size=11, color=MUTED, text_align=ft.TextAlign.CENTER),
        ]

    # ---------------------------------------------------------- render
    def set_tab(i):
        state["tab"] = i
        render()

    def set_range(key):
        state["range"] = key
        reload_and_render()

    def lock(e=None):
        state["unlocked"] = False
        state["data"] = None
        show_login()

    def render():
        if not state["unlocked"]:
            show_login()
            return

        tab_row = ft.Row(
            [chip(t, state["tab"] == i, lambda e, idx=i: set_tab(idx)) for i, t in enumerate(TABS)],
            spacing=6,
        )
        children = [tab_row]

        # The date range only affects Sales and Services.
        if state["tab"] in (0, 3):
            children.append(ft.Row(
                [chip(lbl, state["range"] == key, lambda e, k=key: set_range(k), accent=CORAL)
                 for key, lbl in RANGES],
                spacing=6,
            ))

        if state["error"]:
            children.append(card([ft.Text(state["error"], size=12.5, color=CORAL, selectable=True)],
                                 bg=CORAL_SOFT, border=CORAL))
        elif state["data"] is not None:
            views = [view_sales, view_cashbox, view_orders, view_services]
            try:
                children += views[state["tab"]](state["data"])
            except Exception as err:
                children.append(card([ft.Text(f"Could not show this report: {err}",
                                              size=12.5, color=CORAL, selectable=True)]))

        children.append(ft.Row(
            [
                ft.OutlinedButton("Refresh", on_click=reload_and_render),
                ft.TextButton("Lock", on_click=lock),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ))
        shell(children)

    show_login()


if __name__ == "__main__":
    # Flet 1.x replaced ft.app() with ft.run(); fall back for older versions.
    run_app = getattr(ft, "run", None) or ft.app
    if os.environ.get("PORT"):
        run_app(
            main,
            view=ft.AppView.WEB_BROWSER,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8000)),
        )
    else:
        run_app(main, view=ft.AppView.WEB_BROWSER)
