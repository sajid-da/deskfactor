# Technical decisions

## Framework and boundaries

- **React + TypeScript + Vite:** a typed single-page application fits the upload/review/history workflow and has fast local development. OCR, provider credentials, parsing, and schema validation stay in FastAPI.
- **FastAPI + Pydantic:** multipart/text endpoints, OpenAPI, request validation, and report schemas make the backend boundary explicit. Provider and parsing errors are translated into client-safe responses.
- **SQLAlchemy:** one persistence layer supports SQLite for easy local setup and PostgreSQL for Compose. SQLite reduces setup friction; PostgreSQL is a closer hosted relational database. Production migrations are not yet included; `create_all` is used.
- **PyMuPDF:** native PDF text is cheaper and more faithful when usable; page-wise selection also supports mixed text/scanned PDFs. Sparse pages are rendered for OCR rather than blindly OCRing every page.

## OCR.space and Gemini

- **OCR.space:** selected as an external OCR provider for actual image/scanned-page recognition. Engine 2 is selected for explicitly printed documents and Engine 3 for automatic/handwritten mode. Reusing this single external OCR integration avoids a parallel OCR stack. It adds outbound network, quota, service-availability, data-transfer, and language/handwriting limitations. Provider confidence is not fabricated; OCR status and text provenance are recorded.
- **Gemini:** used for semantic understanding and structured clinical information extraction from text produced by the document-processing/OCR layer. It is not used to recognize pixels, and no Gemini model is trained by this project. An alternate configured model is tried for capacity failures; if both return 429/503, a marked deterministic baseline allows source-supported information to remain reviewable. Other provider errors fail visibly. Gemini receives document text when configured, so data handling terms must be reviewed before any sensitive use.
- **Optional OpenAI compatibility:** retained for configurations where Gemini is not set and OpenAI is. It is not required for the documented default path.

## Extraction and review classifier

- A narrow deterministic source-matched extractor complements semantic extraction and preserves matched report fields. Pydantic validation and source-excerpt checks reduce malformed/unsupported output, but do not establish clinical truth. Deterministic missing/inconsistency checks are explainable and deliberately conservative.
- Document-aware categorization leaves absent fields empty, restricts demographics to patient/encounter facts, and preserves unassigned clinically relevant text in `unclassified_information` with provenance and a review marker, and keeps billing/consent/provider-directory material in `administrative_information`. It avoids fixed field distributions and catch-all demographic buckets; the deterministic fallback remains narrow, so ambiguous narrative is preserved instead of semantically overclaimed.
- The TF-IDF + multinomial logistic regression model is local, inexpensive, and reproducibly trainable from a tiny synthetic dataset. It routes document workflow only; it must never be interpreted as clinical risk or triage. Tiny data means weak generalization and uncalibrated scores.
- External OCR/LLM services were chosen over training everything locally because representative labeled clinical datasets and model-development governance are unavailable. The project does not claim its own OCR or clinical language model.

## Persistence, UI, and security

- Persist structured reports, timestamps, status, and processing provenance for history; do not persist uploaded source bytes. Report details include extracted/raw OCR text, so synthetic-only use remains necessary.
- Frontend receives backend report fields and request-level pending/error/success state. It does not fake per-stage OCR/AI progress because the API is synchronous and has no stage event stream.
- Credentials are backend environment variables. Root `.env`/backend `.env`, databases, logs, caches, dependencies, and build output must stay out of Git. CORS is configurable. There is no authentication, tenant boundary, production retention policy, rate limiting, or production encryption/monitoring setup.

## Deployment and trade-offs

Docker Compose provides local PostgreSQL, FastAPI, and Nginx frontend integration. No public hosting project/URL or deploy workflow is configured. CI runs tests/build only. To deploy, provision managed frontend/API/database services, secrets, HTTPS and CORS, persistent database/backup procedures, migrations, monitoring, and then exercise the full flow with synthetic files. Synchronous OCR/LLM calls can tie up workers; production should add job queues, cancellation, retries/idempotency, rate limits, and bounded concurrency.

## Known weaknesses and future improvements

Representative handwriting and multilingual OCR evaluations; stronger table/prescription parsing; medication normalization with explicit provenance and human confirmation; broader source-grounding evaluation; calibrated workflow confidence; structured audit and retention controls; authentication/authorization; database migrations; resilient background jobs; monitoring; accessibility and browser/device visual QA; and privacy/legal review of external services are required before considering clinical or production use.
