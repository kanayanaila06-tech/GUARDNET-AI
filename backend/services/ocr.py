# ============================================================

# GUARDNET-AI OCR ENGINE

# FINAL - FAST + ROBUST + GAMBLING AWARE

# ============================================================

 

import base64

import io

import os

import re

import shutil

import subprocess

from typing import List

 

import pytesseract

from PIL import (

    Image,

    ImageEnhance,

    ImageFilter,

    ImageOps,

)

 

 

# ============================================================

# CONFIGURATION

# ============================================================

 

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

 

MAX_IMAGE_WIDTH = 1800

MAX_IMAGE_HEIGHT = 1800

 

UPSCALE_FACTOR = 2

 

OCR_TIMEOUT = 20

 

 

# ============================================================

# SET TESSERACT

# ============================================================

 

if os.path.exists(TESSERACT_PATH):

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

else:

    detected_tesseract = shutil.which("tesseract")

 

    if detected_tesseract:

        pytesseract.pytesseract.tesseract_cmd = (

            detected_tesseract

        )

    else:

        print(

            "WARNING: Tesseract tidak ditemukan."

        )

 

 

# ============================================================

# GAMBLING OCR CORRECTION

# ============================================================

 

OCR_CORRECTIONS = {

 

    # --------------------------------------------------------

    # JUDI

    # --------------------------------------------------------

 

    "jvdi": "judi",

    "jud1": "judi",

    "jud!": "judi",

    "judl": "judi",

    "jvdl": "judi",

    "judl": "judi",

    "jud!": "judi",

 

    "jvdi": "judi",

 

    # --------------------------------------------------------

    # SLOT

    # --------------------------------------------------------

 

    "s1ot": "slot",

    "sl0t": "slot",

    "5lot": "slot",

    "5l0t": "slot",

    "s|ot": "slot",

    "s!ot": "slot",

    "siot": "slot",

    "s!ot": "slot",

 

    # --------------------------------------------------------

    # GACOR

    # --------------------------------------------------------

 

    "gac0r": "gacor",

    "gacqr": "gacor",

    "gac6r": "gacor",

    "gaccr": "gacor",

 

    # --------------------------------------------------------

    # BONUS

    # --------------------------------------------------------

 

    "b0nus": "bonus",

    "bonvs": "bonus",

    "bon us": "bonus",

 

    # --------------------------------------------------------

    # JACKPOT

    # --------------------------------------------------------

 

    "jackp0t": "jackpot",

    "jackpqt": "jackpot",

 

    # --------------------------------------------------------

    # MAXWIN

    # --------------------------------------------------------

 

    "maxw1n": "maxwin",

    "maxwln": "maxwin",

    "maxwln": "maxwin",

 

    # --------------------------------------------------------

    # DEPOSIT

    # --------------------------------------------------------

 

    "dep0sit": "deposit",

    "depos1t": "deposit",

 

    # --------------------------------------------------------

    # WITHDRAW

    # --------------------------------------------------------

 

    "withdr4w": "withdraw",

    "withdrqw": "withdraw",

 

    # --------------------------------------------------------

    # RTP

    # --------------------------------------------------------

 

    "r7p": "rtp",

    "rtp": "rtp",

 

    # --------------------------------------------------------

    # LINK

    # --------------------------------------------------------

 

    "l1nk": "link",

    "l!nk": "link",

 

    # --------------------------------------------------------

    # DAFTAR

    # --------------------------------------------------------

 

    "d4ftar": "daftar",

    "daft4r": "daftar",

 

    # --------------------------------------------------------

    # CASINO

    # --------------------------------------------------------

 

    "cas1no": "casino",

    "caslno": "casino",

 

    # --------------------------------------------------------

    # TOGEL

    # --------------------------------------------------------

 

    "t0gel": "togel",

    "toge1": "togel",

 

    # --------------------------------------------------------

    # BETTING

    # --------------------------------------------------------

 

    "bett1ng": "betting",

    "bettlng": "betting",

 

    # --------------------------------------------------------

    # SCATTER

    # --------------------------------------------------------

 

    "sc4tter": "scatter",

    "scat7er": "scatter",

 

    # --------------------------------------------------------

    # PAYOUT

    # --------------------------------------------------------

 

    "pay0ut": "payout",

    "payout": "payout",

 

    # --------------------------------------------------------

    # WINRATE

    # --------------------------------------------------------

 

    "w1nrate": "winrate",

    "wlnrate": "winrate",

}

 

 

# ============================================================

# GAMBLING KEYWORD RECOVERY

# ============================================================

 

