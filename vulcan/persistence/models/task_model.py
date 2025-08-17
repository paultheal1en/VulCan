from typing import List

from sqlalchemy import Column, String, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import LONGTEXT
from vulcan.persistence.db_session import Base
from pydantic import *

class TaskModel(Base):
    __tablename__ = "tasks"
    id = Column(String(32), primary_key=True)
    plan_id = Column(String(32), ForeignKey('plans.id'))
    sequence = Column(Integer, nullable=False)
    action = Column(LONGTEXT, nullable=True)
    instruction = Column(LONGTEXT, nullable=True)
    code = Column(JSON, nullable=True)
    result = Column(LONGTEXT, nullable=True)
    is_success = Column(Boolean, default=False)
    is_finished = Column(Boolean, default=False)

    dependencies = Column(JSON, default=list)

    plan = relationship("PlanModel", back_populates="tasks")

class Task(BaseModel):
    id: str = Field(None)
    plan_id: str = Field(None)
    sequence: int = Field(...)
    action: str = Field(None)
    instruction: str = Field(None)
    code: List[str] = Field([])
    result: str = Field("")
    is_success: bool = False
    is_finished: bool = False

    dependencies: List[int] = []

    class Config:
        from_attributes = True