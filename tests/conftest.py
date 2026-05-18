import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')

# Build one shared in-memory engine with StaticPool so all connections share the same DB
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)

# Patch the app's engine and session before importing app modules
import app.core.database as _db_module  # noqa: E402
_db_module.engine = _TEST_ENGINE
_db_module.SessionLocal = _TestSession

from fastapi.testclient import TestClient  # noqa: E402
from app.main import create_app  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.models.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture
def db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    app = create_app()

    def override_session():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_session] = override_session
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


API_KEY = "test-api-key"
AUTH_HEADERS = {"x-api-key": API_KEY}
