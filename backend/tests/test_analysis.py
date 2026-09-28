from app.services.analysis import analyze
from app.services.validation.source_grounding import validate_source_grounding


def test_clean_synthetic_note_extracts_only_source_facts():
    report = analyze("Synthetic patient has fever and cough. Temperature 101 F. Taking paracetamol 500 mg.", "readable")
    assert {x.text.lower() for x in report.symptoms} == {"fever", "cough"}
    assert report.medications[0].text.lower() == "paracetamol 500 mg"
    assert report.vitals["temperature"] == "101 F"
    assert report.patient_information == {}
    assert report.missing_information


def test_inconsistent_ages_are_flagged():
    report = analyze("Age: 42. Later history: age 47.", "readable")
    assert report.potential_inconsistencies
    assert report.requires_review


def test_irrelevant_text_does_not_create_clinical_facts():
    report = analyze("The green folder is on the table.", "readable")
    assert not report.symptoms and not report.diagnoses and not report.medications
    assert report.extraction_quality == "readable"
    assert report.requires_review


def test_explicitly_denied_symptom_is_not_reported_as_present():
    report = analyze("Synthetic note: patient denies fever and cough but reports headache.", "readable")
    assert {x.text.lower() for x in report.symptoms} == {"headache"}


def test_partial_document_requests_source_verification():
    report = analyze("fever", "partial")
    assert report.extraction_quality == "partial"
    assert any("verify" in x for x in report.requires_review)


def test_prescription_sections_map_to_patient_medicines_labs_and_advice():
    source = """Rx
Name
Sample Patient
Age
42 Years
Gender Male
Height 175cms
Weight 62kgs
Date
30-08-2023
Pat Id 123456
Diagnosis
viral fever
Description
fever , cold, myaglia
S.No.
Prescribed Medicines
Dosage
Instructions
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
1. 1.steam inhalation before sleep
2. get rtpcr tested if symptoms doesn't reduce
3. keep checking saturation every 2 hourly
4. isolate yourself
5. avoid cold water
6. get hospitalised if you feel symptoms are worsening
7. don't not panic
"""
    report = analyze(source, "readable")
    validate_source_grounding(report, source)

    assert report.patient_information == {
        "name": "Sample Patient", "age": "42 Years", "gender": "Male", "height": "175cms",
        "weight": "62kgs", "patient_id": "123456", "encounter_date": "30-08-2023",
    }
    assert any(item.text == "viral fever" for item in report.diagnoses)
    assert len(report.medications) == 3
    assert "Daily: 1-0-1" in report.medications[0].text
    assert len(report.lab_tests) == 3
    assert len(report.follow_up) == 1 and report.follow_up[0].text == "3 Days"
    assert len(report.doctor_advice) == 7
    assert any(item.text == "No known Allergies" for item in report.allergies)
    assert not report.missing_information


def test_flattened_pediatric_prescription_maps_syrups_patient_and_vitals():
    source = (
        "Dr. Example Doctor MBBS MD Paediatrics Reg. No.: 12345 Ph: 9000000000 "
        "Date: 20-9-2022 Name: Sample Child Age, Gender: 4 gr / F "
        "Clinical Description: URTI RR-22/min RS-BIL AEE Advice: Weight: 13.25 kg "
        "SYP CALPOL (250/5) 4ML Q6H x 3d Syp DELCON 3 ML TOS x sd "
        "Syp LEVOLIN 3 ML TOS x 5d SYP MEFTAL-P (100/5) 3 ML SOS "
        "മുൻകൂട്ടി ബുക്കിങ്ങ് ഉണ്ടായിരിക്കുന്നതല്ല"
    )
    report = analyze(source, "readable")
    validate_source_grounding(report, source)

    assert report.patient_information["name"] == "Sample Child"
    assert report.patient_information["age"] == "4 gr"
    assert report.patient_information["gender"] == "F"
    assert report.patient_information["encounter_date"] == "20-9-2022"
    assert report.patient_information["weight"] == "13.25 kg"
    assert report.vitals["respiratory_rate"] == "22/min"
    assert report.vitals["weight"] == "13.25 kg"
    assert [item.text for item in report.diagnoses] == ["URTI"]
    assert [item.text for item in report.medications] == [
        "SYP CALPOL (250/5) 4ML Q6H x 3d", "Syp DELCON 3 ML TOS x sd",
        "Syp LEVOLIN 3 ML TOS x 5d", "SYP MEFTAL-P (100/5) 3 ML SOS",
    ]
    assert [item.text for item in report.clinical_observations] == ["RS-BIL AEE"]
    assert any("age" in item.lower() for item in report.requires_review)
