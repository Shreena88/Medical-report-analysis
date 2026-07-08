"""Unit tests for the AI explanation service.

Tests cover:
- Unparseable Groq response returns fallback ExplanationResult without raising
- Empty string Groq response returns fallback ExplanationResult without raising
- Valid response is parsed correctly into ExplanationResult
- System prompt contains "consult" and prohibition keywords (NEVER, diagnos,
  medic/medication, treat)

Validates: Requirements 6.4, 6.5, 12.2, 12.4
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

from unittest.mock import MagicMock, patch

import pytest

from app.models.report import LabTest
from app.services.ai_service import (
    EXPLANATION_SYSTEM_PROMPT,
    FALLBACK_EXPLANATION_RESULT,
    ExplanationResult,
    generate_explanations,
)

# Patch target for the Groq client getter
_GROQ_CLIENT_PATCH = "app.services.ai_service._get_groq_client"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_groq_response(content: str) -> MagicMock:
    """Build a mock Groq API response with the given content string."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_client(mock_response: MagicMock) -> MagicMock:
    """Return a mock Groq client whose create() returns mock_response."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def _make_lab_test(
    test_name: str = "Hemoglobin",
    value: float = 14.2,
    unit: str = "g/dL",
    reference_range: str = "13.5-17.5",
    status: str = "NORMAL",
) -> LabTest:
    return LabTest(
        test_name=test_name,
        value=value,
        unit=unit,
        reference_range=reference_range,
        status=status,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Test: fallback on unparseable response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unparseable_response_returns_fallback_without_raising():
    """Unparseable Groq response returns fallback ExplanationResult, never raises.

    Validates: Requirements 6.5
    """
    mock_response = _make_groq_response("this is not valid json {{{")
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT
    assert result.summary == (
        "Explanations are currently unavailable. "
        "Please consult a healthcare professional."
    )
    assert result.explanations == []


@pytest.mark.asyncio
async def test_unparseable_response_does_not_raise():
    """generate_explanations must never raise on an unparseable response.

    Validates: Requirements 6.5
    """
    mock_response = _make_groq_response("not json at all")
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        try:
            await generate_explanations([_make_lab_test()])
        except Exception as exc:
            pytest.fail(
                f"generate_explanations raised an exception on unparseable "
                f"response: {type(exc).__name__}: {exc}"
            )


# ---------------------------------------------------------------------------
# Test: fallback on empty string response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_string_response_returns_fallback_without_raising():
    """Empty string Groq response returns fallback ExplanationResult, never raises.

    Validates: Requirements 6.5
    """
    mock_response = _make_groq_response("")
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT


@pytest.mark.asyncio
async def test_whitespace_only_response_returns_fallback():
    """Whitespace-only Groq response is treated as empty and returns fallback."""
    mock_response = _make_groq_response("   \n\t  ")
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT


# ---------------------------------------------------------------------------
# Test: fallback on missing keys in JSON response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_missing_summary_key_returns_fallback():
    """JSON response missing 'summary' key returns fallback.

    Validates: Requirements 6.5
    """
    payload = {
        # "summary" key is absent
        "explanations": [{"name": "Hemoglobin", "explanation": "Some text"}]
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT


@pytest.mark.asyncio
async def test_json_missing_explanations_key_returns_fallback():
    """JSON response missing 'explanations' key returns fallback.

    Validates: Requirements 6.5
    """
    payload = {"summary": "All looks okay."}  # "explanations" key is absent
    mock_response = _make_groq_response(json.dumps(payload))
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT


# ---------------------------------------------------------------------------
# Test: fallback on Groq API error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groq_api_error_returns_fallback_without_raising():
    """Groq API exception returns fallback ExplanationResult, never raises.

    Validates: Requirements 6.5
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError(
        "Simulated API failure"
    )

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([_make_lab_test()])

    assert result == FALLBACK_EXPLANATION_RESULT


