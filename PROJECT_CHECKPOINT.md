# Project Checkpoint

## Current Phase
PHASE_29 — compliance audit, document-aware extraction correction, and safe GitHub publication

## Overall Status
IN_PROGRESS — local checks pass. Public deployment and hosted CI are not yet verified.

## Completed
- Audited application/code/tests/docs against the assignment and added `PROJECT_COMPLIANCE_AUDIT.md` with evidence-based PASS/PARTIAL/FAIL status.
- Corrected documentation for the actual OCR.space → extracted text → optional Gemini → Pydantic/source validation → review checks → local workflow classifier → database pipeline.
- Updated architecture diagram; fixed Compose to pass OCR/Gemini credentials to backend only; expanded secret/database/log/build ignore rules.
- Removed unused RapidOCR implementation and dependencies; OCR.space remains the single active OCR provider.
- Added generic retryable 503 responses for database errors and sanitized analysis provider error messages.
- Added `unclassified_information` with source excerpt, uncertainty, reason, and review flag. Gemini prompt now demands semantic category assignment, allows legitimately absent fields, restricts demographics, and preserves uncategorized source details.
- Added server-side guard: unsupported/non-demographic AI keys and oversized values are moved to source-grounded unclassified review segments; they are not kept as patient demographics.
- Added contextual source excerpts for matched findings and deterministic imaging/ECG observation extraction.
- Added API regression cases for synthetic demographic-heavy, mixed narrative, medication-heavy, symptom-focused, diagnosis-focused, and poor/uncertain OCR documents; verified API JSON and persistence. Added Gemini catch-all demographic regression.

## Current Task
- Run final review of publish files and credentials exclusion, create a local commit from this workspace snapshot, publish to existing `sajid-da/deskfactor` default branch if GitHub write succeeds, and inspect hosted CI status.

## Next Task
- If GitHub write is denied, document exact error and local commit SHA. If pushed, inspect Actions. Public deployment still requires a hosting target, secrets, database, and end-to-end synthetic verification.

## Files Created
- `PROJECT_COMPLIANCE_AUDIT.md`; `docs/architecture.png` updated.

## Files Modified
- `README.md`, `PROJECT_PLAN.md`, this checkpoint, `.gitignore`, `.env.example`, `docker-compose.yml`, `backend/app/main.py`, `backend/app/api/reports.py`, `backend/app/schemas/report.py`, `backend/app/services/analysis.py`, `backend/app/services/ai/llm.py`, `backend/app/services/validation/source_grounding.py`, `backend/app/services/ocr/__init__.py`, removal of unused `backend/app/services/ocr/engine.py` and `preprocess.py`, `backend/requirements.txt`, `backend/tests/test_api.py`, `backend/tests/test_llm.py`, frontend `App.tsx`, and docs architecture/AI design/technical decisions.

## Database Status
- SQLite create/list/detail flow covered by tests; database errors return generic 503. PostgreSQL container/runtime not tested because Docker CLI is absent.

## Backend Status
- OCR.space Engine 2/3 and PDF native-text vs scan selection are implemented. Live OCR was previously checked only on a generated synthetic script-font fixture; no natural handwriting benchmark exists. Gemini is source-grounded semantic extraction, not OCR; real provider capacity remains intermittent.

## Frontend Status
- Input, report/history, loading/error/recovery UI and the unclassified review section are implemented. Build, lint, TS and component tests pass; full browser/device visual automation not run during this audit.

## AI/ML Status
- Deterministic extractor is intentionally narrow; unclassified relevant text is preserved with provenance and human-review requirement. Gemini prompt/schema/source checks mitigate but cannot prove clinical correctness. Classifier labels are synthetic admin workflow only, not clinical risk.

## Testing Status
- Backend: 50 passed, one Starlette/httpx deprecation warning. Ruff passes. Frontend: ESLint passes, Vitest 4 pass, TS check passes, Vite production build passes. Synthetic evaluation: 3 samples, fact precision 1.00 / recall 1.00 / unsupported facts 0; not clinical evidence.
- Docker unavailable. GitHub Actions hosted run pending publication.

## Deployment Status
- Not deployed. No public frontend/API URLs or hosting provider configured. Compose topology exists but cannot be run on this host.

## Known Issues
- No natural-handwriting or multilingual accuracy benchmark; external OCR/Gemini availability can change; narrow deterministic extraction; tiny uncalibrated synthetic classifier; no auth, tenant isolation, production privacy/retention controls, migration framework, or public deployment.
- Local `backend/.env`, SQLite DBs, server logs, dependency/cache/build output are private and must not be committed.

