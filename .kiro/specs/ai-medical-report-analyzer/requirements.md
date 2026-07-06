# Requirements Document

## Introduction

The AI Medical Report Analyzer is a web application that allows authenticated users to upload laboratory reports (PDF or image), extracts medical information using OCR, analyzes the report using an LLM (Groq API), stores all data in MongoDB Atlas, and presents an easy-to-understand dashboard with trend charts.

The system is strictly an educational and informational tool. It extracts and explains lab values, compares them to reference ranges, and generates plain-language summaries. It never diagnoses diseases, never prescribes medication, and always displays a medical disclaimer.

## Glossary

- **System**: The AI Medical Report Analyzer application as a whole
- **Backend**: The FastAPI server handling authentication, file upload, OCR, AI extraction, and analysis
- **Frontend**: The React single-page application presenting the user interface
- **User**: An authenticated human interacting with the system via the Frontend
- **OCR_Service**: The service responsible for extracting text from uploaded files using EasyOCR
- **Extractor**: The service that sends OCR text to the Groq LLM and parses structured test data from the response
- **Reference_Checker**: The Python service that compares extracted lab values against stored reference ranges to produce LOW / NORMAL / HIGH statuses
- **AI_Service**: The service that sends validated, structured test data to the Groq LLM to generate plain-language educational explanations
- **Auth_Service**: The service handling user registration, login, JWT issuance, and password hashing
- **Report**: A document record in MongoDB representing one uploaded file, its OCR text, extracted tests, statuses, and AI summary
- **Lab_Test**: A single laboratory measurement extracted from a Report, containing test name, value, unit, reference range, and status
- **Reference_Range**: A MongoDB document defining normal male/female minimum and maximum values, unit, and description for a given test name or alias
- **JWT**: JSON Web Token used to authenticate API requests after login
- **Groq_Client**: The HTTP client configured to call the Groq API using the model specified by the GROQ_MODEL environment variable
- **Dashboard**: The Frontend page displaying aggregated statistics, recent uploads, and abnormal result summaries
- **Trend_Chart**: A Chart.js visualization showing a specific lab test value across multiple Reports over time

---

## Requirements

### Requirement 1: User Registration and Authentication

**User Story:** As a new user, I want to create an account and log in, so that my reports are private and tied to my identity.

#### Acceptance Criteria

1. WHEN a POST request is made to `/signup` with a valid email and password, THE Auth_Service SHALL create a new user record with the password hashed using bcrypt and return a success response.
2. WHEN a POST request is made to `/signup` with an email that already exists, THE Auth_Service SHALL return a 409 Conflict error with a descriptive message.
3. WHEN a POST request is made to `/login` with valid credentials, THE Auth_Service SHALL return a signed JWT with a configurable expiry.
4. WHEN a POST request is made to `/login` with invalid credentials, THE Auth_Service SHALL return a 401 Unauthorized error.
5. WHEN a GET request is made to `/profile` with a valid JWT in the Authorization header, THE Auth_Service SHALL return the authenticated user's profile data excluding the password hash.
6. IF a request is made to any protected endpoint without a valid JWT, THEN THE Backend SHALL return a 401 Unauthorized error.
7. THE Auth_Service SHALL hash all passwords using bcrypt before storing them in MongoDB.

---

### Requirement 2: File Upload

**User Story:** As a user, I want to upload a PDF or image of my lab report, so that the system can process and analyze it.

#### Acceptance Criteria

1. WHEN an authenticated user submits a POST request to `/upload` with a file of type PDF, JPG, or PNG, THE Backend SHALL save the file to the `uploads/` directory and store file metadata (user_id, file_name, uploaded_at) in the `reports` MongoDB collection.
2. WHEN a file is uploaded, THE Backend SHALL assign a unique identifier to the Report and return it in the response.
3. IF the uploaded file is not of type PDF, JPG, or PNG, THEN THE Backend SHALL return a 422 Unprocessable Entity error with a descriptive message.
4. IF the uploaded file exceeds the maximum allowed size, THEN THE Backend SHALL return a 413 Payload Too Large error.
5. WHILE a file upload is in progress, THE Backend SHALL use async I/O so that other requests are not blocked.

---

### Requirement 3: OCR Text Extraction

**User Story:** As a user, I want the system to extract text from my uploaded report, so that the content can be analyzed.

