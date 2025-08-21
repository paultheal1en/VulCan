from datetime import datetime
from typing import Optional
from pydantic import *
from langchain_core.documents import Document

from sqlalchemy import Column, Integer, String, DateTime, func

from vulcan.persistence.db_session import Base

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

class MatchDocument(Document):
    id: Optional[str] = None



class KnowledgeBaseModel(Base):

    __tablename__ = "knowledge_base"
    id = Column(Integer, primary_key=True, autoincrement=True, comment="Knowledge base ID")
    kb_name = Column(String(50), comment="Knowledge base name")
    kb_info = Column(String(200), comment="Knowledge base description (for Agent)")
    vs_type = Column(String(50), comment="Vector store type")
    embed_model = Column(String(50), comment="Embedding model name")
    file_count = Column(Integer, default=0, comment="File count")
    create_time = Column(DateTime, default=func.now(), comment="Creation time")

    def __repr__(self):
        return f"<KnowledgeBase(id='{self.id}', kb_name='{self.kb_name}',kb_intro='{self.kb_info} vs_type='{self.vs_type}', embed_model='{self.embed_model}', file_count='{self.file_count}', create_time='{self.create_time}')>"



class KnowledgeBaseSchema(BaseModel):
    id: int = Field(..., description="Knowledge base ID")
    kb_name: str = Field(..., description="Knowledge base name")
    kb_info: Optional[str] = Field(None, description="Knowledge base description (for Agent)")
    vs_type: Optional[str] = Field(None, description="Vector store type")
    embed_model: Optional[str] = Field(None, description="Embedding model name")
    file_count: Optional[int] = Field(0, description="File count")
    create_time: Optional[datetime] = Field(None, description="Creation time")


    class Config:
        from_attributes = True