GAMBLING_OCR_TERMS = [

    "judi",

    "slot",

    "gacor",

    "casino",

    "togel",

    "betting",

    "jackpot",

    "maxwin",

    "scatter",

    "bonus",

    "deposit",

    "withdraw",

    "rtp",

    "winrate",

    "payout",

    "daftar",

    "login",

    "link",

    "bet",

    "spin",

    "free spin",

    "freegame",

    "kemenangan",

    "menang",

]

 

OCR_CONTEXT_TERMS = [

    "situs",

    "website",

    "klik",

    "akses",

    "promo",

    "promosi",

    "hadiah",

    "klaim",

    "modal",

    "taruhan",

    "saldo",

    "wd",

]

 

 

def normalize_ocr_for_matching(text: str) -> str:

    """

    Membuat bentuk teks yang lebih stabil untuk pencocokan kata,

    tanpa mengubah output OCR asli secara agresif.

    """

    text = normalize_ocr_text(text).lower()

 

    replacements = {

        "|": "i",

        "!": "i",

        "0": "o",

        "1": "i",

        "5": "s",

        "7": "t",

    }

 

    normalized = text

 

    for old, new in replacements.items():

        normalized = normalized.replace(old, new)

 

    normalized = re.sub(

        r"[^a-z0-9\s]",

        " ",

        normalized

    )

 

    normalized = re.sub(

        r"\s+",

        " ",

        normalized

    )

 

    return normalized.strip()

 

 

def recover_gambling_terms(text: str) -> List[str]:

    """

    Mencari istilah perjudian yang masih terbaca sebagian oleh OCR.

    Recovery hanya digunakan sebagai evidence tambahan; tidak

    menggantikan teks OCR asli.

    """

    normalized = normalize_ocr_for_matching(text)

 

    if not normalized:

        return []

 

    found = []

 

    for term in GAMBLING_OCR_TERMS:

        term_normalized = normalize_ocr_for_matching(term)

 

        if (

            term_normalized

            and term_normalized in normalized

        ):

            found.append(term)

 

    return found

 

 

def calculate_ocr_information_score(text: str) -> float:

    """

    Skor kualitas informasi OCR sederhana.

    Dipakai untuk memilih kandidat OCR yang paling berguna,

    bukan sebagai probabilitas judi.

    """

    if not text:

        return 0.0

 

    normalized = normalize_ocr_text(text)

 

    if not normalized:

        return 0.0

 

    alnum_count = sum(

        character.isalnum()

        for character in normalized

    )

 

    total_count = len(normalized)

 

    if total_count == 0:

        return 0.0

 

    alnum_ratio = (

        alnum_count / total_count

    )

 

    words = normalized.split()

 

    word_score = min(

        len(words) / 20.0,

        1.0

    )

 

    gambling_hits = recover_gambling_terms(

        normalized

    )

 

    context_hits = [

        term

        for term in OCR_CONTEXT_TERMS

        if term in normalize_ocr_for_matching(normalized)

    ]

 

    gambling_bonus = min(

        len(gambling_hits) * 0.12,

        0.60

    )

 

    context_bonus = min(

        len(context_hits) * 0.04,

        0.20

    )

 

    return (

        (alnum_ratio * 0.45)

        + (word_score * 0.20)

        + gambling_bonus

        + context_bonus

    )

 

 

def select_best_ocr_candidate(

    candidates: List[str]

) -> str:

    """

    Memilih hasil OCR yang paling informatif.

    Kandidat yang mengandung gambling evidence diberi

    prioritas, tetapi tidak mengarang teks baru.

    """

    cleaned = []

 

    for candidate in candidates:

        candidate = correct_ocr_text(candidate)

 

        if not candidate:

            continue

 

        if candidate not in cleaned:

            cleaned.append(candidate)

 

    if not cleaned:

        return ""

 

    return max(

        cleaned,

        key=calculate_ocr_information_score

    )

 

 

# ============================================================

# NORMALIZE OCR TEXT

# ============================================================

 

def normalize_ocr_text(text: str) -> str:

 

    if not text:

        return ""

 

    text = str(text)

 

    # Normalisasi line break

    text = text.replace("\r", "\n")

 

    # Hilangkan karakter kontrol

    text = re.sub(

        r"[\x00-\x08\x0B\x0C\x0E-\x1F]",

        " ",

        text

    )

 

    # OCR sering menghasilkan spasi berlebihan

    text = re.sub(

        r"[ \t]+",

        " ",

        text

    )

 

    # Rapikan baris kosong

    text = re.sub(

        r"\n{3,}",

        "\n\n",

        text

    )

 

    return text.strip()

 

 