## Environment Variables
- Backend-only: `OCR_SPACE_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, optional `OPENAI_API_KEY`/`OPENAI_MODEL`, `DATABASE_URL`, `MAX_UPLOAD_MB`, `CORS_ORIGINS`.
- Compose root `.env`: `POSTGRES_PASSWORD` and backend keys. Frontend build variable: public API URL only (`VITE_API_URL`).

## Important Decisions
- OCR.space performs pixel reading; Gemini semantically structures the text. Neither key is exposed to frontend.
- Native PDF text is preferred when useful. Poor/uncertain OCR is review-marked. Do not invent field distributions or medical confidence.
- Commit synthetic examples and source only; never commit user reports, `.env`, databases, logs, or generated build/dependency directories.

## Commands
- Backend tests: isolated SQLite DB and `PYTHONPATH=backend`; last command used an isolated database under the writable Codex visualization folder.
- Ruff from backend: `python -m ruff check --no-cache app tests evaluate.py ml`.
- Frontend from frontend: `npm run lint`; `npm test -- --run --configLoader native`; `npx tsc --noEmit -p tsconfig.json`; Vite build to an external temporary directory.

## Do Not Redo
- Do not redo OCR/Gemini integration or dashboard motion work absent a verified regression.
- Do not expose, copy, print, stage, or publish secret values or local databases.

## Last Verified
- 2026-09-28: 50 backend tests pass; Ruff; frontend lint, 4 Vitest, TS check, Vite build pass; six API JSON regression cases pass; synthetic evaluation ran. Docker unavailable.

## Resume Instructions
- Review `PROJECT_COMPLIANCE_AUDIT.md`, `git status`, and staged file list; publish safe source tree to `sajid-da/deskfactor` only. Verify remote commit and Actions status. Do not claim deployed until a public host is provisioned and tested.


PHASE_30 — administrative agreement extraction and report UI
- Added `administrative_information` to the report schema and connected it through deterministic extraction, Gemini guidance, source-grounding, persistence/API merge, and the report UI. Billing, payment, consent, provider, and clinic-contact details are preserved as source-backed review items; they are not forced into clinical categories.
- Added a synthetic payment-agreement API regression covering patient/date extraction, cost and payment terms, empty clinical categories, review flags, summary, and classifier presence.
- Fixed inline date parsing so a labeled date cannot absorb all following agreement text into patient information.
- Frontend Vitest: 4 passed; TypeScript and Vite production build passed. Focused deterministic backend extraction and source-grounding passed using the bundled Python/Pydantic runtime. Full pytest suite could not run in this environment because no available Python interpreter has pytest/FastAPI/SQLAlchemy installed.
- Verified `assign/AI_ML_Internship_Technical_Assignment.docx` requirements by extracting its text; visual render was unavailable because LibreOffice is not installed. `assign/` is excluded from the public repository.
- User-provided source is an administrative surgery payment agreement. Empty clinical categories are expected; amount/terms and agreement context now display in the administrative agreement section.


PHASE_31 — production deployment audit and provider setup
- Chosen topology: Vercel SPA + Render FastAPI + private free managed PostgreSQL in Singapore. Free Render service/database tiers were rejected for production history because web services sleep and free Postgres expires after 30 days.
- Added psycopg v3 URL normalization, database-backed /health readiness, Vercel SPA routing, and a Render Blueprint with private DB access, server-side OCR/Gemini secrets, and deployment after CI. Frontend production builds require an HTTPS API origin and never fall back to localhost.
- Backend Ruff clean; pytest 51 passed; classifier preparation, training, and extraction evaluation passed.
- Credential scan: key-like content found only in ignored backend/.env; no matching values in tracked source. Do not commit the local env file.
- No deployment is live: the Vercel dashboard requires account login; this environment has no Vercel/Render CLI or token. User sign-in, GitHub authorization, and private key entry remain necessary. No hosting payment is required for this demo configuration. No real patient data should be uploaded because the API has no authentication/tenant isolation.


PHASE_32 - no-cost hosted demo preparation
- Replaced the paid Render service plan with the free Render FastAPI and free 1 GB Postgres plans; deployment no longer requires accepting a hosting bill. Render free API sleeps after 15 minutes idle and free Postgres expires after 30 days.
- Added a Vercel build guard that blocks a hosted build unless VITE_API_URL is set to an HTTPS backend URL; local builds remain unaffected. Added frontend/.env.example.
- Updated README, architecture and technical decisions to match the no-cost topology and its limits. Provider account sign-in, repository authorization, and server-side OCR/Gemini secrets are still required; no public deployment is live.
