# ============================================================
# GUARDNET-AI BACKEND
# ============================================================
# Backend utama GuardNet-AI:
# - Content management
# - Case management
# - Report management
# - Evidence management
# - Dashboard
# - Text analysis
# - OCR
# - ASR
# - Visual analysis
# - Payment detection
# - Full multimodal analysis
# ============================================================

import asyncio
import base64
import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models.case import Case
from models.content import Content
from models.evidence import Evidence
from models.report import Report
from models.payment_detector import PaymentDetection

from services.analyzer import analyze_text
from services.evidence import create_evidence as create_evidence_payload
from services.ocr import extract_text_from_base64
from services.payment import detect_payment, verify_payment
from services.visual import analyze_visual


# ============================================================
# CONFIGURATION
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/jpg",
    "image/webp",
}


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="GuardNet-AI API",
    description=(
        "Backend API for GuardNet-AI - "
        "Sistem Deteksi Dini Aktivitas Judi Online"
    ),
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

Base.metadata.create_all(bind=engine)


def get_db():
    """
    Membuat dan menutup database session
    untuk setiap request.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def read_image_file(
    file: UploadFile,
) -> bytes:
    """
    Validasi file gambar dan membaca bytes-nya.

    Dipakai oleh:
    - OCR
    - Visual
    - Payment
    - Analyze Full
    """

    if not file:
        raise HTTPException(
            status_code=400,
            detail="File gambar tidak ditemukan.",
        )

    if (
        file.content_type
        and file.content_type not in ALLOWED_IMAGE_TYPES
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Format gambar tidak didukung. "
                "Gunakan JPG, JPEG, PNG, atau WEBP."
            ),
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="File gambar kosong.",
        )

    return image_bytes


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Mengubah nilai menjadi float
    tanpa membuat endpoint error.
    """

    try:
        return float(value or default)

    except (TypeError, ValueError):
        return default


def safe_list(
    value: Any,
) -> List[Any]:
    """
    Memastikan nilai indikator selalu berupa list.
    """

    return (
        value
        if isinstance(value, list)
        else []
    )


def get_analysis_score(
    result: Dict[str, Any],
) -> float:
    """
    Mengambil score dari hasil analyzer
    dengan fallback aman.
    """

    return safe_float(
        result.get(
            "score",
            result.get(
                "total_score",
                0,
            ),
        )
    )


def get_risk_level(
    result: Dict[str, Any],
) -> str:
    """
    Mengambil risk level dan menormalkannya.
    """

    return str(
        result.get(
            "risk_level",
            "low",
        )
    ).lower()


def merge_unique_items(
    *lists: List[Any],
) -> List[Any]:
    """
    Menggabungkan beberapa list
    tanpa duplikasi.
    """

    merged = []

    for items in lists:

        for item in items:

            if item not in merged:
                merged.append(item)

    return merged


def risk_priority(
    risk_level: str,
) -> int:
    """
    Menentukan prioritas level risiko.

    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
    """

    risk = str(
        risk_level or "low"
    ).lower()

    if risk == "high":
        return 3

    if risk == "medium":
        return 2

    return 1


def generate_case_id() -> str:
    """
    Membuat Case ID unik.
    """

    return (
        f"CASE-{uuid.uuid4().hex.upper()}"
    )


def generate_report_id() -> str:
    """
    Membuat Report ID unik.
    """

    return (
        f"REPORT-{uuid.uuid4().hex.upper()}"
    )


def generate_evidence_id() -> str:
    """
    Membuat Evidence ID unik.
    """
    return f"EVD-{uuid.uuid4().hex[:12].upper()}"



