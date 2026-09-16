from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    case_id = Column(
        String(50),
        unique=True,
        nullable=False
    )

    content_id = Column(
        Integer,
        ForeignKey("contents.id"),
        nullable=True
    )

    status = Column(
        String(30),
        nullable=False,
        default="new"
    )

    risk_level = Column(
        String(20),
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )