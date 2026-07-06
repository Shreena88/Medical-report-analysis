"""Trends router: retrieve historical test values for visualization.

Routes:
    GET /trends/{test_name}  → list of TrendPoint sorted by uploaded_at asc
"""

from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.database import get_database
from app.dependencies import get_current_user
from app.models.user import UserInDB

router = APIRouter(prefix="/trends", tags=["trends"])


class TrendPoint(BaseModel):
    """A single data point in a test trend series."""

    report_id: str
    uploaded_at: datetime
    value: float
    unit: str
    status: str


@router.get(
    "/{test_name}",
    response_model=list[TrendPoint],
    summary="Get historical trend data for a specific lab test",
)
async def get_test_trends(
    test_name: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[TrendPoint]:
    """Retrieve values for the given test name across all user's completed reports.

    Results are sorted in chronological order (uploaded_at ascending).
    Matching on test_name is case-insensitive.
    """
    cursor = db["reports"].find(
        {
            "user_id": ObjectId(str(current_user.id)),
            "status": "complete",
        }
    ).sort("uploaded_at", 1)

    trends: list[TrendPoint] = []
    async for doc in cursor:
        report_id = str(doc["_id"])
        uploaded_at = doc["uploaded_at"]

        # Find matching test case-insensitively
        for t in doc.get("lab_tests", []):
            current_name = t.get("test_name", "").strip().lower()
            target_name = test_name.strip().lower()
            if current_name == target_name:
                trends.append(
                    TrendPoint(
                        report_id=report_id,
                        uploaded_at=uploaded_at,
                        value=t["value"],
                        unit=t["unit"],
                        status=t["status"],
                    )
                )
                break  # Stop checking tests in the current report once matched

    return trends
