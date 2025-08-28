from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

# from vulcan.utils.log_common import build_logger
from sentence_transformers import SentenceTransformer

from vulcan.config.config import Configs

# logger = build_logger("RAGEmbedding")


def get_embeddings(embed_model_name: str = None) -> Embeddings:
    """
    Creates and returns a Sentence-Transformer embedding model instance.
    This ensures consistency between data ingestion and querying.
    """
    # Luôn sử dụng model embedding được định nghĩa trong RAG config
    model_name = embed_model_name or Configs.kb_config.embedding_model

    print(f"Creating Sentence-Transformer embeddings with model: '{model_name}'")

    try:
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        print(
            f"Failed to create Sentence-Transformer Embeddings for model '{model_name}': {e}\n"
        )
        raise
