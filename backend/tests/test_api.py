from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_text_review_is_validated_persisted_and_listed():
    response = client.post("/api/reports", data={"text": "Synthetic patient has fever. Temperature 101 F. Taking paracetamol."})
    assert response.status_code == 200
    report = response.json()
    assert report["report"]["symptoms"][0]["text"].lower() == "fever"
    assert report["report"]["ml_prediction"]["category"] in {"routine", "review_required", "urgent_review"}
    assert report["report"]["extraction_method"] == "provided_text"
    assert client.get(f"/api/reports/{report['id']}").status_code == 200
    assert any(row["id"] == report["id"] for row in client.get("/api/reports").json())


def test_text_review_preserves_labeled_prescription_sections(monkeypatch):
    from app.api import reports as report_api
    monkeypatch.setattr(report_api, "refine_with_llm", lambda source, report: report)
    source = """Name
Sample Patient
Age
42 Years
Date
30-08-2023
Diagnosis
viral fever
Description
fever, cold, myaglia
Prescribed Medicines
1.
TABLET AZITHROMYCIN (250MG)
Daily: 1-0-1
3 Days; After Meal;
2.
TABLET SINAREST (100MG)
Daily: 1-0-1
3 Days; After Meal;
3.
TABLET DOLO PARACETAMOL(650MG)
Daily: 1-0-1
3 Days; After Meal;
Drug Allergies
No known Allergies
Lab Test
1. RT PCR FOR COVID 19
2. Fever Profile (CBC, ESR, CUE, Smear for MP, Widal, SGPT)
3. Dengue Antigen NS1, IgG & IgM
Follow Up
3 Days
Doctor's Advice
1. Steam inhalation before sleep
2. Isolate yourself
"""
    response = client.post("/api/reports", data={"text": source})
    assert response.status_code == 200, response.text
    result = response.json()
    report = result["report"]
    assert result["status"] == "needs_review"
    assert report["patient_information"]["name"] == "Sample Patient"
    assert report["patient_information"]["age"] == "42 Years"
    assert report["patient_information"]["encounter_date"] == "30-08-2023"
    assert any(item["text"] == "viral fever" for item in report["diagnoses"])
    assert len(report["medications"]) == 3
    assert "Daily: 1-0-1" in report["medications"][0]["text"]
    assert len(report["lab_tests"]) == 3
    assert report["follow_up"][0]["text"] == "3 Days"
    assert len(report["doctor_advice"]) == 2
    assert any(item["text"] == "No known Allergies" for item in report["allergies"])


def test_empty_submission_gets_actionable_validation_error():
    response = client.post("/api/reports", data={})
    assert response.status_code == 400


def test_ai_provider_failure_is_not_returned_as_a_successful_report(monkeypatch):
    from app.api import reports
    from app.services.ai import AnalysisServiceError

    def provider_failure(source, report):
        raise AnalysisServiceError("provider unavailable")

    monkeypatch.setattr(reports, "refine_with_llm", provider_failure)
    response = client.post("/api/reports", data={"text": "Synthetic patient documentation with fever and enough words to invoke structured review."})
    assert response.status_code == 503
    assert response.json() == {"detail": "The analysis service did not return a valid source-grounded review. Please retry later."}


