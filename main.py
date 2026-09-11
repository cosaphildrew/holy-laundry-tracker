"""
Holy Laundry - Order Tracker (public website)

A tiny, standalone public site: a customer types in the tracking number
printed on their ticket and sees the current status of their order. No
login, no account - the tracking number itself is the "key" (same idea as
a courier parcel-tracking page).

Deployed completely separately from the staff app (different Render
service, different URL), but reads from the SAME Postgres database via
the SAME DATABASE_URL env var - so statuses update here the instant staff
change them on the tablet/dashboard.

Run locally:
    DATABASE_URL=postgres://... python main.py
    -> opens on http://localhost:8000 (or $PORT if set, e.g. on Render)
"""

import os
import datetime
import flet as ft

import database as db

STAGES = ["Dropped Off", "Washing", "Ready", "Picked Up"]

TEAL = "#1F7A78"
TEAL_DARK = "#13524F"
TEAL_SOFT = "#E2F0EE"
CORAL = "#FF6B55"
CORAL_SOFT = "#FFE7E2"
INK = "#16292B"
MUTED = "#6F8688"
BG = "#EFF5F5"
LINE = "#E2EBEC"

STATUS_MESSAGES = {
    "Dropped Off": "We've received your laundry and it's in the queue.",
    "Washing": "Your laundry is currently being washed.",
    "Ready": "Ready for pickup! Please claim it at your earliest convenience.",
    "Picked Up": "This order has been picked up. Thanks for choosing us!",
}


def border_all(width, color):
    side = ft.BorderSide(width, color)
    return ft.Border(left=side, top=side, right=side, bottom=side)


def fmt_date(d):
    if not d:
        return ""
    try:
        dt = datetime.date.fromisoformat(d)
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return d


def main(page: ft.Page):
    page.title = "Track My Laundry - Holy Laundry"
    page.bgcolor = BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    result_area = ft.Column(spacing=14)
    error_text = ft.Text("", color=CORAL, size=13, weight=ft.FontWeight.W_600)

    tracking_field = ft.TextField(
        label="Tracking number",
        hint_text="e.g. HL-260910-143207",
        width=340,
        autofocus=True,
        border_radius=10,
        on_submit=lambda e: do_search(e),
    )

    def timeline_row(current_status):
        current_idx = STAGES.index(current_status) if current_status in STAGES else 0
        dots = []
        for i, stage in enumerate(STAGES):
            reached = i <= current_idx
            is_current = i == current_idx
            dots.append(
                ft.Column(
                    [
                        ft.Container(
                            width=16, height=16, border_radius=999,
                            bgcolor=TEAL if reached else "white",
                            border=border_all(2, TEAL if reached else LINE),
                        ),
                        ft.Text(
                            stage, size=10.5,
                            weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                            color=TEAL_DARK if reached else MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            if i < len(STAGES) - 1:
                dots.append(
                    ft.Container(
                        height=2, expand=True, bgcolor=TEAL if i < current_idx else LINE,
                        margin=ft.Margin(0, 7, 0, 0),
                    )
                )
        return ft.Row(dots, alignment=ft.MainAxisAlignment.CENTER)

    def order_result_view(order):
        client = db.get_client_by_id(order.get("client_id"))
        client_name = client["name"] if client else None

        items = order.get("items") or []
        item_rows = [
            ft.Row(
                [
                    ft.Text(f"{i.get('qty', 0):g}x {i.get('type', 'Item')}", size=13, color=INK),
                ],
            )
            for i in items
        ] or [ft.Text("No items logged yet.", size=12.5, color=MUTED)]

        status = order.get("status", "Dropped Off")
        badge_color = {
            "Dropped Off": "#9C6B17",
            "Washing": TEAL_DARK,
            "Ready": "#C8492F",
            "Picked Up": "#1F7A41",
        }.get(status, TEAL_DARK)

        greeting = f"Hi {client_name.split()[0]}!" if client_name else "Order found"

        due_line = None
        if order.get("due_date"):
            due_line = ft.Text(f"Estimated ready by {fmt_date(order['due_date'])}", size=12.5, color=MUTED)

        card = ft.Container(
            content=ft.Column(
                [
                    ft.Text(greeting, size=15, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text(f"Tracking #{order['tracking_number']}", size=12, color=MUTED),
                    ft.Container(height=6),
                    timeline_row(status),
                    ft.Container(height=6),
                    ft.Container(
                        content=ft.Text(status.upper(), size=12, weight=ft.FontWeight.BOLD, color="white"),
                        bgcolor=badge_color, border_radius=999, padding=ft.Padding(12, 5, 12, 5),
                        alignment=ft.alignment.Alignment(0, 0),
                    ),
                    ft.Text(STATUS_MESSAGES.get(status, ""), size=12.5, color=MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Divider(height=1),
                    ft.Text("ITEMS", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
                    ft.Column(item_rows, spacing=4),
                    ft.Divider(height=1),
                    ft.Row(
                        [
                            ft.Text("Dropped off", size=12, color=MUTED),
                            ft.Text(fmt_date(order.get("drop_off_date")), size=12, weight=ft.FontWeight.BOLD),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    *([due_line] if due_line else []),
                    ft.Row(
                        [
                            ft.Text("Order type", size=12, color=MUTED),
                            ft.Text("Rush" if order.get("is_rush") else "Regular", size=12, weight=ft.FontWeight.BOLD,
                                     color=CORAL if order.get("is_rush") else INK),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text("Total", size=13, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"₱{order['price']:.2f}" if order.get("price") else "Not priced yet",
                                size=15, weight=ft.FontWeight.BOLD, color=TEAL,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="white", border=border_all(1, LINE), border_radius=16,
            padding=20, width=380,
        )
        return card

    def do_search(e):
        error_text.value = ""
        result_area.controls = []
        value = (tracking_field.value or "").strip().upper()
        if not value:
            error_text.value = "Please enter your tracking number."
            page.update()
            return

        try:
            order = db.get_order_by_tracking_number(value)
        except Exception as err:
            error_text.value = f"Something went wrong looking that up: {err}"
            page.update()
            return

        if not order:
            error_text.value = "No order found with that tracking number. Please double-check and try again."
            page.update()
            return

        result_area.controls = [order_result_view(order)]
        page.update()

    search_btn = ft.ElevatedButton(
        "Track Order", bgcolor=TEAL, color="white", width=340,
        on_click=do_search,
    )

    header = ft.Container(
        content=ft.Column(
            [
                ft.Text("Holy Laundry", size=22, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Track your order", size=13, color="white"),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=TEAL,
        padding=ft.Padding(24, 32, 24, 28),
        alignment=ft.alignment.Alignment(0, 0),
        width=page.width,
    )

    page.add(
        ft.Column(
            [
                header,
                ft.Container(height=24),
                ft.Column(
                    [
                        tracking_field,
                        error_text,
                        search_btn,
                        ft.Container(height=8),
                        result_area,
                    ],
                    spacing=10,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=32),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
    )


if __name__ == "__main__":
    if os.environ.get("PORT"):
        ft.app(
            target=main,
            view=ft.AppView.WEB_BROWSER,
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 8000)),
        )
    else:
        ft.app(target=main, view=ft.AppView.WEB_BROWSER)
