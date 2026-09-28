"""Small deterministic TF-IDF + multinomial logistic regression inference."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.report import ClassProbability, MLPrediction

MODEL_PATH = Path(__file__).resolve().parent / "models" / "document_review_classifier.json"
MODEL_NAME = "Synthetic Document Workflow Classifier"
MODEL_VERSION = "1.0.0"
CONFIDENCE_HIGH = 0.75
CONFIDENCE_MEDIUM = 0.50


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


def vectorize(text: str, model: dict[str, Any]) -> dict[int, float]:
    counts: dict[str, int] = {}
    for word in tokens(text):
        counts[word] = counts.get(word, 0) + 1
    values = {
        model["vocabulary"][word]: (1 + math.log(count)) * model["idf"][model["vocabulary"][word]]
        for word, count in counts.items() if word in model["vocabulary"]
    }
    norm = math.sqrt(sum(value * value for value in values.values()))
    return {index: value / norm for index, value in values.items()} if norm else {}


def load_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Trained ML artifact not found at {path}; run `python -m ml.train` from backend.")
    model = json.loads(path.read_text(encoding="utf-8"))
    if model.get("algorithm") != "tfidf_multinomial_logistic_regression" or not model.get("weights"):
        raise ValueError("ML artifact is invalid; expected a trained TF-IDF logistic regression model.")
    return model


@lru_cache(maxsize=1)
def _load_default_model() -> dict[str, Any]:
    return load_model()


def predict(text: str, model: dict[str, Any] | None = None) -> MLPrediction:
    model = model or _load_default_model()
    vector = vectorize(text, model)
    logits = [bias + sum(row[index] * value for index, value in vector.items()) for row, bias in zip(model["weights"], model["bias"], strict=True)]
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    total = sum(exponentials)
    probabilities = [value / total for value in exponentials]
    best = max(range(len(probabilities)), key=probabilities.__getitem__)
    confidence = probabilities[best]
    label = "high" if confidence >= CONFIDENCE_HIGH else "medium" if confidence >= CONFIDENCE_MEDIUM else "low"
    signals = sorted(((model["weights"][best][index] * value, model["terms"][index]) for index, value in vector.items()), reverse=True)
    return MLPrediction(
        category=model["classes"][best],
        probabilities=[ClassProbability(category=category, probability=value) for category, value in zip(model["classes"], probabilities, strict=True)],
        confidence=confidence, confidence_label=label, model_name=MODEL_NAME, model_version=model["version"],
        feature_signals=[term for contribution, term in signals if contribution > 0][:5],
    )
