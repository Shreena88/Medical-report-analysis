"""OCR service: provider interface, EasyOCR implementation, and factory.

The OCR layer is abstracted behind a Python Protocol (OCRProvider) so the
underlying engine can be swapped (e.g., EasyOCR → Google Vision) without
touching any business logic in the pipeline.

OCRError is the single typed exception this module raises so callers can
handle OCR failures distinctly from other errors.
"""

from __future__ import annotations

import os
from typing import Protocol


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class OCRError(Exception):
    """Raised when text extraction fails for any reason."""
    pass


# ---------------------------------------------------------------------------
# Provider Protocol
# ---------------------------------------------------------------------------


class OCRProvider(Protocol):
    """Interface every OCR provider must satisfy."""

    def extract_text(self, file_path: str) -> str:
        """Extract text from the file at *file_path*.

        Returns a non-empty string on success.
        Raises :class:`OCRError` on any failure.
        """
        ...


# ---------------------------------------------------------------------------
# EasyOCR implementation
# ---------------------------------------------------------------------------


class EasyOCRProvider:
    """OCR provider backed by EasyOCR.

    The ``easyocr.Reader`` is expensive to initialise (it loads ML model
    weights) so it is constructed lazily on the first call to
    ``extract_text`` rather than at module import time.  This keeps the
    module importable cheaply in tests and other contexts where real OCR is
    not needed.
    """

    def __init__(self) -> None:
        # Deferred — populated on first call to _get_reader()
        self._reader = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_reader(self):  # type: ignore[return]
        """Return the cached EasyOCR Reader, creating it on first call."""
        if self._reader is None:
            try:
                import easyocr  # imported lazily so tests can mock it easily
                self._reader = easyocr.Reader(["en"], gpu=False)
            except Exception as exc:
                raise OCRError(f"Failed to initialise EasyOCR reader: {exc}") from exc
        return self._reader

    def _run_easyocr_on_image(self, image) -> str:
        """Run EasyOCR on a PIL Image or a file path and return extracted text.

        EasyOCR ``readtext`` returns a list of ``(bbox, text, confidence)``
        tuples.  We concatenate only the text segments separated by spaces.
        """
        reader = self._get_reader()
        try:
            results = reader.readtext(image)
        except Exception as exc:
            raise OCRError(f"EasyOCR readtext failed: {exc}") from exc

        if not results:
            return ""

        return " ".join(segment[1] for segment in results if segment[1])

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_text(self, file_path: str) -> str:
        """Extract text from *file_path* (PDF, JPG, JPEG, or PNG).

        - **PDF**: each page is rendered to a PIL Image via ``pdf2image``,
          then EasyOCR processes each image; all page texts are joined with
          newlines.
        - **JPG / JPEG / PNG**: EasyOCR is called directly on the file path.

        Returns the concatenated text (guaranteed non-empty on success).
        Raises :class:`OCRError` on any failure, including an empty result.
        """
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".pdf":
                text = self._extract_from_pdf(file_path)
            elif ext in {".jpg", ".jpeg", ".png"}:
                text = self._extract_from_image(file_path)
            else:
                raise OCRError(
                    f"Unsupported file extension '{ext}'. "
                    "Supported: .pdf, .jpg, .jpeg, .png"
                )
        except OCRError:
            raise
        except Exception as exc:
            raise OCRError(f"Unexpected error during OCR extraction: {exc}") from exc

        if not text or not text.strip():
            raise OCRError("OCR extraction returned empty text for the provided file.")

        return text

    def _extract_from_pdf(self, file_path: str) -> str:
        """Convert each PDF page to an image and run OCR on each."""
        try:
            from pdf2image import convert_from_path  # lazy import
        except ImportError as exc:
            raise OCRError("pdf2image is not installed; cannot process PDF files.") from exc

        try:
            pages = convert_from_path(file_path)
        except Exception as exc:
            raise OCRError(f"pdf2image failed to convert '{file_path}': {exc}") from exc

        if not pages:
            raise OCRError(f"pdf2image returned no pages for '{file_path}'.")

        page_texts: list[str] = []
        for page_num, page_image in enumerate(pages, start=1):
            # Convert PIL Image to numpy array which EasyOCR accepts
            try:
                import numpy as np
                page_array = np.array(page_image)
            except ImportError:
                # Fallback: pass PIL image directly (EasyOCR also accepts PIL)
                page_array = page_image

            page_text = self._run_easyocr_on_image(page_array)
            if page_text:
                page_texts.append(page_text)

        return "\n".join(page_texts)

    def _extract_from_image(self, file_path: str) -> str:
        """Run EasyOCR directly on a JPG or PNG file path."""
        return self._run_easyocr_on_image(file_path)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def get_ocr_provider() -> OCRProvider:
    """Return an :class:`EasyOCRProvider` instance.

    Swap the returned type here to change the OCR backend without modifying
    any caller.
    """
    return EasyOCRProvider()
