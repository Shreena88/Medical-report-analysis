"""Property-based tests for the reference range checker service.

**Validates: Requirements 5.2, 5.3, 5.4, 12.5**

Property 3: A value strictly below min → LOW; strictly above max → HIGH;
            within [min, max] → NORMAL.

Property 4: A test_name with no matching reference range always yields
            status UNKNOWN and does not raise an exception.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Ensure required env vars are set before any app code is imported.
# ---------------------------------------------------------------------------

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")

import asyncio
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from mongomock_motor import AsyncMongoMockClient

from app.models.report import LabTest
from app.services.reference_checker import check_ranges

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

# The name of the test entry we seed into the mock DB for property tests.
_KNOWN_TEST_NAME = "TestMarker"
_KNOWN_GENDER_MALE = "male"
_KNOWN_GENDER_FEMALE = "female"

# Shared reference range values used in the mock DB.
_MALE_MIN = 10.0
_MALE_MAX = 20.0
_FEMALE_MIN = 8.0
_FEMALE_MAX = 18.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_db_with_reference(ref_doc: dict[str, Any]):
    """Return an in-memory Motor database pre-seeded with one reference range."""
    client = AsyncMongoMockClient()
    db = client.get_database("test_db")
    await db["reference_ranges"].insert_one(ref_doc)
    return db


async def _make_empty_db():
    """Return an in-memory Motor database with no reference ranges."""
    client = AsyncMongoMockClient()
    db = client.get_database("test_db")
    return db


def _make_lab_test(name: str, value: float) -> LabTest:
    """Create a minimal LabTest with the given name and value."""
    return LabTest(
        test_name=name,
        value=value,
        unit="unit",
        reference_range="n/a",
    )


# ---------------------------------------------------------------------------
# Property 3 — correct status based on arithmetic comparison
# ---------------------------------------------------------------------------
# **Validates: Requirements 5.2, 5.3, 12.5**
#
# Strategy: generate a reference range (min < max) and three distinct values:
#   - below_min:     strictly less than min  → expect "LOW"
#   - within_range:  in [min, max]           → expect "NORMAL"
#   - above_max:     strictly greater than max → expect "HIGH"
# ---------------------------------------------------------------------------


@given(
    min_val=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    range_width=st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    below_offset=st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    above_offset=st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    within_fraction=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=200)
def test_property3_value_below_min_is_low(
    min_val: float,
    range_width: float,
    below_offset: float,
    above_offset: float,
    within_fraction: float,
    gender: str,
) -> None:
    """Property 3: A value strictly below min → LOW.

    **Validates: Requirements 5.2, 5.3, 12.5**
    """
    max_val = min_val + range_width
    value = min_val - below_offset  # guaranteed < min_val

    # Build the reference range document with same values for both genders
    # so the test is gender-agnostic
    ref_doc = {
        "test_name": _KNOWN_TEST_NAME,
        "aliases": [],
        "unit": "unit",
        "male_min": min_val,
        "male_max": max_val,
        "female_min": min_val,
        "female_max": max_val,
        "description": "test",
    }

    lab_test = _make_lab_test(_KNOWN_TEST_NAME, value)

    async def _run():
        db = await _make_db_with_reference(ref_doc)
        results = await check_ranges([lab_test], gender, db)
        assert results[0].status == "LOW", (
            f"Expected LOW for value={value} < min={min_val}, got {results[0].status}"
        )

    asyncio.run(_run())


@given(
    min_val=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    range_width=st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    above_offset=st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=200)
def test_property3_value_above_max_is_high(
    min_val: float,
    range_width: float,
    above_offset: float,
    gender: str,
) -> None:
    """Property 3: A value strictly above max → HIGH.

    **Validates: Requirements 5.2, 5.3, 12.5**
    """
    max_val = min_val + range_width
    value = max_val + above_offset  # guaranteed > max_val

    ref_doc = {
        "test_name": _KNOWN_TEST_NAME,
        "aliases": [],
        "unit": "unit",
        "male_min": min_val,
        "male_max": max_val,
        "female_min": min_val,
        "female_max": max_val,
        "description": "test",
    }

    lab_test = _make_lab_test(_KNOWN_TEST_NAME, value)

    async def _run():
        db = await _make_db_with_reference(ref_doc)
        results = await check_ranges([lab_test], gender, db)
        assert results[0].status == "HIGH", (
            f"Expected HIGH for value={value} > max={max_val}, got {results[0].status}"
        )

    asyncio.run(_run())


@given(
    min_val=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    range_width=st.floats(min_value=0.0, max_value=1e4, allow_nan=False, allow_infinity=False),
    within_fraction=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=200)
def test_property3_value_within_range_is_normal(
    min_val: float,
    range_width: float,
    within_fraction: float,
    gender: str,
) -> None:
    """Property 3: A value within [min, max] → NORMAL.

    **Validates: Requirements 5.2, 5.3, 12.5**
    """
    max_val = min_val + range_width
    # Interpolate: value = min + fraction * (max - min)
    value = min_val + within_fraction * range_width

    # Guard against floating-point edge cases that slip outside due to
    # precision loss (e.g., min_val + 1.0 * range_width > max_val)
    assume(min_val <= value <= max_val)

    ref_doc = {
        "test_name": _KNOWN_TEST_NAME,
        "aliases": [],
        "unit": "unit",
        "male_min": min_val,
        "male_max": max_val,
        "female_min": min_val,
        "female_max": max_val,
        "description": "test",
    }

    lab_test = _make_lab_test(_KNOWN_TEST_NAME, value)

    async def _run():
        db = await _make_db_with_reference(ref_doc)
        results = await check_ranges([lab_test], gender, db)
        assert results[0].status == "NORMAL", (
            f"Expected NORMAL for value={value} in [{min_val}, {max_val}], "
            f"got {results[0].status}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 3 — gender-specific thresholds (male vs female)
# ---------------------------------------------------------------------------


@given(
    male_min=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    male_width=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    female_min=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    female_width=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property3_gender_selects_correct_thresholds(
    male_min: float,
    male_width: float,
    female_min: float,
    female_width: float,
) -> None:
    """Property 3: gender parameter selects the correct min/max thresholds.

    A value that is within the male range but below the female range should
    be NORMAL for males and LOW for females (when such a configuration exists).

    **Validates: Requirements 5.2, 5.3, 12.5**
    """
    male_max = male_min + male_width
    female_max = female_min + female_width

    # Construct a value that is within the male range but below the female range.
    # This requires female_min > male_max, so we pick a value = male_min + 0.5 * male_width
    # that is inside [male_min, male_max] but below female_min.
    assume(female_min > male_max)  # filter to scenarios where ranges don't overlap
    value = male_min + 0.5 * male_width
    assume(male_min <= value <= male_max)
    assume(value < female_min)

    ref_doc = {
        "test_name": _KNOWN_TEST_NAME,
        "aliases": [],
        "unit": "unit",
        "male_min": male_min,
        "male_max": male_max,
        "female_min": female_min,
        "female_max": female_max,
        "description": "test",
    }

    lab_test = _make_lab_test(_KNOWN_TEST_NAME, value)

    async def _run():
        db_male = await _make_db_with_reference(ref_doc)
        male_results = await check_ranges([lab_test], "male", db_male)
        assert male_results[0].status == "NORMAL", (
            f"Expected NORMAL for male: value={value} in [{male_min}, {male_max}]"
        )

        db_female = await _make_db_with_reference(ref_doc)
        female_results = await check_ranges([lab_test], "female", db_female)
        assert female_results[0].status == "LOW", (
            f"Expected LOW for female: value={value} < female_min={female_min}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property 4 — unknown test name yields UNKNOWN without raising
# ---------------------------------------------------------------------------
# **Validates: Requirements 5.4**
#
# Strategy: generate test names that are guaranteed not to match the single
# known entry seeded into the DB. We seed one entry ("TestMarker") and
# filter out generated names that equal it.
# ---------------------------------------------------------------------------


@given(
    test_name=st.text(min_size=1, max_size=100).filter(
        lambda s: s.strip().lower() != _KNOWN_TEST_NAME.lower()
    ),
    value=st.floats(
        min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
    ),
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=200)
def test_property4_unknown_test_name_yields_unknown_no_exception(
    test_name: str,
    value: float,
    gender: str,
) -> None:
    """Property 4: A test_name with no matching reference range → UNKNOWN, no exception.

    **Validates: Requirements 5.4**
    """
    # Seed the DB with one known entry so we're testing a real miss scenario
    ref_doc = {
        "test_name": _KNOWN_TEST_NAME,
        "aliases": [],
        "unit": "unit",
        "male_min": _MALE_MIN,
        "male_max": _MALE_MAX,
        "female_min": _FEMALE_MIN,
        "female_max": _FEMALE_MAX,
        "description": "test",
    }

    lab_test = _make_lab_test(test_name, value)

    async def _run():
        db = await _make_db_with_reference(ref_doc)
        # Must not raise
        results = await check_ranges([lab_test], gender, db)
        assert len(results) == 1
        assert results[0].status == "UNKNOWN", (
            f"Expected UNKNOWN for unrecognised test_name={test_name!r}, "
            f"got {results[0].status}"
        )

    asyncio.run(_run())


@given(
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=50)
def test_property4_empty_db_always_yields_unknown(gender: str) -> None:
    """Property 4 (edge case): with no reference ranges in DB, every test → UNKNOWN.

    **Validates: Requirements 5.4**
    """
    lab_test = _make_lab_test("Hemoglobin", 14.0)

    async def _run():
        db = await _make_empty_db()
        results = await check_ranges([lab_test], gender, db)
        assert results[0].status == "UNKNOWN"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Unit tests — specific example-based coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_ranges_low_status():
    """A value below the male reference min should return LOW for male gender."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": ["Hgb", "Hb"],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    lab_test = _make_lab_test("Hemoglobin", 10.0)  # below male_min of 13.5
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "LOW"


