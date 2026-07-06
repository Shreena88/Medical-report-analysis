"""Authentication router: signup, login, profile.

Routes:
    POST /auth/signup  → 201 {"message": "User created"} | 409 on duplicate
    POST /auth/login   → 200 {access_token, token_type}  | 401 on bad creds
    GET  /auth/profile → 200 UserProfile                 | 401 if not authed
"""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr

from app.database import get_database
from app.dependencies import get_current_user
from app.models.user import UserCreate, UserInDB, UserProfile
from app.services.auth_service import authenticate_user, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas local to auth routes
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """JSON body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body for POST /auth/login."""
    access_token: str
    token_type: str = "bearer"


class SignupResponse(BaseModel):
    """Response body for POST /auth/signup."""
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupResponse,
    summary="Register a new user account",
)
async def signup(
    user_in: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> SignupResponse:
    """Create a new user.  Returns 409 if the email is already taken."""
    await register_user(user_in.email, user_in.password, user_in.gender, db)
    return SignupResponse(message="User created")


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
)
async def login(
    credentials: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> TokenResponse:
    """Verify email/password and return a signed JWT.  Returns 401 on failure."""
    user = await authenticate_user(credentials.email, credentials.password, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/profile",
    status_code=status.HTTP_200_OK,
    response_model=UserProfile,
    summary="Get the authenticated user's profile",
)
async def profile(
    current_user: UserInDB = Depends(get_current_user),
) -> UserProfile:
    """Return the authenticated user's profile.

    password_hash is intentionally excluded from the response via UserProfile.
    """
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        gender=current_user.gender,
        created_at=current_user.created_at,
    )
