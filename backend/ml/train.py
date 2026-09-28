"""Train deterministic TF-IDF multinomial logistic regression from CSV splits."""
import csv
import json
import math
from collections import Counter
from pathlib import Path

from ml.classifier import MODEL_PATH, tokens, vectorize

ROOT = Path(__file__).resolve().parent
LABELS = ["routine", "review_required", "urgent_review"]


def load_split(name: str) -> tuple[list[str], list[str]]:
    with (ROOT / "data" / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"Dataset split {name!r} is empty")
    return [row["text"] for row in rows], [row["label"] for row in rows]


def fit(texts: list[str], labels: list[str]) -> dict:
    classes = LABELS
    term_sets = [set(tokens(text)) for text in texts]
    document_frequency = Counter(term for terms in term_sets for term in terms)
    terms = sorted(document_frequency)
    vocabulary = {term: index for index, term in enumerate(terms)}
    idf = [math.log((1 + len(texts)) / (1 + document_frequency[term])) + 1 for term in terms]
    model = {
        "algorithm": "tfidf_multinomial_logistic_regression", "version": "1.0.0", "classes": classes,
        "terms": terms, "vocabulary": vocabulary, "idf": idf,
        "weights": [[0.0] * len(terms) for _ in classes], "bias": [0.0] * len(classes),
    }
    vectors = [vectorize(text, model) for text in texts]
    class_indices = [classes.index(label) for label in labels]
    weights = model["weights"]
    bias = model["bias"]
    learning_rate, regularization, epochs = 0.7, 0.001, 1200
    for _ in range(epochs):
        gradients = [[0.0] * len(terms) for _ in classes]
        bias_gradients = [0.0] * len(classes)
        for vector, target in zip(vectors, class_indices, strict=True):
            logits = [bias[c] + sum(weights[c][i] * value for i, value in vector.items()) for c in range(len(classes))]
            maximum = max(logits)
            exp = [math.exp(value - maximum) for value in logits]
            total = sum(exp)
            for c in range(len(classes)):
                error = exp[c] / total - (1.0 if c == target else 0.0)
                bias_gradients[c] += error
                for index, value in vector.items():
                    gradients[c][index] += error * value
        size = len(texts)
        for c in range(len(classes)):
            bias[c] -= learning_rate * bias_gradients[c] / size
            for index in range(len(terms)):
                weights[c][index] -= learning_rate * (gradients[c][index] / size + regularization * weights[c][index])
    model["training_samples"] = len(texts)
    model["epochs"] = epochs
    return model


def evaluate(model: dict, name: str) -> dict:
    texts, expected = load_split(name)
    matrix = [[0 for _ in LABELS] for _ in LABELS]
    predicted = []
    for text in texts:
        vector = vectorize(text, model)
        logits = [model["bias"][c] + sum(model["weights"][c][i] * value for i, value in vector.items()) for c in range(len(LABELS))]
        predicted.append(LABELS[max(range(len(logits)), key=logits.__getitem__)])
    for actual, guess in zip(expected, predicted, strict=True):
        matrix[LABELS.index(actual)][LABELS.index(guess)] += 1
    per_class = {}
    f1_scores = []
    precisions = []
    recalls = []
    for index, label in enumerate(LABELS):
        tp = matrix[index][index]
        fp = sum(matrix[row][index] for row in range(len(LABELS)) if row != index)
        fn = sum(matrix[index][col] for col in range(len(LABELS)) if col != index)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1-score": f1, "support": sum(matrix[index])}
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
    return {"split": name, "sample_count": len(expected), "accuracy": sum(a == b for a, b in zip(expected, predicted, strict=True)) / len(expected),
            "macro_precision": sum(precisions) / len(LABELS), "macro_recall": sum(recalls) / len(LABELS), "macro_f1": sum(f1_scores) / len(LABELS),
            "labels": LABELS, "confusion_matrix": matrix, "per_class": per_class}


def train() -> dict:
    texts, labels = load_split("train")
    model = fit(texts, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {"model": "Synthetic Document Workflow Classifier", "version": "1.0.0", "algorithm": "TF-IDF + multinomial Logistic Regression (full-batch gradient descent)",
              "training_samples": len(labels), "validation": evaluate(model, "validation"), "test": evaluate(model, "test")}
    (ROOT / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    train()
