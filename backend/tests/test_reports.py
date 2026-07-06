"""Unit tests for reports CRUD and trends endpoints.

Tests:
- GET /reports returns only the current user's reports
- GET /report/{id} returns the report on success
- GET /report/{id} returns 403 for another user's report
- GET /report/{id} returns 404 for non-existent reports
- DELETE /report/{id} deletes the report and removes the local file
- DELETE /report/{id} returns 403 for another user's report
- GET /trends/{test_name} returns historical data sorted asc by date
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import mongomock_motor
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from pymongo import ASCENDING

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-reports-tests")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")

from app.database import get_database
from app.main import create_app
from app.services.auth_service import create_access_token, register_user


@pytest_asyncio.fixture
async def mock_db():
    """In-memory mongomock-motor database with required indexes."""
    client = mongomock_motor.AsyncMongoMockClient()
    db = client["testdb"]
    await db["users"].create_index([("email", ASCENDING)], unique=True)
    return db


@pytest_asyncio.fixture
async def app_with_mock_db(mock_db):
    """FastAPI app wired to the mock DB."""
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
async def user1(mock_db):
    """Register user 1 and return a dict with user object and auth headers."""
    user = await register_user(
        email="user1@example.com",
        password="password123",
        gender="male",
        db=mock_db,
    )
    token = create_access_token(subject=str(user.id))
    return {
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest_asyncio.fixture
async def user2(mock_db):
    """Register user 2 and return a dict with user object and auth headers."""
    user = await register_user(
        email="user2@example.com",
        password="password123",
        gender="female",
        db=mock_db,
    )
    token = create_access_token(subject=str(user.id))
    return {
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_get_reports_returns_only_owners_reports(async_client, mock_db, user1, user2):
    """GET /reports must return only reports belonging to the calling user."""
    # Insert report for user 1
    await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "user1_report.pdf",
        "file_path": "uploads/u1.pdf",
        "uploaded_at": datetime.now(tz=timezone.utc),
        "status": "complete",
        "ocr_text": "Sample text",
        "lab_tests": [],
    })

    # Insert report for user 2
    await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user2["user"].id)),
        "file_name": "user2_report.pdf",
        "file_path": "uploads/u2.pdf",
        "uploaded_at": datetime.now(tz=timezone.utc),
        "status": "complete",
        "ocr_text": "Sample text 2",
        "lab_tests": [],
    })

    # Call /reports as user 1
    resp1 = await async_client.get("/reports", headers=user1["headers"])
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1
    assert data1[0]["file_name"] == "user1_report.pdf"

    # Call /reports as user 2
    resp2 = await async_client.get("/reports", headers=user2["headers"])
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert data2[0]["file_name"] == "user2_report.pdf"


@pytest.mark.asyncio
async def test_get_report_by_id_success_and_failures(async_client, mock_db, user1, user2):
    """GET /report/{id} owner checks and 404 errors."""
    # Insert a report for user 1
    res = await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "report.pdf",
        "file_path": "uploads/rep.pdf",
        "uploaded_at": datetime.now(tz=timezone.utc),
        "status": "complete",
        "ocr_text": "Sample text",
        "lab_tests": [],
    })
    report_id = str(res.inserted_id)

    # Success: User 1 requests their own report
    resp = await async_client.get(f"/report/{report_id}", headers=user1["headers"])
    assert resp.status_code == 200
    assert resp.json()["file_name"] == "report.pdf"

    # Failure: User 2 requests User 1's report -> 403 Forbidden
    resp_403 = await async_client.get(f"/report/{report_id}", headers=user2["headers"])
    assert resp_403.status_code == 403

    # Failure: Non-existent report ID -> 404 Not Found
    fake_id = str(ObjectId())
    resp_404 = await async_client.get(f"/report/{fake_id}", headers=user1["headers"])
    assert resp_404.status_code == 404

    # Failure: Invalid report ID format -> 404 Not Found
    resp_invalid = await async_client.get("/report/invalid-id", headers=user1["headers"])
    assert resp_invalid.status_code == 404


@pytest.mark.asyncio
async def test_delete_report_success_removes_file(async_client, mock_db, user1, user2, tmp_path):
    """DELETE /report/{id} deletes the DB document and the local file on success."""
    # Create a temporary file to simulate the report file
    temp_report_file = tmp_path / "dummy_report.pdf"
    temp_report_file.write_bytes(b"dummy pdf bytes")
    assert temp_report_file.exists()

    # Insert report pointing to this file
    res = await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "delete_me.pdf",
        "file_path": str(temp_report_file),
        "uploaded_at": datetime.now(tz=timezone.utc),
        "status": "complete",
        "ocr_text": "Sample text",
        "lab_tests": [],
    })
    report_id = str(res.inserted_id)

    # 403: User 2 tries to delete User 1's report
    resp_403 = await async_client.delete(f"/report/{report_id}", headers=user2["headers"])
    assert resp_403.status_code == 403
    assert temp_report_file.exists()
    assert await mock_db["reports"].find_one({"_id": ObjectId(report_id)}) is not None

    # Success: User 1 deletes their own report
    resp_delete = await async_client.delete(f"/report/{report_id}", headers=user1["headers"])
    assert resp_delete.status_code == 200
    assert not temp_report_file.exists()
    assert await mock_db["reports"].find_one({"_id": ObjectId(report_id)}) is None


@pytest.mark.asyncio
async def test_get_trends_returns_ordered_points(async_client, mock_db, user1):
    """GET /trends/{test_name} returns test values sorted chronologically by uploaded_at."""
    # Insert reports with different upload dates
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 3, tzinfo=timezone.utc)

    # Insert reports out of chronological order to verify sorting
    await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "r1.pdf",
        "file_path": "uploads/r1.pdf",
        "uploaded_at": t1,
        "status": "complete",
        "lab_tests": [{"test_name": "Hemoglobin", "value": 13.5, "unit": "g/dL", "reference_range": "13.5-17.5", "status": "NORMAL"}],
    })

    await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "r2.pdf",
        "file_path": "uploads/r2.pdf",
        "uploaded_at": t2,
        "status": "complete",
        "lab_tests": [{"test_name": "hemoglobin", "value": 15.2, "unit": "g/dL", "reference_range": "13.5-17.5", "status": "NORMAL"}],
    })

    await mock_db["reports"].insert_one({
        "user_id": ObjectId(str(user1["user"].id)),
        "file_name": "r3.pdf",
        "file_path": "uploads/r3.pdf",
        "uploaded_at": t3,
        "status": "complete",
        "lab_tests": [{"test_name": "HEMOGLOBIN ", "value": 14.1, "unit": "g/dL", "reference_range": "13.5-17.5", "status": "NORMAL"}],
    })

    # Call /trends/hemoglobin (case-insensitive test)
    resp = await async_client.get("/trends/hemoglobin", headers=user1["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3

    # Verify chronological order (t1 -> t3 -> t2)
    assert data[0]["value"] == 13.5
    assert data[1]["value"] == 14.1
    assert data[2]["value"] == 15.2

    # Verify all fields are present
    assert data[0]["report_id"] is not None
    assert data[0]["unit"] == "g/dL"
    assert data[0]["status"] == "NORMAL"
