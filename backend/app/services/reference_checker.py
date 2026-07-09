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
      3. Classify the value using a Z-score calculation:
            - mean = (min + max) / 2
            - sd = (max - min) / 4 (assume the range is 4 standard deviations wide)
            - z = (value - mean) / sd (if sd is 0, z = 0)
            - z in [-1, +1] -> "NORMAL"
            - z in [-2, -1) -> "SLIGHTLY_LOW"
            - z < -2        -> "SIGNIFICANTLY_LOW"
            - z in (1, 2]   -> "SLIGHTLY_HIGH"
            - z > 2         -> "SIGNIFICANTLY_HIGH"
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
    import asyncio

    async def _classify_and_copy(test: LabTest) -> LabTest:
        status = await _classify_test(test, gender, db)
        return test.model_copy(update={"status": status})

    # Run lookups concurrently using asyncio.gather
    results = await asyncio.gather(*(_classify_and_copy(test) for test in tests))
    return list(results)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _classify_test(
    test: LabTest,
    gender: str,
    db: AsyncIOMotorDatabase,
) -> str:
    """Return the status string for a single test using Z-score classification.

    Returns one of "NORMAL", "SLIGHTLY_LOW", "SIGNIFICANTLY_LOW", "SLIGHTLY_HIGH",
    "SIGNIFICANTLY_HIGH", or "UNKNOWN".
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

    # Calculate estimated mean and standard deviation
    mean = (min_val + max_val) / 2.0
    sd = (max_val - min_val) / 4.0

    if sd <= 0.0:
        z = 0.0
    else:
        z = (test.value - mean) / sd
        z = round(z, 9)  # Avoid floating-point precision issues at boundaries

    # Z-score based classification
    if -1.0 <= z <= 1.0:
        return "NORMAL"
    elif -2.0 <= z < -1.0:
        return "SLIGHTLY_LOW"
    elif z < -2.0:
        return "SIGNIFICANTLY_LOW"
    elif 1.0 < z <= 2.0:
        return "SLIGHTLY_HIGH"
    else:  # z > 2.0
        return "SIGNIFICANTLY_HIGH"


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
