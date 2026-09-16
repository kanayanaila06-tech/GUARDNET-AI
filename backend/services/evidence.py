# =====================================================
# GUARDNET-AI EVIDENCE SERVICE
# =====================================================

import hashlib
import uuid

from datetime import datetime, timezone
from typing import Optional


# =====================================================
# GENERATE SHA-256 HASH
# =====================================================

def generate_hash(data: bytes) -> str:
    """
    Generate SHA-256 hash untuk data binary.
    Digunakan untuk fingerprint gambar/evidence.
    """

    if data is None:
        return ""

    if not isinstance(data, bytes):
        return ""

    if len(data) == 0:
        return ""

    return hashlib.sha256(data).hexdigest()


# =====================================================
# GENERATE TEXT HASH
# =====================================================

def generate_text_hash(text: str) -> str:
    """
    Generate SHA-256 hash untuk teks OCR.
    """

    if text is None:
        return ""

    text = str(text)

    if text == "":
        return ""

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# =====================================================
# GENERATE EVIDENCE ID
# =====================================================

def generate_evidence_id() -> str:

    return (
        f"EV-{uuid.uuid4().hex[:12].upper()}"
    )


# =====================================================
# GENERATE TIMESTAMP
# =====================================================

def generate_timestamp() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


# =====================================================
# CREATE EVIDENCE
# =====================================================

def create_evidence(
    image_bytes: bytes,
    case_id: Optional[str] = None,
    source_url: Optional[str] = None,
    ocr_text: Optional[str] = None,
    payment_data: Optional[dict] = None
) -> dict:
    """
    Membuat digital evidence GuardNet-AI.

    Evidence terdiri dari:
    - Evidence ID
    - Case ID
    - Source URL
    - Timestamp
    - Image SHA-256
    - OCR SHA-256
    - Payment evidence
    - Integrity status
    """

    # =================================================
    # VALIDASI IMAGE
    # =================================================

    if not image_bytes:

        return {
            "success": False,
            "message": "Data gambar kosong.",
            "evidence": None
        }


    # =================================================
    # NORMALISASI OCR
    # =================================================

    if ocr_text is None:
        ocr_text = ""

    ocr_text = str(ocr_text)


    # =================================================
    # GENERATE EVIDENCE ID
    # =================================================

    evidence_id = generate_evidence_id()


    # =================================================
    # GENERATE IMAGE HASH
    # =================================================

    image_hash = generate_hash(
        image_bytes
    )


    # =================================================
    # GENERATE OCR HASH
    # =================================================

    ocr_hash = generate_text_hash(
        ocr_text
    )


    # =================================================
    # VALIDASI HASH
    # =================================================

    if not image_hash:

        return {
            "success": False,
            "message": "Gagal membuat image hash.",
            "evidence": None
        }


    # =================================================
    # TIMESTAMP
    # =================================================

    detected_at = generate_timestamp()


    # =================================================
    # PAYMENT EVIDENCE
    # =================================================

    payment_evidence = None
    payments = []


    if payment_data:

        payments = payment_data.get(
            "payments",
            []
        )

        if not isinstance(
            payments,
            list
        ):
            payments = []


        payment_evidence = {

            "payment_detected":
                bool(
                    payment_data.get(
                        "payment_detected",
                        False
                    )
                ),

            "payment_type":
                payment_data.get(
                    "payment_type",
                    "unknown"
                ),

            "qr_detected":
                bool(
                    payment_data.get(
                        "qr_detected",
                        False
                    )
                ),

            "verification_status":
                payment_data.get(
                    "verification_status",
                    "unverified"
                ),

            "image_hash":
                payment_data.get(
                    "image_hash"
                ) or image_hash,

            "payments":
                payments
        }


    # =================================================
    # INTEGRITY STATUS
    # =================================================

    integrity_status = "verified"


    # =================================================
    # COMPLETE EVIDENCE OBJECT
    # =================================================

    evidence = {

        "evidence_id":
            evidence_id,

        "case_id":
            case_id,

        "source_url":
            source_url or "",

        "detected_at":
            detected_at,

        "image_hash":
            image_hash,

        "ocr_hash":
            ocr_hash,

        "payment":
            payment_evidence,

        "integrity_status":
            integrity_status
    }


    # =================================================
    # DEBUG LOG
    # =================================================

    print("=================================")
    print("GUARDNET-AI EVIDENCE")
    print("Evidence ID:", evidence_id)
    print("Case ID:", case_id)
    print("Image Hash:", image_hash)
    print("OCR Hash:", ocr_hash)
    print("Detected At:", detected_at)
    print("Integrity:", integrity_status)

    if payment_evidence:

        print(
            "Payment Detected:",
            payment_evidence.get(
                "payment_detected",
                False
            )
        )

        print(
            "Payment Type:",
            payment_evidence.get(
                "payment_type",
                "unknown"
            )
        )

        for payment in payments:

            print(
                "Payment Hash:",
                payment.get(
                    "data_hash",
                    ""
                )
            )

    print("=================================")


    # =================================================
    # FINAL RESPONSE
    # =================================================
    #
    # HASH DISEDIAKAN DI DUA LEVEL:
    #
    # 1. Level utama
    # 2. Di dalam "evidence"
    #
    # Ini menjaga kompatibilitas dengan main.py
    # versi lama maupun versi baru.
    #
    # =================================================

    return {

        "success":
            True,

        "message":
            "Evidence berhasil dibuat.",


        # -------------------------------------------------
        # DIRECT ACCESS
        # -------------------------------------------------

        "evidence_id":
            evidence_id,

        "case_id":
            case_id,

        "source_url":
            source_url or "",

        "detected_at":
            detected_at,

        "image_hash":
            image_hash,

        "ocr_hash":
            ocr_hash,

        "integrity_status":
            integrity_status,


        # -------------------------------------------------
        # COMPLETE OBJECT
        # -------------------------------------------------

        "evidence":
            evidence
    }


