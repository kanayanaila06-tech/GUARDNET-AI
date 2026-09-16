
# ============================================================
# GUARDNET-AI
# VISUAL ANALYZER
# CLIP ZERO-SHOT GAMBLING DETECTION
# FINAL VERSION
# ============================================================
 
import io
import math
from typing import Any, Dict, List
 
from PIL import Image, ImageOps
 
try:
    import torch
except ImportError:
    torch = None
 
try:
    from transformers import CLIPProcessor, CLIPModel
except ImportError:
    CLIPProcessor = None
    CLIPModel = None
 
 
# ============================================================
# CONFIGURATION
# ============================================================
 
MODEL_NAME = "openai/clip-vit-base-patch32"
 
_model = None
_processor = None
_model_loaded = False
 
 
# ============================================================
# GAMBLING PROMPTS
# ============================================================
 
GAMBLING_PROMPTS = [
    "an online gambling game",
    "an online slot machine game",
    "a digital slot machine with spinning reels",
    "a slot gambling game with reels and symbols",
    "an online casino game",
    "a gambling game showing jackpot and winning symbols",
    "an online betting interface",
    "an online gambling website",
    "a mobile phone showing an online gambling game",
    "a gambling advertisement",
    "a person playing an online gambling game",
    "a casino gambling interface with virtual money",
]
 
 
# ============================================================
# SLOT-SPECIFIC PROMPTS
# ============================================================
 
SLOT_PROMPTS = [
    "a screenshot of an online slot machine game with reels",
    "a mobile phone showing a slot game with spinning reels and symbols",
    "a digital slot game showing reels, coins, wins and bonus features",
    "an online casino slot interface with reels and winning symbols",
    "a slot game interface showing a win amount and free spins",
    "a gambling slot machine interface with colorful reels and coins",
]
 
SLOT_INDICATORS = [
    "visual:slot_machine",
    "visual:slot_game",
    "visual:slot_reels",
    "visual:casino_slot",
    "visual:win_free_spin",
    "visual:gambling_slot_interface",
]
 
 
# ============================================================
# NORMAL PROMPTS
# ============================================================
 
NORMAL_PROMPTS = [
    "a normal photograph",
    "a normal social media photograph",
    "a normal lifestyle photograph",
    "a normal room or interior photograph",
    "a normal photograph of a person",
    "a normal food or product photograph",
    "a normal entertainment photograph",
    "a normal video game that is not gambling",
    "a normal mobile application that is not gambling",
    "a normal website that is not related to gambling",
    "a normal photograph of objects and scenery",
    "a normal educational or informational image",
]
 
 
# ============================================================
# INDICATORS
# ============================================================
 
PROMPT_INDICATORS = [
    "visual:online_gambling",
    "visual:slot_machine",
    "visual:slot_game",
    "visual:online_casino",
    "visual:gambling_game",
    "visual:jackpot_game",
    "visual:betting",
    "visual:gambling_website",
    "visual:gambling_mobile",
    "visual:gambling_advertisement",
    "visual:gambling_activity",
    "visual:gambling_content",
]
 
 
# ============================================================
# LOAD MODEL
# ============================================================
 
def load_visual_model() -> bool:
 
    global _model
    global _processor
    global _model_loaded
 
    if _model_loaded:
        return True
 
    if torch is None:
 
        print(
            "GUARDNET-AI VISUAL ERROR: "
            "PyTorch belum terinstall."
        )
 
        return False
 
    if CLIPModel is None or CLIPProcessor is None:
 
        print(
            "GUARDNET-AI VISUAL ERROR: "
            "Transformers belum terinstall."
        )
 
        return False
 
    try:
 
        print(
            "GUARDNET-AI VISUAL: "
            "Memuat model CLIP..."
        )
 
        _processor = CLIPProcessor.from_pretrained(
            MODEL_NAME
        )
 
        _model = CLIPModel.from_pretrained(
            MODEL_NAME
        )
 
        _model.eval()
 
        _model_loaded = True
 
        print(
            "GUARDNET-AI VISUAL: "
            "Model CLIP berhasil dimuat."
        )
 
        return True
 
    except Exception as error:
 
        print(
            "GUARDNET-AI VISUAL ERROR "
            "saat loading model:",
            error
        )
 
        _model = None
        _processor = None
        _model_loaded = False
 
        return False
 
 
