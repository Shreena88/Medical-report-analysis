"""Pydantic models for the Report domain.

Models:
- LabTest       — a single lab measurement with its status and optional explanation
- Report        — full report document as stored in MongoDB
- ReportSummary — lightweight view for list endpoints (omits ocr_text and lab_tests)
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import PyObjectId


class LabTest(BaseModel):
    """A single laboratory measurement extracted from a report."""

    model_config = ConfigDict(populate_by_name=True)

    test_name: str
    value: float
    unit: str
    reference_range: str
    status: Literal[
        "LOW",
        "NORMAL",
        "HIGH",
        "UNKNOWN",
        "SLIGHTLY_LOW",
        "SIGNIFICANTLY_LOW",
        "SLIGHTLY_HIGH",
        "SIGNIFICANTLY_HIGH",
    ] = "UNKNOWN"
    explanation: str | None = None


class SystemStatus(BaseModel):
    """Status details for a specific physiological organ system."""

    system_name: str
    status: Literal["Optimal", "Needs Attention"]
    marker_count: int
    notes: str


class ClinicalOverview(BaseModel):
    """Multi-dimensional AI educational summary of the patient's report."""

    summary: str
    primary_findings: list[str] = Field(default_factory=list)
    affected_systems: list[SystemStatus] = Field(default_factory=list)
    questions_for_doctor: list[str] = Field(default_factory=list)
    lifestyle_considerations: list[str] = Field(default_factory=list)


class Report(BaseModel):
    """Full report document as stored in MongoDB.

    The `id` field maps to MongoDB's `_id`.
    `user_id` is stored as a PyObjectId to preserve the ObjectId relationship.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    file_name: str
    file_path: str
    uploaded_at: datetime
    status: str
    ocr_text: str | None = None
    lab_tests: list[LabTest] = []
    summary: str | None = None
    clinical_overview: ClinicalOverview | None = None
    error_message: str | None = None


class ReportSummary(BaseModel):
    """Lightweight report model for list endpoints.

    Intentionally omits `ocr_text` and `lab_tests` to reduce payload size.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    file_name: str
    uploaded_at: datetime
    status: str
    summary: str | None = None
