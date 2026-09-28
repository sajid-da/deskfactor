from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services.document_processing import DocumentError, extract_document
from app.services.ocr.ocr_space import OCRSpacePage, OCRSpaceResult

FIXTURES = Path(__file__).parent / "fixtures"
OCR_TEXT = "Patient reports fever and cough. Synthetic document for OCR integration checks."


def test_native_text_pdf_avoids_ocr():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Synthetic patient reports fever and cough for two days.")
    result = extract_document(pdf.tobytes(), "sample.pdf", "application/pdf")
    assert "fever" in result.text.lower()
    assert result.method == "pdf_text"
    assert result.ocr_status == "not_used"
    assert result.ocr_used is False
    assert result.ocr_confidence is None


def test_corrupt_pdf_fails_with_helpful_error():
    with pytest.raises(DocumentError, match="could not be opened"):
        extract_document(b"not a pdf", "sample.pdf", "application/pdf")


def test_unsupported_extension_is_rejected():
    with pytest.raises(DocumentError, match="Unsupported file type"):
        extract_document(b"data", "sample.csv", "text/csv")


def test_printed_image_uses_ocr_space_engine_two_and_preserves_text(ocr_space_stub):
    result = extract_document((FIXTURES / "typed_note.png").read_bytes(), "typed_note.png", "image/png", "printed")
    assert OCR_TEXT == result.raw_ocr_text == result.text
    assert result.ocr_status == "success"
    assert result.ocr_used is True
    assert result.ocr_confidence is None
    assert result.ocr_engine == "OCR.space Engine 2"
    assert result.ocr_blocks == []  # OCR.space overlay was not requested; no fabricated boxes.
    assert ocr_space_stub[0]["data"] == (FIXTURES / "typed_note.png").read_bytes()
    assert ocr_space_stub[0]["handwriting"] is False


def test_handwritten_image_uses_engine_three_and_requires_manual_review(ocr_space_stub):
    result = extract_document((FIXTURES / "handwritten_note.png").read_bytes(), "handwritten_note.png", "image/png", "handwritten")
    assert result.document_type == "handwritten"
    assert result.method == "handwriting_ocr"
    assert result.ocr_engine == "OCR.space Engine 3"
    assert result.ocr_status == "partial"
    assert result.raw_ocr_text == result.text == OCR_TEXT
    assert ocr_space_stub[0]["handwriting"] is True


def test_empty_ocr_text_is_low_confidence_and_not_treated_as_readable(monkeypatch):
    def empty_response(*args, **kwargs):
        return OCRSpaceResult("", "low_confidence", "OCR.space Engine 2", [OCRSpacePage("", 1)])

    monkeypatch.setattr("app.services.document_processing.processor.OCRSpaceClient.recognize", empty_response)
    result = extract_document((FIXTURES / "poor_quality_note.png").read_bytes(), "poor_quality_note.png", "image/png")
    assert result.ocr_used is True
    assert result.ocr_status == "low_confidence"
    assert result.quality == "unreadable"
    assert result.text == ""
    assert result.ocr_confidence is None


def test_scanned_pdf_sends_rendered_page_to_ocr_space(ocr_space_stub):
    result = extract_document((FIXTURES / "scanned_note.pdf").read_bytes(), "scanned_note.pdf", "application/pdf", "printed")
    assert result.method == "pdf_ocr"
    assert "Page 1" in result.text
    assert OCR_TEXT in result.text
    assert result.pages_processed == 1
    assert result.ocr_engine == "OCR.space Engine 2"
    assert ocr_space_stub[0]["filename"] == "page-1.png"
    assert ocr_space_stub[0]["content_type"] == "image/png"


def test_mixed_pdf_uses_native_text_and_ocr_only_for_scanned_page(ocr_space_stub):
    image = Image.new("RGB", (1400, 420), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((35, 55), "SYNTHETIC SCAN: patient reports fever and cough.", font=font, fill="black")
    stream = BytesIO()
    image.save(stream, "PNG")
    pdf = pymupdf.open()
    first = pdf.new_page()
    first.insert_text((72, 72), "Synthetic typed page describing a stable patient review.")
    second = pdf.new_page(width=700, height=210)
    second.insert_image(second.rect, stream=stream.getvalue())
    result = extract_document(pdf.tobytes(), "mixed.pdf", "application/pdf")
    assert result.method == "pdf_mixed"
    assert [page.method for page in result.pages] == ["pdf_text", "pdf_ocr"]
    assert len(ocr_space_stub) == 1
