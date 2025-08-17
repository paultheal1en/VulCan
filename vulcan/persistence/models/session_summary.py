from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
import datetime
from vulcan.persistence.db_session import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False)
    summary = Column(LONGTEXT, nullable=False)
    created_at = Column(DateTime, default=func.now())