def test_document_aware_extraction_returns_multiple_distinct_structured_reports(monkeypatch):
    from app.api import reports
    monkeypatch.setattr(reports, "refine_with_llm", lambda source, report: report)
    examples = [
        (
            "demographics",
            "Patient name: Synthetic Person\nAge: 44 years\nGender: F\nHeight: 160 cm\nWeight: 59 kg\nDate: 2026-01-03\nPatient ID: DEMO-42\nContact: synthetic only",
            "patient_information",
        ),
        (
            "mixed narrative",
            "Patient reports intermittent chest discomfort for three days. Diagnosis: migraine. Taking metformin 500 mg daily. ECG shows nonspecific ST changes.",
            "symptoms",
        ),
        (
            "medication-heavy",
            "Current medications: Metformin 500 mg twice daily. Lisinopril 10 mg once daily.",
            "medications",
        ),
        (
            "symptom-focused",
            "Patient reports headache and nausea after a long journey. Symptoms started yesterday.",
            "symptoms",
        ),
        (
            "diagnosis-focused",
            "Assessment: migraine. Differential diagnosis remains uncertain; clinician documents possible medication-related trigger.",
            "diagnoses",
        ),
    ]
    reports = {}
    for name, source, expected_field in examples:
        response = client.post("/api/reports", data={"text": source})
        assert response.status_code == 200, response.text
        payload = response.json()
        structured = payload["report"]
        assert structured[expected_field], (name, structured)
        assert structured["patient_information"] != {"source": source}
        assert len(str(structured["patient_information"])) < len(source) + 20
        reports[name] = structured

    demographics = reports["demographics"]["patient_information"]
    assert len(demographics) >= 6
    assert not reports["demographics"]["symptoms"]
    assert reports["mixed narrative"]["patient_information"] == {}
    assert reports["mixed narrative"]["diagnoses"]
    assert reports["mixed narrative"]["medications"]
    assert reports["medication-heavy"]["patient_information"] == {}
    assert not reports["medication-heavy"]["symptoms"]
    assert not reports["diagnosis-focused"]["patient_information"]
    assert reports["diagnosis-focused"]["unclassified_information"]


