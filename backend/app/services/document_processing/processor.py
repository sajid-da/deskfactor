from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.core.config import OCR_SPACE_API_KEY
from app.services.ocr.ocr_space import OCRSpaceClient, OCRSpaceConfigurationError, OCRSpaceError, OCRSpaceTimeout


class DocumentError(ValueError):
    status_code = 422


class OCRProviderError(DocumentError):
    status_code = 502


class OCRProviderTimeout(DocumentError):
    status_code = 504


class OCRProviderConfigurationError(DocumentError):
    status_code = 503


WritingStyle = Literal["auto", "printed", "handwritten"]


@dataclass(frozen=True)
class PageExtraction:
    page_number: int
    text: str
    method: str
    ocr_used: bool
    ocr_status: str
    ocr_confidence: float | None
    engine_name: str | None = None
    detected_scripts: list[str] | None = None
    unsupported_scripts: list[str] | None = None
    raw_ocr_text: str = ""


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    quality: str
    method: str
    document_type: str
    ocr_used: bool
    ocr_confidence: float | None
    ocr_status: str
    pages_processed: int
    pages: list[PageExtraction]
    ocr_blocks: list
    raw_ocr_text: str = ""
    detected_scripts: list[str] | None = None
    unsupported_scripts: list[str] | None = None
    ocr_engine: str | None = None


def _quality(text: str, status: str) -> str:
    chars = sum(character.isalnum() for character in text)
    if status == "low_confidence" and chars < 30:
        return "unreadable" if chars < 8 else "partial"
    return "readable" if chars >= 30 else "partial" if chars >= 8 else "unreadable"


def _scripts(text: str) -> tuple[list[str], list[str]]:
    found = set()
    for character in text:
        point = ord(character)
        if 0x0D00 <= point <= 0x0D7F:
            found.add("Malayalam")
        elif "A" <= character <= "Z" or "a" <= character <= "z":
            found.add("Latin")
        elif 0x0900 <= point <= 0x097F:
            found.add("Devanagari")
        elif 0x0400 <= point <= 0x052F:
            found.add("Cyrillic")
    scripts = sorted(found)
    return scripts, [script for script in scripts if script == "Malayalam"]


def _normalize_text(text: str) -> str:
    # Preserve OCR.space wording and line structure; normalize only newline style
    # and trim outer whitespace before clinical extraction.
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _combined_status(pages: list[PageExtraction]) -> str:
    ocr_pages = [page for page in pages if page.ocr_used]
    if not ocr_pages:
        return "not_used"
    if any(page.ocr_status == "low_confidence" for page in ocr_pages):
        return "low_confidence"
    if any(page.ocr_status == "partial" for page in ocr_pages):
        return "partial"
    return "success"


def _run_ocr(data: bytes, filename: str, content_type: str, page_number: int,
             writing_style: WritingStyle) -> PageExtraction:
    try:
        result = OCRSpaceClient(OCR_SPACE_API_KEY).recognize(
            data, filename, content_type, handwriting=writing_style != "printed",
        )
    except OCRSpaceConfigurationError as exc:
        raise OCRProviderConfigurationError(str(exc)) from exc
    except OCRSpaceTimeout as exc:
        raise OCRProviderTimeout(str(exc)) from exc
    except OCRSpaceError as exc:
        raise OCRProviderError(str(exc)) from exc
    raw_text = result.text
    text = _normalize_text(raw_text)
    scripts, unsupported = _scripts(text)
    method = "handwriting_ocr" if writing_style == "handwritten" else "image_ocr"
    return PageExtraction(
        page_number=page_number,
        text=text,
        method=method,
        ocr_used=True,
        ocr_status=result.status,
        ocr_confidence=None,
        engine_name=result.engine_name,
        detected_scripts=scripts,
        unsupported_scripts=unsupported,
        raw_ocr_text=raw_text,
    )


def _extract_pdf(data: bytes, writing_style: WritingStyle) -> ExtractedDocument:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count == 0:
                raise DocumentError("This PDF has no pages to review.")
            pages: list[PageExtraction] = []
            for index, page in enumerate(doc, start=1):
                native_text = page.get_text("text").strip()
                useful_chars = sum(char.isalnum() for char in native_text)
                if len(native_text) >= 30 and useful_chars >= 20:
                    pages.append(PageExtraction(index, native_text, "pdf_text", False, "not_used", None))
                    continue
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                rendered = pixmap.tobytes("png")
                extracted = _run_ocr(rendered, f"page-{index}.png", "image/png", index, writing_style)
                method = "pdf_handwriting_ocr" if writing_style == "handwritten" else "pdf_ocr"
                pages.append(PageExtraction(
                    extracted.page_number, extracted.text, method, extracted.ocr_used,
                    extracted.ocr_status, extracted.ocr_confidence, extracted.engine_name,
                    extracted.detected_scripts, extracted.unsupported_scripts, extracted.raw_ocr_text,
                ))
    except (OCRProviderError, OCRProviderTimeout, OCRProviderConfigurationError):
        raise
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError("This PDF could not be opened. Check that the file is not damaged.") from exc

    text = "\n\n".join(f"Page {page.page_number}\n{page.text}" for page in pages if page.text).strip()
    status = _combined_status(pages)
    methods = {page.method for page in pages}
    method = next(iter(methods)) if len(methods) == 1 else "pdf_mixed"
    handwritten_used = writing_style == "handwritten" and any(page.ocr_used for page in pages)
    document_type = "handwritten" if handwritten_used else "pdf"
    engine_names = sorted({page.engine_name for page in pages if page.engine_name})
    scripts = sorted({script for page in pages for script in (page.detected_scripts or [])})
    unsupported = sorted({script for page in pages for script in (page.unsupported_scripts or [])})
    raw_text = "\n\n".join(page.raw_ocr_text for page in pages if page.ocr_used and page.raw_ocr_text)
    return ExtractedDocument(
        text, _quality(text, status), method, document_type, status != "not_used", None,
        status, len(pages), pages, [], raw_text, scripts, unsupported,
        ", ".join(engine_names) or None,
    )


def extract_document(data: bytes, filename: str, content_type: str,
                     writing_style: WritingStyle = "auto") -> ExtractedDocument:
    if writing_style not in {"auto", "printed", "handwritten"}:
        raise DocumentError("Choose automatic, printed, or handwritten document processing.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        return _extract_pdf(data, writing_style)
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        raise DocumentError("Unsupported file type. Upload a PDF, PNG, JPG, WEBP, or TIFF image.")
    try:
        with Image.open(BytesIO(data)) as source:
            source.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise DocumentError("This image could not be opened. Check that the file is valid.") from exc
    page = _run_ocr(data, filename, content_type, 1, writing_style)
    document_type = "handwritten" if writing_style == "handwritten" else "image"
    return ExtractedDocument(
        page.text, _quality(page.text, page.ocr_status), page.method, document_type,
        True, None, page.ocr_status, 1, [page], [], page.raw_ocr_text,
        page.detected_scripts, page.unsupported_scripts, page.engine_name,
    )
