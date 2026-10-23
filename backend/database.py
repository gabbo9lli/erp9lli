import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
if DB_TYPE in ('postgres', 'postgresql'):
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgresql://') and not db_url.startswith('postgresql+'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    SQLALCHEMY_DATABASE_URL = db_url
else:
    SQLALCHEMY_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./site.db')

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
_SessionFactory = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

def SessionLocal():
    conftest = sys.modules.get('conftest')
    if conftest and getattr(conftest, '_current_test_session', None) is not None:
        return conftest._current_test_session
    return _SessionFactory()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Chiude solo se non è la sessione di test attiva gestita dal fixture
        conftest = sys.modules.get('conftest')
        if not (conftest and getattr(conftest, '_current_test_session', None) is db):
            db.close()
