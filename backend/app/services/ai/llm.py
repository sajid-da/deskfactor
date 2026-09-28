import json

import httpx
from pydantic import ValidationError

from app.core.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL
from app.schemas.report import ClinicalReport
from app.services.validation.source_grounding import validate_source_grounding


class AnalysisServiceError(RuntimeError):
    pass


def refine_with_llm(source: str, baseline: ClinicalReport) -> ClinicalReport:
    """Use Gemini preferentially; retain the source-grounded OpenAI fallback."""
    if not GEMINI_API_KEY and not OPENAI_API_KEY:
        return baseline
    schema = ClinicalReport.model_json_schema()
    prompt = (
        "Review clinical documentation. Use ONLY facts explicitly supported by the source. "
        "Extract information according to the semantic meaning of each fact, not according to document position or a fixed distribution of fields. "
        "A document does not need to populate every field. Do not force information into patient_information. "
        "patient_information is reserved for identity, demographics, and encounter-related information. "
        "Financial, payment-plan, billing, consent, legal agreement, clinic contact, and provider-directory details belong in administrative_information; never mislabel them as diagnoses, symptoms, or clinical concerns. "
        "If the source is an administrative agreement with no clinical facts, keep clinical categories empty and summarize the document type without implying it is a clinical note. "
        "Clinical information such as symptoms, diagnoses, medications, laboratory results, imaging findings, observations, treatment history, concerns, and inconsistencies must be assigned to their appropriate categories when supported by the source. "
        "If information cannot confidently be categorized, preserve it as uncertain/unclassified information and mark it for review rather than placing it into an unrelated category. "
        "Never invent information. Never discard source information solely because the expected schema does not have an obvious field. "
        "Never invent symptoms, diagnoses, drugs, demographics, allergies or vitals. Missing fields stay empty; "
        "ambiguous information must be marked low/unknown and flagged for review. Preserve medication names, dose, route, "
        "frequency and duration exactly as written; do not expand uncertain abbreviations or infer why a drug was prescribed. "
        "Do not give diagnosis or treatment advice. "
        "For every extracted fact, source_excerpt must be a verbatim substring of the source. "
        "Return JSON conforming to the supplied schema.\nSOURCE DOCUMENT:\n" + source[:30000]
    )
    analysis_model = OPENAI_MODEL
    try:
        if GEMINI_API_KEY:
            analysis_model = GEMINI_MODEL
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt + "\nJSON Schema:\n" + json.dumps(schema)}]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
            }
            endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
            response = httpx.post(endpoint.format(analysis_model), timeout=45,
                                  headers={"x-goog-api-key": GEMINI_API_KEY}, json=body)
            if response.status_code in {429, 503} and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
                analysis_model = GEMINI_FALLBACK_MODEL
                response = httpx.post(endpoint.format(analysis_model), timeout=45,
                                      headers={"x-goog-api-key": GEMINI_API_KEY}, json=body)
            response.raise_for_status()
            payload = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
        else:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions", timeout=45,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model": OPENAI_MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": "Extract and organize information, do not provide medical advice."},
                                   {"role": "user", "content": prompt + "\nJSON Schema:\n" + json.dumps(schema)}]},
            )
            response.raise_for_status()
            payload = json.loads(response.json()["choices"][0]["message"]["content"])
        response.raise_for_status()
        report = ClinicalReport.model_validate(payload)
        validate_source_grounding(report, source)
    except httpx.HTTPStatusError as exc:
        if GEMINI_API_KEY and exc.response.status_code in {429, 503}:
            baseline.analysis_provider = "deterministic"
            baseline.analysis_model = None
            baseline.analysis_note = (
                "Gemini is temporarily at capacity. This report uses source-grounded local extraction; "
                "verify every item against the document."
            )
            baseline.requires_review.append("Gemini refinement was unavailable; verify extracted fields against the source document.")
            return baseline
        raise AnalysisServiceError("The analysis service did not return a valid source-grounded review. Please retry later.") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise AnalysisServiceError("The analysis service did not return a valid source-grounded review. Please retry later.") from exc
    report.analysis_provider = "Google Gemini" if GEMINI_API_KEY else "OpenAI"
    report.analysis_model = analysis_model
    return report
