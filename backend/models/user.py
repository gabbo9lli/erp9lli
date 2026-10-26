from datetime import datetime, timedelta
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from .base import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default='User') 
    oauth_provider = Column(String(50), default='oidc', nullable=True)
    reset_token = Column(String(100), unique=True, nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return token
