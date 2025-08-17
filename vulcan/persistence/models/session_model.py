from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic.class_validators import validator
from sqlalchemy import Column, String
from sqlalchemy.dialects.mysql import LONGTEXT

from vulcan.persistence.db_session import Base


class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String(32), primary_key=True)
    name = Column(LONGTEXT)
    init_description = Column(LONGTEXT)
    current_role_name = Column(LONGTEXT)
    current_planner_id = Column(String(32), index=True)
    history_planner_ids = Column(String(256))


class ArrayField(List):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return handler(List)


class Session(BaseModel):
    id: str = Field(None)
    name: Optional[str] = ""
    init_description: str = Field(None)
    current_role_name: Optional[str] = ""
    current_planner_id: Optional[str] = ""
    history_planner_ids: ArrayField[str] = Field(default_factory=list)

    @validator("history_planner_ids", pre=True, each_item=False)
    def parse_history_planner_ids(cls, value):
        if isinstance(value, str):
            return value.split(",") if value else []
        return value

    class Config:
        from_attributes = True
