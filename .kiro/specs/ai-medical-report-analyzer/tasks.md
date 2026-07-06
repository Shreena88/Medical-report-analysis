# Implementation Plan: AI Medical Report Analyzer

## Overview

Incremental implementation of a FastAPI + React full-stack application for uploading, OCR-processing, AI-analyzing, and visualizing lab reports. Tasks follow the processing pipeline order: project scaffold → auth → file upload → OCR → AI extraction → reference checking → AI explanations → report CRUD → frontend → dashboard → trends → Docker.

## Tasks

- [x] 1. Project scaffold and configuration
  - Create `backend/app/` directory structure with empty `__init__.py` files in each package
  - Implement `config.py` using `pydantic-settings`: declare all required env vars (`MONGODB_URI`, `JWT_SECRET_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`) with startup `ValidationError` on missing values; optional vars with defaults (`JWT_EXPIRY_MINUTES=60`, `MAX_UPLOAD_SIZE_MB=10`, `ALLOWED_ORIGINS`)
  - Implement `database.py`: Motor `AsyncIOMotorClient` initialized from `config.MONGODB_URI`, expose collection accessors (`users`, `reports`, `reference_ranges`), create all MongoDB indexes on startup
  - Implement `main.py`: FastAPI app factory, CORS middleware, `uploads/` directory creation, lifespan event that creates indexes, router registration placeholders
  - Create `backend/requirements.txt` with pinned versions for: `fastapi`, `uvicorn[standard]`, `motor`, `pydantic[email]`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `easyocr`, `pdf2image`, `Pillow`, `groq`, `pytest`, `pytest-asyncio`, `httpx`
  - Create `frontend/` with `npm create vite@latest` scaffold (React + TypeScript), install `tailwindcss`, `axios`, `react-router-dom`, `chart.js`, `react-chartjs-2`
  - _Requirements: 11.1, 11.2_

- [x] 2. Pydantic data models
  - [x] 2.1 Implement backend Pydantic models
    - `models/user.py`: `UserCreate` (email, password min_length=8, gender Literal), `UserInDB`, `UserProfile` (excludes password_hash)
    - `models/report.py`: `LabTest` (test_name, value, unit, reference_range, status Literal LOW/NORMAL/HIGH/UNKNOWN, explanation), `Report`, `ReportSummary` (omits ocr_text and lab_tests)
    - `models/reference_range.py`: `ReferenceRange` with male/female min/max fields
    - Define `PyObjectId` custom type for MongoDB `_id` serialization
    - _Requirements: 1.5, 4.2, 4.6, 5.2, 7.2_

  - [x] 2.2 Write property test for LabTest model
    - **Property 1: LabTest status field only accepts LOW, NORMAL, HIGH, UNKNOWN**
    - **Validates: Requirements 5.2, 12.5**

