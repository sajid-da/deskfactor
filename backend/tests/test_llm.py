import json

import httpx
import pytest

from app.services.analysis import analyze
from app.services.ai import llm
from app.services.ai.llm import AnalysisServiceError


class GeminiResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("provider error", request=request, response=response)

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(self.payload)}]}}]}


def test_gemini_is_preferred_and_source_grounded(monkeypatch):
    source = "Name: Synthetic Child. Clinical Description: URTI. RR-22/min."
    baseline = analyze(source, "readable")
    calls = []

    def post(url, *, timeout, headers, json):
        calls.append({"url": url, "timeout": timeout, "headers": headers, "body": json})
        return GeminiResponse(baseline.model_dump(mode="json"))

    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "GEMINI_MODEL", "gemini-test-model")
    monkeypatch.setattr(llm, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(llm.httpx, "post", post)

    refined = llm.refine_with_llm(source, baseline)

    assert calls[0]["url"].endswith("/models/gemini-test-model:generateContent")
    assert calls[0]["headers"] == {"x-goog-api-key": "test-gemini-key"}
    assert calls[0]["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert refined.analysis_provider == "Google Gemini"
    assert refined.analysis_model == "gemini-test-model"
    assert refined.vitals["respiratory_rate"] == "22/min"


def test_gemini_uses_fallback_model_on_temporary_capacity_error(monkeypatch):
    source = "Synthetic source text with fever and URTI documented."
    baseline = analyze(source, "readable")
    models = []

    def post(url, *, timeout, headers, json):
        models.append(url)
        return GeminiResponse({}, 503) if len(models) == 1 else GeminiResponse(baseline.model_dump(mode="json"))

    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(llm, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
    monkeypatch.setattr(llm.httpx, "post", post)

    refined = llm.refine_with_llm(source, baseline)

    assert models[0].endswith("/models/gemini-primary:generateContent")
    assert models[1].endswith("/models/gemini-fallback:generateContent")
    assert refined.analysis_model == "gemini-fallback"


def test_gemini_capacity_failure_returns_marked_deterministic_report(monkeypatch):
    source = "Synthetic patient note documents fever and cough."
    baseline = analyze(source, "readable")
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(llm, "GEMINI_FALLBACK_MODEL", "gemini-fallback")
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: GeminiResponse({}, 503))

    refined = llm.refine_with_llm(source, baseline)

    assert refined.analysis_provider == "deterministic"
    assert refined.analysis_model is None
    assert "temporarily at capacity" in refined.analysis_note
    assert any("Gemini refinement was unavailable" in item for item in refined.requires_review)


def test_gemini_timeout_fails_clearly(monkeypatch):
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(llm.httpx, "post", timeout)
    with pytest.raises(AnalysisServiceError, match="did not return a valid"):
        llm.refine_with_llm("Synthetic note with enough text for semantic review.", analyze("Synthetic note with enough text for semantic review.", "readable"))


@pytest.mark.parametrize("payload", [{}, {"unexpected": "shape"}])
def test_gemini_missing_or_invalid_schema_fails_clearly(monkeypatch, payload):
    source = "Synthetic note documents fever and cough for review."
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: GeminiResponse(payload))
    with pytest.raises(AnalysisServiceError, match="did not return a valid"):
        llm.refine_with_llm(source, analyze(source, "readable"))


def test_gemini_invalid_json_fails_clearly(monkeypatch):
    class InvalidJsonResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "not JSON"}]}}]}

    source = "Synthetic note documents fever and cough for review."
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: InvalidJsonResponse())
    with pytest.raises(AnalysisServiceError, match="did not return a valid"):
        llm.refine_with_llm(source, analyze(source, "readable"))


def test_gemini_cannot_put_whole_clinical_narrative_in_patient_information(monkeypatch):
    source = "Patient reports fever and cough. Taking metformin 500 mg."
    payload = analyze(source, "readable").model_dump(mode="json")
    payload["patient_information"] = {"source": source}
    monkeypatch.setattr(llm, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: GeminiResponse(payload))

    report = llm.refine_with_llm(source, analyze(source, "readable"))

    assert report.patient_information == {}
    assert {item.text for item in report.unclassified_information} == {
        "Patient reports fever and cough.", "Taking metformin 500 mg."
    }
    assert all(item.requires_review for item in report.unclassified_information)
