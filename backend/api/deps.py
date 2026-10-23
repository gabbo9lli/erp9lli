from typing import Optional, List
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from api.routers.auth import get_request_identity

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    email, username, groups = get_request_identity(request)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated"
        )
    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered"
        )
    return user

def require_auth(roles: Optional[List[str]] = None):
    def auth_checker(request: Request, db: Session = Depends(get_db)) -> User:
        email, username, groups = get_request_identity(request)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )
        user = db.query(User).filter_by(email=email).first()
        if not user:
            # Fallback auto-provisioning
            is_admin = any('admin' in g.lower() for g in groups)
            role = 'Admin' if is_admin else 'User'
            user = User(username=username or email.split('@')[0], email=email, role=role, oauth_provider='oidc')
            db.add(user)
            db.commit()
            db.refresh(user)

        if roles and user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions"
            )
        return user
    return auth_checker