def normalize_payment_for_db(
    payment: Dict[str, Any],
    payment_result: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Normalisasi satu kandidat payment dari detector.

    Mendukung:
    - Bank / e-wallet
    - QR / QRIS
    - NMID
    - Acquirer
    - Merchant information
    - CRC
    - Technical status
    - Authenticity status
    """

    payment = payment or {}
    payment_result = payment_result or {}

    payment_type = str(
        payment.get("payment_type")
        or payment.get("type")
        or "unknown"
    ).lower()

    # ---------------------------------------------------------
    # QRIS DATA
    # ---------------------------------------------------------

    qris = payment.get("qris") or {}

    if not isinstance(qris, dict):
        qris = {}

    is_qris = bool(
        qris.get("is_qris")
        or payment.get("payment_type") == "qris"
        or payment.get("qr_detected")
    )

    merchant_name = (
        qris.get("merchant_name")
        or qris.get("merchant")
        or payment.get("merchant_name")
    )

    merchant_city = (
        qris.get("merchant_city")
        or qris.get("city")
        or payment.get("merchant_city")
    )

    nmid = qris.get("nmid")

    acquirer = (
        qris.get("acquirer")
        or payment.get("acquirer")
    )

    acquirer_identifier = (
        qris.get("acquirer_identifier")
        or payment.get("acquirer_identifier")
    )

    merchant_category_code = (
        qris.get("merchant_category")
        or qris.get("merchant_category_code")
    )

    currency = (
        qris.get("transaction_currency")
        or qris.get("currency")
    )

    amount = (
        qris.get("transaction_amount")
        or qris.get("amount")
    )

    # ---------------------------------------------------------
    # CRC
    # ---------------------------------------------------------

    crc = qris.get("crc") or {}

    if not isinstance(crc, dict):
        crc = {}

    crc_valid = crc.get("valid")

    # ---------------------------------------------------------
    # TECHNICAL STATUS
    # ---------------------------------------------------------

    qris_technical_status = (
        qris.get("technical_status")
        or "unverifiable"
    )

    # ---------------------------------------------------------
    # AUTHENTICITY
    #
    # IMPORTANT:
    # technically_valid != merchant ownership verified
    # ---------------------------------------------------------

    if qris_technical_status == "invalid":
        authenticity_status = "suspicious"

        authenticity_reason = (
            "Payload QRIS terdeteksi tetapi validasi "
            "teknis/CRC tidak valid."
        )

    elif qris_technical_status == "technically_valid":
        authenticity_status = "unverified"

        authenticity_reason = (
            "Struktur QRIS dan CRC valid secara teknis, "
            "namun kepemilikan merchant belum diverifikasi "
            "dengan data otoritatif PJP/acquirer."
        )

    else:
        authenticity_status = "unverified"

        authenticity_reason = (
            "QRIS terdeteksi tetapi status teknis belum "
            "dapat diverifikasi sepenuhnya."
        )

    # ---------------------------------------------------------
    # QR PAYLOAD
    # ---------------------------------------------------------

    qr_payload = (
        payment.get("qr_data")
        or qris.get("payload")
        or qris.get("qr_data")
        or qris.get("normalized_data")
        or ""
    )

    # ---------------------------------------------------------
    # PROVIDER
    # ---------------------------------------------------------

    provider = (
        payment.get("provider")
        or acquirer
        or payment_result.get("provider")
    )

    # ---------------------------------------------------------
    # ACCOUNT DATA
    # ---------------------------------------------------------

    account_name = (
        payment.get("account_name")
        or payment.get("name")
    )

    if not account_name and is_qris:
        account_name = merchant_name

    account_number = (
        payment.get("account_number")
        or payment.get("account")
        or payment.get("account_id")
        or payment.get("number")
    )

    phone_number = (
        payment.get("phone_number")
        or payment.get("phone")
    )

    # ---------------------------------------------------------
    # IMAGE HASH
    # ---------------------------------------------------------

    image_hash = (
        payment.get("image_hash")
        or ""
    )

    # ---------------------------------------------------------
    # VERIFICATION STATUS
    # ---------------------------------------------------------

    verification_status = str(
        payment.get("verification_status")
        or "unverified"
    ).lower()

    # ---------------------------------------------------------
    # PAYMENT SCORE
    # ---------------------------------------------------------

    payment_score = payment_result.get(
        "payment_score"
    )

    # ---------------------------------------------------------
    # ROUTING
    #
    # Do NOT claim settlement bank from QRIS payload.
    # ---------------------------------------------------------

    destination_bank = None

    if is_qris:
        routing_note = (
            "QRIS menunjukkan identifier acquirer/PJP "
            f"'{acquirer}'"
            if acquirer
            else
            "QRIS terdeteksi, tetapi acquirer tidak "
            "berhasil diidentifikasi dari payload."
        )

        routing_note += (
            " Data ini bukan bukti rekening settlement "
            "atau bank tujuan akhir."
        )

    else:
        routing_note = None

    return {
        "payment_type": payment_type,

        "provider": provider,

        "acquirer": acquirer,

        "acquirer_identifier": acquirer_identifier,

        "account_name": account_name,

        "account_number": account_number,

        "phone_number": phone_number,

        "qr_detected": bool(
            payment.get("qr_detected")
            or is_qris
        ),

        "qris_detected": is_qris,

        "merchant_name": merchant_name,

        "merchant_city": merchant_city,

        "nmid": nmid,

        "merchant_category_code": merchant_category_code,

        "currency": currency,

        "amount": amount,

        "crc_valid": crc_valid,

        "qris_technical_status": qris_technical_status,

        "authenticity_status": authenticity_status,

        "authenticity_reason": authenticity_reason,

        "destination_bank": destination_bank,

        "routing_note": routing_note,

        "verification_status": verification_status,

        "payment_score": (
            str(payment_score)
            if payment_score is not None
            else None
        ),

        "qr_payload": qr_payload,

        "image_hash": image_hash,
    }

def save_payment_detections(
    db: Session,
    report: Report,
    payment_result: Dict[str, Any],
) -> List[PaymentDetection]:
    """
    Simpan hasil payment detection ke database.

    Data berasal langsung dari payment.py.

    Catatan:
    - detected != verified
    - QRIS technically_valid hanya menunjukkan
      integritas payload/CRC.
    """

    if not report or not payment_result.get(
        "payment_detected"
    ):
        return []

    payments = payment_result.get(
        "payments"
    ) or []

    if not isinstance(payments, list):
        return []

    saved = []

    for raw_payment in payments:

        if not isinstance(raw_payment, dict):
            continue

        # =================================================
        # BASIC PAYMENT
        # =================================================

        payment_type = raw_payment.get(
            "payment_type",
            "unknown",
        )

        provider = raw_payment.get(
            "provider"
        )

        account_name = raw_payment.get(
            "account_name"
        )

        account_number = raw_payment.get(
            "account_number"
        )

        phone_number = raw_payment.get(
            "phone_number"
        )

        qr_detected = bool(
            raw_payment.get(
                "qr_detected",
                payment_result.get(
                    "qr_detected",
                    False,
                ),
            )
        )

        verification_status = raw_payment.get(
            "verification_status",
            payment_result.get(
                "verification_status",
                "unverified",
            ),
        )

        image_hash = raw_payment.get(
            "image_hash",
            payment_result.get(
                "image_hash"
            ),
        )

        # =================================================
        # QRIS
        # =================================================

        qris = raw_payment.get(
            "qris"
        )

        if not isinstance(qris, dict):
            qris = {}

        qris_detected = (
            payment_type == "qris"
            or bool(
                qris.get(
                    "is_qris",
                    False,
                )
            )
        )

        # =================================================
        # QRIS MERCHANT
        # =================================================

        merchant_name = qris.get(
            "merchant_name"
        )

        merchant_city = qris.get(
            "merchant_city"
        )

        merchant_category_code = qris.get(
            "merchant_category"
        )

        currency = qris.get(
            "transaction_currency"
        )

        amount = qris.get(
            "transaction_amount"
        )

        # =================================================
        # QRIS TECHNICAL STATUS
        # =================================================

        technical_status = qris.get(
            "technical_status"
        )

        crc = qris.get(
            "crc"
        )

        if not isinstance(crc, dict):
            crc = {}

        crc_valid = crc.get(
            "valid"
        )

        # =================================================
        # QR PAYLOAD
        # =================================================

        qr_payload = raw_payment.get(
            "qr_data"
        )

        # =================================================
        # DUPLICATE CHECK
        # =================================================

        existing = None

        if image_hash:

            existing = (
                db.query(PaymentDetection)
                .filter(
                    PaymentDetection.report_id
                    == report.report_id,
                    PaymentDetection.image_hash
                    == image_hash,
                )
                .first()
            )

        if existing:

            saved.append(existing)

            continue

        # =================================================
        # CREATE RECORD
        # =================================================

        record = PaymentDetection(

            payment_id=(
                f"PAY-"
                f"{uuid.uuid4().hex[:12].upper()}"
            ),

            report_id=report.report_id,

            # -------------------------------------------------
            # BASIC
            # -------------------------------------------------

            payment_type=payment_type,

            provider=provider,

            account_name=account_name,

            account_number=account_number,

            phone_number=phone_number,

            # -------------------------------------------------
            # QR
            # -------------------------------------------------

            qr_detected=qr_detected,

            qris_detected=qris_detected,

            # -------------------------------------------------
            # QRIS MERCHANT
            # -------------------------------------------------

            merchant_name=merchant_name,

            merchant_city=merchant_city,

            merchant_category_code=(
                merchant_category_code
            ),

            currency=currency,

            amount=(
                str(amount)
                if amount is not None
                else None
            ),

            # -------------------------------------------------
            # QRIS TECHNICAL
            # -------------------------------------------------

            crc_valid=crc_valid,

            qris_technical_status=(
                technical_status
            ),

            # -------------------------------------------------
            # VERIFICATION
            # -------------------------------------------------

            verification_status=(
                verification_status
            ),

            # -------------------------------------------------
            # QR PAYLOAD
            # -------------------------------------------------

            qr_payload=qr_payload,

            # -------------------------------------------------
            # IMAGE HASH
            # -------------------------------------------------

            image_hash=image_hash,
        )

        db.add(record)

        db.flush()

        saved.append(record)

    return saved


def get_or_create_case(
    db: Session,
    content: Content,
    risk_level: str,
    description: str,
):
    """
    Mengambil Case yang sudah ada untuk Content
    atau membuat Case baru.

    Tidak membuat duplikasi Case.

    Jika Case sudah ada dan hasil baru memiliki
    risiko lebih tinggi, Case akan dinaikkan levelnya.
    """

    existing_case = (
        db.query(Case)
        .filter(
            Case.content_id == content.id
        )
        .first()
    )

    if existing_case:

        old_priority = risk_priority(
            existing_case.risk_level
        )

        new_priority = risk_priority(
            risk_level
        )

        # ----------------------------------------------------
        # Naikkan risk jika hasil terbaru lebih tinggi
        # ----------------------------------------------------

        if new_priority > old_priority:

            existing_case.risk_level = (
                risk_level
            )

            existing_case.description = (
                description
            )

        elif (
            new_priority == old_priority
            and description
        ):

            existing_case.description = (
                description
            )

        return existing_case, False

    # --------------------------------------------------------
    # Buat Case baru
    # --------------------------------------------------------

    case = Case(
        case_id=generate_case_id(),
        content_id=content.id,
        status="new",
        risk_level=risk_level,
        description=description,
    )

    db.add(case)
    db.flush()

    return case, True


def get_or_create_report(
    db: Session,
    case: Case,
):
    """
    Mengambil Report yang sudah ada
    atau membuat Report baru.

    Report hanya dibuat untuk:
    - MEDIUM
    - HIGH
    """

    if str(
        case.risk_level or ""
    ).lower() not in {
        "medium",
        "high",
    }:
        return None, False

    existing_report = (
        db.query(Report)
        .filter(
            Report.case_id == case.case_id
        )
        .first()
    )

    if existing_report:

        # ----------------------------------------------------
        # Sinkronisasi risk level
        # ----------------------------------------------------

        existing_report.risk_level = (
            case.risk_level
        )

        existing_report.description = (
            case.description
        )

        return existing_report, False

    # --------------------------------------------------------
    # Buat Report baru
    # --------------------------------------------------------

    report = Report(
        report_id=generate_report_id(),
        case_id=case.case_id,
        report_type="online_gambling",
        status="draft",
        risk_level=case.risk_level or "low",
        description=case.description,
        evidence_hash=None,
    )

    db.add(report)
    db.flush()

    return report, True


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "success",
        "message": "GuardNet-AI Backend is running",
    }


# ============================================================
# DATABASE HEALTH
# ============================================================

@app.get("/health/database")
def database_health():

    try:

        with engine.connect():

            return {
                "status": "healthy",
                "database": "guardnet_db",
                "message": (
                    "Database connection successful"
                ),
            }

    except Exception as error:

        return {
            "status": "error",
            "message": str(error),
        }

# =====================================================
# GUARDNET-AI FINAL MULTIMODAL FUSION
# =====================================================
# ============================================================
# GUARDNET-AI
# FINAL MULTIMODAL RISK FUSION
# ============================================================

def calculate_final_multimodal_risk(
    visual_result: dict,
    text_result: dict,
    ocr_text: str = "",
):
    """
    Final multimodal risk fusion.

    Input:
        visual_result : hasil Visual AI
        text_result   : hasil Text Analyzer
        ocr_text      : teks hasil OCR

    Prinsip:
        1. Kata ambigu tidak langsung dianggap judi.
        2. Gambling keyword + promotion context = HIGH.
        3. Gambling + payment = HIGH.
        4. Visual gambling + promotion = HIGH.
        5. Identifier situs/brand judi + konteks perjudian = HIGH.
        6. Visual saja dapat menjadi MEDIUM/HIGH berdasarkan confidence.
        7. Konten normal tetap LOW.
    """

    # ========================================================
    # SAFETY NORMALIZATION
    # ========================================================

    visual_result = (
        visual_result
        if isinstance(visual_result, dict)
        else {}
    )

    text_result = (
        text_result
        if isinstance(text_result, dict)
        else {}
    )

    # ========================================================
    # HELPER
    # ========================================================

    def safe_score(result):
        try:
            score = float(
                result.get("score", 0) or 0
            )
        except (
            TypeError,
            ValueError,
        ):
            score = 0.0

        return max(
            0.0,
            min(score, 0.99)
        )

    def safe_risk(result):
        risk = str(
            result.get(
                "risk_level",
                "low"
            )
            or "low"
        ).lower().strip()

        if risk not in {
            "low",
            "medium",
            "high",
        }:
            return "low"

        return risk

    def get_indicators(result):
        value = result.get(
            "detected_indicators"
        )

        if not isinstance(value, list):
            value = result.get(
                "indicators",
                []
            )

        if not isinstance(value, list):
            return []

        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    def contains_any(text, words):
        text = str(text or "").lower()

        return any(
            word in text
            for word in words
        )

    # ========================================================
    # MODALITY VALUES
    # ========================================================

    visual_risk = safe_risk(
        visual_result
    )

    text_risk = safe_risk(
        text_result
    )

    visual_score = safe_score(
        visual_result
    )

    text_score = safe_score(
        text_result
    )

    visual_indicators = get_indicators(
        visual_result
    )

    text_indicators = get_indicators(
        text_result
    )

    # ========================================================
    # OCR
    # ========================================================

    ocr_text = str(
        ocr_text or ""
    ).strip()

    ocr_result = {}

    if ocr_text:

        try:

            ocr_result = analyze_text(
                ocr_text
            )

        except Exception as error:

            print(
                "[GuardNet-AI] OCR fusion error:",
                error
            )

            ocr_result = {}

    ocr_risk = safe_risk(
        ocr_result
    )

    ocr_score = safe_score(
        ocr_result
    )

    ocr_indicators = get_indicators(
        ocr_result
    )

    # ========================================================
    # MERGE INDICATORS
    # ========================================================

    combined_indicators = merge_unique_items(
        visual_indicators,
        text_indicators,
        ocr_indicators,
    )

    # ========================================================
    # TEXT YANG DIGUNAKAN UNTUK RULE ENGINE
    # ========================================================

    indicator_text = " ".join(
        combined_indicators
    ).lower()

    analysis_text = " ".join(
        [
            indicator_text,
            ocr_text.lower(),
        ]
    ).strip()

    # ========================================================
    # GAMBLING KEYWORDS
    # ========================================================

    gambling_words = (
        "judi",
        "judol",
        "judi online",
        "online gambling",
        "gambling",
        "slot",
        "slots",
        "casino",
        "kasino",
        "togel",
        "betting",
        "bet",
        "taruhan",
        "gacor",
        "scatter",
        "maxwin",
        "jackpot",
        "rtp",
        "payout",
        "deposit",
        "withdraw",
        "mahjong",
        "roulette",
        "blackjack",
        "pragmatic play",
        "pg soft",
        "pgsoft",
    )

    # ========================================================
    # PROMOTION KEYWORDS
    # ========================================================

    promotion_words = (
        "promo",
        "promosi",
        "bonus",
        "daftar",
        "register",
        "registrasi",
        "link",
        "klik",
        "kunjungi",
        "cari kami",
        "main sekarang",
        "bermain sekarang",
        "join",
        "member",
        "membership",
        "cashback",
        "hadiah",
        "menang",
        "cuan",
        "topup",
        "top up",
        "referral",
    )

    # ========================================================
    # PAYMENT KEYWORDS
    # ========================================================

    payment_words = (
        "qris",
        "rekening",
        "transfer",
        "dana",
        "ovo",
        "gopay",
        "go-pay",
        "shopeepay",
        "e-wallet",
        "ewallet",
        "bank",
        "deposit",
        "withdraw",
    )

    # ========================================================
    # GAMBLING BRAND / SITE PATTERN
    #
    # Tidak menggunakan "ALOHA" saja.
    #
    # Identifier seperti:
    # ALOHA4D
    # XXXXX4D
    # XXXXX777
    # situs dengan domain mencurigakan
    #
    # membutuhkan konteks tambahan.
    # ========================================================

    gambling_brand_patterns = (
        r"\b[a-z0-9_-]{3,}(4d|77|777|88|888|99|999)\b",
    )

    # ========================================================
    # SIGNAL DASAR
    # ========================================================

    gambling_signal = contains_any(
        analysis_text,
        gambling_words
    )

    promotion_signal = contains_any(
        analysis_text,
        promotion_words
    )

    payment_signal = contains_any(
        analysis_text,
        payment_words
    )

    # ========================================================
    # BRAND PATTERN DETECTION
    # ========================================================

    import re

    gambling_brand_matches = []

    for pattern in gambling_brand_patterns:

        matches = re.findall(
            pattern,
            analysis_text,
            flags=re.IGNORECASE
        )

        if matches:
            gambling_brand_matches.extend(
                matches
            )

    # ========================================================
    # IDENTIFIER KHUSUS YANG TERLIHAT JELAS
    # ========================================================

    known_gambling_identifiers = (
        "aloha4d",
    )

    known_identifier_signal = contains_any(
        analysis_text,
        known_gambling_identifiers
    )

    gambling_brand_signal = (
        known_identifier_signal
        or bool(gambling_brand_matches)
    )

    # ========================================================
    # VISUAL INDICATORS
    # ========================================================

    visual_indicator_text = " ".join(
        visual_indicators
    ).lower()

    visual_gambling_count = sum(
        1
        for indicator in visual_indicators
        if contains_any(
            indicator,
            gambling_words
        )
    )

    visual_promotion_count = sum(
        1
        for indicator in visual_indicators
        if contains_any(
            indicator,
            promotion_words
        )
    )

    visual_payment_count = sum(
        1
        for indicator in visual_indicators
        if contains_any(
            indicator,
            payment_words
        )
    )

    # ========================================================
    # VISUAL GAME SIGNAL
    # ========================================================

    visual_game_signal = (
        visual_gambling_count > 0
        or contains_any(
            visual_indicator_text,
            (
                "slot",
                "casino",
                "gambling",
                "judi",
                "gambling game",
                "casino game",
                "slot game",
            )
        )
    )

    # ========================================================
    # BASE FUSION SCORE
    # ========================================================

    fusion_score = max(
        visual_score,
        text_score,
        ocr_score,
    )

    # ========================================================
    # TEXT + OCR CORROBORATION
    # ========================================================

    if (
        text_score > 0
        and ocr_score > 0
    ):

        fusion_score = max(
            fusion_score,
            min(
                0.99,
                max(
                    text_score,
                    ocr_score,
                ) + 0.08
            )
        )

    # ========================================================
    # GAMBLING + PROMOTION
    # ========================================================

    if (
        gambling_signal
        and promotion_signal
    ):

        fusion_score = max(
            fusion_score,
            0.84
        )

    # ========================================================
    # GAMBLING + PAYMENT
    # ========================================================

    if (
        gambling_signal
        and payment_signal
    ):

        fusion_score = max(
            fusion_score,
            0.88
        )

    # ========================================================
    # GAMBLING + PROMOTION + PAYMENT
    # ========================================================

    if (
        gambling_signal
        and promotion_signal
        and payment_signal
    ):

        fusion_score = max(
            fusion_score,
            0.95
        )

    # ========================================================
    # VISUAL GAMBLING
    # ========================================================

    if visual_gambling_count >= 1:

        fusion_score = max(
            fusion_score,
            0.78
        )

    if visual_gambling_count >= 2:

        fusion_score = max(
            fusion_score,
            0.88
        )

    # ========================================================
    # VISUAL GAMBLING + PROMOTION
    # ========================================================

    if (
        visual_gambling_count >= 1
        and (
            visual_promotion_count >= 1
            or promotion_signal
        )
    ):

        fusion_score = max(
            fusion_score,
            0.90
        )

    # ========================================================
    # VISUAL GAMBLING + PAYMENT
    # ========================================================

    if (
        visual_gambling_count >= 1
        and (
            visual_payment_count >= 1
            or payment_signal
        )
    ):

        fusion_score = max(
            fusion_score,
            0.92
        )

    # ========================================================
    # GAMBLING BRAND + CONTEXT
    #
    # Contoh:
    #
    # ALOHA4D + slot
    # ALOHA4D + promo
    # ALOHA4D + daftar
    # ALOHA4D + visual gambling
    #
    # -> HIGH
    #
    # Tetapi:
    #
    # ALOHA
    #
    # -> tidak otomatis HIGH
    # ========================================================

    brand_context_signal = (
        gambling_brand_signal
        and (
            gambling_signal
            or promotion_signal
            or payment_signal
            or visual_game_signal
        )
    )

    if brand_context_signal:

        fusion_score = max(
            fusion_score,
            0.95
        )

        combined_indicators.append(
            "identifier situs/brand yang berkaitan dengan perjudian terdeteksi"
        )

    # ========================================================
    # VISUAL HIGH
    # ========================================================

    if visual_risk == "high":

        fusion_score = max(
            fusion_score,
            0.90
        )

    # ========================================================
    # TEXT / OCR HIGH
    # ========================================================

    if (
        text_risk == "high"
        or ocr_risk == "high"
    ):

        fusion_score = max(
            fusion_score,
            0.90
        )

    # ========================================================
    # FINAL RISK DECISION
    # ========================================================

    if brand_context_signal:

        final_risk = "high"

    elif (
        gambling_signal
        and promotion_signal
    ):

        final_risk = "high"

    elif (
        gambling_signal
        and payment_signal
    ):

        final_risk = "high"

    elif (
        visual_gambling_count >= 1
        and (
            visual_promotion_count >= 1
            or promotion_signal
        )
    ):

        final_risk = "high"

    elif (
        visual_risk == "high"
        or text_risk == "high"
        or ocr_risk == "high"
    ):

        final_risk = "high"

    elif fusion_score >= 0.75:

        final_risk = "high"

    elif (
        visual_risk == "medium"
        or text_risk == "medium"
        or ocr_risk == "medium"
    ):

        final_risk = "medium"

    elif fusion_score >= 0.35:

        final_risk = "medium"

    else:

        final_risk = "low"

    # ========================================================
    # FINAL SCORE
    # ========================================================

    final_score = round(
        min(
            fusion_score,
            0.99
        ),
        3
    )

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    if final_risk == "high":

        if (
            brand_context_signal
            or (
                gambling_signal
                and promotion_signal
            )
            or (
                visual_gambling_count >= 1
                and (
                    visual_promotion_count >= 1
                    or promotion_signal
                )
            )
        ):

            classification = (
                "PROMOSI JUDI ONLINE"
            )

            description = (
                "Ditemukan kombinasi indikator "
                "yang kuat mengarah pada promosi "
                "judi online berdasarkan analisis "
                "teks, OCR, visual, dan konteks konten."
            )

        else:

            classification = (
                "INDIKASI JUDI ONLINE"
            )

            description = (
                "Ditemukan indikator kuat yang "
                "berkaitan dengan aktivitas judi "
                "online berdasarkan analisis multimodal."
            )

    elif final_risk == "medium":

        classification = (
            "INDIKASI MENCURIGAKAN"
        )

        description = (
            "Ditemukan beberapa karakteristik "
            "yang berkaitan dengan perjudian atau "
            "promosi dan memerlukan pemeriksaan lebih lanjut."
        )

    else:

        classification = (
            "TIDAK TERINDIKASI"
        )

        description = (
            "Tidak ditemukan indikator kuat "
            "yang mengarah pada aktivitas atau "
            "promosi judi online."
        )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    combined_indicators = list(
        dict.fromkeys(
            combined_indicators
        )
    )

    # ========================================================
    # DEBUG LOG
    # ========================================================

    print(
        "\n"
        + "=" * 60
    )

    print(
        "GUARDNET-AI FINAL FUSION"
    )

    print(
        "Visual Risk       :",
        visual_risk
    )

    print(
        "Visual Score      :",
        visual_score
    )

    print(
        "Text Risk         :",
        text_risk
    )

    print(
        "Text Score        :",
        text_score
    )

    print(
        "OCR Risk          :",
        ocr_risk
    )

    print(
        "OCR Score         :",
        ocr_score
    )

    print(
        "Gambling Signal   :",
        gambling_signal
    )

    print(
        "Promotion Signal  :",
        promotion_signal
    )

    print(
        "Payment Signal    :",
        payment_signal
    )

    print(
        "Gambling Brand    :",
        gambling_brand_signal
    )

    print(
        "Visual Game       :",
        visual_game_signal
    )

    print(
        "Brand + Context   :",
        brand_context_signal
    )

    print(
        "Final Score       :",
        final_score
    )

    print(
        "Final Risk        :",
        final_risk
    )

    print(
        "Classification    :",
        classification
    )

    print(
        "=" * 60
        + "\n"
    )

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {

        "risk_level":
            final_risk,

        "classification":
            classification,

        "score":
            final_score,

        "indicators":
            combined_indicators,

        "indicator_count":
            len(
                combined_indicators
            ),

        "description":
            description,

        # ----------------------------------------------------
        # VISUAL
        # ----------------------------------------------------

        "visual_risk":
            visual_risk,

        "visual_score":
            visual_score,

        "visual_indicators":
            visual_indicators,

        "visual_indicator_count":
            visual_gambling_count,

        # ----------------------------------------------------
        # TEXT
        # ----------------------------------------------------

        "text_risk":
            text_risk,

        "text_score":
            text_score,

        "text_indicators":
            text_indicators,

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        "ocr_risk":
            ocr_risk,

        "ocr_score":
            ocr_score,

        "ocr_indicators":
            ocr_indicators,

        "ocr_text":
            ocr_text,

        # ----------------------------------------------------
        # EVIDENCE FUSION
        # ----------------------------------------------------

        "evidence_fusion": {

            "gambling_signal":
                gambling_signal,

            "promotion_signal":
                promotion_signal,

            "payment_signal":
                payment_signal,

            "gambling_brand_signal":
                gambling_brand_signal,

            "visual_game_signal":
                visual_game_signal,

            "brand_context_signal":
                brand_context_signal,

            "visual_gambling_count":
                visual_gambling_count,

            "visual_promotion_count":
                visual_promotion_count,

            "visual_payment_count":
                visual_payment_count,
        },
    }

    
# ============================================================
# CONTENT
# ============================================================

@app.post("/contents")
def create_content(
    platform: str,
    content_type: str,
    content_url: str = None,
    detected_text: str = None,
    db: Session = Depends(get_db),
):

    try:

        content = Content(
            platform=platform,
            content_type=content_type,
            content_url=content_url,
            detected_text=detected_text,
        )

        db.add(content)

        db.commit()

        db.refresh(content)

        return {
            "status": "success",
            "message": (
                "Content berhasil disimpan"
            ),
            "content_id": content.id,
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal menyimpan content: "
                f"{error}"
            ),
        )


@app.get("/contents")
def get_contents(
    db: Session = Depends(get_db),
):

    return (
        db.query(Content)
        .order_by(Content.id.desc())
        .all()
    )


# ============================================================
# CASE
# ============================================================

@app.get("/cases")
def get_cases(
    db: Session = Depends(get_db),
):

    return (
        db.query(Case)
        .order_by(Case.id.desc())
        .all()
    )


@app.get("/cases/recent")
def get_recent_cases(
    db: Session = Depends(get_db),
):

    return (
        db.query(Case)
        .order_by(Case.id.desc())
        .limit(20)
        .all()
    )


@app.get("/cases/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
):

    case = (
        db.query(Case)
        .filter(
            Case.case_id == case_id
        )
        .first()
    )

    if not case:

        raise HTTPException(
            status_code=404,
            detail="Case tidak ditemukan.",
        )

    return {
        "status": "success",
        "case": {
            "case_id": case.case_id,
            "content_id": case.content_id,
            "status": case.status,
            "risk_level": case.risk_level,
            "description": case.description,
            "created_at": case.created_at,
        },
    }


@app.post("/cases")
def create_case(
    case_id: str,
    content_id: int = None,
    status: str = "new",
    risk_level: str = None,
    description: str = None,
    db: Session = Depends(get_db),
):

    try:

        # ----------------------------------------------------
        # Cegah Case ID duplikat
        # ----------------------------------------------------

        existing_case = (
            db.query(Case)
            .filter(
                Case.case_id == case_id
            )
            .first()
        )

        if existing_case:

            return {
                "status": "success",
                "message": (
                    "Case sudah tersedia."
                ),
                "case_id": (
                    existing_case.case_id
                ),
                "risk_level": (
                    existing_case.risk_level
                ),
            }

        case = Case(
            case_id=case_id,
            content_id=content_id,
            status=status,
            risk_level=risk_level,
            description=description,
        )

        db.add(case)

        db.commit()

        db.refresh(case)

        return {
            "status": "success",
            "message": (
                "Case berhasil disimpan"
            ),
            "case_id": case.case_id,
            "risk_level": case.risk_level,
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal menyimpan case: "
                f"{error}"
            ),
        )


# ============================================================
# REPORT
# ============================================================

def extract_report_indicators(description):
    """Return indicators already present in a report description.

    /reports must not re-run analysis for every historical report because
    that makes the endpoint increasingly slow as the database grows.
    """
    if not description:
        return []

    match = re.search(
        r"indikator\s+terdeteksi\s*:\s*(.+)$",
        str(description).strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    return [item.strip() for item in match.group(1).split(",") if item.strip()]


@app.get("/reports")
def get_reports(
    db: Session = Depends(get_db),
):
    reports = (
        db.query(Report)
        .order_by(Report.id.desc())
        .all()
    )

    result = []

    for report in reports:
        case = (
            db.query(Case)
            .filter(Case.case_id == report.case_id)
            .first()
        )

        content = None
        if case and case.content_id:
            content = (
                db.query(Content)
                .filter(Content.id == case.content_id)
                .first()
            )

        evidence = None
        if case:
            evidence = (
                db.query(Evidence)
                .filter(Evidence.case_id == case.case_id)
                .order_by(Evidence.id.desc())
                .first()
            )

        payments = (
            db.query(PaymentDetection)
            .filter(
                PaymentDetection.report_id == report.report_id
            )
            .order_by(PaymentDetection.id.asc())
            .all()
        )

        result.append({
            "report_id": report.report_id,
            "case_id": report.case_id,
            "report_type": report.report_type,
            "status": report.status,
            "risk_level": report.risk_level,
            "description": report.description,
            "evidence_hash": report.evidence_hash,
            "evidence_timestamp": report.evidence_timestamp,
            "created_at": report.created_at,
            "updated_at": report.updated_at,

            "site": {
                "platform": content.platform if content else None,
                "content_type": (
                    content.content_type if content else None
                ),
                "content_url": (
                    content.content_url if content else None
                ),
            },

            "indicators": extract_report_indicators(report.description),

            "detected_indicators": extract_report_indicators(report.description),

            "payments": [
                {
                    "payment_id": p.payment_id,
                    "payment_type": p.payment_type,
                    "provider": p.provider,
                    "account_name": p.account_name,
                    "account_number": p.account_number,
                    "phone_number": p.phone_number,
                    "qr_detected": p.qr_detected,
                    "verification_status": p.verification_status,
                    "image_hash": p.image_hash,
                    "created_at": p.created_at,
                }
                for p in payments
            ],

            "evidence": (
                {
                    "evidence_id": evidence.evidence_id,
                    "source_url": evidence.source_url,
                    "image_hash": evidence.image_hash,
                    "ocr_hash": evidence.ocr_hash,
                    "integrity_status": evidence.integrity_status,
                    "detected_at": evidence.detected_at,
                    "created_at": evidence.created_at,
                }
                if evidence else None
            ),
        })

    return result


@app.get("/reports/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
):
    report = (
        db.query(Report)
        .filter(Report.report_id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Laporan tidak ditemukan.",
        )

    case = (
        db.query(Case)
        .filter(Case.case_id == report.case_id)
        .first()
    )

    content = None
    if case and case.content_id:
        content = (
            db.query(Content)
            .filter(Content.id == case.content_id)
            .first()
        )

    evidence = None
    if case:
        evidence = (
            db.query(Evidence)
            .filter(Evidence.case_id == case.case_id)
            .order_by(Evidence.id.desc())
            .first()
        )

    payments = (
        db.query(PaymentDetection)
        .filter(
            PaymentDetection.report_id == report.report_id
        )
        .order_by(PaymentDetection.id.asc())
        .all()
    )

    return {
        "status": "success",
        "report": {
            "report_id": report.report_id,
            "case_id": report.case_id,
            "report_type": report.report_type,
            "status": report.status,
            "risk_level": report.risk_level,
            "description": report.description,
            "evidence_hash": report.evidence_hash,
            "evidence_timestamp": report.evidence_timestamp,
            "created_at": report.created_at,
            "updated_at": report.updated_at,

            "site": {
                "platform": content.platform if content else None,
                "content_type": (
                    content.content_type if content else None
                ),
                "content_url": (
                    content.content_url if content else None
                ),
            },

            "indicators": extract_report_indicators(report.description),

            "detected_indicators": extract_report_indicators(report.description),

            "payments": [
                {
                    "payment_id": p.payment_id,
                    "payment_type": p.payment_type,
                    "provider": p.provider,
                    "account_name": p.account_name,
                    "account_number": p.account_number,
                    "phone_number": p.phone_number,
                    "qr_detected": p.qr_detected,
                    "verification_status": p.verification_status,
                    "image_hash": p.image_hash,
                    "created_at": p.created_at,
                }
                for p in payments
            ],

            "evidence": (
                {
                    "evidence_id": evidence.evidence_id,
                    "source_url": evidence.source_url,
                    "image_hash": evidence.image_hash,
                    "ocr_hash": evidence.ocr_hash,
                    "integrity_status": evidence.integrity_status,
                    "detected_at": evidence.detected_at,
                    "created_at": evidence.created_at,
                }
                if evidence else None
            ),
        },
    }


@app.get("/reports/{report_id}/package")
def generate_report_package(
    report_id: str,
    db: Session = Depends(get_db),
):
    """
    Generate a GuardNet-AI Incident Report Package as a ZIP file.

    The package contains structured report metadata, evidence metadata,
    payment evidence metadata, and an integrity manifest. It does not
    claim external verification by a bank, e-wallet, QRIS provider,
    platform, or government institution.
    """
    report = (
        db.query(Report)
        .filter(Report.report_id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Laporan tidak ditemukan.",
        )

    case = (
        db.query(Case)
        .filter(Case.case_id == report.case_id)
        .first()
    )

    content = None
    if case and case.content_id:
        content = (
            db.query(Content)
            .filter(Content.id == case.content_id)
            .first()
        )

    evidence = None
    if case:
        evidence = (
            db.query(Evidence)
            .filter(Evidence.case_id == case.case_id)
            .order_by(Evidence.id.desc())
            .first()
        )

    payments = (
        db.query(PaymentDetection)
        .filter(PaymentDetection.report_id == report.report_id)
        .order_by(PaymentDetection.id.asc())
        .all()
    )

    package_data = {
        "package_type": "GuardNet-AI Incident Report Package",
        "package_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": {
            "report_id": report.report_id,
            "case_id": report.case_id,
            "report_type": report.report_type,
            "status": report.status,
            "risk_level": report.risk_level,
            "description": report.description,
            "evidence_hash": report.evidence_hash,
            "evidence_timestamp": report.evidence_timestamp,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "site": {
                "platform": content.platform if content else None,
                "content_type": content.content_type if content else None,
                "content_url": content.content_url if content else None,
            },
            "detected_indicators": extract_report_indicators(
                report.description
            ),
        },
        "payment_evidence": [
            {
                "payment_id": p.payment_id,
                "payment_type": p.payment_type,
                "provider": p.provider,
                "account_name": p.account_name,
                "account_number": p.account_number,
                "phone_number": p.phone_number,
                "qr_detected": p.qr_detected,
                "verification_status": p.verification_status,
                "image_hash": p.image_hash,
                "created_at": p.created_at,
            }
            for p in payments
        ],
        "evidence": (
            {
                "evidence_id": evidence.evidence_id,
                "source_url": evidence.source_url,
                "image_hash": evidence.image_hash,
                "ocr_hash": evidence.ocr_hash,
                "integrity_status": evidence.integrity_status,
                "detected_at": evidence.detected_at,
                "created_at": evidence.created_at,
            }
            if evidence else None
        ),
    }

    report_json = json.dumps(
        package_data,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    report_sha256 = hashlib.sha256(
        report_json.encode("utf-8")
    ).hexdigest()

    readme = (
        "GUARDNET-AI INCIDENT REPORT PACKAGE\n"
        "=================================\n\n"
        "Package ini berisi metadata laporan, evidence metadata, "
        "payment evidence metadata, dan fingerprint SHA-256.\n"
        "Package ini merupakan bahan pelaporan digital dan tidak "
        "menyatakan adanya verifikasi eksternal oleh bank, penyedia "
        "e-wallet/QRIS, platform, atau instansi pemerintah.\n"
    )

    manifest = (
        "GuardNet-AI Package Integrity Manifest\n"
        f"Report ID: {report.report_id}\n"
        f"SHA-256 Report.json: {report_sha256}\n"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zf:
        zf.writestr("Report.json", report_json)
        zf.writestr("README.txt", readme)
        zf.writestr("Integrity/SHA256.txt", manifest)

    buffer.seek(0)

    filename = f"GuardNetAI_Report_{report.report_id}.zip"

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


@app.patch("/payment/{payment_id}/verify")
def verify_payment_record(
    payment_id: str,
    verification_status: str,
    db: Session = Depends(get_db),
):
    """
    Validasi manual kandidat payment.
    Status: verified atau rejected.
    """
    status = str(
        verification_status or ""
    ).strip().lower()

    if status not in {"verified", "rejected"}:
        raise HTTPException(
            status_code=400,
            detail=(
                "verification_status harus "
                "'verified' atau 'rejected'."
            ),
        )

    payment = (
        db.query(PaymentDetection)
        .filter(
            PaymentDetection.payment_id == payment_id
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Data payment tidak ditemukan.",
        )

    payment.verification_status = status
    db.commit()
    db.refresh(payment)

    return {
        "status": "success",
        "message": (
            "Payment berhasil divalidasi."
            if status == "verified"
            else "Payment ditandai tidak valid."
        ),
        "payment": {
            "payment_id": payment.payment_id,
            "report_id": payment.report_id,
            "payment_type": payment.payment_type,
            "provider": payment.provider,
            "account_name": payment.account_name,
            "account_number": payment.account_number,
            "phone_number": payment.phone_number,
            "qr_detected": payment.qr_detected,
            "verification_status": payment.verification_status,
            "image_hash": payment.image_hash,
        },
    }


@app.post("/reports")
def create_report(
    case_id: str,
    db: Session = Depends(get_db),
):

    case = (
        db.query(Case)
        .filter(
            Case.case_id == case_id
        )
        .first()
    )

    if not case:

        raise HTTPException(
            status_code=404,
            detail="Case tidak ditemukan.",
        )

    try:

        report, created = (
            get_or_create_report(
                db,
                case,
            )
        )

        db.commit()

        if report:
            db.refresh(report)

        return {
            "status": "success",
            "message": (
                "Laporan berhasil dibuat."
                if created
                else
                "Laporan untuk case ini "
                "sudah tersedia."
            ),
            "report_id": (
                report.report_id
                if report
                else None
            ),
            "case_id": case.case_id,
            "risk_level": (
                case.risk_level
            ),
            "report_status": (
                report.status
                if report
                else "not_created"
            ),
        }

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal membuat laporan: "
                f"{error}"
            ),
        )


# ============================================================
# EVIDENCE
# ============================================================

@app.get("/evidence")
def get_evidence(
    db: Session = Depends(get_db),
):

    try:

        return (
            db.query(Evidence)
            .order_by(Evidence.id.desc())
            .all()
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal mengambil evidence: "
                f"{error}"
            ),
        )


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
):

    try:

        cases = (
            db.query(Case)
            .all()
        )

        total_cases = len(cases)

        high_risk = sum(
            1
            for case in cases
            if str(
                case.risk_level or ""
            ).lower() == "high"
        )

        medium_risk = sum(
            1
            for case in cases
            if str(
                case.risk_level or ""
            ).lower() == "medium"
        )

        low_risk = sum(
            1
            for case in cases
            if str(
                case.risk_level or ""
            ).lower() == "low"
        )

        new_cases = sum(
            1
            for case in cases
            if str(
                case.status or ""
            ).lower() == "new"
        )

        return {
            "status": "success",
            "total_cases": total_cases,
            "risk_summary": {
                "high": high_risk,
                "medium": medium_risk,
                "low": low_risk,
            },
            "status_summary": {
                "new": new_cases,
            },
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal mengambil dashboard: "
                f"{error}"
            ),
        )


# ============================================================
# TEXT ANALYSIS
# ============================================================
#
# ALUR:
#
# Chrome Extension
#       ↓
# /contents
#       ↓
# /analyze
#       ↓
# analyze_text()
#       ↓
# Risk Level
#       ↓
# Content Update
#       ↓
# MEDIUM / HIGH?
#       ↓
# Case
#       ↓
# Report
#
# LOW:
# Content saja
#
# MEDIUM/HIGH:
# Content + Case + Report
#
# Evidence TIDAK dibuat di endpoint ini karena
# Evidence membutuhkan image_hash dan ocr_hash
# yang berasal dari bukti gambar nyata.
# ============================================================

@app.post("/analyze")
def analyze_content(
    content_id: int,
    db: Session = Depends(get_db),
):

    # ========================================================
    # 1. CARI CONTENT
    # ========================================================

    content = (
        db.query(Content)
        .filter(
            Content.id == content_id
        )
        .first()
    )

    if not content:

        raise HTTPException(
            status_code=404,
            detail="Content tidak ditemukan",
        )


    # ========================================================
    # 2. AMBIL TEKS
    # ========================================================

    text_content = (
        content.detected_text or ""
    ).strip()


    if not text_content:

        raise HTTPException(
            status_code=400,
            detail=(
                "Teks content kosong "
                "dan tidak dapat dianalisis."
            ),
        )


    # ========================================================
    # 3. ANALISIS TEXT
    # ========================================================

    try:

        result = analyze_text(
            text_content
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Analisis teks gagal: "
                f"{error}"
            ),
        )


    # ========================================================
    # 4. AMBIL HASIL ANALISIS
    # ========================================================

    risk_level = get_risk_level(
        result
    )

    detected_indicators = safe_list(
        result.get(
            "detected_indicators",
            [],
        )
    )

    description = result.get(
        "description",
        "",
    )

    score = get_analysis_score(
        result
    )


    # ========================================================
    # 5. TENTUKAN STATUS JUDI ONLINE
    # ========================================================

    is_suspected_judol = (
        risk_level
        in {
            "medium",
            "high",
        }
    )


    # ========================================================
    # 6. SIMPAN HASIL KE CONTENT
    # ========================================================

    try:

        content.is_suspected_judol = (
            is_suspected_judol
        )

        content.risk_score = (
            score
        )

        db.flush()


        # ====================================================
        # 7. CASE + REPORT
        # ====================================================

        case = None
        report = None
        case_created = False
        report_created = False


        # ----------------------------------------------------
        # Hanya MEDIUM / HIGH yang masuk Case
        # ----------------------------------------------------

        if risk_level in {
            "medium",
            "high",
        }:

            case, case_created = (
                get_or_create_case(
                    db=db,
                    content=content,
                    risk_level=risk_level,
                    description=description,
                )
            )


            # ------------------------------------------------
            # Buat Report otomatis
            # ------------------------------------------------

            report, report_created = (
                get_or_create_report(
                    db=db,
                    case=case,
                )
            )


        # ====================================================
        # 8. COMMIT
        # ====================================================

        db.commit()

        db.refresh(content)

        if case:
            db.refresh(case)

        if report:
            db.refresh(report)


    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal menyimpan hasil analisis: "
                f"{error}"
            ),
        )


    # ========================================================
    # 9. RESPONSE
    # ========================================================

    return {

        "status": "success",

        "message": (
            "Content berhasil dianalisis"
        ),

        "content_id": content.id,

        "risk_level": risk_level,

        "score": score,

        "is_suspected_judol": (
            is_suspected_judol
        ),

        "detected_indicators": (
            detected_indicators
        ),

        "description": description,

        "case_id": (
            case.case_id
            if case
            else None
        ),

        "case_created": (
            case_created
        ),

        "report_id": (
            report.report_id
            if report
            else None
        ),

        "report_created": (
            report_created
        ),

        "report_status": (
            report.status
            if report
            else "not_created"
        ),

        "evidence_status": (
            "available_in_full_analysis"
            if risk_level in {
                "medium",
                "high",
            }
            else "not_required"
        ),
    }


# ============================================================
# OCR
# ============================================================

@app.post("/ocr")
async def ocr_image(
    file: UploadFile = File(...),
):

    try:

        image_bytes = (
            await read_image_file(file)
        )

        image_base64 = (
            base64.b64encode(
                image_bytes
            ).decode("utf-8")
        )

        print(
            "\n=========================================="
        )
        print("GUARDNET-AI OCR")
        print(
            "=========================================="
        )

        print(
            "Filename:",
            file.filename,
        )

        print(
            "Image Bytes:",
            len(image_bytes),
        )

        print(
            "Memulai OCR..."
        )

        ocr_text = (
            extract_text_from_base64(
                image_base64
            )
        )

        ocr_text = (
            ocr_text or ""
        ).strip()

        print(
            "OCR TEXT:",
            repr(ocr_text),
        )

        print(
            "OCR LENGTH:",
            len(ocr_text),
        )

        print(
            "=========================================="
        )

        return {
            "status": "success",
            "message": (
                "OCR berhasil diproses."
            ),
            "filename": file.filename,
            "ocr_text": ocr_text,
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "GUARDNET-AI OCR ERROR:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"OCR gagal: {error}"
            ),
        )


# ============================================================
# ASR / SPEECH TRANSCRIPTION
# ============================================================

class ASRRequest(BaseModel):
    transcript: str


@app.post("/asr")
def analyze_asr(
    request: ASRRequest,
    db: Session = Depends(get_db),
):

    transcript = (
        request.transcript or ""
    ).strip()


    if not transcript:

        raise HTTPException(
            status_code=400,
            detail=(
                "Transcript tidak boleh kosong."
            ),
        )


    # ========================================================
    # 1. ANALISIS TRANSCRIPT
    # ========================================================

    try:

        result = analyze_text(
            transcript
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Analisis transcript gagal: "
                f"{error}"
            ),
        )


    # ========================================================
    # 2. HASIL ANALISIS
    # ========================================================

    risk_level = get_risk_level(
        result
    )

    detected_indicators = safe_list(
        result.get(
            "detected_indicators",
            [],
        )
    )

    description = result.get(
        "description",
        "",
    )

    score = get_analysis_score(
        result
    )


    # ========================================================
    # 3. SIMPAN CONTENT
    # ========================================================

    try:

        content = Content(
            platform="audio",
            content_type="audio",
            content_url=None,
            detected_text=transcript,
        )

        content.is_suspected_judol = (
            risk_level
            in {
                "medium",
                "high",
            }
        )

        content.risk_score = (
            score
        )

        db.add(content)

        db.flush()


        # ====================================================
        # 4. CASE
        # ====================================================

        case = None
        report = None


        if risk_level in {
            "medium",
            "high",
        }:

            case, _ = (
                get_or_create_case(
                    db=db,
                    content=content,
                    risk_level=risk_level,
                    description=description,
                )
            )


            # =================================================
            # 5. REPORT
            # =================================================

            report, _ = (
                get_or_create_report(
                    db=db,
                    case=case,
                )
            )


        # ====================================================
        # 6. COMMIT
        # ====================================================

        db.commit()

        db.refresh(content)

        if case:
            db.refresh(case)

        if report:
            db.refresh(report)


    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal menyimpan hasil ASR: "
                f"{error}"
            ),
        )


    # ========================================================
    # 7. RESPONSE
    # ========================================================

    return {

        "status": "success",

        "message": (
            "Transcript berhasil dianalisis."
        ),

        "case_id": (
            case.case_id
            if case
            else None
        ),

        "content_id": content.id,

        "report_id": (
            report.report_id
            if report
            else None
        ),

        "transcript": transcript,

        "risk_level": risk_level,

        "score": score,

        "detected_indicators": (
            detected_indicators
        ),

        "description": description,
    }


# ============================================================
# VISUAL ANALYSIS
# ============================================================

@app.post("/visual")
async def visual_analysis(
    file: UploadFile = File(...),
):

    try:

        image_bytes = (
            await read_image_file(file)
        )

        result = analyze_visual(
            image_bytes
        )

        return {

            "status": "success",

            "message": (
                "Visual berhasil dianalisis."
            ),

            "filename": file.filename,

            "risk_level": (
                result.get(
                    "risk_level",
                    "low",
                )
            ),

            "detected_indicators": safe_list(
                result.get(
                    "detected_indicators",
                    [],
                )
            ),

            "description": result.get(
                "description",
                "",
            ),

            "score": safe_float(
                result.get(
                    "score",
                    0,
                )
            ),

            "image_width": result.get(
                "image_width",
                0,
            ),

            "image_height": result.get(
                "image_height",
                0,
            ),

            "quality_warnings": safe_list(
                result.get(
                    "quality_warnings",
                    [],
                )
            ),
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "GUARDNET-AI VISUAL ERROR:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Visual gagal dianalisis: {error}"
            ),
        )


# ============================================================
# PAYMENT DETECTION
# ============================================================

@app.post("/payment/detect")
async def payment_detection(
    file: UploadFile = File(...),
):

    try:

        image_bytes = (
            await read_image_file(file)
        )

        result = detect_payment(
            image_bytes=image_bytes,
            detected_text="",
        )

        print(
            "\n=========================================="
        )

        print(
            "GUARDNET-AI PAYMENT DETECTOR"
        )

        print(
            "=========================================="
        )

        print(
            "Filename:",
            file.filename,
        )

        print(
            "Payment Detected:",
            result.get(
                "payment_detected"
            ),
        )

        print(
            "QR Detected:",
            result.get(
                "qr_detected"
            ),
        )

        print(
            "Payment Type:",
            result.get(
                "payment_type"
            ),
        )

        for payment in result.get(
            "payments",
            [],
        ):

            print(
                "Payment Hash:",
                payment.get(
                    "data_hash"
                ),
            )

        print(
            "=========================================="
        )

        return {

            "status": "success",

            "message": (
                "Payment berhasil dideteksi."
            ),

            "filename": file.filename,

            "payment": result,
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "GUARDNET-AI PAYMENT ERROR:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Payment detection gagal: "
                f"{error}"
            ),
        )


# ============================================================
# FAST REALTIME ANALYSIS
# ============================================================
# Dipakai extension untuk memberi hasil awal dengan cepat.
# Tidak menjalankan OCR, payment, evidence, atau report.
# Hasil ini BUKAN pengganti full analysis.
# ============================================================

@app.post("/analyze-fast")
async def analyze_fast(
    file: UploadFile = File(...),
    platform: str = "instagram",
    content_type: str = "image",
    content_url: str = "",
    detected_text: str = "",
):
    try:
        image_bytes = await read_image_file(file)

        # Visual AI dijalankan di thread agar endpoint async tidak
        # menahan event loop FastAPI lebih lama dari perlu.
        visual_result = await asyncio.to_thread(
            analyze_visual,
            image_bytes,
        )

        visual_risk = str(
            visual_result.get("risk_level", "low")
        ).lower()
        visual_score = safe_float(
            visual_result.get("score", 0)
        )
        visual_indicators = safe_list(
            visual_result.get("detected_indicators", [])
        )

        text = str(detected_text or "").lower()

        # Tambahan istilah yang memang muncul pada dataset/regression,
        # tetapi tetap diproses dengan aturan konservatif.
        gambling_terms = (
            "judi",
            "judol",
            "gambling",
            "casino",
            "kasino",
            "togel",
            "slot",
            "bet",
            "betting",
            "taruhan",
            "parlay",
            "freebet",
            "free bet",
            "maxwin",
            "jackpot",
            "scatter",
            "rtp",
            "gacor",
            "roulette",
            "blackjack",
            "mahjong",
        )

        promotion_terms = (
            "daftar",
            "deposit",
            "bonus",
            "promo",
            "payout",
            "withdraw",
            "link",
            "klik",
            "main sekarang",
            "register",
            "freebet",
            "free bet",
            "hadiah",
            "menang",
            "cuan",
            "cashback",
        )

        gambling_hits = [
            w for w in gambling_terms
            if w in text
        ]
        promotion_hits = [
            w for w in promotion_terms
            if w in text
        ]

        # Visual similarity saja adalah weak evidence.
        # Hanya indikator visual eksplisit yang boleh menjadi
        # bukti visual perjudian.
        visual_explicit_indicators = [
            indicator
            for indicator in visual_indicators
            if "possible_gambling_similarity" not in indicator.lower()
            and "similarity" not in indicator.lower()
        ]

        visual_explicit_text = " ".join(
            visual_explicit_indicators
        ).lower()

        explicit_visual_gambling = any(
            word in visual_explicit_text
            for word in (
                "slot",
                "casino",
                "gambling",
                "judi",
                "togel",
                "roulette",
                "blackjack",
                "mahjong",
                "slot game",
                "casino game",
            )
        )

        has_gambling_text = bool(gambling_hits)
        has_promotion_text = bool(promotion_hits)

        # Kata seperti "gacor" dapat muncul pada konteks non-judi,
        # sehingga tidak digunakan sebagai satu-satunya HIGH evidence.
        strong_gambling_hits = [
            w for w in gambling_hits
            if w in (
                "judi",
                "judol",
                "gambling",
                "casino",
                "kasino",
                "togel",
                "slot",
                "betting",
                "taruhan",
                "parlay",
                "freebet",
                "free bet",
                "maxwin",
                "jackpot",
                "scatter",
                "rtp",
                "roulette",
                "blackjack",
                "mahjong",
            )
        ]

        # FAST RISK DECISION
        # --------------------------------------------------------
        # HIGH: gambling evidence + promotion evidence.
        if (
            strong_gambling_hits
            and has_promotion_text
        ):
            fast_risk = "high"
            fast_score = max(
                visual_score,
                0.80,
            )
            classification = (
                "INDIKASI KUAT PROMOSI JUDI ONLINE"
            )

        # HIGH: explicit visual gambling + promotion evidence.
        elif (
            explicit_visual_gambling
            and has_promotion_text
        ):
            fast_risk = "high"
            fast_score = max(
                visual_score,
                0.80,
            )
            classification = (
                "INDIKASI KUAT PROMOSI JUDI ONLINE"
            )

        # MEDIUM: gambling evidence saja.
        elif has_gambling_text:
            fast_risk = "medium"
            fast_score = max(
                visual_score,
                0.50,
            )
            classification = "INDIKASI MENCURIGAKAN"

        # LOW: visual similarity atau promotion umum saja.
        else:
            fast_risk = "low"
            fast_score = min(
                max(visual_score, 0.0),
                0.34,
            )
            classification = "BELUM TERINDIKASI"

        indicators = merge_unique_items(
            visual_indicators,
            [f"text:{w}" for w in gambling_hits[:5]],
            [f"text:{w}" for w in promotion_hits[:5]],
        )

        if fast_risk == "high":
            description = (
                "Analisis cepat menemukan sinyal kuat yang berkaitan "
                "dengan promosi atau aktivitas judi online."
            )
        elif fast_risk == "medium":
            description = (
                "Analisis cepat menemukan beberapa karakteristik "
                "yang perlu diperiksa lebih lanjut."
            )
        else:
            description = (
                "Analisis cepat belum menemukan indikasi kuat judi online. "
                "Analisis final tetap berjalan di latar belakang."
            )

        return {
            "status": "success",
            "stage": "fast",
            "risk_level": fast_risk,
            "classification": classification,
            "score": round(min(fast_score, 0.99), 3),
            "indicators": indicators,
            "detected_indicators": indicators,
            "description": description,
            "visual_risk": visual_risk,
            "visual_score": visual_score,
            "visual_indicators": visual_indicators,
            "content_url": content_url,
            "platform": platform,
            "content_type": content_type,
        }

    except HTTPException:
        raise
    except Exception as error:
        print("GUARDNET-AI FAST ANALYSIS ERROR:", error)
        raise HTTPException(
            status_code=500,
            detail=f"Fast analysis gagal: {error}",
        )


# FULL MULTIMODAL ANALYSIS
# ============================================================
#
# IMAGE
#   ↓
# VISUAL
#   ↓
# OCR
#   ↓
# TEXT + OCR
#   ↓
# TEXT ANALYSIS
#   ↓
# FINAL RISK
#   ↓
# CONTENT
#   ↓
# CASE
#   ↓
# EVIDENCE
#   ↓
# REPORT (MEDIUM / HIGH)
#
# final_score menggunakan score tertinggi
# dari text dan visual.
# ============================================================

@app.post("/analyze-full")
async def analyze_full(
    file: UploadFile = File(...),
    platform: str = "other",
    content_type: str = "image",
    content_url: str = "",
    detected_text: str = "",
    db: Session = Depends(get_db),
):

    print(
        "\n====================================================="
    )

    print(
        "GUARDNET-AI FULL ANALYSIS"
    )

    print(
        "====================================================="
    )

    try:

        # ====================================================
        # 1. VALIDASI IMAGE
        # ====================================================

        image_bytes = (
            await read_image_file(file)
        )

        print(
            "FILE:",
            file.filename,
        )

        print(
            "IMAGE SIZE:",
            len(image_bytes),
            "bytes",
        )

        print(
            "PLATFORM:",
            platform,
        )

        print(
            "CONTENT TYPE:",
            content_type,
        )

        print(
            "CONTENT URL:",
            content_url,
        )

        print(
            "DETECTED TEXT:",
            repr(detected_text),
        )


        # ====================================================
        # 2. VISUAL ANALYSIS
        # ====================================================

        try:

            visual_result = (
                analyze_visual(
                    image_bytes
                )
            )

        except Exception as error:

            print(
                "VISUAL ANALYSIS ERROR:",
                error,
            )

            visual_result = {

                "risk_level": "low",

                "score": 0,

                "detected_indicators": [],

                "description": (
                    "Visual analysis gagal."
                ),
            }


        visual_risk = get_risk_level(
            visual_result
        )

        visual_score = safe_float(
            visual_result.get(
                "score",
                0,
            )
        )

        visual_indicators = safe_list(
            visual_result.get(
                "detected_indicators",
                [],
            )
        )

        visual_description = (
            visual_result.get(
                "description",
                "",
            )
        )


        print(
            "\n========== VISUAL RESULT =========="
        )

        print(
            "Visual Risk:",
            visual_risk,
        )

        print(
            "Visual Score:",
            visual_score,
        )

        print(
            "Visual Indicators:",
            visual_indicators,
        )


        # ====================================================
        # 3. IMAGE → BASE64
        # ====================================================

        image_base64 = (
            base64.b64encode(
                image_bytes
            ).decode("utf-8")
        )


        # ====================================================
        # 4. OCR
        # ====================================================

        print(
            "\n########################################"
        )

        print(
            "### GUARDNET-AI ANALYZE-FULL OCR DEBUG ###"
        )

        print(
            "########################################"
        )

        print(
            "Filename:",
            file.filename,
        )

        print(
            "Image Size:",
            len(image_bytes),
            "bytes",
        )

        print(
            "Memulai OCR..."
        )


        try:

            ocr_text = (
                extract_text_from_base64(
                    image_base64
                )
            )

        except Exception as error:

            print(
                "OCR ERROR:",
                error,
            )

            ocr_text = ""


        ocr_text = (
            ocr_text or ""
        ).strip()


        print(
            "### HASIL OCR DARI ANALYZE-FULL ###"
        )

        print(
            "OCR TEXT:",
            repr(ocr_text),
        )

        print(
            "OCR LENGTH:",
            len(ocr_text),
        )

        print(
            "########################################"
        )


        # ====================================================
        # 5. PAYMENT DETECTION
        # ====================================================

        print("\n========== PAYMENT DETECTION ==========")

        try:
            payment_result = detect_payment(
                image_bytes=image_bytes,
                detected_text=(
                    f"{detected_text or ''}\n"
                    f"{ocr_text or ''}"
                ).strip(),
            )
        except Exception as error:
            print("PAYMENT DETECTION ERROR:", error)
            payment_result = {
                "payment_detected": False,
                "payment_type": "unknown",
                "qr_detected": False,
                "verification_status": "unverified",
                "image_hash": "",
                "payments": [],
            }

        print("Payment Detected:", payment_result.get("payment_detected", False))
        print("Payment Type:", payment_result.get("payment_type", "unknown"))
        print("Payment Count:", len(payment_result.get("payments", [])))
        print("========================================")


        # ====================================================
        # 6. GABUNGKAN MANUAL TEXT + OCR
        # ====================================================

        manual_text = (
            detected_text or ""
        ).strip()

        text_parts = []

        if manual_text:

            text_parts.append(
                manual_text
            )

        if ocr_text:

            text_parts.append(
                ocr_text
            )

        combined_text = (
            "\n".join(
                text_parts
            ).strip()
        )


        print(
            "\n========== COMBINED TEXT =========="
        )

        print(
            repr(combined_text)
        )

        print(
            "COMBINED TEXT LENGTH:",
            len(combined_text),
        )


        # ====================================================
        # 6. TEXT ANALYSIS
        # ====================================================

        if combined_text:

            try:

                text_result = (
                    analyze_text(
                        combined_text
                    )
                )

            except Exception as error:

                print(
                    "TEXT ANALYSIS ERROR:",
                    error,
                )

                text_result = {

                    "risk_level": "low",

                    "score": 0,

                    "detected_indicators": [],

                    "description": (
                        "Text analysis gagal."
                    ),
                }

        else:

            text_result = {

                "risk_level": "low",

                "score": 0,

                "detected_indicators": [],

                "description": (
                    "Tidak ada teks yang "
                    "dapat dianalisis."
                ),
            }


        # ====================================================
        # 7. TEXT RESULT
        # ====================================================

        text_risk = get_risk_level(
            text_result
        )

        text_score = get_analysis_score(
            text_result
        )

        text_indicators = safe_list(
            text_result.get(
                "detected_indicators",
                [],
            )
        )

        text_description = (
            text_result.get(
                "description",
                "",
            )
        )


        print(
            "\n========== TEXT RESULT =========="
        )

        print(
            "Text Risk:",
            text_risk,
        )

        print(
            "Text Score:",
            text_score,
        )

        print(
            "Text Indicators:",
            text_indicators,
        )


        # ====================================================
        # 8. GABUNGKAN INDIKATOR
        # ====================================================

        combined_indicators = (
            merge_unique_items(
                visual_indicators,
                text_indicators,
            )
        )


        # ====================================================
        # 9-10. FINAL MULTIMODAL FUSION
        # ====================================================

        final_result = calculate_final_multimodal_risk(
            visual_result=visual_result,
            text_result=text_result,
            ocr_text=ocr_text,
        )

        final_risk = final_result["risk_level"]
        final_score = safe_float(final_result.get("score", 0))
        combined_indicators = safe_list(
            final_result.get("indicators", [])
        )
        description = final_result.get(
            "description",
            "Tidak ditemukan indikasi kuat aktivitas atau promosi judi online.",
        )
        classification = final_result.get(
            "classification",
            "TIDAK TERINDIKASI",
        )

        print(
            "\n====================================================="
        )
        print("FINAL GUARDNET-AI RESULT")
        print("=====================================================")
        print("Text Risk:", text_risk)
        print("Text Score:", text_score)
        print("OCR Risk:", final_result.get("ocr_risk"))
        print("OCR Score:", final_result.get("ocr_score"))
        print("Visual Risk:", visual_risk)
        print("Visual Score:", visual_score)
        print("FINAL SCORE:", final_score)
        print("FINAL RISK:", final_risk)
        print("CLASSIFICATION:", classification)
        print("FINAL INDICATORS:", combined_indicators)
        print("EVIDENCE FUSION:", final_result.get("evidence_fusion", {}))
        print("=====================================================")


        # ====================================================
        # 11. SAVE CONTENT
        # ====================================================

        content = Content(
            platform=platform,
            content_type=content_type,
            content_url=content_url,
            detected_text=combined_text,
        )

        content.is_suspected_judol = (
            final_risk
            in {
                "medium",
                "high",
            }
        )

        content.risk_score = (
            final_score
        )

        db.add(content)

        db.flush()


        # ====================================================
        # 12. CREATE CASE
        # ====================================================

        case = None

        if final_risk in {
            "medium",
            "high",
        }:

            description = (
                "GuardNet-AI full multimodal analysis. "
                f"Text risk: {text_risk}. "
                f"Visual risk: {visual_risk}. "
                f"Final risk: {final_risk}."
            )

            case, _ = (
                get_or_create_case(
                    db=db,
                    content=content,
                    risk_level=final_risk,
                    description=description,
                )
            )

        else:

            description = (
                "GuardNet-AI full multimodal analysis. "
                f"Text risk: {text_risk}. "
                f"Visual risk: {visual_risk}. "
                f"Final risk: {final_risk}."
            )


        # ====================================================
        # 13. CREATE EVIDENCE
        # ====================================================

        evidence = None

        try:

            # Evidence hanya dibuat jika ada Case.
            if case:

                evidence_data = (
                    create_evidence_payload(
                        image_bytes,
                        case.case_id,
                        content_url,
                        ocr_text,
                    )
                )


                evidence_payload = (
                    evidence_data.get(
                        "evidence",
                        {},
                    )
                )


                image_hash = (
                    evidence_payload.get(
                        "image_hash"
                    )
                )

                ocr_hash = (
                    evidence_payload.get(
                        "ocr_hash"
                    )
                )


                # ------------------------------------------------
                # Jangan masukkan evidence invalid
                # ------------------------------------------------

                if image_hash and ocr_hash:

                    evidence = Evidence(
                        evidence_id=(
                            f"EVD-"
                            f"{uuid.uuid4().hex.upper()}"
                        ),

                        case_id=case.case_id,

                        source_url=content_url,

                        image_hash=image_hash,

                        ocr_hash=ocr_hash,

                        integrity_status=(
                            evidence_payload.get(
                                "integrity_status",
                                "verified",
                            )
                        ),

                        description=(
                            "Evidence generated "
                            "by GuardNet-AI."
                        ),
                    )

                    db.add(evidence)

                    db.flush()

                else:

                    print(
                        "EVIDENCE SKIPPED: "
                        "image_hash atau "
                        "ocr_hash kosong."
                    )


        except Exception as error:

            print(
                "EVIDENCE ERROR:",
                error,
            )

            evidence = None


        # ====================================================
        # 14. AUTOMATIC REPORT
        # ====================================================

        report = None

        if case:

            report, _ = (
                get_or_create_report(
                    db=db,
                    case=case,
                )
            )


            # ------------------------------------------------
            # Hubungkan Evidence Hash ke Report
            # ------------------------------------------------

            if (
                report
                and evidence
            ):

                report.evidence_hash = (
                    evidence.image_hash
                )

                report.evidence_timestamp = (
                    evidence.detected_at
                )


        # ====================================================
        # 15. SAVE PAYMENT DETECTIONS
        # ====================================================

        payment_records = []

        if report:
            payment_records = save_payment_detections(
                db=db,
                report=report,
                payment_result=payment_result,
            )

        print(
            "PAYMENT RECORDS SAVED:",
            len(payment_records),
        )

        # ====================================================
        # 16. COMMIT
        # ====================================================

        db.commit()


        # ====================================================
        # 16. REFRESH
        # ====================================================

        db.refresh(content)

        if case:

            db.refresh(case)

        if evidence:

            db.refresh(evidence)

        if report:

            db.refresh(report)


        # ====================================================
        # 17. FINAL LOG
        # ====================================================

        print(
            "\n====================================================="
        )

        print(
            "GUARDNET-AI FULL ANALYSIS COMPLETED"
        )

        print(
            "====================================================="
        )

        print(
            "Case ID:",
            case.case_id
            if case
            else None,
        )

        print(
            "Content ID:",
            content.id,
        )

        print(
            "Report ID:",
            report.report_id
            if report
            else None,
        )

        print(
            "Evidence ID:",
            evidence.evidence_id
            if evidence
            else None,
        )

        print(
            "OCR:",
            ocr_text,
        )

        print(
            "Text Risk:",
            text_risk,
        )

        print(
            "Text Score:",
            text_score,
        )

        print(
            "Visual Risk:",
            visual_risk,
        )

        print(
            "Visual Score:",
            visual_score,
        )

        print(
            "FINAL RISK:",
            final_risk,
        )

        print(
            "FINAL SCORE:",
            final_score,
        )

        print(
            "Indicators:",
            combined_indicators,
        )

        print(
            "====================================================="
        )


        # ====================================================
        # 18. RESPONSE
        # ====================================================

        return {

            "success": True,

            "case_id": (
                case.case_id
                if case
                else None
            ),

            "content_id": content.id,

            "filename": file.filename,

            "platform": platform,

            "content_type": content_type,

            "content_url": content_url,

            "report_id": (
                report.report_id
                if report
                else None
            ),

            "report_status": (
                report.status
                if report
                else "not_created"
            ),

            "manual_text": manual_text,

            "ocr_text": ocr_text,

            "combined_text": combined_text,

            "risk_level": final_risk,

            "score": final_score,

            "detected_indicators": (
                combined_indicators
            ),

            "description": description,

            "payment": {
                "payment_detected": payment_result.get("payment_detected", False),
                "payment_type": payment_result.get("payment_type", "unknown"),
                "qr_detected": payment_result.get("qr_detected", False),
                "verification_status": payment_result.get("verification_status", "unverified"),
                "image_hash": payment_result.get("image_hash", ""),
                "payments": payment_result.get("payments", []),
                "saved_count": len(payment_records),
            },

            "evidence": (
                {
                    "evidence_id": (
                        evidence.evidence_id
                    ),

                    "image_hash": (
                        evidence.image_hash
                    ),

                    "ocr_hash": (
                        evidence.ocr_hash
                    ),

                    "algorithm": "SHA-256",

                    "integrity_status": (
                        evidence.integrity_status
                    ),
                }
                if evidence
                else None
            ),

            "analysis": {

                "visual": {

                    "risk_level": visual_risk,

                    "score": visual_score,

                    "indicators": (
                        visual_indicators
                    ),

                    "description": (
                        visual_description
                    ),
                },

                "text": {

                    "risk_level": text_risk,

                    "score": text_score,

                    "indicators": (
                        text_indicators
                    ),

                    "description": (
                        text_description
                    ),
                },

                "final": {

                    "risk_level": final_risk,

                    "score": final_score,

                    "indicator_count": len(
                        combined_indicators
                    ),

                    "indicators": (
                        combined_indicators
                    ),
                },
            },
        }


    except HTTPException:

        db.rollback()

        raise


    except Exception as error:

        db.rollback()

        print(
            "\n====================================================="
        )

        print(
            "FULL ANALYSIS ERROR"
        )

        print(
            str(error)
        )

        print(
            "====================================================="
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Analisis content gagal: {error}"
            ),
        )

@app.post("/evidence")
def create_evidence_endpoint(
    case_id: str,
    source_url: str = "",
    image_hash: str = "",
    ocr_hash: str = "",
    description: str = "",
    db: Session = Depends(get_db),
):
    """
    Menyimpan evidence untuk Case tertentu.

    Evidence dibuat setelah Case tersedia dan wajib memiliki
    image_hash + ocr_hash sebagai penanda integritas bukti.
    """
    case = (
        db.query(Case)
        .filter(Case.case_id == case_id)
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case tidak ditemukan.",
        )

    if not image_hash:
        raise HTTPException(
            status_code=400,
            detail="image_hash wajib diisi.",
        )

    if not ocr_hash:
        raise HTTPException(
            status_code=400,
            detail="ocr_hash wajib diisi.",
        )

    try:
        # Hindari evidence duplikat untuk kombinasi
        # case + image hash + OCR hash.
        existing = (
            db.query(Evidence)
            .filter(
                Evidence.case_id == case.case_id,
                Evidence.image_hash == image_hash,
                Evidence.ocr_hash == ocr_hash,
            )
            .first()
        )

        if existing:
            return {
                "success": True,
                "message": "Evidence sudah tersedia.",
                "evidence_id": existing.evidence_id,
                "case_id": existing.case_id,
                "integrity_status": existing.integrity_status,
                "source_url": existing.source_url,
                "image_hash": existing.image_hash,
                "ocr_hash": existing.ocr_hash,
                "created": False,
            }

        evidence = Evidence(
            evidence_id=generate_evidence_id(),
            case_id=case.case_id,
            source_url=source_url or None,
            image_hash=image_hash,
            ocr_hash=ocr_hash,
            # "verified" di sini berarti hash/integritas bukti
            # berhasil direkam, bukan verifikasi identitas
            # pemilik rekening/QRIS oleh provider.
            integrity_status="verified",
            description=description or None,
            detected_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        # Jika Case sudah memiliki Report, sinkronkan evidence hash.
        report = (
            db.query(Report)
            .filter(Report.case_id == case.case_id)
            .first()
        )

        if report:
            report.evidence_hash = evidence.image_hash
            report.evidence_timestamp = evidence.detected_at
            db.commit()
            db.refresh(report)

        return {
            "success": True,
            "message": "Evidence berhasil disimpan.",
            "evidence_id": evidence.evidence_id,
            "case_id": evidence.case_id,
            "integrity_status": evidence.integrity_status,
            "source_url": evidence.source_url,
            "image_hash": evidence.image_hash,
            "ocr_hash": evidence.ocr_hash,
            "created": True,
        }

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menyimpan evidence: {error}",
        )


# ============================================================
# END OF MAIN.PY
# ============================================================