from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

_url = settings.database_url
_engine_kwargs: dict = {"pool_pre_ping": True}
_connect_args: dict = {}

if _url.startswith("postgresql"):
    if "supabase" in _url.lower() and "sslmode" not in _url:
        sep = "&" if "?" in _url else "?"
        _url = f"{_url}{sep}sslmode=require"
    _connect_args = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": 8,  # fail fast on serverless (Vercel limit is 10s)
    }
    _engine_kwargs.update({"pool_size": 5, "max_overflow": 10})
elif _url.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool

if _connect_args and not _url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = _connect_args

engine = create_engine(_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