@pytest.mark.asyncio
async def test_check_ranges_high_status():
    """A value above the male reference max should return HIGH for male gender."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": ["Hgb"],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    lab_test = _make_lab_test("Hemoglobin", 20.0)  # above male_max of 17.5
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "HIGH"


@pytest.mark.asyncio
async def test_check_ranges_normal_status():
    """A value within the reference range should return NORMAL."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": ["Hgb"],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    lab_test = _make_lab_test("Hemoglobin", 15.0)  # within [13.5, 17.5]
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "NORMAL"


@pytest.mark.asyncio
async def test_check_ranges_alias_lookup():
    """A test lookup via an alias should also find the reference range."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": ["Hgb", "Hb"],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    # Use alias "Hgb" instead of canonical "Hemoglobin"
    lab_test = _make_lab_test("Hgb", 15.0)
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "NORMAL"


@pytest.mark.asyncio
async def test_check_ranges_unknown_test():
    """An unrecognised test name should return UNKNOWN without raising."""
    db = await _make_empty_db()
    lab_test = _make_lab_test("SomeObscureTest", 42.0)
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "UNKNOWN"


@pytest.mark.asyncio
async def test_check_ranges_case_insensitive_match():
    """Lookup should be case-insensitive for test_name."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": [],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    lab_test = _make_lab_test("hemoglobin", 15.0)  # lowercase
    results = await check_ranges([lab_test], "male", db)
    assert results[0].status == "NORMAL"


