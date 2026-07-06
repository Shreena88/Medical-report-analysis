"""Reports router: file upload and (future) CRUD endpoints.

Routes:
    POST /upload  → 202 {report_id, message} | 413 oversized | 422 wrong type

File-type detection uses magic-byte inspection of the first few bytes:
    PDF  → %PDF  (25 50 44 46)
    JPEG → FF D8 FF
    PNG  → 89 50 4E 47  (first 4 bytes of the 8-byte PNG signature)

Files are saved to the `uploads/` directory with a UUID4 filename
(preserving the original extension) to prevent path-traversal attacks.
"""

import os
import uuid
from datetime import datetime, timezone

import aiofiles
from bson import ObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.config import settings
from app.database import get_database
from app.dependencies import get_current_user
from app.models.report import Report, ReportSummary
from app.models.user import UserInDB
from app.services.report_service import run_pipeline

router = APIRouter(tags=["reports"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum bytes to read for magic-byte detection — 8 bytes covers all three
# formats.
_MAGIC_READ_BYTES = 8

# Mapping of detected MIME type → allowed extensions
_ALLOWED_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    report_id: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_mime(header: bytes) -> str | None:
    """Return the MIME type string by inspecting magic bytes, or None.

    Checks:
        PDF  — first 4 bytes == b'%PDF'
        JPEG — first 3 bytes == b'\\xff\\xd8\\xff'
        PNG  — first 4 bytes == b'\\x89PNG'
    """
    if header[:4] == b"%PDF":
        return "application/pdf"
    if header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if header[:4] == b"\x89PNG":
        return "image/png"
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadResponse,
    summary="Upload a lab report file and start the analysis pipeline",
)
async def upload_report(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UploadResponse:
    """Accept a PDF/JPG/PNG upload, persist it, and schedule the pipeline.

    Validation (in order):
    1. Read the first 8 bytes and validate magic bytes → 422 if invalid type.
    2. Read the rest of the file and enforce MAX_UPLOAD_SIZE_MB → 413 if over.
    3. Save to ``uploads/<uuid>.<ext>`` using aiofiles.
    4. Insert a Report document with ``status="pending"``.
    5. Schedule ``run_pipeline`` as a BackgroundTask.
    6. Return 202 ``{report_id, message}``.
    """
    # ------------------------------------------------------------------
    # Step 1 — magic-byte MIME detection
    # ------------------------------------------------------------------
    header = await file.read(_MAGIC_READ_BYTES)
    mime_type = _detect_mime(header)

    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported file type. Only PDF, JPEG, and PNG files are accepted. "
                "Please upload a valid lab report."
            ),
        )

    # ------------------------------------------------------------------
    # Step 2 — size enforcement
    # ------------------------------------------------------------------
    # Read the remainder of the file (we already consumed the header).
    remainder = await file.read()
    full_content = header + remainder

    max_bytes = settings.max_upload_size_bytes
    if len(full_content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File too large. Maximum allowed size is "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )

    # ------------------------------------------------------------------
    # Step 3 — persist to uploads/ with a UUID filename
    # ------------------------------------------------------------------
    extension = _ALLOWED_EXTENSIONS[mime_type]
    safe_filename = f"{uuid.uuid4()}{extension}"

    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, safe_filename)

    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(full_content)

    # ------------------------------------------------------------------
    # Step 4 — insert Report document
    # ------------------------------------------------------------------
    now = datetime.now(tz=timezone.utc)
    doc = {
        "user_id": ObjectId(str(current_user.id)),
        "file_name": file.filename or safe_filename,
        "file_path": file_path,
        "uploaded_at": now,
        "status": "pending",
        "ocr_text": None,
        "lab_tests": [],
        "summary": None,
        "error_message": None,
    }

    result = await db["reports"].insert_one(doc)
    report_id = str(result.inserted_id)

    # ------------------------------------------------------------------
    # Step 5 — schedule background pipeline
    # ------------------------------------------------------------------
    background_tasks.add_task(
        run_pipeline,
        report_id=report_id,
        file_path=file_path,
        user_id=str(current_user.id),
        gender=current_user.gender,
    )

    # ------------------------------------------------------------------
    # Step 6 — 202 Accepted
    # ------------------------------------------------------------------
    return UploadResponse(report_id=report_id, message="Processing started")


# ---------------------------------------------------------------------------
# CRUD Routes
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=list[ReportSummary],
    summary="Get all reports for the current user",
)
async def get_reports(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[ReportSummary]:
    """Retrieve all reports for the current user, sorted by uploaded_at desc.

    Intentionally returns lightweight ReportSummary objects.
    """
    cursor = db["reports"].find(
        {"user_id": ObjectId(str(current_user.id))}
    ).sort("uploaded_at", -1)
    
    reports = []
    async for doc in cursor:
        reports.append(
            ReportSummary(
                id=str(doc["_id"]),
                file_name=doc["file_name"],
                uploaded_at=doc["uploaded_at"],
                status=doc["status"],
                summary=doc.get("summary"),
            )
        )
    return reports


@router.get(
    "/report/{id}",
    response_model=Report,
    summary="Get full details of a specific report",
)
async def get_report(
    id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Report:
    """Retrieve full report details for the given ID.

    Validates ownership (returns 403 if user_id doesn't match) and existence (404).
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
        
    doc = await db["reports"].find_one({"_id": ObjectId(id)})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
        
    if doc["user_id"] != ObjectId(str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this report",
        )
        
    return Report(**doc)


@router.delete(
    "/report/{id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a report",
)
async def delete_report(
    id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> dict[str, str]:
    """Delete a report document and its associated file from disk.

    Validates ownership (403) and existence (404).
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
        
    doc = await db["reports"].find_one({"_id": ObjectId(id)})
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
        
    if doc["user_id"] != ObjectId(str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this report",
        )
        
    # Delete database record first
    await db["reports"].delete_one({"_id": ObjectId(id)})
    
    # Attempt to delete file from disk
    file_path = doc.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            # Log issue but don't fail the deletion response
            pass
            
    return {"message": "Report deleted successfully"}