# ============================================================
# LOAD IMAGE
# ============================================================
 
def load_image(
    image_bytes: bytes
) -> Image.Image:
 
    if not image_bytes:
 
        raise ValueError(
            "Data gambar kosong."
        )
 
    image = Image.open(
        io.BytesIO(image_bytes)
    )
 
    image = ImageOps.exif_transpose(
        image
    )
 
    if image.mode != "RGB":
 
        image = image.convert(
            "RGB"
        )
 
    return image
 
 
# ============================================================
# IMAGE QUALITY
# ============================================================
 
def calculate_image_quality(
    image: Image.Image
) -> float:
 
    width, height = image.size
 
    if width <= 0 or height <= 0:
        return 0.0
 
    area = width * height
 
    if area >= 1280 * 720:
        return 1.0
 
    if area >= 640 * 480:
        return 0.85
 
    if area >= 320 * 240:
        return 0.65
 
    return 0.45
 
 
# ============================================================
# SAFE FEATURE EXTRACTION
# ============================================================
 
def extract_pooler_tensor(
    output: Any,
    name: str
) -> Any:
 
    """
    Mengambil tensor dari output CLIP.
 
    Kompatibel dengan:
    - BaseModelOutputWithPooling
    - tuple
    - tensor langsung
    """
 
    # --------------------------------------------------------
    # LANGSUNG TENSOR
    # --------------------------------------------------------
 
    if torch.is_tensor(output):
 
        return output
 
 
    # --------------------------------------------------------
    # BaseModelOutputWithPooling
    # --------------------------------------------------------
 
    pooler_output = getattr(
        output,
        "pooler_output",
        None
    )
 
    if pooler_output is not None:
 
        if torch.is_tensor(
            pooler_output
        ):
 
            return pooler_output
 
 
    # --------------------------------------------------------
    # TUPLE / LIST
    # --------------------------------------------------------
 
    if isinstance(
        output,
        (tuple, list)
    ):
 
        for item in output:
 
            if torch.is_tensor(item):
 
                # Biasanya tensor pertama/yang sesuai
                # adalah hidden state atau pooled output.
 
                if item.ndim == 2:
 
                    return item
 
        # fallback
        for item in output:
 
            if torch.is_tensor(item):
 
                return item
 
 
    raise TypeError(
        f"Feature CLIP {name} bukan tensor. "
        f"Tipe yang diterima: {type(output)}"
    )
 
 
# ============================================================
# CALCULATE PROMPT SCORES
# ============================================================
 
def calculate_prompt_scores(
    image: Image.Image,
    prompts: List[str]
) -> List[float]:
 
    if not load_visual_model():
 
        raise RuntimeError(
            "Model CLIP tidak tersedia."
        )
 
    # ========================================================
    # IMAGE INPUT
    # ========================================================
 
    image_inputs = _processor(
        images=image,
        return_tensors="pt"
    )
 
    # ========================================================
    # TEXT INPUT
    # ========================================================
 
    text_inputs = _processor(
        text=prompts,
        return_tensors="pt",
        padding=True
    )
 
    # ========================================================
    # IMAGE FEATURES
    # ========================================================
 
    with torch.no_grad():
 
        vision_output = _model.vision_model(
            pixel_values=image_inputs[
                "pixel_values"
            ]
        )
 
    image_features = extract_pooler_tensor(
        vision_output,
        "IMAGE"
    )
 
    # --------------------------------------------------------
    # PROJECT IMAGE
    # --------------------------------------------------------
 
    image_features = _model.visual_projection(
        image_features
    )
 
    # ========================================================
    # TEXT FEATURES
    # ========================================================
 
    with torch.no_grad():
 
        text_output = _model.text_model(
            input_ids=text_inputs[
                "input_ids"
            ],
            attention_mask=text_inputs[
                "attention_mask"
            ]
        )
 
    text_features = extract_pooler_tensor(
        text_output,
        "TEXT"
    )
 
    # --------------------------------------------------------
    # PROJECT TEXT
    # --------------------------------------------------------
 
    text_features = _model.text_projection(
        text_features
    )
 
    # ========================================================
    # NORMALIZATION
    # ========================================================
 
    image_norm = image_features.norm(
        dim=-1,
        keepdim=True
    )
 
    text_norm = text_features.norm(
        dim=-1,
        keepdim=True
    )
 
    image_norm = torch.clamp(
        image_norm,
        min=1e-8
    )
 
    text_norm = torch.clamp(
        text_norm,
        min=1e-8
    )
 
    image_features = (
        image_features
        / image_norm
    )
 
    text_features = (
        text_features
        / text_norm
    )
 
    # ========================================================
    # COSINE SIMILARITY
    # ========================================================
 
    similarity = (
        image_features
        @ text_features.T
    )
 
    return [
        float(value)
        for value in similarity[0]
    ]
 
 
