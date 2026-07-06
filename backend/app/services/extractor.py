"""Lab test extractor service.

Uses the Groq LLM to extract structured lab test results from OCR text.
The Groq client is initialized lazily to avoid hitting the API on import.

Raises :class:`ExtractionError` if the Groq response cannot be parsed or
fails Pydantic validation.  Partial data is never stored.
"""

from __future__ import annotations

import json

from app.models.report import LabTest

# ---------------------------------------------------------------------------
# Extraction system prompt
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You are a medical data extraction assistant.
Extract lab test results from the provided OCR text and return ONLY valid JSON.

Output format (strict):
{"tests": [{"test_name": str, "value": float, "unit": str, "reference_range": str}]}

Rules you MUST follow:
- NEVER include disease names, diagnoses, or any diagnostic conclusions.
- NEVER include medication names, dosages, or treatment recommendations.
- NEVER suggest or imply any medical treatments or interventions.
- NEVER add any text, explanation, or commentary outside the JSON object.
- Only extract numerical lab test measurements (e.g., Hemoglobin, Glucose, WBC).
- If a field is not present in the text, use an empty string for string fields.
- The "value" field must always be a number (float).
"""

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Raised when lab test extraction or parsing fails."""
    pass


# ---------------------------------------------------------------------------
# Groq client (lazy initialization)
# ---------------------------------------------------------------------------

_groq_client = None


def _get_groq_client():
    """Return the Groq client, creating it on first call.

    The Groq constructor is deferred so the heavy ``groq`` package is only
    instantiated when a real extraction is requested, not at import time.
    """
    global _groq_client
    if _groq_client is None:
        from groq import Groq  # lazy import of the groq package
        from app.config import settings
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_tests(ocr_text: str) -> list[LabTest]:
    """Extract lab test results from OCR text using the Groq API.

    Sends the OCR text to Groq with :data:`EXTRACTION_SYSTEM_PROMPT` and
    parses the structured JSON response into a validated list of
    :class:`~app.models.report.LabTest` objects.

    Parameters
    ----------
    ocr_text:
        Raw text extracted from an uploaded lab report via OCR.

    Returns
    -------
    list[LabTest]
        Validated lab test records parsed from the Groq response.

    Raises
    ------
    ExtractionError
        If the Groq response cannot be parsed as JSON, if the JSON structure
        is unexpected, or if any item fails Pydantic validation.  Partial
        data is never returned.
    """
    from app.config import settings  # lazy import — avoids startup failure when env vars missing

    client = _get_groq_client()

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": ocr_text},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise ExtractionError(f"Groq API call failed: {exc}") from exc

    raw_content = response.choices[0].message.content

    # --- Parse JSON -----------------------------------------------------------
    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ExtractionError(
            f"Groq response is not valid JSON: {exc}. Raw content: {raw_content!r}"
        ) from exc

    # --- Extract tests array --------------------------------------------------
    if "tests" not in parsed:
        raise ExtractionError(
            f"Groq response JSON missing 'tests' key. Got keys: {list(parsed.keys())}"
        )

    raw_tests = parsed["tests"]

    if not isinstance(raw_tests, list):
        raise ExtractionError(
            f"Expected 'tests' to be a list, got {type(raw_tests).__name__}"
        )

    # --- Validate each item with Pydantic -------------------------------------
    # We validate ALL items before returning any, so partial data is never stored.
    validated: list[LabTest] = []
    for index, item in enumerate(raw_tests):
        try:
            lab_test = LabTest(**item)
        except Exception as exc:
            raise ExtractionError(
                f"Pydantic validation failed for test at index {index}: {exc}. "
                f"Item: {item!r}"
            ) from exc
        validated.append(lab_test)

    return validated
