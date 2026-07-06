"""Pydantic model for the ReferenceRange domain.

A ReferenceRange document stores the normal min/max values for a lab test,
split by gender, along with a description and optional aliases for the test name.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import PyObjectId


class ReferenceRange(BaseModel):
    """Reference range document as stored in MongoDB."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    test_name: str
    aliases: list[str] = []
    unit: str
    male_min: float
    male_max: float
    female_min: float
    female_max: float
    description: str
