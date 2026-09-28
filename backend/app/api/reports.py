import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_BYTES, MAX_TEXT_CHARS
from app.db.database import Base, SessionLocal, engine
from app.models.report import ReportRecord
from app.schemas.report import ClinicalReport, OCRBlockOut, PageProcessingOut, ReportOut
from app.services.analysis import analyze
from app.services.document_processing import DocumentError, extract_document
from app.services.ai import AnalysisServiceError, refine_with_llm
from ml.classifier import predict as predict_document_category

Base.metadata.create_all(bind=engine)
router = APIRouter(tags=["reports"])


def _merge_source_findings(source_findings, refined_findings):
    merged = list(source_findings)
    seen = {item.text.casefold() for item in merged}
    seen.update(item.source_excerpt.casefold() for item in merged if item.source_excerpt)
    for item in refined_findings:
        keys = {item.text.casefold()}
        if item.source_excerpt:
            keys.add(item.source_excerpt.casefold())
        if not keys & seen:
            merged.append(item)
            seen.update(keys)
    return merged


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _out(row: ReportRecord) -> ReportOut:
    return ReportOut(id=row.id, created_at=row.created_at, input_type=row.input_type, filename=row.filename,
                     status=row.status, summary=row.summary, report=ClinicalReport.model_validate(row.report) if row.report else None,
                     processing_error=row.processing_error)


@router.post("/reports", response_model=ReportOut)
async def create_report(text: str | None = Form(default=None), file: UploadFile | None = File(default=None),
                        writing_style: str = Form(default="auto"), db: Session = Depends(get_db)):
    if (text is None or not text.strip()) and file is None:
        raise HTTPException(400, "Enter clinical text or choose a document to review.")
    if text and file:
        raise HTTPException(400, "Submit text or a document in one review.")
    if text and len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, "Text is too long. Keep submissions under 100,000 characters.")
    filename = None
    if file:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File is too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", (file.filename or "document")[:120])
        try:
            extracted = extract_document(data, filename, file.content_type or "", writing_style=writing_style)
        except DocumentError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        source_text, quality = extracted.text, extracted.quality
        input_type = "pdf" if filename.lower().endswith(".pdf") or file.content_type == "application/pdf" else "image"
    else:
        source_text, quality, input_type = text.strip(), "readable", "text"
    deterministic = analyze(source_text, quality)
    report = deterministic
    if source_text and len(source_text) >= 30:
        try:
            report = refine_with_llm(source_text, report)
        except AnalysisServiceError as exc:
            raise HTTPException(
                503,
                "The analysis service did not return a valid source-grounded review. Please retry later.",
            ) from exc
    report.patient_information = {**report.patient_information, **deterministic.patient_information}
    report.vitals = {**report.vitals, **deterministic.vitals}
    for field in ("symptoms", "diagnoses", "medications", "allergies", "clinical_observations", "clinical_concerns", "lab_tests", "follow_up", "doctor_advice", "unclassified_information", "administrative_information"):
        setattr(report, field, _merge_source_findings(getattr(deterministic, field), getattr(report, field)))
    report.potential_inconsistencies = list(dict.fromkeys([*report.potential_inconsistencies, *deterministic.potential_inconsistencies]))
    report.missing_information = list(dict.fromkeys([*report.missing_information, *deterministic.missing_information]))
    report.requires_review = list(dict.fromkeys([*report.requires_review, *deterministic.requires_review]))
    if file:
        report.document_type = extracted.document_type
        report.extraction_method = extracted.method
        report.ocr_used = extracted.ocr_used
        report.ocr_confidence = extracted.ocr_confidence
        report.readability = extracted.quality
        report.ocr_status = extracted.ocr_status
        report.ocr_engine = extracted.ocr_engine
        report.raw_ocr_text = extracted.raw_ocr_text
        report.normalized_text = extracted.text
        report.detected_scripts = extracted.detected_scripts or []
        report.unsupported_scripts = extracted.unsupported_scripts or []
        report.pages_processed = extracted.pages_processed
        report.page_processing = [
            PageProcessingOut(page_number=page.page_number, method=page.method, ocr_used=page.ocr_used,
             ocr_status=page.ocr_status, ocr_confidence=page.ocr_confidence,
             chars_extracted=sum(character.isalnum() for character in page.text))
            for page in extracted.pages
        ]
        report.ocr_blocks = [OCRBlockOut.model_validate(block.__dict__) for block in extracted.ocr_blocks]
        if report.unsupported_scripts:
            report.requires_review.append(
                "Some detected writing uses an unsupported script (" + ", ".join(report.unsupported_scripts) + "). It may be missing or inaccurate; verify it against the original."
            )
        if extracted.ocr_status == "low_confidence":
            report.requires_review.append("OCR could not reliably read part of this document. Some information may be missing. Manual review is recommended.")
        elif extracted.ocr_status == "partial":
            report.requires_review.append("OCR confidence or document legibility is limited. Verify the extracted text against the original.")
        if extracted.document_type == "handwritten":
            report.requires_review.append("Handwriting OCR is approximate. Verify the extracted text against the original; some information may be missing.")
    report.ml_prediction = predict_document_category(source_text)
    needs_review = (quality != "readable" or report.ocr_status in {"partial", "low_confidence"}
                    or report.document_type == "handwritten" or bool(report.requires_review)
                    or bool(report.missing_information))
    row = ReportRecord(id=str(uuid4()), input_type=input_type, filename=filename, status="needs_review" if needs_review else "completed",
                      summary=report.summary, report=report.model_dump(mode="json"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/reports", response_model=list[ReportOut])
def list_reports(limit: int = 50, db: Session = Depends(get_db)):
    return [_out(row) for row in db.query(ReportRecord).order_by(ReportRecord.created_at.desc()).limit(min(max(limit, 1), 100)).all()]


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    row = db.get(ReportRecord, report_id)
    if row is None:
        raise HTTPException(404, "Review not found.")
    return _out(row)
