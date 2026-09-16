from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from database import Base


class PaymentDetection(Base):

    __tablename__ = "payment_detections"


    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(String(50), unique=True, nullable=False, index=True)

    report_id = Column(String(50), ForeignKey("reports.report_id"), nullable=False, index=True)

    payment_type = Column(String(30), nullable=False, default="unknown")

    provider = Column(String(100), nullable=True)

    acquirer = Column(String(100), nullable=True)

    acquirer_identifier = Column(String(150), nullable=True)

    account_name = Column(String(150), nullable=True)

    account_number = Column(String(100), nullable=True)

    phone_number = Column(String(30), nullable=True)

    qr_detected = Column(Boolean, default=False, nullable=False)

    qris_detected = Column(Boolean, default=False, nullable=False)

    merchant_name = Column(String(200), nullable=True)

    merchant_city = Column(String(100), nullable=True)

    nmid = Column(String(100), nullable=True)

    merchant_category_code = Column(String(20), nullable=True)

    currency = Column(String(10), nullable=True)

    amount = Column(String(50), nullable=True)

    crc_valid = Column(Boolean, nullable=True)

    qris_technical_status = Column(String(30), nullable=True)

    qris_data_quality_status = Column(String(40), nullable=True)

    qris_technical_checks = Column(Text, nullable=True)

    qris_quality_reasons = Column(Text, nullable=True)

    authenticity_status = Column(String(30), nullable=True)

    authenticity_reason = Column(Text, nullable=True)

    destination_bank = Column(String(100), nullable=True)

    routing_note = Column(Text, nullable=True)

    verification_status = Column(String(30), default="unverified", nullable=False)

    payment_score = Column(String(20), nullable=True)

    qr_payload = Column(Text, nullable=True)

    image_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)