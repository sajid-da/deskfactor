import pytest

from app.services.ocr.ocr_space import OCRSpacePage, OCRSpaceResult


@pytest.fixture(autouse=True)
def disable_external_language_models(monkeypatch):
    """Keep tests deterministic and never send fixture text to configured providers."""
    monkeypatch.setattr("app.services.ai.llm.GEMINI_API_KEY", "")
    monkeypatch.setattr("app.services.ai.llm.OPENAI_API_KEY", "")


@pytest.fixture
def ocr_space_stub(monkeypatch):
    calls = []

    def recognize(client, data, filename, content_type, *, handwriting=False):
        calls.append({"data": data, "filename": filename, "content_type": content_type, "handwriting": handwriting})
        text = "Patient reports fever and cough. Synthetic document for OCR integration checks."
        return OCRSpaceResult(text, "partial" if handwriting else "success",
                              "OCR.space Engine 3" if handwriting else "OCR.space Engine 2",
                              [OCRSpacePage(text, 1)])

    monkeypatch.setattr("app.services.document_processing.processor.OCRSpaceClient.recognize", recognize)
    return calls
