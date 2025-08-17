from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import Column, String, JSON, DateTime, func, TEXT
from sqlalchemy.dialects.mysql import LONGTEXT
from pydantic import *
from vulcan.persistence.db_session import Base


class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(String(32), primary_key=True)
    conversation_id = Column(String(32), index=True)
    chat_type = Column(String(50))
    query = Column(LONGTEXT)
    response = Column(LONGTEXT)  
    meta_data = Column(JSON, default={})
    create_time = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<message(id='{self.id}', conversation_id='{self.conversation_id}', chat_type='{self.chat_type}', query='{self.query}', response='{self.response}',meta_data='{self.meta_data}', create_time='{self.create_time}')>"


class Message(BaseModel):
    id: str = Field(...)
    conversation_id: str = Field(...)
    chat_type: Optional[str] = Field(None)
    query: Optional[str] = Field(None, max_length=10000)
    # response: Optional[str] = Field(None, max_length=8192)
    response: Optional[str] = Field(None)
    meta_data: Optional[Dict] = Field(default_factory=dict)
    create_time: Optional[datetime] = Field(None)

    class Config:
        from_attributes = True
