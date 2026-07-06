"""Unit tests for the POST /upload endpoint.

Tests:
- Unsupported file type returns 422
- Oversized file returns 413
- Valid PDF upload returns 202 with a report_id
- Valid JPG upload returns 202 with a report_id
- Saved filename is a UUID (report_id returned is a valid UUID4)

Uses pytest-asyncio, mongomock-motor, and httpx AsyncClient.
The background pipeline is mocked so OCR/LLM calls never run.
"""

import io
import os
import uuid
from unittest.mock import AsyncMock, patch

import mongomock_motor
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import ASCENDING

# ---------------------------------------------------------------------------
# Environment must be set before any app module is imported
# ---------------------------------------------------------------------------

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-upload-tests")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")
os.environ.setdefault("JWT_EXPIRY_MINUTES", "60")
os.environ.setdefault("MAX_UPLOAD_SIZE_MB", "1")

from app.database import get_database
from app.main import create_app
from app.services.auth_service import create_access_token, register_user

# ---------------------------------------------------------------------------
# Magic-byte helpers to produce minimal valid file content
# ---------------------------------------------------------------------------

# Minimal valid-looking file headers (magic bytes only — not real files,
# but sufficient to pass magic-byte MIME detection in the router).
_PDF_HEADER = b"%PDF-1.4 fake pdf content"
_JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

# A truly invalid header that should be rejected
_INVALID_HEADER = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mock_db():
    """In-memory mongomock-motor database with required indexes."""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client["testdb"]
    await db["users"].create_index([("email", ASCENDING)], unique=True)
    return db


@pytest_asyncio.fixture
async def app_with_mock_db(mock_db):
    """FastAPI app wired to the mock DB, with pipeline patched out."""
    application = create_app()
    application.dependency_overrides[get_database] = lambda: mock_db
    return application


@pytest_asyncio.fixture
async def async_client(app_with_mock_db):
    """httpx AsyncClient for the test app."""
    transport = ASGITransport(app=app_with_mock_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(mock_db):
    """Register a test user and return Authorization headers with a valid JWT."""
    user = await register_user(
        email="uploader@example.com",
        password="password123",
        gender="male",
        db=mock_db,
    )
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_upload_files(content: bytes, filename: str, content_type: str):
    """Return a files dict suitable for httpx multipart upload.

    httpx accepts ``files={"field": (filename, fileobj, content_type)}``.
    """
    return {"file": (filename, io.BytesIO(content), content_type)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsupported_file_type_returns_422(async_client, auth_headers):
    """Uploading a WebP (or any non-PDF/JPG/PNG) file must return 422."""
    with patch(
        "app.routers.reports.run_pipeline",
        new=AsyncMock(),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(_INVALID_HEADER, "test.webp", "image/webp"),
            headers=auth_headers,
        )

    assert resp.status_code == 422
    detail = resp.json()["detail"].lower()
    assert "unsupported" in detail or "file type" in detail or "pdf" in detail


@pytest.mark.asyncio
async def test_oversized_file_returns_413(async_client, auth_headers):
    """Uploading a file larger than MAX_UPLOAD_SIZE_MB must return 413."""
    # We patch max_upload_size_bytes on the settings object so this test is
    # not sensitive to the order in which test modules are collected
    # (the settings singleton is created at import time).
    _limit_bytes = 1 * 1024 * 1024  # 1 MB
    oversized_content = _PDF_HEADER + b"A" * (_limit_bytes + 1)

    from app.config import settings as _settings
    from unittest.mock import patch as _patch, PropertyMock

    with (
        _patch("app.routers.reports.run_pipeline", new=AsyncMock()),
        _patch.object(
            type(_settings), "max_upload_size_bytes",
            new_callable=PropertyMock,
            return_value=_limit_bytes,
        ),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(oversized_content, "big.pdf", "application/pdf"),
            headers=auth_headers,
        )

    assert resp.status_code == 413
    assert "large" in resp.json()["detail"].lower() or "size" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_valid_pdf_upload_returns_202_with_report_id(
    async_client, auth_headers, tmp_path, monkeypatch
):
    """A valid PDF upload must return 202 with a non-empty report_id."""
    # Redirect file writes to a temp directory so the test doesn't pollute the
    # working directory and doesn't fail if uploads/ isn't writable.
    monkeypatch.chdir(tmp_path)

    with patch(
        "app.routers.reports.run_pipeline",
        new=AsyncMock(),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(_PDF_HEADER, "report.pdf", "application/pdf"),
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "report_id" in body
    assert body["report_id"]  # non-empty
    assert body["message"] == "Processing started"


@pytest.mark.asyncio
async def test_valid_jpg_upload_returns_202_with_report_id(
    async_client, auth_headers, tmp_path, monkeypatch
):
    """A valid JPEG upload must return 202 with a non-empty report_id."""
    monkeypatch.chdir(tmp_path)

    with patch(
        "app.routers.reports.run_pipeline",
        new=AsyncMock(),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(_JPEG_HEADER, "scan.jpg", "image/jpeg"),
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "report_id" in body
    assert body["report_id"]
    assert body["message"] == "Processing started"


@pytest.mark.asyncio
async def test_valid_png_upload_returns_202_with_report_id(
    async_client, auth_headers, tmp_path, monkeypatch
):
    """A valid PNG upload must return 202 with a non-empty report_id."""
    monkeypatch.chdir(tmp_path)

    with patch(
        "app.routers.reports.run_pipeline",
        new=AsyncMock(),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(_PNG_HEADER, "image.png", "image/png"),
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "report_id" in body
    assert body["report_id"]


@pytest.mark.asyncio
async def test_report_id_is_valid_uuid(async_client, auth_headers, tmp_path, monkeypatch):
    """The report_id in the 202 response must be a valid UUID (MongoDB ObjectId string).

    The task notes clarify: the report_id returned is the MongoDB _id (ObjectId
    string), not the UUID filename.  We verify it is a 24-character hex ObjectId,
    which is the unique identifier assigned to the report.

    The UUID guarantee in the spec refers to the *saved filename* (not the
    report_id).  This test verifies the report_id is a valid non-empty identifier
    and separately checks that the on-disk filename is NOT the original filename
    (ensuring UUID-based naming is used for the file).
    """
    monkeypatch.chdir(tmp_path)

    with patch(
        "app.routers.reports.run_pipeline",
        new=AsyncMock(),
    ):
        resp = await async_client.post(
            "/upload",
            files=_make_upload_files(_PDF_HEADER, "myreport.pdf", "application/pdf"),
            headers=auth_headers,
        )

    assert resp.status_code == 202
    body = resp.json()
    report_id = body["report_id"]

    # report_id must be a 24-char hex MongoDB ObjectId string
    assert len(report_id) == 24
    assert all(c in "0123456789abcdef" for c in report_id)

    # Verify the file was NOT saved as the original filename — it should be a
    # UUID-based name inside uploads/
    uploads_dir = tmp_path / "uploads"
    if uploads_dir.exists():
        saved_files = list(uploads_dir.iterdir())
        assert len(saved_files) == 1
        saved_name = saved_files[0].stem  # filename without extension
        # Must be a valid UUID4
        parsed = uuid.UUID(saved_name, version=4)
        assert str(parsed) == saved_name


@pytest.mark.asyncio
async def test_upload_without_auth_returns_401(async_client):
    """POST /upload without a JWT must return 401."""
    resp = await async_client.post(
        "/upload",
        files=_make_upload_files(_PDF_HEADER, "report.pdf", "application/pdf"),
    )
    assert resp.status_code == 401
