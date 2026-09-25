"""
GuardNet-AI - Train Text Classifier
Dataset: youtube_chat_jogja_clean.csv

Purpose:
Train the TEXT component only. The resulting probability is an evidence
signal for GuardNet-AI multimodal fusion; it is not itself LOW/MEDIUM/HIGH.
"""

from pathlib import Path
import json
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

BASE = Path(__file__).resolve().parent
DATASET = BASE / "dataset" / "youtube_chat_jogja_clean.csv"
MODEL_DIR = BASE / "ml_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATASET)

required = {"message", "cleaned_message", "label"}
missing = required - set(df.columns)
if missing:
    raise ValueError(f"Kolom dataset kurang: {sorted(missing)}")

# Prefer cleaned_message; fall back to original message.
texts = (
    df["cleaned_message"]
    .fillna(df["message"])
    .fillna("")
    .astype(str)
    .str.strip()
)
mask = texts.ne("")
X = texts[mask]
y = df.loc[mask, "label"].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

vectorizer = FeatureUnion([
    ("word", TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.98,
        sublinear_tf=True,
        max_features=80000,
    )),
    ("char", TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=2,
        sublinear_tf=True,
        max_features=100000,
    )),
])

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

model = LogisticRegression(
    max_iter=1000,
    class_weight="balanced",
    solver="liblinear",
    random_state=42,
)
model.fit(X_train_vec, y_train)

pred = model.predict(X_test_vec)

accuracy = accuracy_score(y_test, pred)
report = classification_report(y_test, pred, digits=4)
matrix = confusion_matrix(y_test, pred)

joblib.dump(
    vectorizer,
    MODEL_DIR / "judol_text_vectorizer.joblib",
    compress=3,
)
joblib.dump(
    model,
    MODEL_DIR / "judol_text_model.joblib",
    compress=3,
)

metadata = {
    "dataset": DATASET.name,
    "rows_total": int(len(df)),
    "rows_used": int(len(X)),
    "label_distribution": {
        str(k): int(v) for k, v in y.value_counts().sort_index().items()
    },
    "model": "LogisticRegression",
    "features": {
        "word_ngram": [1, 2],
        "char_ngram": [3, 5],
    },
    "test_size": 0.20,
    "random_state": 42,
    "accuracy": float(accuracy),
    "note": (
        "In-domain evaluation on the YouTube dataset. "
        "Do not interpret this as Instagram accuracy."
    ),
}

(MODEL_DIR / "metadata.json").write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("\n=== GUARDNET-AI TEXT MODEL ===")
print(f"Dataset       : {DATASET}")
print(f"Rows used     : {len(X)}")
print(f"Accuracy      : {accuracy:.4f}")
print("\nClassification report:")
print(report)
print("Confusion matrix:")
print(matrix)
print("\nModel tersimpan di:")
print(MODEL_DIR / "judol_text_vectorizer.joblib")
print(MODEL_DIR / "judol_text_model.joblib")
