from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401 — ensures models are registered before create_all
from app.routers import auth, properties, rooms, tenants, rent, complaints, billing

app = FastAPI(title="PG/Hostel Manager API", version="0.1.0")

# CORS: wide open for local development. Tighten this to your real frontend
# domain before going to production (allow_origins=["https://yourapp.com"]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(rooms.router)
app.include_router(tenants.router)
app.include_router(rent.router)
app.include_router(complaints.router)
app.include_router(billing.router)


@app.on_event("startup")
def on_startup():
    # MVP convenience: creates any tables that don't exist yet (this handles
    # the new `payments` table automatically — it's brand new).
    Base.metadata.create_all(bind=engine)

    # create_all does NOT alter existing tables, so the two new subscription
    # columns on `owners` need a one-time manual add. This runs safely every
    # startup — "IF NOT EXISTS" makes it a no-op once the columns are there.
    # Once you have real customer data flowing regularly, replace this
    # pattern with proper Alembic migrations.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE owners ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP"))
        conn.execute(text("ALTER TABLE owners ADD COLUMN IF NOT EXISTS subscription_active_until TIMESTAMP"))
        # Any owner created before this feature existed has trial_ends_at = NULL,
        # which would read as "trial already over". Give existing accounts a
        # fresh trial window counted from when they originally signed up.
        conn.execute(text(
            "UPDATE owners SET trial_ends_at = created_at + INTERVAL '90 days' "
            "WHERE trial_ends_at IS NULL"
        ))


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    # The landing page is the front door now; it links to /static/login.html itself.
    return RedirectResponse(url="/static/landing.html")


# Serves everything in app/static/ — login.html, dashboard.html, property.html,
# and the css/js folders. Mounted last so it doesn't shadow the API routes above.
app.mount("/static", StaticFiles(directory="app/static"), name="static")