# ============================================================

# APPLY OCR CORRECTION

# ============================================================

 

def correct_ocr_text(text: str) -> str:

 

    if not text:

        return ""

 

    result = text

 

    # --------------------------------------------------------

    # Word-based correction

    # --------------------------------------------------------

 

    words = result.split()

 

    corrected_words = []

 

    for word in words:

 

        clean_word = word.strip()

 

        # Hilangkan punctuation luar

        prefix = ""

        suffix = ""

 

        while (

            clean_word

            and not clean_word[0].isalnum()

        ):

            prefix += clean_word[0]

            clean_word = clean_word[1:]

 

        while (

            clean_word

            and not clean_word[-1].isalnum()

        ):

            suffix = clean_word[-1] + suffix

            clean_word = clean_word[:-1]

 

        lower_word = clean_word.lower()

 

        if lower_word in OCR_CORRECTIONS:

 

            clean_word = OCR_CORRECTIONS[

                lower_word

            ]

 

        corrected_words.append(

            prefix + clean_word + suffix

        )

 

    result = " ".join(corrected_words)

 

    # --------------------------------------------------------

    # Phrase correction

    # --------------------------------------------------------

 

    for wrong, correct in OCR_CORRECTIONS.items():

 

        result = re.sub(

            rf"\b{re.escape(wrong)}\b",

            correct,

            result,

            flags=re.IGNORECASE

        )

 

    return normalize_ocr_text(result)

 

 

# ============================================================

# RESIZE IMAGE

# ============================================================

 

def resize_image(image: Image.Image) -> Image.Image:

 

    width, height = image.size

 

    scale = min(

        MAX_IMAGE_WIDTH / width,

        MAX_IMAGE_HEIGHT / height,

        1.0

    )

 

    if scale < 1.0:

 

        new_width = int(width * scale)

        new_height = int(height * scale)

 

        image = image.resize(

            (new_width, new_height),

            Image.Resampling.LANCZOS

        )

 

    return image

 

 

# ============================================================

# PREPROCESS IMAGE

# ============================================================

 

def preprocess_image(

    image: Image.Image,

    mode: str

) -> Image.Image:

 

    image = image.convert("RGB")

 

    # --------------------------------------------------------

    # Resize

    # --------------------------------------------------------

 

    image = resize_image(image)

 

    # --------------------------------------------------------

    # Upscale

    # --------------------------------------------------------

 

    width, height = image.size

 

    image = image.resize(

        (

            min(width * UPSCALE_FACTOR, 2400),

            min(height * UPSCALE_FACTOR, 2400)

        ),

        Image.Resampling.LANCZOS

    )

 

    # --------------------------------------------------------

    # Grayscale

    # --------------------------------------------------------

 

    gray = ImageOps.grayscale(image)

 

    # --------------------------------------------------------

    # Contrast

    # --------------------------------------------------------

 

    gray = ImageEnhance.Contrast(

        gray

    ).enhance(2.0)

 

    # --------------------------------------------------------

    # Sharpness

    # --------------------------------------------------------

 

    gray = ImageEnhance.Sharpness(

        gray

    ).enhance(2.0)

 

    # --------------------------------------------------------

    # Mode 1 - grayscale

    # --------------------------------------------------------

 

    if mode == "gray":

 

        return gray

 

    # --------------------------------------------------------

    # Mode 2 - threshold

    # --------------------------------------------------------

 

    if mode == "threshold":

 

        threshold = 165

 

        return gray.point(

            lambda pixel:

            255 if pixel > threshold else 0

        )

 

    # --------------------------------------------------------

    # Mode 3 - inverted threshold

    # --------------------------------------------------------

 

    if mode == "threshold_dark":

 

        threshold = 190

 

        return gray.point(

            lambda pixel:

            255 if pixel > threshold else 0

        )

 

    # --------------------------------------------------------

    # Mode 4 - sharpen

    # --------------------------------------------------------

 

    if mode == "sharpen":

 

        return gray.filter(

            ImageFilter.SHARPEN

        )

 

    return gray

 

 

# ============================================================

# OCR SINGLE PASS

# ============================================================

 

def run_tesseract(

    image: Image.Image,

    psm: int

) -> str:

 

    try:

 

        config = (

            f"--oem 3 --psm {psm} "

            "-c preserve_interword_spaces=1"

        )

 

        text = pytesseract.image_to_string(

            image,

            lang="eng",

            config=config,

            timeout=OCR_TIMEOUT

        )

 

        return normalize_ocr_text(text)

 

    except subprocess.TimeoutExpired:

 

        print(

            "GuardNet-AI OCR timeout."

        )

 

        return ""

 

    except Exception as error:

 

        print(

            "GuardNet-AI OCR pass error:",

            error

        )

 

        return ""

 

 

