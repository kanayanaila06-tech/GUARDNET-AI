"""GuardNet-AI text model inference service."""

from pathlib import Path
import re
import joblib


# ============================================================
# PATH
# ============================================================

BASE = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE / "ml_models"

VECTOR_PATH = MODEL_DIR / "judol_text_vectorizer.joblib"
MODEL_PATH = MODEL_DIR / "judol_text_model.joblib"


_VECTOR = None
_MODEL = None


# ============================================================
# LOAD MODEL
# ============================================================

def _load():
    global _VECTOR, _MODEL

    if _VECTOR is not None and _MODEL is not None:
        return

    if not MODEL_DIR.exists():
        raise FileNotFoundError(
            f"Folder model tidak ditemukan: {MODEL_DIR}"
        )

    if not VECTOR_PATH.exists():
        raise FileNotFoundError(
            f"Vectorizer tidak ditemukan: {VECTOR_PATH}"
        )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model tidak ditemukan: {MODEL_PATH}"
        )

    print("[GuardNet-AI] Loading text vectorizer...")
    _VECTOR = joblib.load(VECTOR_PATH)

    print("[GuardNet-AI] Loading text model...")
    _MODEL = joblib.load(MODEL_PATH)

    print("[GuardNet-AI] Text model berhasil dimuat.")


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    text = str(text or "").lower()

    # Gabungkan whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# TEXT PREDICTION
# ============================================================

def predict_judol_text(text: str) -> dict:

    text = normalize_text(text)

    # Tidak ada teks
    if not text:
        return {
            "available": True,
            "probability": 0.0,
            "label": 0,
            "risk": "LOW",
            "model": "youtube_chat_jogja_tfidf_logreg",
        }

    # Load model
    _load()

    # Transform text menggunakan vectorizer
    x = _VECTOR.transform([text])

    # Probabilitas kelas 1
    probability = float(
        _MODEL.predict_proba(x)[0][1]
    )

    # Label
    label = int(probability >= 0.50)

    # TEXT evidence saja
    if probability >= 0.80:
        risk = "HIGH"
    elif probability >= 0.45:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "available": True,
        "probability": round(probability, 6),
        "label": label,
        "risk": risk,
        "model": "youtube_chat_jogja_tfidf_logreg",
    }


# ============================================================
# TEST MANUAL
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("GUARDNET-AI TEXT MODEL TEST")
    print("=" * 60)

    test_texts = [
        "halo selamat malam",
        "bonus besar daftar sekarang",
        "main slot gacor maxwin",
    ]

    for text in test_texts:

        try:
            result = predict_judol_text(text)

            print()
            print("TEXT :", text)
            print("RESULT :", result)

        except Exception as e:

            print()
            print("TEXT :", text)
            print("ERROR :", repr(e))