# ---------------------------------------------------------------------------
# Test: valid response is correctly parsed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_response_parsed_correctly():
    """Valid Groq JSON response is correctly parsed into ExplanationResult.

    Validates: Requirements 6.1, 6.2
    """
    payload = {
        "summary": (
            "Your lab results are generally within normal range. "
            "Please consult a qualified healthcare professional for guidance."
        ),
        "primary_findings": ["No high-risk deviations detected."],
        "affected_systems": [
            {
                "system_name": "Hematology",
                "status": "Optimal",
                "marker_count": 0,
                "notes": "Red and white blood cell levels are optimal."
            }
        ],
        "questions_for_doctor": ["What does my hemoglobin level indicate about my oxygen capacity?"],
        "lifestyle_considerations": ["Continue a balanced nutrition rich in iron."],
        "explanations": [
            {
                "name": "Hemoglobin",
                "explanation": (
                    "Hemoglobin carries oxygen in your blood. "
                    "Your level is within the range."
                ),
            },
            {
                "name": "Blood Sugar",
                "explanation": (
                    "Blood sugar measures glucose in your blood. "
                    "A normal fasting value is generally 70–100 mg/dL."
                ),
            },
        ],
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_client = _mock_client(mock_response)

    tests = [
        _make_lab_test("Hemoglobin", 14.2, "g/dL", "13.5-17.5", "NORMAL"),
        _make_lab_test("Blood Sugar", 95.0, "mg/dL", "70-100", "NORMAL"),
    ]

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations(tests)

    assert isinstance(result, ExplanationResult)
    assert "normal range" in result.summary.lower()
    assert result.primary_findings == ["No high-risk deviations detected."]
    assert len(result.affected_systems) == 1
    assert result.affected_systems[0]["system_name"] == "Hematology"
    assert result.questions_for_doctor == ["What does my hemoglobin level indicate about my oxygen capacity?"]
    assert result.lifestyle_considerations == ["Continue a balanced nutrition rich in iron."]
    assert len(result.explanations) == 2

    hgb = result.explanations[0]
    assert hgb["name"] == "Hemoglobin"
    assert "oxygen" in hgb["explanation"].lower()

    glucose = result.explanations[1]
    assert glucose["name"] == "Blood Sugar"


@pytest.mark.asyncio
async def test_valid_response_with_empty_explanations_list():
    """A valid response with an empty 'explanations' list is accepted."""
    payload = {
        "summary": "No tests to explain. Consult a qualified healthcare professional.",
        "explanations": [],
    }
    mock_response = _make_groq_response(json.dumps(payload))
    mock_client = _mock_client(mock_response)

    with patch(_GROQ_CLIENT_PATCH, return_value=mock_client), \
         patch("app.config.settings") as mock_settings:
        mock_settings.GROQ_MODEL = "llama3-8b-8192"
        result = await generate_explanations([])

    assert isinstance(result, ExplanationResult)
    assert result.explanations == []
    assert result.summary != ""


# ---------------------------------------------------------------------------
# Test: system prompt keywords
# ---------------------------------------------------------------------------


def test_system_prompt_contains_consult_advisory():
    """EXPLANATION_SYSTEM_PROMPT must contain 'consult' advisory.

    Validates: Requirements 6.4, 12.2
    """
    assert "consult" in EXPLANATION_SYSTEM_PROMPT.lower(), (
        "EXPLANATION_SYSTEM_PROMPT must include a 'consult a qualified "
        "healthcare professional' advisory."
    )


def test_system_prompt_contains_never():
    """EXPLANATION_SYSTEM_PROMPT must contain the word 'NEVER'.

    Validates: Requirements 6.4, 12.4
    """
    assert "NEVER" in EXPLANATION_SYSTEM_PROMPT, (
        "EXPLANATION_SYSTEM_PROMPT must use 'NEVER' to prohibit diagnostic "
        "and prescriptive content."
    )


def test_system_prompt_prohibits_diagnoses():
    """EXPLANATION_SYSTEM_PROMPT must prohibit disease diagnoses.

    Validates: Requirements 6.4, 12.1
    """
    prompt_lower = EXPLANATION_SYSTEM_PROMPT.lower()
    assert "diagnos" in prompt_lower, (
        "EXPLANATION_SYSTEM_PROMPT must explicitly prohibit diagnoses "
        "(e.g., 'NEVER diagnose any disease or condition')."
    )


def test_system_prompt_prohibits_medications():
    """EXPLANATION_SYSTEM_PROMPT must prohibit medication names and dosages.

    Validates: Requirements 6.4, 12.2
    """
    prompt_lower = EXPLANATION_SYSTEM_PROMPT.lower()
    assert "medic" in prompt_lower or "medication" in prompt_lower, (
        "EXPLANATION_SYSTEM_PROMPT must explicitly prohibit medication names "
        "and dosages."
    )


def test_system_prompt_prohibits_treatment():
    """EXPLANATION_SYSTEM_PROMPT must prohibit treatment recommendations.

    Validates: Requirements 6.4, 12.2
    """
    prompt_lower = EXPLANATION_SYSTEM_PROMPT.lower()
    assert "treat" in prompt_lower or "treatment" in prompt_lower, (
        "EXPLANATION_SYSTEM_PROMPT must explicitly prohibit treatment plans."
    )


def test_system_prompt_specifies_json_output_format():
    """EXPLANATION_SYSTEM_PROMPT must specify the required JSON output format.

    Validates: Requirements 6.2
    """
    assert "summary" in EXPLANATION_SYSTEM_PROMPT, (
        "EXPLANATION_SYSTEM_PROMPT must specify the 'summary' field in JSON format."
    )
    assert "primary_findings" in EXPLANATION_SYSTEM_PROMPT
    assert "affected_systems" in EXPLANATION_SYSTEM_PROMPT
    assert "questions_for_doctor" in EXPLANATION_SYSTEM_PROMPT
    assert "lifestyle_considerations" in EXPLANATION_SYSTEM_PROMPT
    assert "explanations" in EXPLANATION_SYSTEM_PROMPT, (
        "EXPLANATION_SYSTEM_PROMPT must specify the 'explanations' array."
    )
    assert "name" in EXPLANATION_SYSTEM_PROMPT, (
        "EXPLANATION_SYSTEM_PROMPT must specify the 'name' field in explanations."
    )
    assert "explanation" in EXPLANATION_SYSTEM_PROMPT, (
        "EXPLANATION_SYSTEM_PROMPT must specify the 'explanation' field."
    )


# ---------------------------------------------------------------------------
# Test: fallback constant is correctly defined
# ---------------------------------------------------------------------------


def test_fallback_result_has_correct_summary():
    """FALLBACK_EXPLANATION_RESULT summary contains expected unavailability message."""
    assert "unavailable" in FALLBACK_EXPLANATION_RESULT.summary.lower()
    assert "consult" in FALLBACK_EXPLANATION_RESULT.summary.lower()


def test_fallback_result_has_empty_explanations():
    """FALLBACK_EXPLANATION_RESULT has an empty explanations list."""
    assert FALLBACK_EXPLANATION_RESULT.explanations == []


def test_fallback_result_is_explanation_result_instance():
    """FALLBACK_EXPLANATION_RESULT is an instance of ExplanationResult."""
    assert isinstance(FALLBACK_EXPLANATION_RESULT, ExplanationResult)