# =====================================================
# VERIFY IMAGE INTEGRITY
# =====================================================

def verify_image_integrity(
    image_bytes: bytes,
    original_hash: str
) -> dict:

    if not image_bytes:

        return {
            "valid": False,
            "status": "invalid",
            "message": "Gambar kosong."
        }


    if not original_hash:

        return {
            "valid": False,
            "status": "invalid",
            "message":
                "Original hash tidak tersedia."
        }


    current_hash = generate_hash(
        image_bytes
    )


    if current_hash == original_hash:

        return {

            "valid":
                True,

            "status":
                "valid",

            "original_hash":
                original_hash,

            "current_hash":
                current_hash,

            "message":
                "Evidence masih sesuai dengan data asli."
        }


    return {

        "valid":
            False,

        "status":
            "modified",

        "original_hash":
            original_hash,

        "current_hash":
            current_hash,

        "message":
            (
                "Evidence berbeda dari data asli "
                "dan perlu diperiksa."
            )
    }


# =====================================================
# VERIFY TEXT INTEGRITY
# =====================================================

def verify_text_integrity(
    text: str,
    original_hash: str
) -> dict:

    if not original_hash:

        return {

            "valid":
                False,

            "status":
                "invalid",

            "message":
                "Original hash tidak tersedia."
        }


    current_hash = generate_text_hash(
        text or ""
    )


    if current_hash == original_hash:

        return {

            "valid":
                True,

            "status":
                "valid",

            "original_hash":
                original_hash,

            "current_hash":
                current_hash,

            "message":
                "Teks evidence masih sesuai."
        }


    return {

        "valid":
            False,

        "status":
            "modified",

        "original_hash":
            original_hash,

        "current_hash":
            current_hash,

        "message":
            "Teks evidence berbeda dari data asli."
    }


# =====================================================
# VERIFY PAYMENT RELATION
# =====================================================

def verify_payment_relation(
    evidence: dict,
    payment_data: dict
) -> dict:

    if not evidence:

        return {

            "matched":
                False,

            "status":
                "invalid",

            "message":
                "Evidence tidak tersedia."
        }


    evidence_payment = evidence.get(
        "payment"
    )


    if not evidence_payment:

        return {

            "matched":
                False,

            "status":
                "not_found",

            "message":
                "Evidence tidak memiliki payment."
        }


    try:

        from services.payment import (
            verify_payment_relation as verify_payment
        )

        return verify_payment(
            evidence_payment,
            payment_data
        )

    except Exception as error:

        return {

            "matched":
                False,

            "status":
                "error",

            "message":
                f"Gagal melakukan verifikasi payment: {error}"
        }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    print("=================================")
    print("GUARDNET-AI EVIDENCE SYSTEM")
    print("Status: READY")
    print("=================================")