#### Acceptance Criteria

1. WHEN a file is successfully saved, THE OCR_Service SHALL extract text from the file using EasyOCR and store the resulting text in the corresponding Report document in MongoDB.
2. WHEN OCR extraction succeeds, THE Backend SHALL update the Report's status to indicate OCR is complete before triggering AI extraction.
3. IF OCR extraction fails for any reason, THEN THE Backend SHALL update the Report's status to reflect the failure and return a descriptive error response without proceeding to AI extraction.
4. THE OCR_Service SHALL support PDF, JPG, and PNG input formats.
5. THE OCR_Service SHALL be implemented behind an interface so that the underlying OCR provider (e.g., EasyOCR or Google Vision API) can be swapped without modifying business logic.

---

### Requirement 4: AI-Powered Lab Test Extraction

**User Story:** As a user, I want the system to identify and extract individual lab test results from my report, so that each test can be analyzed separately.

#### Acceptance Criteria

1. WHEN OCR text is available for a Report, THE Extractor SHALL send the OCR text to the Groq API using the model specified by the `GROQ_MODEL` environment variable and request structured JSON output.
2. THE Extractor SHALL parse the Groq response into an array of Lab_Test objects, each containing `test_name`, `value`, `unit`, and `reference_range` fields.
3. THE Extractor SHALL store the parsed Lab_Test array in the corresponding Report document in MongoDB.
4. IF the Groq API returns a response that cannot be parsed into the expected JSON structure, THEN THE Extractor SHALL log the error and return a descriptive error response without storing partial data.
5. THE Extractor SHALL never add diagnostic conclusions, disease names, or treatment recommendations to the extracted data.
6. THE Extractor SHALL use Pydantic models to validate the structure of all data received from the Groq API before storing it.

---

### Requirement 5: Reference Range Validation

**User Story:** As a user, I want each lab test result to be compared against normal reference ranges, so that I can see which values are LOW, NORMAL, or HIGH.

#### Acceptance Criteria

1. WHEN Lab_Tests have been extracted for a Report, THE Reference_Checker SHALL look up each test by `test_name` or any configured alias in the `reference_ranges` MongoDB collection.
2. WHEN a matching Reference_Range is found, THE Reference_Checker SHALL compare the test value against the male or female thresholds based on the user's profile and assign a status of `LOW`, `NORMAL`, or `HIGH`.
3. THE Reference_Checker SHALL perform all range comparisons using Python arithmetic, never delegating this logic to the LLM.
4. WHEN no matching Reference_Range is found for a test, THE Reference_Checker SHALL assign a status of `UNKNOWN` and continue processing remaining tests.
5. THE Reference_Checker SHALL store the status on each Lab_Test object in MongoDB after comparison.

---

### Requirement 6: AI Explanation Generation

**User Story:** As a user, I want plain-language explanations of my abnormal lab results, so that I can understand what they mean without needing medical training.

#### Acceptance Criteria

1. WHEN reference range validation is complete, THE AI_Service SHALL send the validated Lab_Test array (including statuses) to the Groq API and request educational explanations in plain language.
2. THE AI_Service SHALL parse the Groq response into a summary string and an array of per-test explanation objects, each containing `name` and `explanation` fields.
3. THE AI_Service SHALL store the summary and explanations in the corresponding Report document in MongoDB.
4. THE AI_Service SHALL instruct the Groq API via the system prompt to never include disease diagnoses, medication names, or treatment recommendations in the explanations.
5. IF the Groq API returns an unparseable or empty response, THEN THE AI_Service SHALL log the error and store a fallback message indicating explanations are unavailable, without failing the entire Report.
6. THE System SHALL include a medical disclaimer on every page that displays AI-generated content, stating that the information is educational only and not a substitute for professional medical advice.

---

### Requirement 7: Report Storage and Retrieval

**User Story:** As a user, I want to view, list, and delete my uploaded reports, so that I can manage my medical history in the system.

#### Acceptance Criteria

