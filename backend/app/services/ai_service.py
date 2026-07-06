"""AI explanation service.

Uses the Groq LLM to generate plain-language educational explanations for
validated lab test results.  The Groq client is initialized lazily (same
pattern as extractor.py).

This service NEVER raises.  Any failure (API error, unparseable response,
missing keys) is caught, logged, and replaced by a safe fallback result so
the overall report pipeline always reaches the ``complete`` status.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel

from app.models.report import LabTest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Explanation system prompt
# ---------------------------------------------------------------------------

EXPLANATION_SYSTEM_PROMPT = """You are a medical education assistant helping users understand their lab results.
Provide plain-language educational explanations of what each lab value means.

Rules you MUST follow:
- NEVER diagnose any disease or condition.
- NEVER mention medication names, dosages, or treatment plans.
- NEVER suggest the user stop or start any medication or supplement.
- Always remind users to consult a qualified healthcare professional for any medical concerns.

Output ONLY valid JSON in this exact format:
{"summary": str, "explanations": [{"name": str, "explanation": str}]}

Where:
- "summary" is a brief overall summary of the lab results in plain language.
- "explanations" is an array where each object has "name" (the test name) and
  "explanation" (a plain-language explanation of what that value means).
"""

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ExplanationResult(BaseModel):
    """Parsed result from the AI explanation service."""

    summary: str
    explanations: list[dict]


# ---------------------------------------------------------------------------
# Safe fallback
# ---------------------------------------------------------------------------

FALLBACK_EXPLANATION_RESULT = ExplanationResult(
    summary=(
        "Explanations are currently unavailable. "
        "Please consult a healthcare professional."
    ),
    explanations=[],
)

# ---------------------------------------------------------------------------
# Groq client (lazy initialization)
# ---------------------------------------------------------------------------

_groq_client = None


def _get_groq_client():
    """Return the Groq client, creating it on first call.

    Defers instantiation so the ``groq`` package is only loaded when an
    actual explanation is requested, not at import time.
    """
    global _groq_client
    if _groq_client is None:
        from groq import Groq  # lazy import
        from app.config import settings
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_explanations(tests: list[LabTest]) -> ExplanationResult:
    """Generate plain-language educational explanations for the given lab tests.

    Sends the lab test data to the Groq API using :data:`EXPLANATION_SYSTEM_PROMPT`
    and parses the structured JSON response into an :class:`ExplanationResult`.

    This function **never raises**.  Any failure is caught, logged, and
    :data:`FALLBACK_EXPLANATION_RESULT` is returned so the pipeline can always
    reach the ``complete`` status.

    Parameters
    ----------
    tests:
        Validated lab tests (including status) from the reference checker.

    Returns
    -------
    ExplanationResult
        Parsed summary and per-test explanations, or the fallback result on
        any failure.
    """
    from app.config import settings  # lazy — avoids startup failure on missing env vars

    try:
        client = _get_groq_client()

        # Serialize lab tests to a JSON-friendly structure for the user message
        tests_data = [
            {
                "test_name": t.test_name,
                "value": t.value,
                "unit": t.unit,
                "reference_range": t.reference_range,
                "status": t.status,
            }
            for t in tests
        ]
        user_message = json.dumps({"lab_tests": tests_data})

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content

        if not raw_content or not raw_content.strip():
            logger.error(
                "generate_explanations: Groq returned an empty response; "
                "using fallback."
            )
            return FALLBACK_EXPLANATION_RESULT

        try:
            parsed = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "generate_explanations: Groq response is not valid JSON: %s. "
                "Raw content: %r",
                exc,
                raw_content,
            )
            return FALLBACK_EXPLANATION_RESULT

        # Validate required keys
        if "summary" not in parsed or "explanations" not in parsed:
            logger.error(
                "generate_explanations: Groq JSON missing required keys. "
                "Got keys: %s",
                list(parsed.keys()),
            )
            return FALLBACK_EXPLANATION_RESULT

        # Validate explanations is a list of dicts with 'name' and 'explanation'
        explanations = parsed["explanations"]
        if not isinstance(explanations, list):
            logger.error(
                "generate_explanations: 'explanations' is not a list. "
                "Got type: %s",
                type(explanations).__name__,
            )
            return FALLBACK_EXPLANATION_RESULT

        validated_explanations: list[dict] = []
        for item in explanations:
            if not isinstance(item, dict):
                logger.error(
                    "generate_explanations: explanation item is not a dict: %r",
                    item,
                )
                return FALLBACK_EXPLANATION_RESULT
            if "name" not in item or "explanation" not in item:
                logger.error(
                    "generate_explanations: explanation item missing 'name' or "
                    "'explanation' key: %r",
                    item,
                )
                return FALLBACK_EXPLANATION_RESULT
            validated_explanations.append(
                {"name": item["name"], "explanation": item["explanation"]}
            )

        return ExplanationResult(
            summary=str(parsed["summary"]),
            explanations=validated_explanations,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "generate_explanations: unexpected error: %s", exc, exc_info=True
        )
        return FALLBACK_EXPLANATION_RESULT
