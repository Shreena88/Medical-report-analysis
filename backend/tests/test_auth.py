"""Unit tests for the auth service and auth router.

Tests:
- Duplicate email registration returns 409
- Invalid credentials login returns 401
- JWT contains correct subject and expiry claims
- UserProfile response never includes password_hash

Uses mongomock-motor for an in-memory MongoDB and httpx AsyncClient for
route-level tests.  Settings are monkeypatched so no real .env file is needed.
"""

import pytest
import pytest_asyncio
from datetime import timedelta, datetime, timezone

import mongomock_motor
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Patch settings BEFORE any app code is imported so the required env vars
# are present and the module-level `settings = Settings()` call succeeds.
# ---------------------------------------------------------------------------

import os

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")
os.environ.setdefault("JWT_EXPIRY_MINUTES", "60")

# Now safe to import app modules
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    register_user,
    verify_token,
)
from app.models.user import UserProfile
from jose import jwt as jose_jwt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_db():
    """Return an in-memory mongomock-motor database with indexes pre-created."""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client["testdb"]
    # Create the unique email index so DuplicateKeyError is raised correctly
    from pymongo import ASCENDING
    await db["users"].create_index([("email", ASCENDING)], unique=True)
    return db


@pytest_asyncio.fixture
async def app_with_mock_db(mock_db):
    """Build a minimal FastAPI app wired to the mock DB."""
    # Import here so the settings env vars are already set
    from app.main import create_app
    from app import dependencies
    from app.database import get_database

    application = create_app()

    # Override the get_database dependency to use mock_db
    application.dependency_overrides[get_database] = lambda: mock_db

    return application


@pytest_asyncio.fixture
async def async_client(app_with_mock_db):
    """Provide an httpx AsyncClient for the test FastAPI app."""
    transport = ASGITransport(app=app_with_mock_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Helper: register a user directly via service (bypasses HTTP layer)
# ---------------------------------------------------------------------------

async def _register(mock_db, email="user@example.com", password="password123", gender="male"):
    return await register_user(email, password, gender, mock_db)


# ===========================================================================
# 3.4 — Auth service unit tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Duplicate email returns 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_409(async_client):
    """Registering the same email twice must return HTTP 409 Conflict."""
    payload = {"email": "dup@example.com", "password": "securePass1", "gender": "female"}

    resp1 = await async_client.post("/auth/signup", json=payload)
    assert resp1.status_code == 201

    resp2 = await async_client.post("/auth/signup", json=payload)
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Invalid credentials return 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(async_client):
    """Logging in with wrong password must return HTTP 401."""
    # Register first
    await async_client.post(
        "/auth/signup",
        json={"email": "login_test@example.com", "password": "validPass99", "gender": "male"},
    )

    # Attempt login with wrong password
    resp = await async_client.post(
        "/auth/login",
        json={"email": "login_test@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert "invalid credentials" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(async_client):
    """Logging in with an email that was never registered returns 401."""
    resp = await async_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "doesntmatter"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# JWT contains correct subject and expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jwt_contains_correct_subject(mock_db):
    """The JWT sub claim must equal the user's string _id."""
    user = await _register(mock_db, email="jwt_sub@example.com")
    token = create_access_token(subject=str(user.id))

    from app.config import settings
    payload = jose_jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])

    assert payload["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_jwt_contains_expiry_claim(mock_db):
    """The JWT must contain an 'exp' claim that is in the future."""
    user = await _register(mock_db, email="jwt_exp@example.com")
    token = create_access_token(subject=str(user.id))

    from app.config import settings
    payload = jose_jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])

    assert "exp" in payload
    exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert exp_dt > datetime.now(tz=timezone.utc)


@pytest.mark.asyncio
async def test_jwt_expiry_respects_custom_delta(mock_db):
    """A custom expires_delta must be reflected in the JWT exp claim."""
    user = await _register(mock_db, email="jwt_delta@example.com")
    delta = timedelta(minutes=30)
    token = create_access_token(subject=str(user.id), expires_delta=delta)

    from app.config import settings
    payload = jose_jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])

    issued = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    expires = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    # Allow ±5s for execution time
    assert abs((expires - issued).total_seconds() - delta.total_seconds()) < 5


@pytest.mark.asyncio
async def test_verify_token_returns_subject(mock_db):
    """verify_token must return the original subject string."""
    user = await _register(mock_db, email="verify_sub@example.com")
    token = create_access_token(subject=str(user.id))
    returned_sub = verify_token(token)
    assert returned_sub == str(user.id)


@pytest.mark.asyncio
async def test_verify_token_raises_401_on_garbage():
    """verify_token must raise HTTPException 401 for an invalid token."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        verify_token("not.a.valid.jwt.token")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# UserProfile response never includes password_hash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profile_response_excludes_password_hash(async_client):
    """GET /auth/profile must not include password_hash in the response body."""
    # Register
    await async_client.post(
        "/auth/signup",
        json={"email": "profile@example.com", "password": "safePass99", "gender": "female"},
    )

    # Login to get token
    login_resp = await async_client.post(
        "/auth/login",
        json={"email": "profile@example.com", "password": "safePass99"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Fetch profile
    profile_resp = await async_client.get(
        "/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_resp.status_code == 200

    body = profile_resp.json()
    assert "password_hash" not in body
    assert "password" not in body
    assert "email" in body
    assert "gender" in body
    assert "id" in body


@pytest.mark.asyncio
async def test_profile_returns_correct_user_data(async_client):
    """GET /auth/profile must return the right email and gender."""
    await async_client.post(
        "/auth/signup",
        json={"email": "data@example.com", "password": "secureData1", "gender": "male"},
    )

    login_resp = await async_client.post(
        "/auth/login",
        json={"email": "data@example.com", "password": "secureData1"},
    )
    token = login_resp.json()["access_token"]

    profile_resp = await async_client.get(
        "/auth/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = profile_resp.json()
    assert body["email"] == "data@example.com"
    assert body["gender"] == "male"


@pytest.mark.asyncio
async def test_profile_without_token_returns_401(async_client):
    """GET /auth/profile without a token must return 401."""
    resp = await async_client.get("/auth/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_with_invalid_token_returns_401(async_client):
    """GET /auth/profile with a tampered token must return 401."""
    resp = await async_client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer invalidtoken.xyz"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Additional auth service unit tests (service-layer, no HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_user_stores_hashed_password(mock_db):
    """Stored password_hash must differ from the plaintext password."""
    user = await _register(mock_db, email="hash@example.com", password="plaintext")
    assert user.password_hash != "plaintext"
    assert user.password_hash.startswith("$2b$")  # bcrypt hash prefix


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_on_valid_creds(mock_db):
    """authenticate_user must return UserInDB for correct credentials."""
    await _register(mock_db, email="auth@example.com", password="correct_pw")
    result = await authenticate_user("auth@example.com", "correct_pw", mock_db)
    assert result is not None
    assert result.email == "auth@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_on_wrong_password(mock_db):
    """authenticate_user must return None for an incorrect password."""
    await _register(mock_db, email="wrongpw@example.com", password="correct_pw")
    result = await authenticate_user("wrongpw@example.com", "wrong_pw", mock_db)
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_for_missing_user(mock_db):
    """authenticate_user must return None for an unregistered email."""
    result = await authenticate_user("nobody@example.com", "anything", mock_db)
    assert result is None
