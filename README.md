# PulseAnalytics — AI Medical Report Analyzer

PulseAnalytics is a full-stack, AI-powered health intelligence web application designed to help users upload, OCR-process, analyze, and monitor physiological biomarker trends from clinical laboratory reports. 

Using **FastAPI** on the backend, **MongoDB** for persistence, **EasyOCR** for text digitization, **Groq Cloud (Llama 3.3 70B)** for structured medical extraction and context generation, and **React + TypeScript + Tailwind CSS** on the frontend, this app provides real-time feedback and timeline visualization of blood work metrics.

---

## Key Features

1. **Secure Authentication & Isolation**: User-specific registration and sessions. Bio-gender classification (Male/Female) is used to select corresponding clinical reference range thresholds.
2. **Multi-Format Ingestion**: Supports uploading lab reports in PDF, PNG, and JPEG formats, validating file integrity and size (<10MB) client-side and server-side.
3. **Advanced Async Processing Pipeline**:
   - **OCR Layer**: Automatic page layout rendering and text extraction via EasyOCR.
   - **Biomarker Extraction**: Large Language Model prompts structure unstructured text into valid JSON formats without diagnostic or prescriptive outputs.
   - **Clinical Checker**: Compares extracted values (e.g., Hemoglobin, WBC, ALT) against strict gender-appropriate physiological ranges.
   - **AI Context & Explanations**: Generates educational summaries and detailed explanation cards for out-of-range biomarkers.
4. **Interactive Dashboard**: Quick statistics, processing progress meters (polling states), and historical records management.
5. **Timeline Trend Charting**: Renders interactive time-series graphs mapping out-of-range fluctuations across multiple reports using Chart.js.

---

## Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── models/        # Pydantic schemas (User, Report, ReferenceRange)
│   │   ├── routers/       # API endpoints (Auth, Reports, Trends)
│   │   ├── services/      # Business logic (OCR, Groq LLM, Reference Checker)
│   │   ├── config.py      # Pydantic environment configurations
│   │   ├── database.py    # MongoDB Motor initialization & index creation
│   │   └── main.py        # FastAPI app initialization
│   ├── scripts/           # DB Seeding scripts
│   ├── tests/             # Pytest unit & property test suites
│   ├── uploads/           # Persisted upload storage
│   └── requirements.txt   # Python dependency manifest
└── frontend/
    ├── src/
    │   ├── api/           # Axios instance with auth interceptors
    │   ├── components/    # Reusable UI widgets (Navbar, Badges, Charts)
    │   ├── contexts/      # React Auth Context providers
    │   ├── pages/         # Page views (Dashboard, Analysis Detail, Trends)
    │   ├── App.tsx        # React Router routes and core shell
    │   └── main.tsx       # Vite entrypoint
    ├── tailwind.config.js # Styling configurations
    └── package.json       # Node package manager manifest
```

---

## Getting Started

### Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- **MongoDB** (running locally on port `27017` or a MongoDB Atlas connection string)
- **Groq API Key** (from [console.groq.com](https://console.groq.com/))

---

### Backend Setup

1. Navigate to the backend directory and configure your environment variables:
   ```bash
   cd backend
   ```
   Create a `.env` file containing:
   ```env
   MONGODB_URI=mongodb://localhost:27017/medical_analyzer
   JWT_SECRET_KEY=your-jwt-signing-secret-key-here
   GROQ_API_KEY=gsk_your_groq_api_credential_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
   ```

2. (Optional) Set up a python virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # On Windows
   source .venv/bin/activate    # On macOS/Linux
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Seed the clinical laboratory reference database ranges:
   ```bash
   python scripts/seed_reference_ranges.py
   ```

5. Run the FastAPI backend development server:
   ```bash
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

---

### Frontend Setup

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install the node modules:
   ```bash
   npm install
   ```

3. Run the development server (configured to run on port `3000` and proxy backend requests automatically):
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to **[http://localhost:3000](http://localhost:3000)**.

---

## Running Backend Tests

The backend includes a comprehensive testing suite comprising unit, integration, and property-based test modules. You can execute them by running:

```bash
cd backend
pytest
```

---

## Medical Disclaimer

This application is strictly for **educational and demonstration purposes only**. It does not diagnose, treat, or mitigate any disease or physiological condition, and must never be used as a substitute for professional medical advice, evaluation, or counseling.
