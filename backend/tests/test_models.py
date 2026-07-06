"""Property-based tests for Pydantic data models.

**Validates: Requirements 5.2, 12.5**

Property 1: LabTest status field only accepts LOW, NORMAL, HIGH, UNKNOWN.
  - Any string value NOT in the valid set must raise a ValidationError.
  - All four valid values must be accepted without error.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models.report import LabTest

# The only accepted status values
VALID_STATUSES = {"LOW", "NORMAL", "HIGH", "UNKNOWN"}

# A minimal valid LabTest payload — everything except `status` is fixed so
# that tests focus solely on the status field behavior.
_BASE_LAB_TEST = {
    "test_name": "Hemoglobin",
    "value": 14.0,
    "unit": "g/dL",
    "reference_range": "13.5-17.5",
}


# ---------------------------------------------------------------------------
# Property 1 — invalid status values are rejected
# ---------------------------------------------------------------------------

@given(
    invalid_status=st.text().filter(lambda s: s not in VALID_STATUSES)
)
@settings(max_examples=200)
def test_labtest_rejects_invalid_status(invalid_status: str) -> None:
    """Property 1 (negative): any status string outside the valid set raises ValidationError.

    **Validates: Requirements 5.2, 12.5**
    """
    with pytest.raises(ValidationError):
        LabTest(**_BASE_LAB_TEST, status=invalid_status)


# ---------------------------------------------------------------------------
# Property 1 — valid status values are accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valid_status", sorted(VALID_STATUSES))
def test_labtest_accepts_all_valid_statuses(valid_status: str) -> None:
    """Property 1 (positive): each of the four valid statuses must be accepted.

    **Validates: Requirements 5.2, 12.5**
    """
    lab_test = LabTest(**_BASE_LAB_TEST, status=valid_status)
    assert lab_test.status == valid_status


# ---------------------------------------------------------------------------
# Unit tests — default status and optional explanation
# ---------------------------------------------------------------------------

def test_labtest_default_status_is_unknown() -> None:
    """When status is omitted the default must be UNKNOWN."""
    lab_test = LabTest(**_BASE_LAB_TEST)
    assert lab_test.status == "UNKNOWN"


def test_labtest_explanation_defaults_to_none() -> None:
    """explanation field must default to None when omitted."""
    lab_test = LabTest(**_BASE_LAB_TEST)
    assert lab_test.explanation is None


def test_labtest_explanation_accepts_string() -> None:
    """explanation field must accept a non-None string value."""
    lab_test = LabTest(**_BASE_LAB_TEST, explanation="This value is within normal range.")
    assert lab_test.explanation == "This value is within normal range."