@pytest.mark.asyncio
async def test_check_ranges_returns_updated_list_length():
    """check_ranges returns the same number of tests as input."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": [],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    tests = [
        _make_lab_test("Hemoglobin", 15.0),
        _make_lab_test("UnknownTest", 99.0),
    ]
    results = await check_ranges(tests, "male", db)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_check_ranges_female_thresholds():
    """Female gender uses female_min / female_max thresholds."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": [],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    # 16.0 is within male range [13.5, 17.5] but above female max of 15.5
    lab_test = _make_lab_test("Hemoglobin", 16.0)
    results = await check_ranges([lab_test], "female", db)
    assert results[0].status == "HIGH"


@pytest.mark.asyncio
async def test_check_ranges_does_not_mutate_original():
    """check_ranges must not mutate the original LabTest objects."""
    ref_doc = {
        "test_name": "Hemoglobin",
        "aliases": [],
        "unit": "g/dL",
        "male_min": 13.5,
        "male_max": 17.5,
        "female_min": 12.0,
        "female_max": 15.5,
        "description": "Hemoglobin test",
    }
    db = await _make_db_with_reference(ref_doc)
    original = _make_lab_test("Hemoglobin", 10.0)  # would be LOW
    assert original.status == "UNKNOWN"  # default before check

    results = await check_ranges([original], "male", db)
    assert results[0].status == "LOW"
    # Original should still be UNKNOWN (not mutated in place)
    assert original.status == "UNKNOWN"
