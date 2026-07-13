from pydantic import BaseModel, EmailStr, field_serializer
from typing import Optional
from datetime import datetime
from app.core.datetime_utils import utc_iso


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: str = "tecnico_n1"
    is_active: bool = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    permissions: list = []
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'last_login')
    def serialize_dt(self, v: Optional[datetime], _info):
        return utc_iso(v)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
