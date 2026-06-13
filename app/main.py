from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models
from .routers import calls, tasks, upload, webhooks, batches, settings_router
from .routers import home, analyze
from .services.model_settings import set_model_key

from fastapi import FastAPI

# Create new tables; does not touch existing ones
Base.metadata.create_all(bind=engine)

# Add columns introduced after initial schema creation (SQLite can't ALTER existing cols)
def _migrate_sqlite() -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    new_cols = {
        "caller_id":          "VARCHAR(60)",
        "campaign_name":      "VARCHAR(200)",
        "termination_reason": "VARCHAR(200)",
        "no_payout_reason":   "VARCHAR(200)",
        "batch_id":           "INTEGER",
        "status":             "VARCHAR(20) DEFAULT 'done'",
        "conversion_barrier": "TEXT",
    }
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(calls)"))}
        for col, dtype in new_cols.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE calls ADD COLUMN {col} {dtype}"))
        conn.commit()

_migrate_sqlite()


def _init_model() -> None:
    """Restore saved model selection from DB on startup."""
    db = SessionLocal()
    try:
        row = db.query(models.Setting).filter(models.Setting.key == "model").first()
        if row:
            set_model_key(row.value)
    finally:
        db.close()

_init_model()

app = FastAPI(title="AI Call Analyzer", version="0.2.0")

app.include_router(home.router)
app.include_router(analyze.router)
app.include_router(webhooks.router)
app.include_router(upload.router)
app.include_router(calls.router)
app.include_router(tasks.router)
app.include_router(batches.router)
app.include_router(settings_router.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
