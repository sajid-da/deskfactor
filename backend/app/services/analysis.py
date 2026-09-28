import re

from app.schemas.report import ClinicalReport, Finding


SYMPTOM_PATTERN = r"\b(?:fever|cold|myalgia|myaglia|cough|pain|chest discomfort|abdominal discomfort|headache|nausea|vomiting|fatigue|shortness of breath|dizziness|rash|diarrhea|sore throat)\b"
DIAGNOSIS_PATTERN = r"\b(?:viral fever|hypertension|diabetes|asthma|pneumonia|migraine|infection|anemia|bronchitis|URTI)\b"
MEDICATION_PATTERN = r"\b(?:azithromycin|sinarest|dolo(?:\s+paracetamol)?|paracetamol|acetaminophen|ibuprofen|amoxicillin|metformin|aspirin|insulin|lisinopril|calpol|delcon|levolin|meftal-p)\b(?:\s*\(?\s*\d+(?:\.\d+)?\s*(?:mg|mcg|ml)(?:/\d+(?:\.\d+)?)?\s*\)?)?"
LABELS = {"name", "age", "gender", "sex", "height", "weight", "date", "pat id", "patient id", "patient name", "dob", "date of birth"}
INLINE_LABEL_PATTERN = re.compile(r"(?:patient name|clinical description|age\s*,\s*gender|date of birth|patient id|pat id|gender|weight|height|name|age|sex|date)\s*:", re.I)


def _findings(text: str, pattern: str, *, certainty: str = "medium") -> list[Finding]:
    found: list[Finding] = []
    seen: set[str] = set()
    for match in re.finditer(pattern, text, re.I):
        context = text[max(0, match.start() - 45):match.start()]
        if re.search(r"(?:\bno\b|\bdenies\b|\bwithout\b|\bnegative for\b|\bnot\b)(?:\s+\w+){0,2}\s*$", context, re.I):
            continue
        value = match.group(0).strip()
        if value.casefold() not in seen:
            seen.add(value.casefold())
            start = text.rfind("\n", 0, match.start()) + 1
            end_candidates = [position for marker in ("\n", ".", "!", "?")
                              if (position := text.find(marker, match.end())) >= 0]
            end = min(end_candidates) + 1 if end_candidates else len(text)
            excerpt = text[start:end].strip()
            found.append(Finding(text=value, certainty=certainty, source_excerpt=excerpt or value))
    return found


def _label_value(text: str, labels: tuple[str, ...]) -> str | None:
    lines = text.splitlines()
    label_pattern = re.compile(r"^\s*(" + "|".join(re.escape(label) for label in labels) + r")\s*:?[ \t]*(.*)$", re.I)
    for index, line in enumerate(lines):
        match = label_pattern.match(line)
        if not match:
            continue
        value = match.group(2).strip()
        if value:
            return value
        for candidate in lines[index + 1:]:
            candidate = candidate.strip()
            if not candidate:
                continue
            if re.match(r"^[\w ]+\s*:?$", candidate) and candidate.casefold().rstrip(":") in LABELS:
                break
            return candidate
    return None


def _section(text: str, heading: str, end_headings: tuple[str, ...]) -> list[str]:
    end = "|".join(re.escape(item) for item in end_headings)
    match = re.search(rf"(?ims)^\s*{re.escape(heading)}\s*:?\s*\n(.*?)(?=^\s*(?:{end}|Page\s+\d+)\s*:?\s*$|\Z)", text)
    return match.group(1).splitlines() if match else []


def _list_findings(lines: list[str], *, certainty: str = "high") -> list[Finding]:
    findings: list[Finding] = []
    for line in lines:
        excerpt = line.strip()
        if not excerpt:
            continue
        value = re.sub(r"^\s*\d+[.)]\s*(?:\d+\.\s*)?", "", excerpt).strip()
        if value:
            findings.append(Finding(text=value, certainty=certainty, source_excerpt=excerpt))
    return findings


