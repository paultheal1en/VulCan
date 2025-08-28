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


class ArrayField(List):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return handler(List)


class Session(BaseModel):
    id: str = Field(None)
    name: Optional[str] = ""
    init_description: str = Field(None)

    class Config:
        from_attributes = True