# ============================================================
# MULTI-VIEW PROMPT SCORING
# ============================================================
 
def make_image_views(image: Image.Image) -> List[Image.Image]:
    """Full image plus central crops for UI/game screenshots."""
    views = [image]
    width, height = image.size
 
    for crop_w_ratio, crop_h_ratio in ((0.80, 0.80), (0.68, 0.94)):
        crop_w = max(int(width * crop_w_ratio), 1)
        crop_h = max(int(height * crop_h_ratio), 1)
        left = max((width - crop_w) // 2, 0)
        top = max((height - crop_h) // 2, 0)
        right = min(left + crop_w, width)
        bottom = min(top + crop_h, height)
        views.append(image.crop((left, top, right, bottom)))
 
    return views
 
 
def calculate_multiview_prompt_scores(
    image: Image.Image,
    prompts: List[str]
) -> List[float]:
    """Score each prompt on several views and keep the strongest view."""
    views = make_image_views(image)
    view_scores = []
 
    for view_index, view in enumerate(views, start=1):
        scores = calculate_prompt_scores(view, prompts)
        view_scores.append(scores)
        print(f"Visual view {view_index}: berhasil dianalisis.")
 
    return [
        max(scores[index] for scores in view_scores)
        for index in range(len(prompts))
    ]
 
 
def score_visual_risk(
    gambling_scores: List[float],
    slot_scores: List[float],
    normal_scores: List[float],
) -> Dict[str, Any]:
    """Ensemble scoring untuk gambling umum dan slot secara spesifik."""
    gambling_max = max(gambling_scores) if gambling_scores else 0.0
    slot_max = max(slot_scores) if slot_scores else 0.0
    normal_max = max(normal_scores) if normal_scores else 0.0
 
    gambling_top = sorted(gambling_scores, reverse=True)[:3]
    slot_top = sorted(slot_scores, reverse=True)[:3]
 
    gambling_avg = sum(gambling_top) / len(gambling_top) if gambling_top else 0.0
    slot_avg = sum(slot_top) / len(slot_top) if slot_top else 0.0
 
    gambling_margin = gambling_max - normal_max
    slot_margin = slot_max - normal_max
 
    ensemble_signal = max(
        gambling_avg,
        slot_avg,
        gambling_max * 0.40 + slot_max * 0.60
    )
 
    # HIGH: sinyal slot/gambling sangat kuat.
    if (slot_max >= 0.25 and slot_margin >= -0.005) or (
        gambling_max >= 0.27 and gambling_margin >= 0.005
    ):
        score = 0.90
        risk = "high"
 
    # MEDIUM: sinyal spesifik slot cukup kuat walaupun normal sedikit lebih tinggi.
    elif (slot_max >= 0.21 and slot_margin >= -0.035) or (
        gambling_max >= 0.22 and gambling_margin >= -0.015
    ):
        score = 0.65
        risk = "medium"
 
    elif slot_max >= 0.19 and slot_margin >= -0.055:
        score = 0.50
        risk = "medium"
 
    else:
        score = 0.0
        risk = "low"
 
    return {
        "risk_level": risk,
        "score": score,
        "gambling_max": gambling_max,
        "slot_max": slot_max,
        "normal_max": normal_max,
        "gambling_avg": gambling_avg,
        "slot_avg": slot_avg,
        "gambling_margin": gambling_margin,
        "slot_margin": slot_margin,
        "ensemble_signal": ensemble_signal,
    }
 
 
# ============================================================
# SIGMOID
# ============================================================
 
def sigmoid(
    value: float
) -> float:
 
    try:
 
        return 1.0 / (
            1.0 +
            math.exp(-value)
        )
 
    except OverflowError:
 
        if value > 0:
            return 1.0
 
        return 0.0
 
 
# ============================================================
# ANALYZE VISUAL
# ============================================================
 
def analyze_visual(
    image_bytes: bytes
) -> Dict[str, Any]:
 
    # ========================================================
    # LOAD IMAGE
    # ========================================================
 
    try:
 
        image = load_image(
            image_bytes
        )
 
    except Exception as error:
 
        return {
 
            "status": "error",
 
            "risk_level": "low",
 
            "score": 0.0,
 
            "detected_indicators": [],
 
            "description":
                "Gambar tidak dapat diproses.",
 
            "evidence": {
                "error": str(error)
            },
 
        }
 
 
    # ========================================================
    # IMAGE INFORMATION
    # ========================================================
 
    width, height = image.size
 
    quality = calculate_image_quality(
        image
    )
 
 
    print()
    print("=" * 60)
    print("GUARDNET-AI VISUAL ANALYSIS")
    print("=" * 60)
 
    print(
        "IMAGE SIZE:",
        width,
        "x",
        height
    )
 
    print(
        "IMAGE QUALITY:",
        round(
            quality,
            3
        )
    )
 
 
    # ========================================================
    # LOAD MODEL
    # ========================================================
 
    if not load_visual_model():
 
        return {
 
            "status": "error",
 
            "risk_level": "low",
 
            "score": 0.0,
 
            "detected_indicators": [],
 
            "description":
                "Visual analyzer tidak dapat dijalankan "
                "karena model CLIP tidak tersedia.",
 
            "evidence": {
 
                "model":
                    MODEL_NAME,
 
                "model_loaded":
                    False,
 
            },
 
        }
 
 
    # ========================================================
    # CALCULATE SCORES
    # ========================================================
 
    try:
        gambling_scores = calculate_multiview_prompt_scores(
            image, GAMBLING_PROMPTS
        )
 
        slot_scores = calculate_multiview_prompt_scores(
            image, SLOT_PROMPTS
        )
 
        normal_scores = calculate_multiview_prompt_scores(
            image, NORMAL_PROMPTS
        )
 
    except Exception as error:
        print(
            "GUARDNET-AI VISUAL ERROR:",
            error
        )
 
        return {
            "status": "error",
            "risk_level": "low",
            "score": 0.0,
            "detected_indicators": [],
            "description":
                "Terjadi kesalahan saat menganalisis visual gambar.",
            "evidence": {"error": str(error)},
        }
 
    scoring = score_visual_risk(
        gambling_scores,
        slot_scores,
        normal_scores
    )
 
    max_gambling_score = scoring["gambling_max"]
    max_slot_score = scoring["slot_max"]
    max_normal_score = scoring["normal_max"]
    average_top_gambling = scoring["gambling_avg"]
    average_top_slot = scoring["slot_avg"]
    average_top_normal = (
        sum(sorted(normal_scores, reverse=True)[:3])
        / len(sorted(normal_scores, reverse=True)[:3])
        if normal_scores else 0.0
    )
    max_margin = scoring["gambling_margin"]
    slot_margin = scoring["slot_margin"]
    average_margin = average_top_gambling - average_top_normal
 
    probability_input = max(average_margin, slot_margin) * 35.0
    gambling_probability = sigmoid(probability_input)
    normal_probability = 1.0 - gambling_probability
    probability_margin = gambling_probability - normal_probability
 
    score = scoring["score"]
    risk_level = scoring["risk_level"]
 
    # ========================================================
    # IMAGE QUALITY ADJUSTMENT
    # ========================================================
 
    if quality < 0.50:
 
        score = min(
            score,
            0.50
        )
 
 
    # ========================================================
    # RISK LEVEL
    # ========================================================
 
    if score >= 0.75:
        risk_level = "high"
    elif score >= 0.35:
        risk_level = "medium"
    else:
        risk_level = "low"
 
    # ========================================================
    # INDICATORS
    # ========================================================
 
    indicators = []
 
    if risk_level in {"medium", "high"}:
        slot_sorted = sorted(
            enumerate(slot_scores),
            key=lambda item: item[1],
            reverse=True
        )
        gambling_sorted = sorted(
            enumerate(gambling_scores),
            key=lambda item: item[1],
            reverse=True
        )
 
        for index, similarity in slot_sorted:
            if similarity < max_slot_score - 0.025:
                continue
            indicator = SLOT_INDICATORS[index]
            if indicator not in indicators:
                indicators.append(indicator)
            if len(indicators) >= 3:
                break
 
        for index, similarity in gambling_sorted:
            if similarity < max_gambling_score - 0.025:
                continue
            indicator = PROMPT_INDICATORS[index]
            if indicator not in indicators:
                indicators.append(indicator)
            if len(indicators) >= 5:
                break
 
        if not indicators:
            indicators.append("visual:gambling_content")
 
    # ========================================================
    # DESCRIPTION
    # ========================================================
 
    if risk_level == "high":
 
        description = (
            "Analisis visual CLIP menemukan "
            "kemiripan kuat dengan tampilan "
            "permainan atau aktivitas perjudian "
            "online."
        )
 
    elif risk_level == "medium":
 
        description = (
            "Analisis visual menemukan "
            "karakteristik yang menyerupai "
            "permainan atau aktivitas perjudian "
            "online. Hasil dapat diperkuat dengan "
            "OCR, teks, komentar, atau ASR."
        )
 
    else:
 
        description = (
            "Tidak ditemukan perbedaan visual "
            "yang cukup kuat antara kategori "
            "perjudian dan visual normal."
        )
 
 
    # ========================================================
    # TOP PREDICTIONS
    # ========================================================
 
    top_predictions = []
 
    slot_sorted = sorted(
        enumerate(slot_scores),
        key=lambda item: item[1],
        reverse=True
    )
    gambling_sorted = sorted(
        enumerate(gambling_scores),
        key=lambda item: item[1],
        reverse=True
    )
 
    for index, similarity in slot_sorted[:3]:
        top_predictions.append({
            "label": SLOT_PROMPTS[index],
            "score": round(similarity, 4),
            "indicator": SLOT_INDICATORS[index],
            "group": "slot"
        })
 
    for index, similarity in gambling_sorted[:3]:
        top_predictions.append({
            "label": GAMBLING_PROMPTS[index],
            "score": round(similarity, 4),
            "indicator": PROMPT_INDICATORS[index],
            "group": "gambling"
        })
 
    # ========================================================
    # DEBUG TERMINAL
    # ========================================================
 
    print(
        "Max Slot Similarity:",
        round(max_slot_score, 4)
    )
 
    print(
        "Average Slot:",
        round(average_top_slot, 4)
    )
 
    print(
        "Slot Margin:",
        round(slot_margin, 4)
    )
 
    print(
        "Ensemble Signal:",
        round(scoring["ensemble_signal"], 4)
    )
 
    print(
        "Max Gambling Similarity:",
        round(
            max_gambling_score,
            4
        )
    )
 
    print(
        "Max Normal Similarity:",
        round(
            max_normal_score,
            4
        )
    )
 
    print(
        "Average Gambling:",
        round(
            average_top_gambling,
            4
        )
    )
 
    print(
        "Average Normal:",
        round(
            average_top_normal,
            4
        )
    )
 
    print(
        "Max Margin:",
        round(
            max_margin,
            4
        )
    )
 
    print(
        "Average Margin:",
        round(
            average_margin,
            4
        )
    )
 
    print(
        "Gambling Probability:",
        round(
            gambling_probability,
            4
        )
    )
 
    print(
        "Normal Probability:",
        round(
            normal_probability,
            4
        )
    )
 
    print(
        "Probability Margin:",
        round(
            probability_margin,
            4
        )
    )
 
    print(
        "Visual Risk:",
        risk_level
    )
 
    print(
        "Visual Score:",
        score
    )
 
    print(
        "Indicators:",
        indicators
    )
 
    print("=" * 60)
 
 
    # ========================================================
    # FINAL RESULT
    # ========================================================
 
    return {
 
        "status":
            "success",
 
        "risk_level":
            risk_level,
 
        "score":
            round(
                score,
                3
            ),
 
        "detected_indicators":
            indicators,
 
        "description":
            description,
 
        "evidence": {
 
            "model":
                MODEL_NAME,
 
            "model_type":
                "CLIP zero-shot multi-view ensemble",
 
            "image_width":
                width,
 
            "image_height":
                height,
 
            "image_quality":
                round(
                    quality,
                    3
                ),
 
            "max_gambling_similarity":
                round(
                    max_gambling_score,
                    4
                ),
 
            "max_normal_similarity":
                round(
                    max_normal_score,
                    4
                ),
 
            "max_slot_similarity":
                round(
                    max_slot_score,
                    4
                ),
 
            "average_top_slot":
                round(
                    average_top_slot,
                    4
                ),
 
            "slot_margin":
                round(
                    slot_margin,
                    4
                ),
 
            "ensemble_signal":
                round(
                    scoring["ensemble_signal"],
                    4
                ),
 
            "average_top_gambling":
                round(
                    average_top_gambling,
                    4
                ),
 
            "average_top_normal":
                round(
                    average_top_normal,
                    4
                ),
 
            "max_margin":
                round(
                    max_margin,
                    4
                ),
 
            "average_margin":
                round(
                    average_margin,
                    4
                ),
 
            "gambling_probability":
                round(
                    gambling_probability,
                    4
                ),
 
            "normal_probability":
                round(
                    normal_probability,
                    4
                ),
 
            "probability_margin":
                round(
                    probability_margin,
                    4
                ),
 
            "top_predictions":
                top_predictions,
 
        },
 
    }
 
 
# ============================================================
# SIMPLE TEST
# ============================================================
 
if __name__ == "__main__":
 
    import os
 
    print("=" * 60)
    print("GUARDNET-AI VISUAL ANALYZER TEST")
    print("=" * 60)
 
    test_file = os.getenv(
        "GUARDNET_TEST_IMAGE"
    )
 
    if not test_file:
 
        print(
            "Set environment variable "
            "GUARDNET_TEST_IMAGE terlebih dahulu."
        )
 
        print()
        print(
            "Contoh:"
        )
 
        print(
            'export GUARDNET_TEST_IMAGE="D:/foto.jpg"'
        )
 
    elif not os.path.exists(
        test_file
    ):
 
        print(
            "File tidak ditemukan:",
            test_file
        )
 
    else:
 
        with open(
            test_file,
            "rb"
        ) as file:
 
            image_bytes = file.read()
 
        result = analyze_visual(
            image_bytes
        )
 
        print()
        print("=" * 60)
        print("HASIL VISUAL ANALYSIS")
        print("=" * 60)
 
        print(
            "Risk Level:",
            result.get(
                "risk_level"
            )
        )
 
        print(
            "Score:",
            result.get(
                "score"
            )
        )
 
        print(
            "Indicators:",
            result.get(
                "detected_indicators"
            )
        )
 
        print(
            "Description:",
            result.get(
                "description"
            )
        )
 
        print("=" * 60)
