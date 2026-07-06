"""Reference range checker service.

Compares extracted lab test values against the reference_ranges MongoDB
collection and assigns a status of LOW, NORMAL, HIGH, or UNKNOWN to each
LabTest.

All comparisons are performed using Python arithmetic only — no LLM is
ever consulted for this decision (Requirement 5.3, 12.5).
"""

from __future__ import annotations

import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.report import LabTest


async def check_ranges(
    tests: list[LabTest],
    gender: str,
    db: AsyncIOMotorDatabase,
) -> list[LabTest]:
    """Compare each LabTest value against its reference range.

    For each test:
      1. Query the ``reference_ranges`` collection by ``test_name`` (case-
         insensitive exact match) OR by the ``aliases`` array (case-insensitive
         exact match on any element).
      2. If a matching document is found, select the male or female thresholds
         based on ``gender`` ("male" → male_min / male_max, anything else →
         female_min / female_max).
      3. Classify the value using Python arithmetic:
           - value < min  → "LOW"
           - value > max  → "HIGH"
           - otherwise    → "NORMAL"
      4. If no matching document is found, set status to "UNKNOWN" and continue
         (never raise an exception for an unrecognised test name).

    Parameters
    ----------
    tests:
        List of :class:`~app.models.report.LabTest` objects to classify.
    gender:
        User's reported gender — ``"male"`` selects male thresholds; any
        other value selects female thresholds.
    db:
        Async Motor database handle used to query ``reference_ranges``.

    Returns
    -------
    list[LabTest]
        New list of LabTest objects with the ``status`` field updated.
        The original list is not mutated.
    """
    results: list[LabTest] = []

    for test in tests:
        status = await _classify_test(test, gender, db)
        # LabTest is not frozen, but we use model_copy for safety and clarity
        updated = test.model_copy(update={"status": status})
        results.append(updated)

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _classify_test(
    test: LabTest,
    gender: str,
    db: AsyncIOMotorDatabase,
) -> str:
    """Return the status string for a single test.

    Returns one of "LOW", "NORMAL", "HIGH", or "UNKNOWN".
    Never raises.
    """
    try:
        ref = await _lookup_reference(test.test_name, db)
    except Exception:
        # Defensive: any DB error → treat as unknown
        return "UNKNOWN"

    if ref is None:
        return "UNKNOWN"

    # Select thresholds based on gender
    if gender == "male":
        min_val: float = ref["male_min"]
        max_val: float = ref["male_max"]
    else:
        min_val = ref["female_min"]
        max_val = ref["female_max"]

    # Pure Python arithmetic — no LLM (Requirements 5.3, 12.5)
    if test.value < min_val:
        return "LOW"
    if test.value > max_val:
        return "HIGH"
    return "NORMAL"


async def _lookup_reference(
    test_name: str,
    db: AsyncIOMotorDatabase,
) -> dict | None:
    """Query reference_ranges by test_name or aliases (case-insensitive).

    Returns the raw MongoDB document dict, or None if not found.
    """
    escaped = re.escape(test_name)
    query_filter = {
        "$or": [
            {
                "test_name": {
                    "$regex": f"^{escaped}$",
                    "$options": "i",
                }
            },
            {
                "aliases": {
                    "$regex": f"^{escaped}$",
                    "$options": "i",
                }
            },
        ]
    }
    return await db["reference_ranges"].find_one(query_filter)
