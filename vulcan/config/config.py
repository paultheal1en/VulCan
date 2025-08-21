import os
from strenum import StrEnum  
from typing import Dict, Any
from pathlib import Path
from functools import cached_property

# Đảm bảo import từ đúng vị trí trong cấu trúc mới
from .pydantic_settings_file import BaseFileSettings, SettingsConfigDict, settings_property

# --- Định nghĩa đường dẫn gốc của dự án ---
VULCAN_ROOT = Path(__file__).resolve().parents[2] # Trỏ ra ngoài thư mục vulcan/config/

class Mode(StrEnum):
    Auto = "auto"
    Manual = "manual"
    SemiAuto = "semi"

# --- Lớp Cấu hình Chung ---
class BasicConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=VULCAN_ROOT / "config.yaml")

    log_verbose: bool = True
    mode: str = Mode.Auto
    max_iterations: int = 100
    confirmations: bool = False
    keep_memory: bool = False

    KB_ROOT_PATH: str = str(VULCAN_ROOT / "knowledge_base_data")

    target_shell: dict = {
        "hostname": "127.0.0.1",
        "port": 22,
        "username": "root",
        "password": "password",
    }
    
    @cached_property
    def LOG_PATH(self) -> Path:
        p = VULCAN_ROOT / "logs"
        return p

    @cached_property
    def EVIDENCE_PATH(self) -> Path:
        p = VULCAN_ROOT / "evidence"
        return p
    
    @cached_property
    def TOOLS_PATH(self) -> Path:
        p = VULCAN_ROOT / "vulcan/tools"
        return p

    def make_dirs(self):
        for p in [self.LOG_PATH, self.EVIDENCE_PATH, self.TOOLS_PATH]:
            p.mkdir(parents=True, exist_ok=True)

# --- Lớp Cấu hình Database ---
class DBConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=VULCAN_ROOT / "db_config.yaml")
    mysql: dict = {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "password",
        "database": "vulcan_db",
    }

# --- Lớp Cấu hình Mô hình Ngôn ngữ ---
class LLMConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=VULCAN_ROOT / "llm_config.yaml")

    server: str = "remote"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    ollama_host: str = "http://localhost:11434"
    ollama_model_id: str = "llama3.2:3b"
    ollama_embedding_model_id: str = "mxbai-embed-large"
    temperature: float = 0.5
    history_len: int = 10
    timeout: int = 600

class KBConfig(BaseFileSettings):
    model_config = SettingsConfigDict(yaml_file=VULCAN_ROOT / "kb_config.yaml")
    
    # --- Cấu hình KB & Vector Store ---
    kb_name: str = "default_rag"
    KB_ROOT_PATH: str = str(VULCAN_ROOT / "knowledge_base_data")
    default_vs_type: str = "milvus"
    milvus: dict = { "uri": "", "user": "", "password": "" }

    # --- Cấu hình Embedding & Reranker ---
    embedding_model: str = "all-MiniLM-L6-v2"
    rerank_model_name: str = "maidalun1020/bce-reranker-base_v1"
    
    chunk_size: int = 750
    overlap_size: int = 150
    top_k: int = 3 # Số kết quả lấy từ Milvus
    top_n: int = 1 # Số kết quả lấy sau khi rerank
    score_threshold: float = 0.5
    
    search_params: dict = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    index_params: dict = { "index_type": "AUTOINDEX", "metric_type": "COSINE", "params": {} }
    
    text_splitter_dict: dict = {
        "RecursiveCharacterTextSplitter": { "source": "tiktoken", "tokenizer_name_or_path": "cl100k_base" },
    }
    text_splitter_name: str = "RecursiveCharacterTextSplitter"

# --- Container chính để truy cập tất cả cấu hình ---
class ConfigsContainer:
    VULCAN_ROOT = VULCAN_ROOT

    basic_config: BasicConfig = settings_property(BasicConfig())
    db_config: DBConfig = settings_property(DBConfig())
    llm_config: LLMConfig = settings_property(LLMConfig())
    kb_config: KBConfig = settings_property(KBConfig())

    def create_all_templates(self):
        # Tạo các tệp YAML mẫu
        self.basic_config.create_template_file(write_file=True, file_format="yaml")
        self.db_config.create_template_file(write_file=True, file_format="yaml")
        self.llm_config.create_template_file(write_file=True, file_format="yaml")
        self.kb_config.create_template_file(write_file=True, file_format="yaml")
        # Đổi tên các tệp mẫu cho đúng

Configs = ConfigsContainer()