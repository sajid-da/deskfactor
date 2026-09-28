from app.schemas.report import ClinicalReport
from app.schemas.report import Finding
import re


PATIENT_FIELD_TERMS = {
    "name", "age", "gender", "sex", "birth", "dob", "date", "encounter",
    "patient", "id", "identifier", "height", "weight", "address", "contact",
    "phone", "email", "registration", "mrn", "record", "race", "ethnicity",
}


def _patient_key_is_demographic(key: str) -> bool:
    terms = set(re.findall(r"[a-z]+", key.casefold()))
    allowed = PATIENT_FIELD_TERMS | {"of", "the", "and"}
    return bool(terms) and terms <= allowed and bool(terms & PATIENT_FIELD_TERMS)


def _preserve_unclassified_value(report: ClinicalReport, value: str) -> None:
    """Move supported non-demographic AI output into reviewable source segments."""
    for segment in re.split(r"(?<=[.!?])\s+|\n+", value):
        segment = segment.strip()
        if not segment or len(segment) > 1200:
            continue
        if any(item.source_excerpt == segment for item in report.unclassified_information):
            continue
        report.unclassified_information.append(Finding(
            text=segment,
            certainty="unknown",
            source_excerpt=segment,
            reason="The source text was returned under patient information but is not confidently demographic; verify its category.",
            requires_review=True,
        ))


def validate_source_grounding(report: ClinicalReport, source: str) -> None:
    folded = source.casefold()
    patient_information: dict[str, str | None] = {}
    for key, value in report.patient_information.items():
        if value is None:
            patient_information[key] = None
            continue
        if value.casefold() not in folded:
            raise ValueError("The analysis service returned a detail that could not be verified against the source.")
        if _patient_key_is_demographic(key) and len(value) <= 500:
            patient_information[key] = value
        else:
            _preserve_unclassified_value(report, value)
    report.patient_information = patient_information
    for item in [*report.symptoms, *report.diagnoses, *report.medications, *report.allergies,
                 *report.clinical_observations, *report.clinical_concerns, *report.lab_tests,
                 *report.follow_up, *report.doctor_advice, *report.unclassified_information, *report.administrative_information]:
        if not item.source_excerpt or item.source_excerpt.casefold() not in folded or item.text.casefold() not in folded:
            raise ValueError("The analysis service returned a detail that could not be verified against the source.")
    for value in [*report.patient_information.values(), *report.vitals.values()]:
        if value and value.casefold() not in folded:
            raise ValueError("The analysis service returned a detail that could not be verified against the source.")
