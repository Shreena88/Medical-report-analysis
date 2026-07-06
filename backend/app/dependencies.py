"""FastAPI dependency providers for the application.

`get_current_user` extracts and validates the Bearer JWT from the
Authorization header and returns the corresponding UserInDB document.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.models.user import UserInDB
from app.services.auth_service import verify_token

# OAuth2PasswordBearer extracts the token from the Authorization: Bearer header.
# tokenUrl is the login endpoint — used by OpenAPI's "Authorize" UI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserInDB:
    """Resolve the currently authenticated user from the Bearer JWT.

    1. Extracts the Bearer token via OAuth2PasswordBearer.
    2. Decodes and validates the token with `verify_token` (raises 401 on error).
    3. Fetches the user document from MongoDB by the subject (user_id).
    4. Returns the UserInDB; raises 401 if the user no longer exists.

    Raises:
        HTTPException 401: if the token is missing, invalid, or the user is gone.
    """
    user_id = verify_token(token)  # raises 401 if invalid

    from bson import ObjectId

    raw = await db["users"].find_one({"_id": ObjectId(user_id)})
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserInDB(**raw)
