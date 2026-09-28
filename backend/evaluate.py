"""Small synthetic extraction evaluation: python evaluate.py"""
from app.services.analysis import analyze

CASES = [
    {"text": "Synthetic patient reports fever and cough. Temperature 101 F. Taking paracetamol.",
     "symptoms": {"fever", "cough"}, "medications": {"paracetamol"}, "vitals": {"temperature": "101 F"}},
    {"text": "Synthetic note: patient has headache and nausea; taking ibuprofen 200 mg.",
     "symptoms": {"headache", "nausea"}, "medications": {"ibuprofen 200 mg"}, "vitals": {}},
    {"text": "Synthetic chart: Age 42. Later history says age 47. Patient reports dizziness.",
     "symptoms": {"dizziness"}, "medications": set(), "vitals": {}},
]


def main():
    tp = predicted = expected = unsupported = 0
    for case in CASES:
        report = analyze(case["text"], "readable")
        for field in ("symptoms", "medications"):
            actual = {item.text.casefold() for item in getattr(report, field)}
            wanted = case[field]
            tp += len(actual & wanted)
            predicted += len(actual)
            expected += len(wanted)
            unsupported += sum(1 for item in getattr(report, field) if item.text.casefold() not in case["text"].casefold())
        assert all(value.casefold() in case["text"].casefold() for value in report.vitals.values())
        assert bool(report.potential_inconsistencies) == ("age 42" in case["text"].casefold())
    precision = tp / predicted if predicted else 1
    recall = tp / expected if expected else 1
    print(f"samples={len(CASES)} fact_precision={precision:.2f} fact_recall={recall:.2f} unsupported_facts={unsupported}")
    assert unsupported == 0


if __name__ == "__main__":
    main()
