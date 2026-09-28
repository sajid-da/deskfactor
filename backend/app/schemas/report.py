from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    certainty: Literal["high", "medium", "low", "unknown"] = "unknown"
    source_excerpt: str | None = None
    reason: str | None = None
    requires_review: bool = False


class OCRBlockOut(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[list[float]]
    page_number: int = Field(default=1, ge=1)


class PageProcessingOut(BaseModel):
    page_number: int = Field(ge=1)
    method: str
    ocr_used: bool
    ocr_status: Literal["not_used", "success", "partial", "low_confidence"]
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    chars_extracted: int = Field(ge=0)


class ClassProbability(BaseModel):
    category: Literal["routine", "review_required", "urgent_review"]
    probability: float = Field(ge=0, le=1)


class MLPrediction(BaseModel):
    category: Literal["routine", "review_required", "urgent_review"]
    probabilities: list[ClassProbability]
    confidence: float = Field(ge=0, le=1)
    confidence_label: Literal["high", "medium", "low"]
    model_name: str
    model_version: str
    feature_signals: list[str]
    disclaimer: str = "Synthetic document workflow classification only; not a clinical risk or medical decision."


class ClinicalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_information: dict[str, str | None] = Field(default_factory=dict)
    administrative_information: list[Finding] = Field(default_factory=list)
    unclassified_information: list[Finding] = Field(default_factory=list)
    symptoms: list[Finding] = Field(default_factory=list)
    diagnoses: list[Finding] = Field(default_factory=list)
    medications: list[Finding] = Field(default_factory=list)
    vitals: dict[str, str] = Field(default_factory=dict)
    allergies: list[Finding] = Field(default_factory=list)
    clinical_observations: list[Finding] = Field(default_factory=list)
    clinical_concerns: list[Finding] = Field(default_factory=list)
    lab_tests: list[Finding] = Field(default_factory=list)
    follow_up: list[Finding] = Field(default_factory=list)
    doctor_advice: list[Finding] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    potential_inconsistencies: list[str] = Field(default_factory=list)
    requires_review: list[str] = Field(default_factory=list)
    summary: str
    extraction_quality: Literal["readable", "partial", "unreadable"]
    document_type: Literal["text", "pdf", "image", "handwritten"] = "text"
    extraction_method: Literal["provided_text", "pdf_text", "pdf_ocr", "image_ocr", "handwriting_ocr", "pdf_handwriting_ocr", "pdf_mixed"] = "provided_text"
    ocr_used: bool = False
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_status: Literal["not_used", "success", "partial", "low_confidence"] = "not_used"
    pages_processed: int = Field(default=0, ge=0)
    page_processing: list[PageProcessingOut] = Field(default_factory=list)
    readability: Literal["readable", "partial", "unreadable"] = "readable"
    ocr_blocks: list[OCRBlockOut] = Field(default_factory=list)
    ocr_engine: str | None = None
    raw_ocr_text: str = ""
    normalized_text: str = ""
    detected_scripts: list[str] = Field(default_factory=list)
    unsupported_scripts: list[str] = Field(default_factory=list)
    analysis_provider: Literal["deterministic", "Google Gemini", "OpenAI"] = "deterministic"
    analysis_model: str | None = None
    analysis_note: str | None = None
    ml_prediction: MLPrediction | None = None
    disclaimer: str = "For documentation review only; not a diagnosis or treatment recommendation."


class ReportOut(BaseModel):
    id: str
    created_at: datetime
    input_type: str
    filename: str | None
    status: str
    summary: str | None
    report: ClinicalReport | None
    processing_error: str | None = None