def _prescribed_medicines(text: str) -> list[Finding]:
    lines = text.splitlines()
    results: list[Finding] = []
    dose_pattern = re.compile(r"\b(?:daily|dosage|dose|once|twice)\s*:", re.I)
    for index, line in enumerate(lines):
        if not dose_pattern.search(line):
            continue
        medicine_index = index - 1
        if medicine_index < 0:
            continue
        medicine = lines[medicine_index].strip()
        if re.fullmatch(r"\d+\.", medicine) and medicine_index > 0:
            medicine_index -= 1
            medicine = lines[medicine_index].strip()
        if not re.search(r"\b(?:tablet|capsule|syrup|injection|ointment|drops)\b", medicine, re.I):
            continue
        instruction_index = index + 1
        while instruction_index < len(lines) and not lines[instruction_index].strip():
            instruction_index += 1
        start_index = medicine_index
        if medicine_index > 0 and re.fullmatch(r"\s*\d+\.\s*", lines[medicine_index - 1]):
            start_index -= 1
        excerpt = "\n".join(part.strip() for part in lines[start_index:min(instruction_index + 1, len(lines))] if part.strip())
        if not excerpt:
            continue
        results.append(Finding(text=excerpt, certainty="high", source_excerpt=excerpt))
    # OCR commonly flattens pediatric prescriptions onto one line. Keep each
    # syrup and its dose/duration together, stopping before the next medicine.
    syrup_matches = list(re.finditer(r"\b(?:syp|syrup)\s+", text, re.I))
    for index, match in enumerate(syrup_matches):
        end = syrup_matches[index + 1].start() if index + 1 < len(syrup_matches) else len(text)
        excerpt = text[match.start():end].strip(" \t\r\n;,.:-")
        excerpt = re.split(r"\s+(?:മുൻകൂട്ടി|മുന്‍കൂട്ടി)", excerpt, maxsplit=1)[0].strip(" \t\r\n;,.:-")
        if re.search(r"\b\d+(?:\.\d+)?\s*ml\b", excerpt, re.I):
            results.append(Finding(text=excerpt, certainty="high", source_excerpt=excerpt))
    return _unique_findings(results)


def _inline_values(text: str) -> dict[str, str]:
    matches = list(INLINE_LABEL_PATTERN.finditer(text))
    values: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = re.sub(r"\s+", " ", match.group(0).rstrip(":")).casefold()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = re.sub(r"\s+", " ", text[match.end():end]).strip(" \t\r\n:;,.|")
        if value:
            values[label] = value
    return values


def _unique_findings(*groups: list[Finding]) -> list[Finding]:
    results: list[Finding] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = item.text.casefold()
            if key not in seen:
                seen.add(key)
                results.append(item)
    return results


def _unclassified_clinical_segments(text: str, known_findings: list[Finding], *, quality: str) -> list[Finding]:
    """Retain likely clinical source segments that no structured category captured."""
    known = [item.text.casefold() for item in known_findings if item.text]
    patient_label = re.compile(
        r"^\s*(?:name|patient name|age|age\s*,\s*gender|gender|sex|height|weight|date|dob|date of birth|pat id|patient id|mrn)\s*:?\s*",
        re.I,
    )
    clinical_context = re.compile(
        r"\b(?:clinical|history|reports?|present(?:ing)?|complain(?:s|t)?|symptom|diagnos(?:is|ed)|"
        r"assessment|impression|finding|shows?|reveals?|without|denies|negative|positive|normal|abnormal|"
        r"pain|swelling|lesion|infection|inflammation|scan|imaging|x-?ray|ultrasound|mri|ct\b|ecg|ekg|"
        r"lab(?:oratory)?|test result|prescribed|taking|treatment|dose|follow.?up|observation|advice|concern|"
        r"unclear|illegible|fever|cough|cold|myalgia|headache|nausea|vomiting|fatigue|rash|diarrhea)\b",
        re.I,
    )
    results: list[Finding] = []
    seen: set[str] = set()
    for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
        segment = re.sub(r"\s+", " ", raw).strip(" \t\r\n-•")
        if len(segment) < 12 or len(segment) > 1200 or patient_label.match(segment):
            continue
        folded = segment.casefold()
        compact = re.sub(r"\W", "", folded)
        matching_known = [item for item in known if re.sub(r"\W", "", item) in compact]
        if matching_known and not re.search(
            r"\b(?:uncertain|unclear|illegible|unreadable|possible|suspected|cannot rule out)\b",
            segment, re.I,
        ):
            continue
        if not clinical_context.search(segment) or folded in seen:
            continue
        seen.add(folded)
        results.append(Finding(
            text=raw.strip(),
            certainty="low" if quality != "readable" else "unknown",
            source_excerpt=raw.strip(),
            reason="Source text appears clinically relevant but could not be confidently assigned to a structured field.",
            requires_review=True,
        ))
    return results


