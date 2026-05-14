from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.user import Role


class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
