from typing import Optional, List
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = "User"

class UserCreate(UserBase):
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