def test_uncertain_handwriting_is_preserved_as_reviewable_unclassified_source(monkeypatch, ocr_space_stub):
    from app.api import reports as report_api
    from app.services.ocr.ocr_space import OCRSpacePage, OCRSpaceResult
    from pathlib import Path

    source = "Clinical note: pat?nt reports abdominal discomfort and illegible handwritten finding."
    def uncertain_ocr(*args, **kwargs):
        return OCRSpaceResult(source, "partial", "OCR.space Engine 3", [OCRSpacePage(source, 1)])

    monkeypatch.setattr(report_api, "refine_with_llm", lambda text, report: report)
    monkeypatch.setattr("app.services.document_processing.processor.OCRSpaceClient.recognize", uncertain_ocr)
    fixture = Path(__file__).parent / "fixtures" / "handwritten_note.png"
    response = client.post("/api/reports", data={"writing_style": "handwritten"},
                           files={"file": ("synthetic_uncertain.png", fixture.read_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["patient_information"] == {}
    assert report["symptoms"]
    assert report["unclassified_information"][0]["text"] == source
    assert report["unclassified_information"][0]["requires_review"] is True
    assert report["unclassified_information"][0]["source_excerpt"] == source
    assert any("unclassified" in warning for warning in report["requires_review"])
    saved = client.get(f"/api/reports/{response.json()['id']}").json()["report"]
    assert saved["unclassified_information"] == report["unclassified_information"]


def test_health_endpoint():
    assert client.get("/health").json() == {"status": "ok"}


def test_scanned_pdf_api_passes_ocr_text_through_clinical_analysis_and_ml(ocr_space_stub, monkeypatch):
    from io import BytesIO
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1400, 420), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        except OSError:
            font = ImageFont.load_default()
    draw.text((40, 40), "SYNTHETIC DOCUMENT REVIEW", font=font, fill="black")
    draw.text((40, 130), "Patient reports fever and cough.", font=font, fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    pdf = pymupdf.open()
    pdf.new_page(width=700, height=210).insert_image(pymupdf.Rect(0, 0, 700, 210), stream=buffer.getvalue())
    from app.api import reports as report_api
    extracted_inputs = []
    classifier_inputs = []
    real_analyze = report_api.analyze
    real_predict = report_api.predict_document_category

    def analyze_spy(source_text, quality):
        extracted_inputs.append(source_text)
        return real_analyze(source_text, quality)

    def predict_spy(source_text):
        classifier_inputs.append(source_text)
        return real_predict(source_text)

    monkeypatch.setattr(report_api, "analyze", analyze_spy)
    monkeypatch.setattr(report_api, "predict_document_category", predict_spy)
    response = client.post("/api/reports", files={"file": ("synthetic_scan.pdf", pdf.tobytes(), "application/pdf")})
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["document_type"] == "pdf"
    assert report["extraction_method"] == "pdf_ocr"
    assert report["ocr_used"] is True
    assert report["ocr_confidence"] is None
    assert report["ocr_blocks"] == []
    assert report["ocr_engine"] == "OCR.space Engine 3"
    assert report["raw_ocr_text"] == "Patient reports fever and cough. Synthetic document for OCR integration checks."
    assert "fever" in " ".join(item["text"] for item in report["symptoms"]).lower()
    expected_text = "Page 1\n" + report["raw_ocr_text"]
    assert extracted_inputs and all(value == expected_text for value in extracted_inputs)
    assert classifier_inputs == [expected_text]
    assert report["ml_prediction"]["probabilities"]
    assert "OCR_SPACE_API_KEY" not in response.text


def test_handwritten_image_api_uses_engine_three_and_requires_review(ocr_space_stub):
    from pathlib import Path
    image = Path(__file__).parent / "fixtures" / "handwritten_note.png"
    response = client.post(
        "/api/reports",
        data={"writing_style": "handwritten"},
        files={"file": ("handwritten_note.png", image.read_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["document_type"] == "handwritten"
    assert report["extraction_method"] == "handwriting_ocr"
    assert report["ocr_status"] in {"partial", "low_confidence"}
    assert report["ocr_engine"] == "OCR.space Engine 3"
    assert report["pages_processed"] == 1
    assert report["page_processing"][0]["page_number"] == 1
    assert any("Handwriting OCR is approximate" in warning for warning in report["requires_review"])
    assert report["ml_prediction"] is not None


def test_database_failure_does_not_claim_a_completed_review(monkeypatch):
    from app.api import reports
    from sqlalchemy.exc import OperationalError
    class BrokenDB:
        def add(self, row): pass
        def commit(self): raise OperationalError("insert", {}, RuntimeError("database unavailable"))
        def close(self): pass
    app.dependency_overrides[reports.get_db] = lambda: BrokenDB()
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/reports", data={"text": "Synthetic patient has fever and cough with enough documentation text."}
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "The review could not be saved or loaded. Please retry."}
    finally:
        app.dependency_overrides.pop(reports.get_db, None)


def test_payment_agreement_details_are_preserved_as_administrative_not_clinical(monkeypatch):
    from app.api import reports as report_api

    monkeypatch.setattr(report_api, "refine_with_llm", lambda source, report: report)
    source = """ACCOUNT PAYMENT AGREEMENT
Patient Name: Synthetic Patient
Date: 2026-02-14
The undersigned agrees to pay all charges incurred at Example Surgical Clinic.
The total cost of this procedure from Example Surgical Clinic is $ 2585.00.
The down payment required to schedule this procedure is $ . You agree to pay $ 100.00 per month until paid in full.
If you are scheduled for a procedure, you may receive separate statements from the hospital and testing provider.
You may also apply for Care Credit which is a separate payment plan.
If this account is turned over to a collection agency, the undersigned agrees to pay fees and related court costs.
"""
    response = client.post("/api/reports", data={"text": source})
    assert response.status_code == 200, response.text
    payload = response.json()
    report = payload["report"]
    admin = report["administrative_information"]
    joined = "\n".join(item["text"] for item in admin)
    assert "ACCOUNT PAYMENT AGREEMENT" not in joined
    assert "total cost" in joined.lower()
    assert "$ 2585.00" in joined
    assert "$ 100.00 per month" in joined
    assert "Care Credit" in joined
    assert all(item["source_excerpt"] == item["text"] for item in admin)
    assert all(item["requires_review"] for item in admin)
    assert not report["symptoms"]
    assert not report["diagnoses"]
    assert not report["medications"]
    assert not report["vitals"]
    assert report["patient_information"]["name"] == "Synthetic Patient"
    assert report["patient_information"] != {"source": source}
    assert any("administrative payment agreement" in item for item in report["requires_review"])
    assert "administrative agreement terms" in report["summary"]
    assert report["ml_prediction"] is not None
    assert payload["status"] == "needs_review"
