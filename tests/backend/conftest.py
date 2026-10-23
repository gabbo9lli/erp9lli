import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["TESTING"] = "1"
os.environ["DB_TYPE"] = "sqlite"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from main import app as fastapi_app
from database import get_db
from models import Base
import database

# Monkey patch httpx Response per offrire get_json(), content_type e data
httpx.Response.get_json = lambda self: self.json()
httpx.Response.content_type = property(lambda self: self.headers.get("content-type", ""))
httpx.Response.data = property(lambda self: self.content)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)

_current_test_session = None

def get_test_session_or_new():
    return _current_test_session if _current_test_session is not None else TestingSessionLocal()

database.SessionLocal = get_test_session_or_new

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    global _current_test_session
    _current_test_session = session
    try:
        yield session
    finally:
        _current_test_session = None
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client_instance = TestClient(fastapi_app)
    yield client_instance
    fastapi_app.dependency_overrides.clear()
