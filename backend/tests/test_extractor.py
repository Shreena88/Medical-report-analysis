"""Unit tests for the lab test extractor service.

Tests cover:
- Valid Groq JSON response is correctly parsed into a list[LabTest]
- Malformed JSON response raises ExtractionError without storing partial data
- Missing 'tests' key in JSON raises ExtractionError
- Pydantic validation failure raises ExtractionError
- EXTRACTION_SYSTEM_PROMPT contains prohibition keywords (NEVER clause)

Validates: Requirements 4.4, 4.5, 12.4
"""

from __future__ import annotations

import json
import os

# ---------------------------------------------------------------------------
# Set required env vars BEFORE any app code is imported so that the
# module-level `settings = Settings()` call in app.config succeeds.
# ---------------------------------------------------------------------------

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
os.environ.setdefault("GROQ_MODEL", "llama3-8b-8192")

# Now safe to import app modules
from unittest.mock import MagicMock, patch

import pytest

from app.models.report import LabTest
from app.services.extractor import (
    EXTRACTION_SYSTEM_PROMPT,
    ExtractionError,
    extract_tests,
)

# Patch target — settings is imported lazily inside extract_tests via app.config
_GROQ_CLIENT_PATCH = "app.services.extractor._get_groq_client"
_SETTINGS_PATCH = "app.services.extractor.settings"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_groq_response(content: str) -> MagicMock:
    """Build a mock Groq API response object with the given content string."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_client(mock_response: MagicMock) -> MagicMock:
    """Return a mock Groq client that returns mock_response from create()."""
    from unittest.mock import AsyncMock
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# Test: valid JSON response → correctly parsed list[LabTest]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_tests_valid_response_returns_lab_tests():
    """Valid Groq JSON response is correctly parsed into a list[LabTest].

    Validates: Requirements 4.2, 4.6
    """
    valid_payload = {
        "tests": [
            {
                "test_name": "Hemoglobin",
                "value": 14.2,
                "unit": "g/dL",
                "reference_range": "13.5-17.5",
            },
            {
                "test_name": "Blood Sugar",
                "value": 95.0,
                "unit": "mg/dL",
                "reference_range": "70-100",
            },
        ]
    }
    mock_response = _make_groq_response(json.dumps(valid_payload))
    mock_groq_client = _mock_client(mock_response)

    # Patch _get_groq_client so no real Groq client is created,
    # and patch the locally-imported settings inside extract_tests
    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await extract_tests("Hemoglobin 14.2 g/dL Blood Sugar 95 mg/dL")

    assert isinstance(result, list)
    assert len(result) == 2

    first = result[0]
    assert isinstance(first, LabTest)
    assert first.test_name == "Hemoglobin"
    assert first.value == 14.2
    assert first.unit == "g/dL"
    assert first.reference_range == "13.5-17.5"

    second = result[1]
    assert isinstance(second, LabTest)
    assert second.test_name == "Blood Sugar"
    assert second.value == 95.0


@pytest.mark.asyncio
async def test_extract_tests_empty_tests_array_returns_empty_list():
    """An empty 'tests' array returns an empty list (not an error)."""
    payload = {"tests": []}
    mock_response = _make_groq_response(json.dumps(payload))
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await extract_tests("some ocr text")

    assert result == []


@pytest.mark.asyncio
async def test_extract_tests_single_test_returned():
    """A single test in the response is returned as a one-element list."""
    payload = {
        "tests": [
            {
                "test_name": "Vitamin D",
                "value": 32.5,
                "unit": "ng/mL",
                "reference_range": "30-100",
            }
        ]
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await extract_tests("Vitamin D 32.5 ng/mL")

    assert len(result) == 1
    assert result[0].test_name == "Vitamin D"


# ---------------------------------------------------------------------------
# Test: malformed JSON raises ExtractionError — no partial data stored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_tests_malformed_json_raises_extraction_error():
    """Malformed JSON response raises ExtractionError without storing partial data.

    Validates: Requirements 4.4
    """
    mock_response = _make_groq_response("this is not valid json {{{")
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        with pytest.raises(ExtractionError) as exc_info:
            await extract_tests("some ocr text")

    assert "not valid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_tests_malformed_json_raises_not_generic_exception():
    """The raised exception must be ExtractionError specifically, not a generic one.

    Validates: Requirements 4.4
    """
    mock_response = _make_groq_response("not json at all")
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        try:
            await extract_tests("ocr text")
        except ExtractionError:
            pass  # Correct — ExtractionError is expected
        except Exception as exc:
            pytest.fail(
                f"Expected ExtractionError but got {type(exc).__name__}: {exc}"
            )


@pytest.mark.asyncio
async def test_extract_tests_missing_tests_key_raises_extraction_error():
    """JSON without a 'tests' key raises ExtractionError.

    Validates: Requirements 4.4
    """
    payload = {"results": []}  # wrong key
    mock_response = _make_groq_response(json.dumps(payload))
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        with pytest.raises(ExtractionError) as exc_info:
            await extract_tests("some ocr text")

    assert "tests" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_extract_tests_invalid_item_raises_extraction_error():
    """A test item that fails Pydantic validation raises ExtractionError.

    Validates: Requirements 4.4, 4.6
    """
    payload = {
        "tests": [
            {
                "test_name": "Hemoglobin",
                # 'value' is a string that cannot be coerced to float
                "value": "not-a-number",
                "unit": "g/dL",
                "reference_range": "13.5-17.5",
            }
        ]
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        with pytest.raises(ExtractionError):
            await extract_tests("some ocr text")


@pytest.mark.asyncio
async def test_extract_tests_partial_data_not_stored_on_validation_failure():
    """When validation fails for one item, no partial list is returned.

    The function must raise ExtractionError, not return the valid items so far.
    Validates: Requirements 4.4
    """
    payload = {
        "tests": [
            # First item is valid
            {
                "test_name": "Hemoglobin",
                "value": 14.2,
                "unit": "g/dL",
                "reference_range": "13.5-17.5",
            },
            # Second item has an invalid value type
            {
                "test_name": "Platelets",
                "value": "high",  # invalid — not a number
                "unit": "10^9/L",
                "reference_range": "150-400",
            },
        ]
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_groq_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_groq_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        with pytest.raises(ExtractionError):
            await extract_tests("lab report text")


# ---------------------------------------------------------------------------
# Test: EXTRACTION_SYSTEM_PROMPT prohibition keywords
# ---------------------------------------------------------------------------


def test_system_prompt_contains_never():
    """EXTRACTION_SYSTEM_PROMPT must contain the word 'NEVER'.

    Validates: Requirements 4.5, 12.4
    """
    assert "NEVER" in EXTRACTION_SYSTEM_PROMPT, (
        "EXTRACTION_SYSTEM_PROMPT must contain 'NEVER' to explicitly prohibit "
        "diagnostic and prescriptive content."
    )


def test_system_prompt_prohibits_diagnoses():
    """EXTRACTION_SYSTEM_PROMPT must reference 'diagnos' in a prohibition clause.

    The prompt must explicitly prohibit diagnostic content by mentioning words
    like 'diagnos' or 'diagnoses' in a NEVER clause.

    Validates: Requirements 4.5, 12.4
    """
    prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
    assert "diagnos" in prompt_lower, (
        "EXTRACTION_SYSTEM_PROMPT must explicitly prohibit diagnostic content "
        "by referencing 'diagnos' (e.g., 'NEVER include diagnoses')."
    )


def test_system_prompt_never_clause_precedes_diagnos():
    """The NEVER clause should appear before or alongside diagnostic prohibition.

    Validates: Requirements 4.5, 12.4
    """
    prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
    never_pos = prompt_lower.find("never")
    diagnos_pos = prompt_lower.find("diagnos")

    assert never_pos != -1, "EXTRACTION_SYSTEM_PROMPT must contain 'NEVER'"
    assert diagnos_pos != -1, (
        "EXTRACTION_SYSTEM_PROMPT must mention 'diagnos' as a prohibited topic"
    )
    # NEVER appears before the diagnos prohibition
    assert never_pos < diagnos_pos, (
        "The 'NEVER' keyword should appear before the 'diagnos' prohibition in the prompt"
    )


def test_system_prompt_specifies_json_output_format():
    """EXTRACTION_SYSTEM_PROMPT must specify the required JSON output format.

    Validates: Requirements 4.1, 4.2
    """
    assert "tests" in EXTRACTION_SYSTEM_PROMPT, (
        "EXTRACTION_SYSTEM_PROMPT must specify the 'tests' array in the JSON format."
    )
    assert "test_name" in EXTRACTION_SYSTEM_PROMPT, (
        "EXTRACTION_SYSTEM_PROMPT must specify 'test_name' field in the JSON format."
    )
    assert "reference_range" in EXTRACTION_SYSTEM_PROMPT, (
        "EXTRACTION_SYSTEM_PROMPT must specify 'reference_range' field in JSON format."
    )


def test_system_prompt_prohibits_medications():
    """EXTRACTION_SYSTEM_PROMPT must prohibit medication-related content.

    Validates: Requirements 4.5, 12.4
    """
    prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
    assert "medication" in prompt_lower or "medic" in prompt_lower, (
        "EXTRACTION_SYSTEM_PROMPT must explicitly prohibit medication-related content."
    )


def test_system_prompt_prohibits_treatment():
    """EXTRACTION_SYSTEM_PROMPT must prohibit treatment recommendations.

    Validates: Requirements 4.5, 12.4
    """
    prompt_lower = EXTRACTION_SYSTEM_PROMPT.lower()
    assert "treatment" in prompt_lower or "treat" in prompt_lower, (
        "EXTRACTION_SYSTEM_PROMPT must explicitly prohibit treatment recommendations."
    )
