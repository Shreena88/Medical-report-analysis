"""FastAPI application factory.

Responsibilities:
- Configure CORS middleware using ALLOWED_ORIGINS from settings.
- Create the `uploads/` directory on startup.
- Run create_indexes during the lifespan startup event.
- Register all routers (stubs included for future tasks).
- Expose /docs (FastAPI OpenAPI UI) automatically.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_indexes, get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler."""
    # --- Startup ---
    # Ensure the uploads directory exists
    os.makedirs("uploads", exist_ok=True)

    # Create MongoDB indexes
    db = get_database()
    await create_indexes(db)

    yield

    # --- Shutdown (nothing to tear down for now) ---


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application."""
    app = FastAPI(
        title="AI Medical Report Analyzer",
        description=(
            "Upload lab reports, extract medical data via OCR and LLM, "
            "compare values against reference ranges, and visualize trends. "
            "This application is strictly educational and not a substitute "
            "for professional medical advice."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS middleware
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Router registration
    # Routers are imported here; each module is a stub until its task
    # is implemented.  Import errors from missing routers are caught so
    # the app can still start during early scaffold tasks.
    # ------------------------------------------------------------------
    try:
        from app.routers import auth  # noqa: F401 — task 3
        app.include_router(auth.router)
    except (ImportError, AttributeError):
        pass

    try:
        from app.routers import reports  # noqa: F401 — tasks 5, 11
        app.include_router(reports.router)
    except (ImportError, AttributeError):
        pass

    try:
        from app.routers import trends  # noqa: F401 — task 11
        app.include_router(trends.router)
    except (ImportError, AttributeError):
        pass

    return app


# Module-level app instance used by uvicorn and tests
app = create_app()
