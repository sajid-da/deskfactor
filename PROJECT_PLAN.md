# Project plan and current status

## Objective

Maintain a local-first clinical document review prototype that accepts synthetic text, images, and PDFs; extracts source-supported information; flags uncertainty, missing data, and inconsistencies; saves structured reports; and provides a review/history UI. The app is documentation support only, not a clinical decision system.

## Current phase

**PHASE_29 — final compliance audit, deployment/configuration review, and GitHub publication.** Core implementation is present. This phase updates inaccurate docs, closes local reliability/security gaps, runs CI-equivalent checks, and publishes a safe project tree if GitHub writes are authorized and work.

## Implemented architecture

- Frontend: React + TypeScript + Vite; text/image/PDF workflow, report and history views, responsive motion UI.
- Backend: FastAPI REST routes, Pydantic report contracts, SQLAlchemy persistence.
- Processing: PyMuPDF native text per PDF page; OCR.space Engine 2 for explicitly printed and Engine 3 for automatic/handwriting; OCR text goes to source-grounded clinical extraction and classifier.
- AI: Gemini structured semantic extraction preferred when configured; model capacity fallback produces a clearly marked deterministic report. Optional OpenAI provider remains available if Gemini is not configured.
- ML: local TF-IDF + multinomial logistic-regression administrative workflow classifier trained on tiny synthetic datasets only.
- Persistence: SQLite local; PostgreSQL through Docker Compose.
- CI: GitHub Actions runs backend lint/tests/evaluation and frontend lint/tests/build. CI is not deployment.

## Verification and current gaps

The detailed evidence and PASS/PARTIAL/FAIL ratings are in `PROJECT_COMPLIANCE_AUDIT.md`. Last locally checked: backend pytest 50 passed, Ruff passed; frontend ESLint passed, Vitest 4 passed, TypeScript check passed, and production Vite build passed. Six varied synthetic documents were exercised through the API and their structured JSON/persistence checked. The synthetic evaluation reported fact precision 1.00, recall 1.00, unsupported facts 0 across only 3 examples; this is not clinical evidence.

Remaining: Docker/Compose runtime is unverified because Docker is unavailable; the public app/backend are not deployed; natural handwriting and broad language accuracy are unvalidated; Gemini live response is capacity-dependent; GitHub Actions has not run from this workspace yet. The workspace has no `.git` metadata and the linked repository initially had no files. Never publish `.env`, databases, logs, user records, build output, or credentials.

## Next steps

1. Review audit, documentation, diagram, and secret-safe publish file list.
2. If remote integration permits, create/push an initial commit to existing `sajid-da/deskfactor` `main` only; verify tree, commit, CI status.
3. If hosting is later provisioned, deploy API/frontend/PostgreSQL with runtime secrets, then verify text/image/PDF and report-history flows using synthetic data.
4. Update this plan/checkpoint with hosted CI and deployment evidence only after those checks actually run.

## Safety and constraints

- Use synthetic data only. Local environment files and SQLite databases are private and must stay untracked.
- Keep OCR/Gemini keys server-side; never add them to Vite variables or source control.
- Do not claim clinical accuracy, all-handwriting recognition, or production readiness.