def _administrative_agreement_findings(text: str) -> list[Finding]:
    """Preserve source-grounded financial/consent terms outside clinical fields."""
    agreement = re.search(r"\b(?:account\s+payment|payment|financial|billing)\s+agreement\b", text, re.I)
    if not agreement:
        return []
    signals = re.compile(
        r"\b(?:payment|per month|procedure|surgical clinic|billing|hospital|care credit|collection|monthly|total cost|"
        r"down payment|insurance|charges incurred|waives? all rights|professional services|business office|medical arts|fax|telephone|opelika|alabama|"
        r"gastrointestinal|endoscopy|vein center|vascular|laparoscopic|FACS|MBBS|M\.D\.|Reg\.? No|Reg\.? Id|\bPh\.?\s*[:.]|"
        r"undersigned|fees|court costs|services rendered)\b",
        re.I,
    )
    findings: list[Finding] = []
    seen: set[str] = set()
    for raw in re.split(r"(?<=[.!?])\s+|\n+", text):
        excerpt = raw.strip()
        folded = re.sub(r"\s+", " ", excerpt).casefold()
        if (len(excerpt) < 12 or re.fullmatch(r"(?:account\s+)?(?:payment|financial|billing)\s+agreement", excerpt, re.I)
                or not signals.search(excerpt) or folded in seen):
            continue
        seen.add(folded)
        findings.append(Finding(
            text=excerpt,
            certainty="medium",
            source_excerpt=excerpt,
            reason="Administrative payment or consent term; verify amounts and obligations against the original agreement.",
            requires_review=True,
        ))
    return findings


