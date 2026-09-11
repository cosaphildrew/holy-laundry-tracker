# Holy Laundry - Order Tracker (public site)

A separate, public mini-site: customers type in their tracking number
(e.g. `HL-260910-143207`) and see their order's current status. No login.
Reads from the same Postgres database as your main Holy Laundry app.

## Files
- `main.py` - the whole site (one page, one search box)
- `database.py` - a standalone copy of the DB module, with two small
  read-only additions (`get_client_by_id`, `get_service_by_id`) so the
  page can say "Hi, [Name]!" without exposing phone/address.
- `requirements.txt` - `flet` + `pg8000`

## Run locally
```
pip install -r requirements.txt
DATABASE_URL="postgresql://...same-url-as-your-main-app..." python main.py
```
Then open http://localhost:8000

## Deploy on Render (same idea as your main app)
1. Push this folder to its own GitHub repo (or a subfolder of an existing
   one, pointed at as its own Render Web Service).
2. On Render: **New > Web Service**, connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py`
5. Add an environment variable `DATABASE_URL` set to the **exact same**
   connection string your main app uses (same Neon/Supabase/etc. database)
   so statuses stay in sync automatically.
6. Deploy. You'll get a URL like `holy-laundry-tracker.onrender.com` -
   that's what you'd print on receipts / share with customers, completely
   separate from the staff tablet app.

## Notes
- This site only ever *reads* the `orders`, `clients`, and `services`
  tables - it never writes anything, so there's no risk of a customer
  accidentally changing an order.
- It never shows phone numbers or addresses - only name, status, items,
  dates, order type, and price.
- If a customer mistypes the tracking number, they just get "No order
  found" - no hints, no listing of other tracking numbers.
