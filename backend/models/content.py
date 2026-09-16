from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func

from database import Base


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)

    platform = Column(String(50), nullable=False)

    content_url = Column(String(500), nullable=True)

    content_type = Column(String(50), nullable=False)

    detected_text = Column(Text, nullable=True)

    is_suspected_judol = Column(Boolean, default=False)

    risk_score = Column(Integer, default=0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )