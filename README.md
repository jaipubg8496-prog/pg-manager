# PG/Hostel Manager — Backend (MVP)

Working FastAPI backend covering: owner auth, properties, rooms/beds, tenants,
and the core rent-cycle + WhatsApp reminder logic from the blueprint.

## What's included

- `app/models.py` — all 7 tables (owners, properties, rooms, beds, tenants, rent_cycles, complaints)
- `app/schemas.py` — request/response validation
- `app/auth/` — JWT login, password hashing, `get_current_owner` dependency
- `app/routers/auth.py` — signup / login / me
- `app/routers/properties.py` — create/list properties (owner-scoped)
- `app/routers/rooms.py` — create rooms + auto-generate beds
- `app/routers/tenants.py` — add tenant to a bed, move-out (frees the bed)
- `app/routers/rent.py` + `app/services/rent_service.py` — generate monthly
  rent cycles, mark paid, auto-flag overdue, build WhatsApp reminder links
- `app/main.py` — app entrypoint, wires up all routers

All files have been syntax-checked (`py_compile`) but **not yet run against a
live database** — you'll do that in step 3 below. Read through the code
before running it; understanding every line is more valuable right now than
speed.

## Setup

### 1. Create a free Postgres database
Sign up at [neon.tech](https://neon.tech) or [supabase.com](https://supabase.com),
create a project, and copy the connection string (starts with `postgresql://`).

### 2. Configure environment
```bash
cd pg-manager
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: paste your DATABASE_URL, and generate a SECRET_KEY with:
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Run it
```bash
uvicorn app.main:app --reload
```
Tables are auto-created on startup (see `main.py`). Open **http://127.0.0.1:8000/docs**
— this is FastAPI's built-in Swagger UI, and it's how you should test every
endpoint before building any frontend page.

## Suggested test flow in `/docs`

1. `POST /api/auth/signup` — create an owner account
2. `POST /api/auth/login` — get an access token (click the padlock icon in
   Swagger, paste the token, and every request below will now be authenticated)
3. `POST /api/properties` — create a property
4. `POST /api/properties/{id}/rooms` — create a room with `num_beds: 2`
   (this auto-creates Bed A and Bed B)
5. `POST /api/properties/{id}/tenants` — add a tenant to `bed_id` from step 4
6. `POST /api/properties/{id}/rent-cycles/generate?due_date=2026-10-05` —
   generates this month's rent cycle for every active tenant
7. `GET /api/properties/{id}/rent-status` — see the dashboard: who owes what,
   how many beds are vacant
8. `GET /api/rent-cycles/{id}/reminder-text` — get the pre-filled WhatsApp
   message + `wa.me` link for a pending tenant
9. `POST /api/rent-cycles/{id}/mark-paid` — mark it paid, watch the dashboard
   total drop

## What's deliberately NOT built yet (by design)

- Frontend HTML/CSS/JS — build this next, against the working API above
- Alembic migrations — fine to skip while you're the only one using the DB;
  add before onboarding real customers so schema changes don't wipe data
- Complaints router — schema/model exist, router follows the exact same
  pattern as `tenants.py` — build it yourself as practice
- Scheduled/automatic rent cycle generation — for now the owner clicks a
  button once a month; automate with a cron job only once this is validated
- Payment gateway integration — owners mark rent "paid" manually after
  collecting cash/UPI directly; don't add Razorpay for rent collection until
  customers actually ask for it

## A note on security

Look closely at `_get_owned_property`, `_get_owned_tenant`, and
`_get_owned_rent_cycle` in the router files. Every single one of them checks
that the record belongs to the logged-in owner before returning anything.
This is the single most important pattern in the whole codebase — copy it
exactly when you build the complaints router or anything else.
