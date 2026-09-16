# =====================================================
# GUARDNET-AI EVIDENCE MODEL
# =====================================================

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey
)

from database import Base


# =====================================================
# EVIDENCE MODEL
# =====================================================

class Evidence(Base):

    __tablename__ = "evidence"


    # =================================================
    # PRIMARY KEY
    # =================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    # =================================================
    # EVIDENCE ID
    # =================================================

    evidence_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )


    # =================================================
    # CASE ID
    # =================================================

    case_id = Column(
        String(50),
        ForeignKey("cases.case_id"),
        nullable=False,
        index=True
    )


    # =================================================
    # SOURCE URL
    # =================================================

    source_url = Column(
        Text,
        nullable=True
    )


    # =================================================
    # IMAGE HASH
    # =================================================
    #
    # SHA-256 = 64 karakter
    #
    # Evidence baru WAJIB memiliki image_hash.
    #
    # =================================================

    image_hash = Column(
        String(64),
        nullable=False
    )


    # =================================================
    # OCR HASH
    # =================================================
    #
    # SHA-256 = 64 karakter
    #
    # Evidence baru WAJIB memiliki ocr_hash.
    #
    # =================================================

    ocr_hash = Column(
        String(64),
        nullable=False
    )


    # =================================================
    # INTEGRITY STATUS
    # =================================================

    integrity_status = Column(
        String(30),
        nullable=False,
        default="verified"
    )


    # =================================================
    # DESCRIPTION
    # =================================================

    description = Column(
        Text,
        nullable=True
    )


    # =================================================
    # DETECTED AT
    # =================================================

    detected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        )
    )


    # =================================================
    # CREATED AT
    # =================================================

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        )
    )