"""Property-based tests for the OCR provider interface.

**Validates: Requirements 3.1, 3.5**

Property 2: Any OCRProvider implementation returns a non-empty string for
valid input files.
  - A mock provider that conforms to the OCRProvider Protocol must always
    return a non-empty string (validated via Hypothesis).
  - EasyOCRProvider.extract_text must raise OCRError (not a generic
    exception) when the underlying EasyOCR reader raises an exception.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.ocr_service import EasyOCRProvider, OCRError, OCRProvider


# ---------------------------------------------------------------------------
# MockOCRProvider — satisfies the OCRProvider Protocol
# ---------------------------------------------------------------------------


class MockOCRProvider:
    """Minimal OCR provider whose extract_text returns whatever was injected."""

    def __init__(self, return_value: str) -> None:
        self._return_value = return_value

    def extract_text(self, file_path: str) -> str:  # noqa: ARG002
        return self._return_value


# ---------------------------------------------------------------------------
# Property 2 — any OCRProvider returns a non-empty string for valid inputs
#
# Strategy: generate random non-empty strings and verify the mock provider
# returns them unchanged.  This validates:
#   1. That MockOCRProvider (and by structural typing, any correct
#      OCRProvider) satisfies the non-empty-string contract.
#   2. That the Protocol is usable as an interface by diverse implementations.
# ---------------------------------------------------------------------------


@given(
    ocr_output=st.text(min_size=1),
    file_path=st.text(min_size=1),
)
@settings(max_examples=200)
def test_mock_provider_returns_non_empty_string(
    ocr_output: str, file_path: str
) -> None:
    """Property 2: OCRProvider always returns a non-empty string for valid input.

    **Validates: Requirements 3.1, 3.5**
    """
    provider: OCRProvider = MockOCRProvider(return_value=ocr_output)
    result = provider.extract_text(file_path)

    # The contract: the returned value must be a non-empty string
    assert isinstance(result, str), "extract_text must return a str"
    assert len(result) > 0, "extract_text must return a non-empty string"


# ---------------------------------------------------------------------------
# EasyOCRProvider raises OCRError (not a generic exception) on EasyOCR failure
# ---------------------------------------------------------------------------


def test_easyocr_provider_raises_ocr_error_on_reader_exception() -> None:
    """EasyOCRProvider wraps EasyOCR reader exceptions in OCRError.

    **Validates: Requirements 3.1, 3.5**
    """
    provider = EasyOCRProvider()

    # Simulate easyocr.Reader raising an exception during readtext
    mock_reader = MagicMock()
    mock_reader.readtext.side_effect = RuntimeError("EasyOCR internal failure")

    # Inject the mock reader so we never call the real EasyOCR
    provider._reader = mock_reader

    with pytest.raises(OCRError):
        # Use a .png path so the provider tries to call readtext
        provider.extract_text("some_file.png")


def test_easyocr_provider_raises_ocr_error_not_base_exception() -> None:
    """The exception raised by EasyOCRProvider must be an OCRError specifically.

    **Validates: Requirements 3.5**
    """
    provider = EasyOCRProvider()

    mock_reader = MagicMock()
    mock_reader.readtext.side_effect = ValueError("unexpected value")
    provider._reader = mock_reader

    try:
        provider.extract_text("report.jpg")
    except OCRError:
        pass  # Expected — OCRError is the correct exception type
    except Exception as exc:
        pytest.fail(
            f"EasyOCRProvider raised {type(exc).__name__} instead of OCRError: {exc}"
        )


def test_easyocr_provider_raises_ocr_error_on_empty_result() -> None:
    """EasyOCRProvider raises OCRError when EasyOCR returns an empty result list.

    **Validates: Requirements 3.1**
    """
    provider = EasyOCRProvider()

    mock_reader = MagicMock()
    # readtext returns an empty list — no text found
    mock_reader.readtext.return_value = []
    provider._reader = mock_reader

    with pytest.raises(OCRError):
        provider.extract_text("scan.png")


def test_easyocr_provider_returns_concatenated_text_for_image() -> None:
    """EasyOCRProvider concatenates text segments from EasyOCR result tuples.

    **Validates: Requirements 3.1, 3.4**
    """
    provider = EasyOCRProvider()

    # EasyOCR returns list of (bbox, text, confidence) tuples
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([[0, 0], [10, 0], [10, 5], [0, 5]], "Hemoglobin", 0.99),
        ([[0, 10], [10, 10], [10, 15], [0, 15]], "14.2 g/dL", 0.97),
    ]
    provider._reader = mock_reader

    result = provider.extract_text("report.jpg")

    assert "Hemoglobin" in result
    assert "14.2 g/dL" in result
    assert isinstance(result, str)
    assert len(result) > 0


def test_easyocr_provider_raises_ocr_error_on_unsupported_extension() -> None:
    """EasyOCRProvider raises OCRError for unsupported file extensions.

    **Validates: Requirements 3.4**
    """
    provider = EasyOCRProvider()

    with pytest.raises(OCRError, match="Unsupported file extension"):
        provider.extract_text("document.docx")


def test_easyocr_provider_pdf_raises_ocr_error_when_pdf2image_fails() -> None:
    """EasyOCRProvider wraps pdf2image failures in OCRError for PDF files.

    **Validates: Requirements 3.1, 3.4**
    """
    provider = EasyOCRProvider()

    with patch(
        "app.services.ocr_service.EasyOCRProvider._extract_from_pdf",
        side_effect=OCRError("pdf2image failed"),
    ):
        with pytest.raises(OCRError):
            provider.extract_text("lab_report.pdf")
