"""Report pipeline orchestrator.

Implements the full async pipeline:
    OCR → Extraction → Reference_Check → AI_Explanation

Each step updates the Report document in MongoDB with status and results.
Failures at OCR and Extraction steps are terminal (pipeline stops).
Reference_Check always succeeds (UNKNOWN for unmatched tests).
AI_Explanation never raises — uses a safe fallback on any failure.

This function is launched as a FastAPI BackgroundTask and must NOT raise
exceptions to the caller.  All errors are caught and stored on the Report.
"""

from __future__ import annotations

import logging

from bson import ObjectId

from app.database import get_database
from app.models.report import LabTest
from app.services.ai_service import generate_explanations
from app.services.extractor import ExtractionError, extract_tests
from app.services.ocr_service import OCRError, get_ocr_provider
from app.services.reference_checker import check_ranges

logger = logging.getLogger(__name__)


async def run_pipeline(
    report_id: str,
    file_path: str,
    user_id: str,
    gender: str,
) -> None:
    """Orchestrate OCR → Extraction → Reference-check → Explanation.

    Sequentially runs each pipeline step and persists intermediate results
    to MongoDB after every step.  The function is intentionally
    exception-safe: any unhandled error is caught, stored in
    ``error_message``, and the pipeline terminates gracefully.

    Parameters
    ----------
    report_id:
        MongoDB ObjectId string of the Report document to update.
    file_path:
        Path to the uploaded file on disk.
    user_id:
        ID of the user who owns this report (used for logging only here;
        ownership is already enforced at upload time).
    gender:
        ``"male"`` or ``"female"`` — used by the Reference_Checker to
        select the correct threshold set.
    """
    db = get_database()
    oid = ObjectId(report_id)

    # ------------------------------------------------------------------
    # Step 1 — OCR
    # ------------------------------------------------------------------
    try:
        ocr_text = get_ocr_provider().extract_text(file_path)
    except OCRError as exc:
        logger.error("run_pipeline[%s]: OCR failed: %s", report_id, exc)
        await db["reports"].update_one(
            {"_id": oid},
            {"$set": {"status": "failed_ocr", "error_message": str(exc)}},
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "run_pipeline[%s]: unexpected error during OCR: %s",
            report_id,
            exc,
            exc_info=True,
        )
        await db["reports"].update_one(
            {"_id": oid},
            {"$set": {"status": "failed_ocr", "error_message": str(exc)}},
        )
        return

    await db["reports"].update_one(
        {"_id": oid},
        {"$set": {"ocr_text": ocr_text, "status": "ocr_complete"}},
    )

    # ------------------------------------------------------------------
    # Step 2 — Extraction
    # ------------------------------------------------------------------
    try:
        tests: list[LabTest] = await extract_tests(ocr_text)
    except ExtractionError as exc:
        logger.error("run_pipeline[%s]: extraction failed: %s", report_id, exc)
        await db["reports"].update_one(
            {"_id": oid},
            {"$set": {"status": "failed_extraction", "error_message": str(exc)}},
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "run_pipeline[%s]: unexpected error during extraction: %s",
            report_id,
            exc,
            exc_info=True,
        )
        await db["reports"].update_one(
            {"_id": oid},
            {"$set": {"status": "failed_extraction", "error_message": str(exc)}},
        )
        return

    await db["reports"].update_one(
        {"_id": oid},
        {
            "$set": {
                "lab_tests": [t.model_dump() for t in tests],
                "status": "extracted",
            }
        },
    )

    # ------------------------------------------------------------------
    # Step 3 — Reference range check (always succeeds)
    # ------------------------------------------------------------------
    tests = await check_ranges(tests, gender, db)

    await db["reports"].update_one(
        {"_id": oid},
        {
            "$set": {
                "lab_tests": [t.model_dump() for t in tests],
                "status": "validated",
            }
        },
    )

    # ------------------------------------------------------------------
    # Step 4 — AI explanation (never raises — uses fallback on failure)
    # ------------------------------------------------------------------
    result = await generate_explanations(tests)

    # Build a lookup from test_name → explanation text
    explanation_map: dict[str, str] = {
        item["name"]: item["explanation"]
        for item in result.explanations
        if "name" in item and "explanation" in item
    }

    # Attach per-test explanations by matching on test_name
    tests_with_explanations = [
        t.model_copy(
            update={"explanation": explanation_map.get(t.test_name, t.explanation)}
        )
        for t in tests
    ]

    await db["reports"].update_one(
        {"_id": oid},
        {
            "$set": {
                "lab_tests": [t.model_dump() for t in tests_with_explanations],
                "summary": result.summary,
                "status": "complete",
            }
        },
    )
