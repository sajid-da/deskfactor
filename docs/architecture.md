# System architecture

## Runtime components

```text
User
  ↓
React + TypeScript + Vite frontend
  ↓ multipart/form-data or text REST
FastAPI report API
  ├─ input/type/size validation
  ├─ text → direct source text
  ├─ PDF → PyMuPDF native text per page when useful
  │        sparse/scanned page → render to PNG → OCR.space
  ├─ image → OCR.space
  │        printed selection → Engine 2; auto/handwriting → Engine 3
  ├─ deterministic source-matched clinical extraction
  ├─ optional Gemini structured semantic refinement
  ├─ Pydantic schema + source excerpt validation
  ├─ deterministic missing/inconsistency/review checks
  ├─ local synthetic document-workflow classifier
  └─ SQLAlchemy persistence → SQLite local / managed Render PostgreSQL (deployment blueprint)
          ↓
       report and history REST responses → frontend
```

External OCR.space and Gemini services are called only by the backend. Neither secret is sent to the browser. PDF pages with sufficient native text do not incur OCR calls; a mixed PDF may combine local text extraction and OCR per page. Processing state in the UI describes the pending request because the API does not stream stage events.

![Architecture diagram](architecture.png)

## API surface

- `GET /health` returns a simple service health response.
- `POST /api/reports` accepts one text input or one uploaded file, with optional `writing_style` (`auto`, `printed`, `handwritten`).
- `GET /api/reports?limit=50` lists saved report summaries, newest first.
- `GET /api/reports/{id}` returns a saved report and its structured details.

The structured response includes `unclassified_information` for clinically relevant text that cannot confidently be placed in an existing category. These source-backed items carry a reason and require human review; they are not appended to patient demographics.

Request validation and document processing errors have explicit client or upstream status codes. OCR errors/timeouts are translated to 502/504; missing OCR configuration returns 503; invalid input/document formats return 4xx. Non-capacity Gemini failures are returned as 503 rather than silently presented as a successful refinement. Gemini 429/503 capacity after the configured fallback uses a local source-grounded report with an explicit provider-unavailable note and review flag.

## Data and trust boundaries

The API persists report fields and extraction/OCR provenance, not uploaded source bytes. The report payload can contain raw OCR text and normalized extracted text as report details. Gemini, when configured, receives a bounded text excerpt of the submitted document for semantic structuring. OCR.space receives the image bytes or rendered scanned PDF page. Use synthetic documents only until privacy/security controls and provider terms are reviewed.

Input is treated as untrusted. The backend owns secrets, validation, extraction, AI calls, and persistence. SQLAlchemy supports local SQLite and PostgreSQL via Compose. CORS is configurable. API keys must be provided using backend runtime environment configuration; never pass them through Vite variables or commit `.env`.

## Deployment status

The local Docker Compose topology remains. frontend/vercel.json configures SPA routing; render.yaml declares a free FastAPI service and a free managed PostgreSQL database in Singapore, with database-ready health checks and deploy-after-CI. These resources are not provisioned yet: provider sign-in, private OCR/Gemini secret entry, and the Vercel CORS origin are still required. No hosting payment is required. Render free web services sleep after 15 minutes without traffic; the free PostgreSQL database expires after 30 days and is deleted after its grace period. SQLAlchemy create_all initializes new databases; migrations are not configured. The API has no authentication or tenant isolation, so use synthetic records only.
