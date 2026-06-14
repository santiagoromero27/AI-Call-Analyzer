import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

_db_url = settings.DATABASE_URL

# Convert relative SQLite paths to absolute so the DB file location never
# depends on which directory uvicorn happens to be launched from.
if _db_url.startswith("sqlite:///") and not _db_url.startswith("sqlite:////"):
    _rel = _db_url[len("sqlite:///"):]
    if _rel.startswith("./") or not os.path.isabs(_rel):
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _db_url = "sqlite:///" + os.path.join(_project_root, _rel.lstrip("./"))

_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine = create_engine(_db_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
