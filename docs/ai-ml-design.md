# AI/ML design

## Actual processing flow

1. **Input:** the API accepts text, an image, or a PDF. Empty, oversized, unsupported, and unreadable uploads are rejected with actionable errors.
2. **Document reading:** text is passed directly. PyMuPDF extracts each PDF page's embedded text; pages with sufficient usable text stay local. Sparse pages are rendered as PNG. Images and rendered scanned pages are sent to OCR.space. Explicit printed mode selects Engine 2; `auto` and `handwritten` select Engine 3. OCR.space returns `ParsedResults[].ParsedText`; the backend preserves this text and records OCR-used/status/engine/page metadata. The response provides no confidence value used by this application, so confidence remains null.
3. **Clinical extraction:** a deterministic Python baseline recognizes a limited source-matched vocabulary and labeled prescription/document sections. It does not fill absent fields. Optional Gemini semantic structuring receives the actual extracted/native text, is instructed to preserve source wording and return schema-shaped JSON, and is **not the OCR engine**. The project does not train Gemini or a handwriting model.
4. **Validation and document-aware categorization:** Pydantic validates the structured report, source excerpt checks require evidence excerpts to occur verbatim in the input, and deterministic checks add missing-information, age conflict, low-readability, OCR, and handwriting review flags. `patient_information` is reserved for identity/demographics/encounter facts. Gemini is explicitly prompted to categorize semantically and leave unsupported fields empty. The deterministic baseline is merged to preserve its source-supported fields. Clinical-looking source segments not confidently represented are retained as `unclassified_information` with source excerpt, reason, uncertainty, and a review flag rather than being forced into demographics or discarded. Billing, payment-plan, consent, legal agreement, clinic contact, and provider-directory facts from non-clinical documents are preserved separately in `administrative_information`; they are never misrepresented as clinical findings.
5. **Workflow classifier:** a separate local TF-IDF + multinomial Logistic Regression classifier categorizes synthetic administrative document workflow as `routine`, `review_required`, or `urgent_review`. It receives the extracted source text, not a clinical risk label. Scores are uncalibrated and not clinical probabilities.
6. **Persistence/display:** the report, summary, timestamp, processing status, structured fields, classifier result, and relevant OCR/AI provenance are saved via SQLAlchemy. The frontend reads report/history API responses; it does not perform OCR or semantic extraction.

```text
TEXT ───────────────────────────────────────────────────┐
IMAGE/PDF → document processing → OCR.space (as needed) ├→ extracted text
NATIVE PDF TEXT ────────────────────────────────────────┘
extracted text → deterministic extraction + optional Gemini structuring
→ Pydantic/schema and source-grounding validation
→ missing/inconsistency/review checks
→ synthetic workflow classifier
→ SQL database → report/history UI
```

### External services and fallback

- **OCR.space:** external OCR service at `https://api.ocr.space/parse/image`. API credentials stay on the server. Timeouts, malformed replies, provider errors, and empty text are explicit failures or marked low-readability reports; OCR is never marked used for native-text pages.
- **Gemini:** Google Generative Language `generateContent` endpoint with JSON response mode. This application configures `GEMINI_MODEL` and `GEMINI_FALLBACK_MODEL` (defaults currently `gemini-3.8-flash` and `gemini-3.6-flash`). Provider model availability/capacity is external and may change. If both attempts report temporary capacity (429/503), a deterministic source-grounded report is saved with a visible analysis note and review flag. Other API/network/timeout/invalid-JSON/schema/source-grounding failures produce an API error; they are not mislabeled as AI success.
- **OpenAI:** optional compatibility fallback is used only when no Gemini key is configured and an OpenAI key is provided. It uses configured `OPENAI_MODEL` and the same validation path.

## Structured clinical fields

The report schema covers patient information, administrative agreement information, symptoms, diagnoses, medications, vitals, allergies, clinical observations/concerns, missing information, possible inconsistencies, review flags, summary, and workflow prediction. Medication name, strength, dose, route, frequency, and duration should remain source-faithful. Ambiguous shorthand must remain ambiguous and be flagged. Missing data is not inferred from norms or context. The extraction system is documentation support, not diagnosis or treatment advice.

## Training and evaluation

The only trained model is the small local workflow classifier. Its hand-authored train/validation/test data in `backend/ml/data/` is synthetic. `python -m ml.prepare_data` prepares data and `python -m ml.train` fits the artifact `backend/ml/models/document_review_classifier.json`; `python evaluate.py` separately evaluates the deterministic extraction baseline. These tiny datasets and tests are engineering checks, not clinical performance evidence. The handwriting-style fixture is generated script-font text, not natural handwriting.

## Limitations

OCR quality varies by scan, script, layout, handwriting, image resolution, and OCR.space availability. OCR errors can propagate to structured fields. Source substring evidence verifies traceability, not correctness. Clinical extraction patterns remain narrow. Gemini output can omit or misinterpret details even with schema and source checks. Classifier labels and scores are synthetic administrative workflow signals and are not calibrated. No representative clinical validation, clinical governance, authentication, tenant isolation, privacy operations, or medical-device controls are implemented. Use synthetic data only.
