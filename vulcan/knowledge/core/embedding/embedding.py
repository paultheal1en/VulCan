from langchain_core.embeddings import Embeddings

from langchain_huggingface import HuggingFaceEmbeddings

from vulcan.config.config import Configs
from vulcan.utils.log_common import build_logger

logger = build_logger("RAGEmbedding")

def get_embeddings(embed_model_name: str = None) -> Embeddings:
    """
    Creates and returns a HuggingFace embedding model instance.
    This ensures consistency between data ingestion and querying.
    """
    # Luôn sử dụng model embedding được định nghĩa trong RAG config
    model_name = embed_model_name or Configs.kb_config.embedding_model

    logger.info(f"Creating HuggingFace embeddings with model: '{model_name}'")

    try:
        # Luôn tạo HuggingFaceEmbeddings, bất kể chế độ remote hay local
        # Điều này đảm bảo kích thước vector luôn khớp với dữ liệu đã nạp.
        return HuggingFaceEmbeddings(model_name=model_name)
    except Exception as e:
        logger.error(f"Failed to create HuggingFace Embeddings for model '{model_name}': {e}")
        raise