# ============================================================

# EXTRACT TEXT FROM IMAGE

# ============================================================

 

def extract_text_from_image(

    image_bytes: bytes

) -> str:

 

    if not image_bytes:

 

        return ""

 

    try:

 

        image = Image.open(

            io.BytesIO(image_bytes)

        )

 

        image.load()

 

        print(

            "GuardNet-AI OCR image:",

            image.size

        )

 

        # ----------------------------------------------------

        # PASS 1

        # ----------------------------------------------------

 

        gray_image = preprocess_image(

            image,

            "gray"

        )

 

        text_1 = run_tesseract(

            gray_image,

            11

        )

 

        # ----------------------------------------------------

        # PASS 2

        # ----------------------------------------------------

 

        threshold_image = preprocess_image(

            image,

            "threshold"

        )

 

        text_2 = run_tesseract(

            threshold_image,

            6

        )

 

        # ----------------------------------------------------

        # PASS 3

        # ----------------------------------------------------

 

        sharpen_image = preprocess_image(

            image,

            "sharpen"

        )

 

        text_3 = run_tesseract(

            sharpen_image,

            11

        )

 

        # ----------------------------------------------------

        # PASS 4

        # Untuk tulisan poster / overlay

        # ----------------------------------------------------

 

        threshold_dark = preprocess_image(

            image,

            "threshold_dark"

        )

 

        text_4 = run_tesseract(

            threshold_dark,

            12

        )

 

        # ----------------------------------------------------

        # Gabungkan

        # ----------------------------------------------------

 

        candidates = [

            text_1,

            text_2,

            text_3,

            text_4

        ]

 

        candidates = [

            normalize_ocr_text(text)

            for text in candidates

            if text

        ]

 

        if not candidates:

 

            return ""

 

        # ----------------------------------------------------

        # Pilih kandidat paling informatif

        # ----------------------------------------------------

 

        best_candidate = select_best_ocr_candidate(

            candidates

        )

 

        # ----------------------------------------------------

        # Tambahkan evidence gambling yang benar-benar

        # ditemukan dari hasil OCR yang ada.

        # Tidak mengarang teks OCR baru.

        # ----------------------------------------------------

 

        gambling_terms = recover_gambling_terms(

            best_candidate

        )

 

        context_terms = [

            term

            for term in OCR_CONTEXT_TERMS

            if term in normalize_ocr_for_matching(

                best_candidate

            )

        ]

 

        print(

            "GuardNet-AI OCR best candidate:",

            best_candidate

        )

 

        print(

            "GuardNet-AI OCR gambling terms:",

            gambling_terms

        )

 

        print(

            "GuardNet-AI OCR context terms:",

            context_terms

        )

 

        return best_candidate.strip()

 

    except Exception as error:

 

        print(

            "GuardNet-AI OCR image error:",

            error

        )

 

        return ""

 

 

# ============================================================

# BASE64 OCR

# ============================================================

 

def extract_text_from_base64(

    image_base64: str

) -> str:

 

    if not image_base64:

 

        return ""

 

    try:

 

        # ----------------------------------------------------

        # Hapus data URI jika ada

        # ----------------------------------------------------

 

        if "," in image_base64:

 

            prefix, data = (

                image_base64.split(

                    ",",

                    1

                )

            )

 

            if "base64" in prefix.lower():

 

                image_base64 = data

 

        # ----------------------------------------------------

        # Decode

        # ----------------------------------------------------

 

        image_bytes = base64.b64decode(

            image_base64,

            validate=False

        )

 

        if not image_bytes:

 

            return ""

 

        # ----------------------------------------------------

        # OCR

        # ----------------------------------------------------

 

        text = extract_text_from_image(

            image_bytes

        )

 

        return (

            text or ""

        ).strip()

 

    except Exception as error:

 

        print(

            "GuardNet-AI Base64 OCR error:",

            error

        )

 

        return ""

 

 

# ============================================================

# ALIAS

# ============================================================

 

def ocr_image(

    image_bytes: bytes

) -> dict:

 

    text = extract_text_from_image(

        image_bytes

    )

 

    return {

        "success": True,

        "ocr_text": text

    }

 

 

# ============================================================

# TEST

# ============================================================

 

if __name__ == "__main__":

 

    print(

        "GuardNet-AI OCR Engine siap."

    )

 

    print(

        "Tesseract:",

        pytesseract.pytesseract.tesseract_cmd

    )