import os
import re
from datetime import datetime, timedelta
import jwt
from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import User
from core.config import settings

router = APIRouter(prefix="/api", tags=["Auth"])

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

def create_access_token(identity: str) -> str:
    payload = {
        "sub": identity,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

def get_request_identity(request: Request):
    email = request.headers.get('X-Forwarded-Email')
    username = request.headers.get('X-Forwarded-Preferred-Username') or request.headers.get('X-Forwarded-User')
    groups_header = request.headers.get('X-Forwarded-Groups', '')
    groups = [g.strip() for g in groups_header.split(',') if g.strip()]

    if not email and settings.is_dev and not settings.is_testing:
        email = settings.DEV_AUTH_USER
        username = username or 'dev'
        groups = [settings.DEV_AUTH_ROLE]

    return email, username, groups

@router.get("/hello")
def hello():
    return {"message": "Hello from backend!", "status": "success"}

@router.get("/data")
def get_data():
    return {"message": "Hello from FastAPI!"}

@router.get("/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    email, username, groups = get_request_identity(request)
    if not email:
        return JSONResponse(
            status_code=401,
            content={"authenticated": False, "error": "No identity found"}
        )

    username = username or email.split('@')[0]
    user = db.query(User).filter_by(email=email).first()
    if not user:
        is_admin = any('admin' in g.lower() for g in groups)
        role = 'Admin' if is_admin else 'User'
        user = User(username=username, email=email, role=role, oauth_provider='oidc')
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter_by(email=email).first()

    return {
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": getattr(user, 'role', 'User')
    }

@router.post("/signup")
async def signup(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get('email')
    password = data.get('password')

    if not email or not re.match(EMAIL_REGEX, email):
        return JSONResponse(status_code=400, content={"error": "Invalid email format"})

    if db.query(User).filter_by(email=email).first():
        return JSONResponse(status_code=400, content={"error": "An account with this email already exists"})

    user = User(username=email, email=email)
    user.set_password(password)
    db.add(user)
    db.commit()
    return JSONResponse(status_code=201, content={"message": "Account created successfully"})

@router.post("/signin")
async def signin(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return JSONResponse(status_code=400, content={"msg": "Email and password are required"})

    user = db.query(User).filter_by(email=email).first()
    if user and user.check_password(password):
        token = create_access_token(identity=user.email)
        return {"access_token": token}

    return JSONResponse(status_code=401, content={"msg": "Bad email or password"})

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get('email')
    password = data.get('password')

    user = db.query(User).filter_by(email=email).first()
    if user and user.check_password(password):
        return {"message": "Logged in", "user": user.email}

    return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

@router.post("/forgot-password")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get('email')
    user = db.query(User).filter_by(email=email).first()
    if user:
        token = user.get_reset_token()
        db.commit()

    return {"message": "If an account exists, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    token = data.get('token')
    new_password = data.get('new_password')

    user = db.query(User).filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.utcnow():
        return JSONResponse(status_code=400, content={"error": "Invalid or expired token"})

    user.set_password(new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()
    return {"message": "Password updated successfully"}
