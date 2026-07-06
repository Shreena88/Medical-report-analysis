"""Pydantic models for the User domain.

Models:
- UserCreate   — input model for registration (email, password, gender)
- UserInDB     — full document as stored in MongoDB (includes password_hash)
- UserProfile  — safe read model (excludes password_hash)
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.base import PyObjectId


class UserCreate(BaseModel):
    """Request body for POST /auth/signup."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8)
    gender: Literal["male", "female"]


class UserInDB(BaseModel):
    """Full user document as stored in MongoDB.

    The `id` field maps to MongoDB's `_id` (via the `alias` parameter).
    populate_by_name=True allows construction with either "id" or "_id".
    """

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    gender: str
    password_hash: str
    created_at: datetime


class UserProfile(BaseModel):
    """Public-facing user profile — password_hash is intentionally excluded."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    email: EmailStr
    gender: str
    created_at: datetime