def analyze(text: str, quality: str) -> ClinicalReport:
    """Extract source-grounded patient facts and preserve labeled document sections."""
    administrative_information = _administrative_agreement_findings(text)
    symptoms = _findings(text, SYMPTOM_PATTERN)
    diagnoses = _findings(text, DIAGNOSIS_PATTERN)
    medication_rows = _prescribed_medicines(text)
    medication_mentions = _findings(text, MEDICATION_PATTERN)
    medication_mentions = [item for item in medication_mentions if not any(item.text.casefold() in row.text.casefold() for row in medication_rows)]
    medications = _unique_findings(medication_rows, medication_mentions)
    allergies = _findings(text, r"\b(?:no known allergies|no known drug allergies|allergy to [A-Za-z-]+|allergic to [A-Za-z-]+)\b", certainty="high")
    vital_patterns = {
        "temperature": r"(?:temperature|temp)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?\s*°?\s*[FC]?)",
        "blood_pressure": r"(?:blood pressure|BP)\s*[:=]?\s*(\d{2,3}\s*/\s*\d{2,3})",
        "heart_rate": r"(?:heart rate|pulse|HR)\s*[:=]?\s*(\d{2,3}\s*(?:bpm)?)",
        "oxygen_saturation": r"(?:oxygen saturation|SpO2|O2 sat)\s*[:=]?\s*(\d{2,3}\s*%?)",
        "respiratory_rate": r"\b(?:RR|respiratory rate)\s*[-:=]?\s*(\d{1,3}\s*(?:/\s*min|breaths?\s*/\s*min))",
        "weight": r"\bweight\s*[:=]?\s*(\d{1,3}(?:\.\d+)?\s*(?:kg|kgs))\b",
    }
    vitals = {key: match.group(1).strip() for key, pattern in vital_patterns.items() if (match := re.search(pattern, text, re.I))}

    patient: dict[str, str | None] = {}
    patient_labels = {
        "name": ("patient name", "name"),
        "age": ("age",),
        "gender": ("gender", "sex"),
        "height": ("height",),
        "weight": ("weight",),
        "patient_id": ("patient id", "pat id", "mrn"),
        "encounter_date": ("date of birth", "dob", "date"),
    }
    for field, labels in patient_labels.items():
        value = _label_value(text, labels)
        if value:
            if field == "age":
                age_match = re.fullmatch(r"\s*(\d{1,3})(?:\s*(?:years?|yrs?))?\s*", value, re.I)
                value = age_match.group(0).strip() if age_match else None
            elif field == "gender" and not re.fullmatch(r"\s*(?:male|female|m|f|other|non.?binary)\s*", value, re.I):
                value = None
            elif field == "height" and not re.fullmatch(r"\s*\d{2,3}(?:\.\d+)?\s*(?:cm|cms|m|in|inches)?\s*", value, re.I):
                value = None
            elif field == "weight" and not re.fullmatch(r"\s*\d{1,3}(?:\.\d+)?\s*(?:kg|kgs|lb|lbs)?\s*", value, re.I):
                value = None
            elif field == "encounter_date" and not re.fullmatch(r"\s*(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s*", value):
                value = None
            elif field == "name" and (len(value) > 100 or re.search(r"\b(?:clinical|patient reports?|symptom|diagnos|medication|prescribed|history)\b", value, re.I)):
                value = None
            if value:
                patient[field] = value
    inline = _inline_values(text)
    for field, aliases in {
        "name": ("name", "patient name"), "age": ("age", "age, gender"),
        "gender": ("gender", "sex"), "height": ("height",), "weight": ("weight",),
        "encounter_date": ("date",),
    }.items():
        value = next((inline[alias] for alias in aliases if alias in inline), None)
        if value:
            if field == "name" and (len(value) > 100 or re.search(r"\b(?:clinical|patient reports?|symptom|diagnos|medication|prescribed|history)\b", value, re.I)):
                value = None
            if field == "age" and not re.fullmatch(r"\s*\d{1,3}(?:\s*(?:years?|yrs?|gr))?(?:\s*/\s*(?:male|female|m|f))?\s*", value, re.I):
                value = None
            if value and field == "weight" and (match := re.match(r"\d{1,3}(?:\.\d+)?\s*(?:kg|kgs)\b", value, re.I)):
                value = match.group(0)
            if value and field == "height" and (match := re.match(r"\d{2,3}(?:\.\d+)?\s*(?:cm|cms)\b", value, re.I)):
                value = match.group(0)
            if field == "encounter_date" and not re.fullmatch(r"\s*(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s*", value):
                value = None
            if value and field == "age" and "/" in value:
                age_value, gender_value = (part.strip() for part in value.split("/", 1))
                patient[field] = age_value
                if gender_value and "gender" not in patient:
                    patient["gender"] = gender_value
            elif value:
                patient[field] = value
    for key, value in re.findall(r"\b(RR)\s*[-:=]?\s*(\d{1,3}\s*/\s*min)\b", text, re.I):
        vitals["respiratory_rate"] = f"{value.split('/')[0].strip()}/min"
    clinical_description = inline.get("clinical description", "")
    exam_match = re.search(r"\bRS\s*[-:]\s*BIL\s+AEE\b", clinical_description, re.I)
    clinical_observations = ([Finding(text=exam_match.group(0), certainty="unknown", source_excerpt=exam_match.group(0))]
                             if exam_match else [])
    for observation in re.finditer(
        r"\b(?:ECG|EKG|X-ray|ultrasound|MRI|CT scan|imaging)\s+(?:shows?|reveals?|notes?)\s+[^.!?\n]+",
        text, re.I,
    ):
        clinical_observations.append(Finding(
            text=observation.group(0), certainty="low", source_excerpt=observation.group(0),
            reason="Verify this reported finding against the original source.", requires_review=True,
        ))
    clinical_observations = _unique_findings(clinical_observations)

    diagnosis_value = _section(text, "Diagnosis", ("Description", "Prescribed Medicines", "Drug Allergies", "Lab Test"))
    if diagnosis_value:
        line_values = [line.strip() for line in diagnosis_value if line.strip()]
        diagnoses = _unique_findings(diagnoses, _list_findings(line_values))

    description = _section(text, "Description", ("S.No.", "Prescribed Medicines", "Drug Allergies", "Lab Test"))
    description_symptoms = [
        Finding(text=term.strip(), certainty="high", source_excerpt=term.strip())
        for line in description for term in line.split(",") if term.strip()
    ]
    symptoms = _unique_findings(symptoms, description_symptoms)

    lab_tests = _list_findings(_section(text, "Lab Test", ("Follow Up", "Doctor's Advice", "Doctor’s Advice", "Substitute medicine brand")))
    follow_up = _list_findings(_section(text, "Follow Up", ("Doctor's Advice", "Doctor’s Advice", "Substitute medicine brand")))
    doctor_advice = _list_findings(_section(text, "Doctor's Advice", ("Substitute medicine brand",)))
    if not doctor_advice:
        doctor_advice = _list_findings(_section(text, "Doctor’s Advice", ("Substitute medicine brand",)))

    known_findings = [*symptoms, *diagnoses, *medications, *allergies,
                      *clinical_observations, *lab_tests, *follow_up, *doctor_advice]
    unclassified_information = _unclassified_clinical_segments(text, known_findings, quality=quality)

    patient_age_number = re.search(r"\d{1,3}", patient.get("age", ""))
    ages = {value for value in (patient_age_number.group(0) if patient_age_number else None, *re.findall(r"\bage\s*[:=]?\s*(\d{1,3})", text, re.I), *re.findall(r"\b(\d{1,3})\s*[- ]?year[- ]old\b", text, re.I)) if value}
    inconsistencies = [f"Different ages are documented: {', '.join(sorted(ages))}." ] if len(ages) > 1 else []
    missing = []
    if not patient.get("name") and not patient.get("patient_id"):
        missing.append("Patient name or identifier")
    if not patient.get("age") and not re.search(r"\bDOB\s*[:=]", text, re.I):
        missing.append("Age or date of birth")
    if not patient.get("encounter_date"):
        missing.append("Encounter date")
    review = []
    if quality != "readable":
        review.append("Source text extraction was incomplete; verify the original document.")
    if unclassified_information:
        review.append("Some clinically relevant source text could not be confidently classified; verify the unclassified information against the original.")
    if medications:
        review.append("Verify prescribed medicine names, dosage, and instructions against the source document.")
    if re.search(r"\b\d{1,2}\s*gr\b", patient.get("age", ""), re.I):
        review.append(f"Verify OCR reading of the documented age ({patient['age']}) against the source.")
    if inconsistencies:
        review.extend(inconsistencies)
    if administrative_information and not symptoms and not diagnoses and not medications and not vitals:
        review.append("This appears to be an administrative payment agreement rather than a clinical note; clinical sections are empty because no clinical findings were identified.")
    elif not symptoms and not diagnoses and not medications and not vitals:
        review.append("No common clinical facts could be confidently matched; review the source document.")

    summary_parts = []
    if diagnoses:
        summary_parts.append("Documented diagnosis: " + ", ".join(item.text for item in diagnoses[:2]))
    if symptoms:
        summary_parts.append(f"{len(symptoms)} symptom terms")
    if medications:
        summary_parts.append(f"{len(medications)} prescribed medicines")
    if lab_tests:
        summary_parts.append(f"{len(lab_tests)} lab tests")
    if doctor_advice:
        summary_parts.append(f"{len(doctor_advice)} doctor-advice items")
    if administrative_information:
        summary_parts.append(f"{len(administrative_information)} administrative agreement terms")
    summary = ("Extracted for human verification: " + "; ".join(summary_parts) + ".") if summary_parts else "The document contains little readable clinical information; manual review is needed."

    return ClinicalReport(
        patient_information=patient,
        administrative_information=administrative_information,
        unclassified_information=unclassified_information,
        symptoms=symptoms,
        diagnoses=diagnoses,
        medications=medications,
        vitals=vitals,
        allergies=allergies,
        clinical_observations=clinical_observations,
        clinical_concerns=[Finding(text=value, certainty="medium") for value in inconsistencies],
        lab_tests=lab_tests,
        follow_up=follow_up,
        doctor_advice=doctor_advice,
        missing_information=missing,
        potential_inconsistencies=inconsistencies,
        requires_review=review,
        summary=summary if len(text) >= 30 else "The document contains little readable text; manual review is needed.",
        extraction_quality=quality,
    )
