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
from sqlalchemy.orm import sessionmaker, Query
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from main import app as fastapi_app
from database import get_db
from models import Base

# Monkey patch httpx Response per offrire get_json() come Flask Response
httpx.Response.get_json = lambda self: self.json()

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Collega property .query a Base per compatibilità retroattiva nei test
class CurrentQueryProperty:
    def __get__(self, instance, owner):
        # Usa una sessione aperta o crea temporanea
        return Query(owner, session=TestingSessionLocal())

Base.query = CurrentQueryProperty()

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
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

    class AppContextMock:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class ApplicationMock:
        def app_context(self):
            return AppContextMock()

    client_instance = TestClient(fastapi_app)
    client_instance.application = ApplicationMock()

    yield client_instance
    fastapi_app.dependency_overrides.clear()
