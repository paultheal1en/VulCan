from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, func

from vulcan.persistence.db_session import Base


class KnowledgeFileModel(Base):

    __tablename__ = "knowledge_file"
    id = Column(Integer, primary_key=True, autoincrement=True, comment="Knowledge file ID")
    file_name = Column(String(255), comment="File name")
    file_ext = Column(String(10), comment="File extension")
    kb_name = Column(String(50), comment="Knowledge base name")
    document_loader_name = Column(String(50), comment="Document loader name")
    text_splitter_name = Column(String(50), comment="Text splitter name")
    file_version = Column(Integer, default=1, comment="File version")
    file_mtime = Column(Float, default=0.0, comment="File modification time")
    file_size = Column(Integer, default=0, comment="File size")
    custom_docs = Column(Boolean, default=False, comment="Custom docs")
    docs_count = Column(Integer, default=0, comment="Document count")
    create_time = Column(DateTime, default=func.now(), comment="Creation time")

    def __repr__(self):
        return f"<KnowledgeFile(id='{self.id}', file_name='{self.file_name}', file_ext='{self.file_ext}', kb_name='{self.kb_name}', document_loader_name='{self.document_loader_name}', text_splitter_name='{self.text_splitter_name}', file_version='{self.file_version}', create_time='{self.create_time}')>"


class FileDocModel(Base):

    __tablename__ = "file_doc"
    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    kb_name = Column(String(50), comment="Knowledge base name")
    file_name = Column(String(255), comment="File name")
    doc_id = Column(String(50), comment="Vector store document ID")
    meta_data = Column(JSON, default={})

    def __repr__(self):
        return f"<FileDoc(id='{self.id}', kb_name='{self.kb_name}', file_name='{self.file_name}', doc_id='{self.doc_id}', metadata='{self.meta_data}')>"