1. WHEN an authenticated user sends a GET request to `/reports`, THE Backend SHALL return a list of all Reports belonging to that user, ordered by `uploaded_at` descending.
2. WHEN an authenticated user sends a GET request to `/report/{id}`, THE Backend SHALL return the full Report document including OCR text, extracted tests, statuses, and AI explanation for the report with the given id.
3. IF a user requests a Report that does not belong to them, THEN THE Backend SHALL return a 403 Forbidden error.
4. IF a user requests a Report with an id that does not exist, THEN THE Backend SHALL return a 404 Not Found error.
5. WHEN an authenticated user sends a DELETE request to `/report/{id}` for a Report they own, THE Backend SHALL delete the Report document from MongoDB and the associated file from the `uploads/` directory.
6. THE Backend SHALL use Motor (async MongoDB driver) for all database operations to avoid blocking the event loop.

---

### Requirement 8: Dashboard

**User Story:** As a user, I want a dashboard showing an overview of my reports, so that I can quickly see my health data trends.

#### Acceptance Criteria

1. WHEN an authenticated user navigates to the Dashboard page, THE Frontend SHALL display the total number of Reports for that user.
2. WHEN an authenticated user navigates to the Dashboard page, THE Frontend SHALL display the most recent uploads with file name and upload date.
3. WHEN an authenticated user navigates to the Dashboard page, THE Frontend SHALL display a summary of the latest Report's AI-generated explanation.
4. WHEN an authenticated user navigates to the Dashboard page, THE Frontend SHALL display a count and list of Lab_Tests with `HIGH` or `LOW` status across the most recent Report.
5. THE Frontend SHALL fetch all Dashboard data from the Backend APIs using Axios and JWT authentication headers.

---

### Requirement 9: Report Detail View

**User Story:** As a user, I want to see the full details of a single report, so that I can review all extracted tests and explanations.

#### Acceptance Criteria

1. WHEN a user navigates to the Report detail page, THE Frontend SHALL display the file name, upload date, and processing status of the Report.
2. WHEN a user navigates to the Report detail page, THE Frontend SHALL display each Lab_Test with its name, value, unit, status (LOW / NORMAL / HIGH), reference range, and AI explanation.
3. WHEN a user navigates to the Report detail page, THE Frontend SHALL display the raw OCR text in a collapsible section.
4. THE Frontend SHALL visually distinguish LOW, NORMAL, and HIGH statuses using color coding.
5. THE Frontend SHALL display the medical disclaimer prominently on the Report detail page.

---

### Requirement 10: Trend Charts

**User Story:** As a user, I want to see how specific lab values change across multiple reports over time, so that I can track my health trends.

#### Acceptance Criteria

1. WHEN a user has more than one Report containing a tracked test (Hemoglobin, Blood Sugar, Vitamin D, or Platelets), THE Frontend SHALL render a Trend_Chart for each such test showing value over time.
2. THE Frontend SHALL render all Trend_Charts using Chart.js.
3. WHEN a user has only one Report or no data for a tracked test, THE Frontend SHALL display a placeholder message instead of an empty chart.

---

### Requirement 11: Security and Configuration

**User Story:** As a system operator, I want all secrets and configuration to be managed via environment variables, so that credentials are never hardcoded.

#### Acceptance Criteria

1. THE Backend SHALL read the MongoDB connection string, JWT secret key, Groq API key, and GROQ_MODEL from environment variables at startup.
2. IF any required environment variable is missing at startup, THEN THE Backend SHALL log a descriptive error and refuse to start.
3. THE Backend SHALL never log or expose JWT secrets, API keys, or password hashes in API responses or log output.
4. THE Backend SHALL enforce HTTPS-only communication in production configuration.
5. THE Backend SHALL include OpenAPI documentation automatically generated by FastAPI, accessible at `/docs`.

---

### Requirement 12: Prohibited Actions (Safety Guardrails)

**User Story:** As a system operator, I want the system to be strictly scoped to educational content, so that users are never misled into thinking the system provides medical diagnoses.

#### Acceptance Criteria

1. THE System SHALL never include disease diagnosis statements in any API response or UI display.
2. THE System SHALL never include medication names, dosage recommendations, or treatment plans in any API response or UI display.
3. THE System SHALL display a medical disclaimer on every page that presents AI-generated content.
4. THE Extractor AND THE AI_Service SHALL use system prompts that explicitly instruct the Groq model to refuse to generate diagnostic or prescriptive content.
5. THE Reference_Checker SHALL be the sole component responsible for assigning LOW / NORMAL / HIGH status, using only Python arithmetic against stored reference ranges.
