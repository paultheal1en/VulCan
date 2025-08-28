import datetime

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base

from vulcan.persistence.db_session import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False)
    summary = Column(LONGTEXT, nullable=False)
    created_at = Column(DateTime, default=func.now())
