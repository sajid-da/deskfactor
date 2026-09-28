from ml.classifier import load_model, predict
from ml.train import fit, load_split


def test_saved_model_predicts_probabilities_and_explanation():
    prediction = predict("The document is complete, legible, and ready for routine filing.")
    assert prediction.category == "routine"
    assert abs(sum(item.probability for item in prediction.probabilities) - 1) < 1e-9
    assert prediction.model_name
    assert prediction.model_version == "1.0.0"
    assert prediction.feature_signals


def test_priority_routing_is_classified_as_administrative_workflow():
    prediction = predict("This record carries a priority review routing marker; use the designated queue.")
    assert prediction.category == "urgent_review"
    assert "not a clinical risk" in prediction.disclaimer


def test_loaded_model_predictions_are_deterministic():
    model = load_model()
    text = "A missing signature and conflicting date require manual document review."
    assert predict(text, model).model_dump() == predict(text, model).model_dump()


def test_training_is_deterministic():
    texts, labels = load_split("train")
    first = fit(texts, labels)
    second = fit(texts, labels)
    assert first == second