- [x] 3. Auth service and router
  - [x] 3.1 Implement `services/auth_service.py`
    - `register_user`: hash password with bcrypt work factor ≥ 12, insert to `users`, raise `409` on duplicate email
    - `authenticate_user`: fetch user by email, verify bcrypt hash, return `UserInDB | None`
    - `create_access_token`: sign HS256 JWT with `JWT_SECRET_KEY` and configurable expiry
    - `verify_token`: decode JWT, raise `HTTPException 401` on invalid/expired token
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7_

  - [x] 3.2 Implement `dependencies.py`
    - `get_current_user` dependency: extract Bearer token from `Authorization` header, call `verify_token`, fetch and return `UserInDB`; raise `401` if missing or inx`valid
    - _Requirements: 1.6_

  - [x] 3.3 Implement `routers/auth.py`
    - `POST /auth/signup` → `201` on success, `409` on duplicate email
    - `POST /auth/login` → `200 {access_token, token_type}`, `401` on bad credentials
    - `GET /auth/profile` → `200 UserProfile` (requires `get_current_user`); password_hash must not appear in response
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 3.4 Write unit tests for auth service
    - Test duplicate email returns 409
    - Test invalid credentials return 401
    - Test JWT contains correct subject and expiry
    - Test `UserProfile` response never includes `password_hash`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [~] 4. Checkpoint — auth layer complete
  - Ensure all auth tests pass. Start `uvicorn app.main:app --reload` and verify `/docs` shows auth routes. Ask the user if questions arise.

- [x] 5. File upload endpoint
  - [x] 5.1 Implement file upload in `routers/reports.py`
    - `POST /upload`: validate MIME type server-side (PDF/JPG/PNG only → `422`), enforce `MAX_UPLOAD_SIZE_MB` → `413`, save file to `uploads/` with UUID filename to prevent path traversal, insert `Report` document (status=`pending`), launch `run_pipeline` as `BackgroundTask`, return `202 {report_id}`
    - Use async file I/O (`aiofiles` or `SpooledTemporaryFile`) so uploads don't block the event loop
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 5.2 Write unit tests for file upload
    - Test unsupported file type returns 422
    - Test oversized file returns 413
    - Test valid upload returns 202 with a report_id
    - Test saved filename is a UUID (not the original filename)
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 6. OCR service
  - [x] 6.1 Implement `services/ocr_service.py`
    - Define `OCRProvider` Protocol with `extract_text(file_path: str) -> str`
    - Implement `EasyOCRProvider`: PDF → `pdf2image` → list of PIL images → EasyOCR each page → concatenate; JPG/PNG → EasyOCR directly
    - `get_ocr_provider()` factory returns `EasyOCRProvider` instance
    - Raise `OCRError` (custom exception) on any extraction failure
    - _Requirements: 3.1, 3.4, 3.5_

  - [x] 6.2 Write property test for OCR provider interface
    - **Property 2: Any OCRProvider implementation returns a non-empty string for valid input files**
    - **Validates: Requirements 3.1, 3.5**

- [x] 7. Lab test extractor
  - [x] 7.1 Implement `services/extractor.py`
    - Initialize Groq client from `config.GROQ_API_KEY` and `config.GROQ_MODEL`
    - Define `EXTRACTION_SYSTEM_PROMPT` that prohibits diagnostic content and specifies exact JSON output format
    - `extract_tests(ocr_text: str) -> list[LabTest]`: call Groq API, `json.loads` response, validate each item with `LabTest` Pydantic model, raise `ExtractionError` if parsing fails, never store partial data
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 7.2 Write unit tests for extractor
    - Test valid Groq JSON response → correctly parsed `list[LabTest]`
    - Test malformed JSON raises `ExtractionError` without storing partial data
    - Test system prompt text contains prohibition keywords (no "diagnos", no "medic", no "treat")
    - _Requirements: 4.4, 4.5, 12.4_

- [x] 8. Reference range checker
  - [x] 8.1 Seed reference ranges data
    - Create `backend/scripts/seed_reference_ranges.py` that inserts at minimum 10 test entries: Hemoglobin, Blood Sugar (Glucose), Vitamin D, Platelets, WBC, RBC, Hematocrit, Creatinine, ALT, AST — each with male/female min/max, unit, aliases, description
    - _Requirements: 5.1_

  - [x] 8.2 Implement `services/reference_checker.py`
    - `check_ranges(tests: list[LabTest], gender: str, db) -> list[LabTest]`
    - For each test: query `reference_ranges` by `test_name` or `aliases` (case-insensitive `$regex` or `$in`)
    - Select male or female thresholds by `gender`
    - Compare value using Python `<` / `>` only — no LLM
    - Set `status` = `LOW` / `NORMAL` / `HIGH` if found, `UNKNOWN` if not found; always continue
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.5_

  - [x] 8.3 Write property test for reference checker
    - **Property 3: A value strictly below min → LOW; strictly above max → HIGH; within [min, max] → NORMAL**
    - **Validates: Requirements 5.2, 5.3, 12.5**

  - [x] 8.4 Write property test for unknown handling
    - **Property 4: A test_name with no matching reference range always yields status UNKNOWN and does not raise an exception**
    - **Validates: Requirements 5.4**

- [x] 9. AI explanation service
  - [x] 9.1 Implement `services/ai_service.py`
    - Define `EXPLANATION_SYSTEM_PROMPT` prohibiting diagnoses, medication names, treatment plans; requiring "consult a healthcare professional" advisory
    - `generate_explanations(tests: list[LabTest]) -> ExplanationResult`
    - Parse response into `{summary: str, explanations: [{name, explanation}]}`
    - On empty or unparseable response: log error, return safe fallback `ExplanationResult` (never raise)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 12.4_

  - [x] 9.2 Write unit tests for AI service fallback
    - Test unparseable Groq response returns fallback `ExplanationResult` without raising
    - Test system prompt contains prohibition keywords and "consult" advisory
    - _Requirements: 6.4, 6.5, 12.2, 12.4_

- [ ] 10. Report pipeline orchestrator
  - [~] 10.1 Implement `services/report_service.py`
    - `run_pipeline(report_id, file_path, user_id, gender)`: sequentially call OCR → Extractor → Reference_Checker → AI_Service; update `Report.status` in MongoDB after each step (`ocr_complete` → `extracted` → `validated` → `complete`); on `OCRError` → set `failed_ocr`; on `ExtractionError` → set `failed_extraction`; AI_Service failures use fallback (status remains `complete`)
    - Wire pipeline into the `POST /upload` `BackgroundTask`
    - _Requirements: 3.1, 3.2, 3.3, 4.3, 5.5, 6.3_

  - [~] 10.2 Write property test for pipeline status transitions
    - **Property 5: Report status only ever moves forward through the defined sequence and never regresses to an earlier state**
    - **Validates: Requirements 3.2, 3.3**

- [~] 11. Report CRUD routes
  - [~] 11.1 Implement report list and detail in `routers/reports.py`
    - `GET /reports`: Motor query `{user_id: current_user.id}` sorted by `uploaded_at` desc, return `list[ReportSummary]`
    - `GET /report/{id}`: fetch full `Report`; return `403` if `user_id` mismatch, `404` if not found
    - All queries include `user_id` filter (user isolation)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6_

  - [~] 11.2 Implement report delete in `routers/reports.py`
    - `DELETE /report/{id}`: verify ownership (`403` / `404`), delete MongoDB document, delete file from `uploads/`
    - _Requirements: 7.5, 7.6_

  - [~] 11.3 Implement trends route in `routers/trends.py`
    - `GET /trends/{test_name}`: aggregate across user's completed reports, find matching `LabTest` by `test_name` (case-insensitive), return `[{report_id, uploaded_at, value, unit, status}]` sorted by `uploaded_at` asc
    - _Requirements: 10.1_

  - [~] 11.4 Write unit tests for report routes
    - Test `GET /report/{id}` for another user's report returns 403
    - Test `GET /report/{id}` for non-existent id returns 404
    - Test `DELETE /report/{id}` removes document and file
    - _Requirements: 7.3, 7.4, 7.5_

- [~] 12. Checkpoint — backend complete
  - Ensure all backend tests pass. Verify `/docs` shows all routes. Ask the user if questions arise.

- [~] 13. Frontend scaffold and API layer
  - [~] 13.1 Set up React Router and Axios instance
    - `api/axios.ts`: Axios instance with `baseURL = VITE_API_URL`, attach `Authorization: Bearer <token>` from localStorage on every request, 401 interceptor clears token and redirects to `/login`
    - `contexts/AuthContext.tsx`: store JWT in localStorage, expose `login`, `logout`, `user` state
    - `components/ProtectedRoute.tsx`: redirect to `/login` if no JWT
    - `App.tsx`: React Router v6 routes for `/login`, `/signup`, `/dashboard`, `/report/:id`, `/trends`
    - _Requirements: 8.5_

  - [~] 13.2 Implement API modules
    - `api/auth.ts`: `login(email, password)`, `signup(...)`, `getProfile()`
    - `api/reports.ts`: `uploadReport(file)`, `getReports()`, `getReport(id)`, `deleteReport(id)`
    - `api/trends.ts`: `getTrends(test_name)`
    - _Requirements: 8.5, 9.1, 10.1_

- [~] 14. Auth pages
  - Implement `pages/LoginPage.tsx`: form with email + password fields, calls `api/auth.login`, stores JWT in `AuthContext`, redirects to `/dashboard`
  - Implement `pages/SignupPage.tsx`: form with email, password, gender select, calls `api/auth.signup`, redirects to `/login` on success
  - Implement `components/Navbar.tsx`: shows user email, logout button (clears `AuthContext`)
  - _Requirements: 1.1, 1.3_

- [~] 15. Shared components
  - [~] 15.1 Implement reusable UI components
    - `components/StatusBadge.tsx`: renders color-coded badge — red for LOW, green for NORMAL, orange for HIGH, gray for UNKNOWN
    - `components/MedicalDisclaimer.tsx`: persistent banner "This information is educational only and not a substitute for professional medical advice"
    - `components/ReportCard.tsx`: summary card showing file name, upload date, status badge, link to detail page
    - _Requirements: 9.4, 9.5, 6.6, 12.3_

- [~] 16. Report detail page
  - [~] 16.1 Implement `pages/ReportDetailPage.tsx`
    - On mount: `GET /report/:id`; if status is pending/processing, poll every 3 seconds until `complete` or a failed state
    - Display file name, upload date, pipeline status
    - Render `LabTestRow` component for each Lab_Test: test name, value, unit, `StatusBadge`, reference range, AI explanation
    - Collapsible section for raw OCR text
    - Render `MedicalDisclaimer` prominently
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [~] 16.2 Implement `components/LabTestRow.tsx`
    - Display one row: test_name | value + unit | `StatusBadge` | reference_range | explanation text
    - _Requirements: 9.2, 9.4_

- [~] 17. Dashboard page
  - Implement `pages/DashboardPage.tsx`
    - Fetch `GET /reports` on mount
    - Display: total report count, list of recent uploads (file name + date) using `ReportCard`, latest report AI summary, count and names of HIGH/LOW tests from most recent complete report
    - Upload button: file picker → `api/reports.uploadReport` → navigate to new report's detail page
    - Render `MedicalDisclaimer`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 12.3_

- [~] 18. Trends page
  - [~] 18.1 Implement `components/TrendChart.tsx`
    - Wrap Chart.js `Line` chart via `react-chartjs-2`; accept `{test_name, data: [{uploaded_at, value, status}]}` as props
    - Plot value over time with date labels on x-axis
    - _Requirements: 10.1, 10.2_

  - [~] 18.2 Implement `pages/TrendsPage.tsx`
    - For each tracked test (Hemoglobin, Blood Sugar, Vitamin D, Platelets): call `GET /trends/{test_name}`
    - If data has ≥ 2 points: render `TrendChart`; otherwise render placeholder message
    - _Requirements: 10.1, 10.2, 10.3_

- [~] 19. Docker Compose and environment configuration
  - Create `backend/Dockerfile` (python:3.11-slim, pip install requirements, uvicorn entrypoint)
  - Create `frontend/Dockerfile` (node:20-alpine build stage + nginx:alpine serve stage)
  - Create `frontend/nginx.conf`: serve React SPA, proxy `/auth`, `/upload`, `/reports`, `/report`, `/trends` to backend
  - Create `docker-compose.yml` with `backend` (port 8000, `uploads/` volume mount, `env_file: .env`) and `frontend` (port 3000, depends_on backend) services
  - Create `.env.example` listing all required and optional env vars with placeholder values
  - _Requirements: 11.1, 11.2, 11.4_

- [~] 20. Final checkpoint — full integration
  - Ensure all backend tests pass, frontend builds without errors, `/docs` is accessible at `http://localhost:8000/docs`. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness; unit tests validate specific examples and edge cases
- The Reference_Checker is the sole arbiter of LOW/NORMAL/HIGH — LLMs are never used for this decision
- Medical disclaimers must appear on every page displaying AI-generated content (Requirements 6.6, 12.3)
