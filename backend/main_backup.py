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

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
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



def normalize_payment_for_db(payment: Dict[str, Any]) -> Dict[str, Any]:
    """Normalisasi satu kandidat payment dari detector."""
    payment = payment or {}

    payment_type = str(
        payment.get("payment_type")
        or payment.get("type")
        or "unknown"
    ).lower()

    return {
        "payment_type": payment_type,
        "provider": (
            payment.get("provider")
            or payment.get("bank")
            or payment.get("bank_name")
            or payment.get("ewallet")
            or payment.get("e_wallet")
        ),
        "account_name": (
            payment.get("account_name")
            or payment.get("name")
            or payment.get("merchant_name")
        ),
        "account_number": (
            payment.get("account_number")
            or payment.get("account")
            or payment.get("account_id")
            or payment.get("number")
        ),
        "phone_number": (
            payment.get("phone_number")
            or payment.get("phone")
        ),
        "qr_detected": bool(
            payment.get("qr_detected")
            or payment_type in {"qris", "qr"}
        ),
        "verification_status": str(
            payment.get("verification_status")
            or "unverified"
        ).lower(),
        "image_hash": (
            payment.get("image_hash")
            or payment.get("data_hash")
        ),
    }


def save_payment_detections(
    db: Session,
    report: Report,
    payment_result: Dict[str, Any],
) -> List[PaymentDetection]:
    """
    Simpan kandidat payment ke report.
    Hasil detector tidak otomatis dianggap terverifikasi.
    """
    if not report or not payment_result.get("payment_detected"):
        return []

    payments = payment_result.get("payments") or []

    if not isinstance(payments, list):
        return []

    saved = []

    for raw_payment in payments:
        if not isinstance(raw_payment, dict):
            continue

        normalized = normalize_payment_for_db(raw_payment)

        payment_hash = normalized.get("image_hash")

        existing = None
        if payment_hash:
            existing = (
                db.query(PaymentDetection)
                .filter(
                    PaymentDetection.report_id == report.report_id,
                    PaymentDetection.image_hash == payment_hash,
                )
                .first()
            )

        if existing:
            saved.append(existing)
            continue

        record = PaymentDetection(
            payment_id=f"PAY-{uuid.uuid4().hex[:12].upper()}",
            report_id=report.report_id,
            payment_type=normalized["payment_type"],
            provider=normalized["provider"],
            account_name=normalized["account_name"],
            account_number=normalized["account_number"],
            phone_number=normalized["phone_number"],
            qr_detected=normalized["qr_detected"],
            verification_status=normalized["verification_status"],
            image_hash=normalized["image_hash"],
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

            "indicators": (
                analyze_text(
                    content.detected_text
                ).get("indicators", [])
                if content
                and content.detected_text
                else []
            ),

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

            "indicators": (
                analyze_text(
                    content.detected_text
                ).get("indicators", [])
                if content
                and content.detected_text
                else []
            ),

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
        # 9. FINAL RISK
        # ====================================================

        if (
            text_risk == "high"
            or visual_risk == "high"
        ):

            final_risk = "high"

        elif (
            text_risk == "medium"
            or visual_risk == "medium"
        ):

            final_risk = "medium"

        else:

            final_risk = "low"


        # ====================================================
        # 10. FINAL SCORE
        # ====================================================

        final_score = max(
            text_score,
            visual_score,
        )


        print(
            "\n====================================================="
        )

        print(
            "FINAL GUARDNET-AI RESULT"
        )

        print(
            "====================================================="
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
            "FINAL SCORE:",
            final_score,
        )

        print(
            "FINAL RISK:",
            final_risk,
        )

        print(
            "FINAL INDICATORS:",
            combined_indicators,
        )

        print(
            "====================================================="
        )


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