"""Motor async MongoDB client, collection accessors, and index creation.

The client is initialized once from config.MONGODB_URI.  All collection
accessors return the Motor AsyncIOMotorCollection for use in route handlers
and services.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import ASCENDING, DESCENDING

from app.config import settings

# Module-level Motor client — created once and reused across requests.
_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Return (and lazily create) the Motor client."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URI)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the default database from the connection URI."""
    return get_client().get_default_database()


# ---------------------------------------------------------------------------
# Collection accessors
# ---------------------------------------------------------------------------

def get_users_collection() -> AsyncIOMotorCollection:
    """Return the `users` collection."""
    return get_database()["users"]


def get_reports_collection() -> AsyncIOMotorCollection:
    """Return the `reports` collection."""
    return get_database()["reports"]


def get_reference_ranges_collection() -> AsyncIOMotorCollection:
    """Return the `reference_ranges` collection."""
    return get_database()["reference_ranges"]


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------

async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all required MongoDB indexes.

    Called once during the FastAPI lifespan startup event.
    Safe to call repeatedly — MongoDB is idempotent for existing indexes.
    """

    # users: unique index on email for fast lookups and duplicate prevention
    await db["users"].create_index(
        [("email", ASCENDING)],
        unique=True,
        name="users_email_unique",
    )

    # reports: compound index for per-user sorted list queries
    await db["reports"].create_index(
        [("user_id", ASCENDING), ("uploaded_at", DESCENDING)],
        name="reports_user_id_uploaded_at",
    )

    # reference_ranges: unique index on test_name
    await db["reference_ranges"].create_index(
        [("test_name", ASCENDING)],
        unique=True,
        name="reference_ranges_test_name_unique",
    )

    # reference_ranges: index on aliases array for alias lookups
    await db["reference_ranges"].create_index(
        [("aliases", ASCENDING)],
        name="reference_ranges_aliases",
    )
