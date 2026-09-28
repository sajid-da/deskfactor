"""Write deterministic, entirely synthetic document-workflow datasets."""
import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SPLITS = {
    "train": [
        ("routine", ["The {doc} is complete, legible, and ready for routine filing.", "All required sections in this {doc} are present and internally consistent.", "This {doc} passed the documentation checklist with no follow-up requested.", "The {doc} is readable and complete for standard processing.", "Required fields are filled in this {doc}; route through the usual queue.", "No document quality issues were found in the {doc}; standard workflow applies."]),
        ("review_required", ["The {doc} has a missing signature and needs a completeness check.", "Conflicting dates appear in this {doc}; please verify the source.", "Several fields are blank in this {doc}, so a manual documentation review is needed.", "The {doc} is partly illegible and should be checked against the original.", "A duplicate page and an inconsistent identifier were found in this {doc}.", "This {doc} is missing a required section; return it for document follow-up."]),
        ("urgent_review", ["This {doc} carries a priority review routing marker; follow the organization's escalation workflow.", "The {doc} is explicitly marked urgent for document handling; route to the designated queue.", "An immediate records review was requested for this {doc} by the submitting office.", "Priority handling is requested on the cover sheet of this {doc}; use the approved routing process.", "This {doc} has an urgent administrative review flag; confirm receipt promptly.", "The submitting office marked this {doc} for immediate workflow review, not clinical triage."]),
    ],
    "validation": [
        ("routine", ["Routine filing: this {doc} is legible, complete, and has no follow-up flags.", "Checklist passed for the {doc}; all sections are consistent and present.", "The {doc} can move through standard processing with no documentation issue.", "A complete readable {doc} was received for normal records processing."]),
        ("review_required", ["Please inspect the {doc}; its date fields conflict and a signature is missing.", "The {doc} contains unreadable text and omitted sections needing manual verification.", "A blank field and duplicate attachment were found in the {doc}; request a correction.", "Manual records review needed: the {doc} has an incomplete identifier."]),
        ("urgent_review", ["Priority workflow flag: the office requests immediate review of this {doc}.", "Route the {doc} to the designated urgent records queue per office procedure.", "This {doc} was marked for prompt administrative review; confirm routing.", "An explicit immediate handling request accompanies this {doc}; use standard escalation steps."]),
    ],
    "test": [
        ("routine", ["Standard processing is appropriate: the {doc} is clear, complete, and internally consistent.", "All checklist items are present in this readable {doc}; no action is pending.", "The records packet is complete and ready for routine filing.", "No administrative flags; this {doc} passed the quality review."]),
        ("review_required", ["This {doc} has conflicting identifiers and an unreadable section; verify manually.", "The records packet is incomplete because a required attachment is missing.", "A date mismatch was noted in the {doc}; hold for source comparison.", "Manual verification requested because the {doc} has blank and duplicate fields."]),
        ("urgent_review", ["The cover page requests immediate administrative review of this {doc}.", "An explicit priority routing label is present; forward this {doc} per local procedure.", "The sending office requests prompt workflow handling for this {doc}.", "Marked urgent for records routing only; send this {doc} to the designated queue."]),
    ],
}
DOCUMENTS = ["document", "record", "packet"]


def write_datasets() -> None:
    for split, groups in SPLITS.items():
        path = DATA / f"{split}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["text", "label"])
            writer.writeheader()
            for label, templates in groups:
                for index, template in enumerate(templates):
                    writer.writerow({"text": template.format(doc=DOCUMENTS[index % len(DOCUMENTS)]), "label": label})


if __name__ == "__main__":
    write_datasets()
