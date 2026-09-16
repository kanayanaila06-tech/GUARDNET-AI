# =====================================================
# GUARDNET-AI REPORT MODEL
# =====================================================

from datetime import datetime

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
# REPORT
# =====================================================

class Report(Base):

    __tablename__ = "reports"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # -------------------------------------------------
    # IDENTITAS LAPORAN
    # -------------------------------------------------

    report_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    case_id = Column(
        String(50),
        ForeignKey("cases.case_id"),
        nullable=False,
        index=True
    )

    # -------------------------------------------------
    # INFORMASI LAPORAN
    # -------------------------------------------------

    report_type = Column(
        String(50),
        default="online_gambling"
    )

    status = Column(
        String(30),
        default="draft"
    )

    risk_level = Column(
        String(20),
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    # -------------------------------------------------
    # BUKTI
    # -------------------------------------------------

    evidence_hash = Column(
        String(64),
        nullable=True,
        index=True
    )

    evidence_timestamp = Column(
        DateTime,
        default=datetime.utcnow
    )

    # -------------------------------------------------
    # WAKTU LAPORAN
    # -------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )