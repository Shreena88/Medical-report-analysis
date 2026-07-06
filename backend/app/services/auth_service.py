"""Authentication service: user registration, login, JWT creation/verification.

Uses passlib[bcrypt] for password hashing (work factor ≥ 12) and
python-jose[cryptography] for HS256 JWT signing.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.models.user import UserInDB

# ---------------------------------------------------------------------------
# Password hashing context — bcrypt, work factor 12
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------

async def register_user(
    email: str,
    password: str,
    gender: str,
    db: AsyncIOMotorDatabase,
) -> UserInDB:
    """Create a new user document in the *users* collection.

    Raises:
        HTTPException 409: if the email is already registered.
    """
    password_hash = _hash_password(password)
    now = datetime.now(tz=timezone.utc)

    doc = {
        "email": email,
        "password_hash": password_hash,
        "gender": gender,
        "created_at": now,
    }

    try:
        result = await db["users"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    doc["_id"] = result.inserted_id
    return UserInDB(**doc)


# ---------------------------------------------------------------------------
# User authentication
# ---------------------------------------------------------------------------

async def authenticate_user(
    email: str,
    password: str,
    db: AsyncIOMotorDatabase,
) -> Optional[UserInDB]:
    """Return the UserInDB if credentials are valid, otherwise None."""
    raw = await db["users"].find_one({"email": email})
    if raw is None:
        return None
    if not _verify_password(password, raw["password_hash"]):
        return None
    return UserInDB(**raw)


# ---------------------------------------------------------------------------
# JWT creation
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Sign and return an HS256 JWT with the given *subject* (user_id as str).

    The expiry defaults to *JWT_EXPIRY_MINUTES* from settings when
    *expires_delta* is not provided.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRY_MINUTES)

    now = datetime.now(tz=timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------

def verify_token(token: str) -> str:
    """Decode *token* and return the subject (user_id as str).

    Raises:
        HTTPException 401: if the token is invalid, expired, or missing *sub*.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise credentials_exception

    sub: Optional[str] = payload.get("sub")
    if sub is None:
        raise credentials_exception

    return sub
