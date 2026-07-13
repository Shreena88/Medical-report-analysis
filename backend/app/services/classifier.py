"""Document classification service.

Uses the Groq LLM to check if the OCR text belongs to a medical laboratory report.
The Groq client is initialized lazily.
"""

from __future__ import annotations

import json
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """You are a document classifier.

Determine whether the following text is from a medical laboratory report.

Return ONLY JSON.

{
  "is_medical_report": true,
  "confidence": 0.98,
  "report_type": "CBC"
}

Possible report_type values:
- CBC
- LFT
- KFT
- Lipid Profile
- Thyroid
- Blood Sugar
- Vitamin
- Unknown

If the document is not a medical laboratory report, return:

{
  "is_medical_report": false,
  "confidence": 0.99,
  "reason": "The document appears to be an invoice."
}
"""


class ClassificationError(Exception):
    """Raised when document classification fails."""
    pass


class ClassificationResult(BaseModel):
    is_medical_report: bool
    confidence: float
    report_type: str | None = None
    reason: str | None = None


_groq_client = None


def _get_groq_client():
    """Return the Groq client, creating it on first call."""
    global _groq_client
    if _groq_client is None:
        from groq import AsyncGroq
        from app.config import settings
        _groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _groq_client


async def classify_document(ocr_text: str) -> ClassificationResult:
    """Classify if the OCR text is a medical laboratory report."""
    from app.config import settings

    client = _get_groq_client()

    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": ocr_text},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise ClassificationError(f"Groq API call failed: {exc}") from exc

    raw_content = response.choices[0].message.content

    try:
        parsed = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ClassificationError(
            f"Groq response is not valid JSON: {exc}. Raw content: {raw_content!r}"
        ) from exc

    if "is_medical_report" not in parsed:
        raise ClassificationError(
            f"Groq response JSON missing 'is_medical_report' key. Got keys: {list(parsed.keys())}"
        )

    try:
        # Validate using Pydantic
        result = ClassificationResult(**parsed)
    except Exception as exc:
        raise ClassificationError(
            f"Pydantic validation failed for classification: {exc}. Got: {parsed!r}"
        ) from exc

    return result
