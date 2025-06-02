from pydantic import BaseModel, EmailStr
from datetime import datetime

class MovieCreate(BaseModel):
    title: str

class MovieResponse(BaseModel):
    id: int
    title: str
    duration: int

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str