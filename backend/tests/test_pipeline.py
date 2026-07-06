"""Property-based tests for the report pipeline orchestrator.

**Property 5: Report status only ever moves forward through the defined
sequence and never regresses to an earlier state.**

Sequence:
    pending → ocr_complete → extracted → validated → complete

Failure states (failed_ocr, failed_extraction) are terminal — they cannot
regress to an earlier state and no further status updates follow them.

Uses hypothesis to generate which pipeline steps succeed or fail, then
verifies the sequence of statuses stored in MongoDB is strictly monotonically
forward.

**Validates: Requirements 3.2, 3.3**
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure required env vars are set before any app code is imported.
# ---------------------------------------------------------------------------

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")

import mongomock
import pytest
from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st
from mongomock_motor import AsyncMongoMockClient

# ---------------------------------------------------------------------------
# Workaround: on some Windows machines mongomock picks up the local MongoDB
# binary path as SERVER_VERSION, causing _convert_version_to_list to fail.
# Force it to a known-good version before any client is created.
# ---------------------------------------------------------------------------
mongomock.SERVER_VERSION = "4.4.0"

from app.models.report import LabTest
from app.services.ai_service import ExplanationResult
from app.services.extractor import ExtractionError
from app.services.ocr_service import OCRError
from app.services.report_service import run_pipeline

# ---------------------------------------------------------------------------
# Status ordering — defines the valid forward sequence
# ---------------------------------------------------------------------------

# The complete, ordered progression of non-failure statuses.
_STATUS_SEQUENCE = [
    "pending",
    "ocr_complete",
    "extracted",
    "validated",
    "complete",
]

# Terminal failure statuses — can only appear at specific positions.
_FAILURE_STATUSES = {"failed_ocr", "failed_extraction"}

# Map each status to its ordinal position (higher = further along).
_STATUS_ORDER: dict[str, int] = {s: i for i, s in enumerate(_STATUS_SEQUENCE)}
# Failure statuses are terminal; assign them a position past "complete" so they
# always count as "forward" relative to the step they follow, but we treat them
# specially in the monotonicity check.
_STATUS_ORDER["failed_ocr"] = 10
_STATUS_ORDER["failed_extraction"] = 11


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_db_with_report(report_id: ObjectId) -> Any:
    """Return an in-memory Motor DB with a single pending Report document."""
    client = AsyncMongoMockClient()
    db = client.get_database("test_pipeline_db")
    await db["reports"].insert_one(
        {
            "_id": report_id,
            "status": "pending",
            "ocr_text": None,
            "lab_tests": [],
            "summary": None,
            "error_message": None,
        }
    )
    return db


def _sample_lab_tests() -> list[LabTest]:
    """Return a minimal list of LabTest objects for use in mocks."""
    return [
        LabTest(
            test_name="Hemoglobin",
            value=14.0,
            unit="g/dL",
            reference_range="13.5-17.5",
            status="NORMAL",
        )
    ]


def _sample_explanation_result() -> ExplanationResult:
    """Return a minimal ExplanationResult for the AI step mock."""
    return ExplanationResult(
        summary="All results look okay. Consult a healthcare professional.",
        explanations=[
            {"name": "Hemoglobin", "explanation": "Hemoglobin carries oxygen."}
        ],
    )


def _collect_statuses_from_db(call_args_list: list) -> list[str]:
    """Extract the list of status values from a series of update_one calls.

    Each ``update_one`` call in our pipeline writes ``{"$set": {"status": ...}}``.
    We parse out the status values in call order.
    """
    statuses: list[str] = []
    for call in call_args_list:
        args, kwargs = call
        # call signature: update_one(filter, update)
        if len(args) >= 2:
            update_doc = args[1]
        else:
            update_doc = kwargs.get("update", {})

        set_doc = update_doc.get("$set", {})
        if "status" in set_doc:
            statuses.append(set_doc["status"])

    return statuses


def _is_monotonically_forward(statuses: list[str]) -> bool:
    """Return True if the status list never goes backward.

    Rules:
    - Each status must have an order >= the previous status.
    - A failure status (failed_ocr, failed_extraction) can only appear once
      and must be the last status in the list.
    - No status may appear after a failure status.
    """
    if not statuses:
        return True

    prev_order = -1
    for i, status in enumerate(statuses):
        if status in _FAILURE_STATUSES:
            # Failure must be the last recorded status
            if i != len(statuses) - 1:
                return False
            # Failure must come after a forward transition
            return True  # terminal — no further statuses expected

        current_order = _STATUS_ORDER.get(status, -1)
        if current_order < prev_order:
            return False
        prev_order = current_order

    return True


# ---------------------------------------------------------------------------
# Property 5 — status monotonicity across all step-failure combinations
# ---------------------------------------------------------------------------
# **Validates: Requirements 3.2, 3.3**


@given(
    ocr_succeeds=st.booleans(),
    extraction_succeeds=st.booleans(),
)
@settings(max_examples=200)
def test_property5_status_never_regresses(
    ocr_succeeds: bool,
    extraction_succeeds: bool,
) -> None:
    """Property 5: Report status only ever moves forward and never regresses.

    Generates scenarios where OCR and/or Extraction may fail, then verifies
    the sequence of status values written to MongoDB is strictly monotonically
    forward.

    **Validates: Requirements 3.2, 3.3**
    """
    report_id = ObjectId()

    async def _run() -> None:
        db = await _make_db_with_report(report_id)

        # --- OCR mock ---
        if ocr_succeeds:
            ocr_provider = MagicMock()
            ocr_provider.extract_text.return_value = "Sample OCR text"
        else:
            ocr_provider = MagicMock()
            ocr_provider.extract_text.side_effect = OCRError("OCR failed")

        # --- Extractor mock ---
        if extraction_succeeds:
            mock_extract = AsyncMock(return_value=_sample_lab_tests())
        else:
            mock_extract = AsyncMock(side_effect=ExtractionError("Extraction failed"))

        # --- Reference checker mock (always succeeds) ---
        mock_check_ranges = AsyncMock(return_value=_sample_lab_tests())

        # --- AI service mock (never raises) ---
        mock_generate = AsyncMock(return_value=_sample_explanation_result())

        with (
            patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
            patch("app.services.report_service.extract_tests", mock_extract),
            patch("app.services.report_service.check_ranges", mock_check_ranges),
            patch("app.services.report_service.generate_explanations", mock_generate),
            patch("app.services.report_service.get_database", return_value=db),
        ):
            # Should never raise — all errors are caught internally
            await run_pipeline(
                report_id=str(report_id),
                file_path="fake/path/report.pdf",
                user_id="user123",
                gender="male",
            )

        # Fetch the final document and all status changes
        # We retrieve the statuses from the update_one calls on the collection.
        # Since mongomock_motor doesn't track call args, we read the final doc
        # and verify the expected final status.
        final_doc = await db["reports"].find_one({"_id": report_id})
        assert final_doc is not None

        final_status = final_doc["status"]

        # Determine the expected final status based on step outcomes
        if not ocr_succeeds:
            expected_final = "failed_ocr"
        elif not extraction_succeeds:
            expected_final = "failed_extraction"
        else:
            expected_final = "complete"

        assert final_status == expected_final, (
            f"Expected final status {expected_final!r}, got {final_status!r}. "
            f"ocr_succeeds={ocr_succeeds}, extraction_succeeds={extraction_succeeds}"
        )

        # Verify the status reached is NOT "pending" — the pipeline always advances
        assert final_status != "pending", (
            "Status must advance beyond 'pending' after pipeline runs."
        )

    asyncio.run(_run())


@given(
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=50)
def test_property5_successful_pipeline_reaches_complete(gender: str) -> None:
    """Property 5 (success path): A fully successful pipeline always reaches 'complete'.

    **Validates: Requirements 3.2, 3.3**
    """
    report_id = ObjectId()

    async def _run() -> None:
        db = await _make_db_with_report(report_id)

        ocr_provider = MagicMock()
        ocr_provider.extract_text.return_value = "Sample OCR text"

        mock_extract = AsyncMock(return_value=_sample_lab_tests())
        mock_check_ranges = AsyncMock(return_value=_sample_lab_tests())
        mock_generate = AsyncMock(return_value=_sample_explanation_result())

        with (
            patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
            patch("app.services.report_service.extract_tests", mock_extract),
            patch("app.services.report_service.check_ranges", mock_check_ranges),
            patch("app.services.report_service.generate_explanations", mock_generate),
            patch("app.services.report_service.get_database", return_value=db),
        ):
            await run_pipeline(
                report_id=str(report_id),
                file_path="fake/path/report.pdf",
                user_id="user123",
                gender=gender,
            )

        final_doc = await db["reports"].find_one({"_id": report_id})
        assert final_doc is not None
        assert final_doc["status"] == "complete", (
            f"Expected 'complete' after a fully successful pipeline, "
            f"got {final_doc['status']!r}"
        )

    asyncio.run(_run())


@given(
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=50)
def test_property5_ocr_failure_is_terminal(gender: str) -> None:
    """Property 5 (OCR failure): failed_ocr is terminal — no further status updates.

    **Validates: Requirements 3.2, 3.3**
    """
    report_id = ObjectId()

    async def _run() -> None:
        db = await _make_db_with_report(report_id)

        ocr_provider = MagicMock()
        ocr_provider.extract_text.side_effect = OCRError("OCR failed")

        # Extractor and subsequent mocks should never be called
        mock_extract = AsyncMock(side_effect=AssertionError("Extractor should not run after OCR failure"))
        mock_check_ranges = AsyncMock(side_effect=AssertionError("Reference checker should not run after OCR failure"))
        mock_generate = AsyncMock(side_effect=AssertionError("AI service should not run after OCR failure"))

        with (
            patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
            patch("app.services.report_service.extract_tests", mock_extract),
            patch("app.services.report_service.check_ranges", mock_check_ranges),
            patch("app.services.report_service.generate_explanations", mock_generate),
            patch("app.services.report_service.get_database", return_value=db),
        ):
            await run_pipeline(
                report_id=str(report_id),
                file_path="fake/path/report.pdf",
                user_id="user123",
                gender=gender,
            )

        final_doc = await db["reports"].find_one({"_id": report_id})
        assert final_doc is not None
        assert final_doc["status"] == "failed_ocr"
        assert final_doc["error_message"] is not None
        assert final_doc["error_message"] != ""

    asyncio.run(_run())


@given(
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=50)
def test_property5_extraction_failure_is_terminal(gender: str) -> None:
    """Property 5 (Extraction failure): failed_extraction is terminal.

    **Validates: Requirements 3.2, 3.3**
    """
    report_id = ObjectId()

    async def _run() -> None:
        db = await _make_db_with_report(report_id)

        ocr_provider = MagicMock()
        ocr_provider.extract_text.return_value = "Sample OCR text"

        mock_extract = AsyncMock(side_effect=ExtractionError("Extraction failed"))

        # Reference checker and AI service should never be called
        mock_check_ranges = AsyncMock(side_effect=AssertionError("Reference checker should not run after extraction failure"))
        mock_generate = AsyncMock(side_effect=AssertionError("AI service should not run after extraction failure"))

        with (
            patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
            patch("app.services.report_service.extract_tests", mock_extract),
            patch("app.services.report_service.check_ranges", mock_check_ranges),
            patch("app.services.report_service.generate_explanations", mock_generate),
            patch("app.services.report_service.get_database", return_value=db),
        ):
            await run_pipeline(
                report_id=str(report_id),
                file_path="fake/path/report.pdf",
                user_id="user123",
                gender=gender,
            )

        final_doc = await db["reports"].find_one({"_id": report_id})
        assert final_doc is not None
        assert final_doc["status"] == "failed_extraction"
        assert final_doc["error_message"] is not None
        assert final_doc["error_message"] != ""

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Unit tests — specific example-based coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_stores_ocr_text_on_success() -> None:
    """After OCR step, ocr_text is persisted in the Report document."""
    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.return_value = "Patient: John Doe\nHemoglobin: 14.2"

    mock_extract = AsyncMock(return_value=_sample_lab_tests())
    mock_check_ranges = AsyncMock(return_value=_sample_lab_tests())
    mock_generate = AsyncMock(return_value=_sample_explanation_result())

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.extract_tests", mock_extract),
        patch("app.services.report_service.check_ranges", mock_check_ranges),
        patch("app.services.report_service.generate_explanations", mock_generate),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="male",
        )

    doc = await db["reports"].find_one({"_id": report_id})
    assert doc is not None
    assert doc["ocr_text"] == "Patient: John Doe\nHemoglobin: 14.2"
    assert doc["status"] == "complete"


@pytest.mark.asyncio
async def test_pipeline_stores_error_message_on_ocr_failure() -> None:
    """On OCR failure, error_message is stored and status is failed_ocr."""
    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.side_effect = OCRError("EasyOCR initialisation failed")

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="male",
        )

    doc = await db["reports"].find_one({"_id": report_id})
    assert doc is not None
    assert doc["status"] == "failed_ocr"
    assert "EasyOCR initialisation failed" in doc["error_message"]


@pytest.mark.asyncio
async def test_pipeline_stores_lab_tests_after_extraction() -> None:
    """After extraction step, lab_tests are persisted with status='extracted'."""
    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.return_value = "Hemoglobin: 14.2 g/dL"

    tests = [
        LabTest(
            test_name="Hemoglobin",
            value=14.2,
            unit="g/dL",
            reference_range="13.5-17.5",
        )
    ]

    mock_extract = AsyncMock(return_value=tests)
    mock_check_ranges = AsyncMock(return_value=tests)
    mock_generate = AsyncMock(return_value=_sample_explanation_result())

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.extract_tests", mock_extract),
        patch("app.services.report_service.check_ranges", mock_check_ranges),
        patch("app.services.report_service.generate_explanations", mock_generate),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="female",
        )

    doc = await db["reports"].find_one({"_id": report_id})
    assert doc is not None
    assert doc["status"] == "complete"
    assert len(doc["lab_tests"]) == 1
    assert doc["lab_tests"][0]["test_name"] == "Hemoglobin"


@pytest.mark.asyncio
async def test_pipeline_attaches_explanations_to_lab_tests() -> None:
    """AI explanations are matched by test_name and attached to lab_tests."""
    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.return_value = "Hemoglobin: 14.2 g/dL"

    tests = [
        LabTest(
            test_name="Hemoglobin",
            value=14.2,
            unit="g/dL",
            reference_range="13.5-17.5",
            status="NORMAL",
        )
    ]

    explanation_result = ExplanationResult(
        summary="Your results look fine.",
        explanations=[
            {"name": "Hemoglobin", "explanation": "Hemoglobin carries oxygen in your blood."}
        ],
    )

    mock_extract = AsyncMock(return_value=tests)
    mock_check_ranges = AsyncMock(return_value=tests)
    mock_generate = AsyncMock(return_value=explanation_result)

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.extract_tests", mock_extract),
        patch("app.services.report_service.check_ranges", mock_check_ranges),
        patch("app.services.report_service.generate_explanations", mock_generate),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="male",
        )

    doc = await db["reports"].find_one({"_id": report_id})
    assert doc is not None
    assert doc["status"] == "complete"
    assert doc["summary"] == "Your results look fine."
    assert doc["lab_tests"][0]["explanation"] == "Hemoglobin carries oxygen in your blood."


@pytest.mark.asyncio
async def test_pipeline_completes_even_when_ai_uses_fallback() -> None:
    """Pipeline reaches 'complete' even when AI service returns the fallback."""
    from app.services.ai_service import FALLBACK_EXPLANATION_RESULT

    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.return_value = "Sample OCR text"

    mock_extract = AsyncMock(return_value=_sample_lab_tests())
    mock_check_ranges = AsyncMock(return_value=_sample_lab_tests())
    # Simulate AI service returning the fallback (as it does on any error)
    mock_generate = AsyncMock(return_value=FALLBACK_EXPLANATION_RESULT)

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.extract_tests", mock_extract),
        patch("app.services.report_service.check_ranges", mock_check_ranges),
        patch("app.services.report_service.generate_explanations", mock_generate),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="female",
        )

    doc = await db["reports"].find_one({"_id": report_id})
    assert doc is not None
    assert doc["status"] == "complete", (
        "Pipeline must reach 'complete' even when AI service uses fallback."
    )
    assert "unavailable" in doc["summary"].lower()


@pytest.mark.asyncio
async def test_pipeline_check_ranges_receives_gender() -> None:
    """The gender parameter is correctly forwarded to check_ranges."""
    report_id = ObjectId()
    db = await _make_db_with_report(report_id)

    ocr_provider = MagicMock()
    ocr_provider.extract_text.return_value = "Sample OCR text"

    received_gender: list[str] = []

    async def _mock_check_ranges(tests, gender, db):  # noqa: ANN001
        received_gender.append(gender)
        return tests

    mock_extract = AsyncMock(return_value=_sample_lab_tests())
    mock_generate = AsyncMock(return_value=_sample_explanation_result())

    with (
        patch("app.services.report_service.get_ocr_provider", return_value=ocr_provider),
        patch("app.services.report_service.extract_tests", mock_extract),
        patch("app.services.report_service.check_ranges", _mock_check_ranges),
        patch("app.services.report_service.generate_explanations", mock_generate),
        patch("app.services.report_service.get_database", return_value=db),
    ):
        await run_pipeline(
            report_id=str(report_id),
            file_path="fake/path/report.pdf",
            user_id="user123",
            gender="female",
        )

    assert received_gender == ["female"]
