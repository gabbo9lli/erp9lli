import os
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
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
