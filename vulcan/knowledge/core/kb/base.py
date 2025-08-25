from abc import ABC, abstractmethod
from typing import List, Union, Dict
from langchain.schema import Document

from vulcan.config.config import Configs


class SupportedVSType:
    """Supported Vector Store Types"""
    MILVUS = "milvus"


class KBService(ABC):
    """
    Abstract Knowledge Base Service
    Simplified version focusing on core search functionality
    """
    
    def __init__(
        self,
        knowledge_base_name: str,
        embed_model: str,
        kb_info: str = None,
    ):
        """
        Initialize Knowledge Base Service
        
        Args:
            knowledge_base_name: Name of the knowledge base
            embed_model: Embedding model to use
            kb_info: Optional knowledge base description
        """
        self.kb_name = knowledge_base_name
        self.embed_model = embed_model
        self.kb_info = kb_info
        self.do_init()

    def __repr__(self) -> str:
        """String representation of the KB service"""
        return f"{self.kb_name} @ {self.embed_model}"

    @abstractmethod
    def do_init(self):
        """
        Initialize the knowledge base service implementation
        This method should be implemented by concrete classes
        """
        pass

    @abstractmethod
    def do_search(
        self, 
        query: str, 
        top_k: int, 
        score_threshold: float
    ) -> List[Document]:
        """
        Search knowledge base for relevant documents
        
        Args:
            query: Search query string
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of relevant Document objects
        """
        pass

    def search_docs(
        self,
        query: str,
        top_k: int,
        score_threshold: float,
    ) -> List[Document]:
        """
        Public interface for searching documents
        
        Args:
            query: Search query string
            top_k: Maximum number of results to return
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of relevant Document objects
        """
        return self.do_search(query, top_k, score_threshold)

    @abstractmethod
    def vs_type(self) -> str:
        """
        Return the vector store type
        
        Returns:
            String identifier for the vector store type
        """
        pass

    # Optional: Add more abstract methods if needed for future functionality
    # @abstractmethod
    # def do_add_doc(self, docs: List[Document], **kwargs) -> List[Dict]:
    #     """Add documents to knowledge base"""
    #     pass
    #
    # @abstractmethod
    # def do_delete_doc(self, doc_id: str) -> bool:
    #     """Delete document from knowledge base"""
    #     pass


class KBServiceFactory:
    """Factory class for creating KB service instances"""
    
    @staticmethod
    def get_service(
        kb_name: str,
        vector_store_type: Union[str, SupportedVSType],
        embed_model: str,
        kb_info: str = None,
    ) -> KBService:
        """
        Create a KB service instance
        
        Args:
            kb_name: Knowledge base name
            vector_store_type: Type of vector store (string or SupportedVSType)
            embed_model: Embedding model name
            kb_info: Optional knowledge base description
            
        Returns:
            KBService instance
            
        Raises:
            AttributeError: If vector_store_type is not supported
            ImportError: If required service module is not available
        """
        if isinstance(vector_store_type, str):
            vector_store_type = getattr(SupportedVSType, vector_store_type.upper())
        
        params = {
            "knowledge_base_name": kb_name,
            "embed_model": embed_model,
            "kb_info": kb_info,
        }
        
        if SupportedVSType.MILVUS == vector_store_type:
            from vulcan.knowledge.core.kb.service.milvus_kb_service import MilvusKBService
            return MilvusKBService(**params)
        
        # Add other vector store types here in the future
        # elif SupportedVSType.FAISS == vector_store_type:
        #     from vulcan.knowledge.core.kb.service.faiss_kb_service import FaissKBService
        #     return FaissKBService(**params)
        #
        # elif SupportedVSType.CHROMA == vector_store_type:
        #     from vulcan.knowledge.core.kb.service.chroma_kb_service import ChromaKBService
        #     return ChromaKBService(**params)
        
        else:
            raise ValueError(f"Unsupported vector store type: {vector_store_type}")

    @staticmethod
    def get_service_by_name(kb_name: str) -> KBService:
        """
        Get a KB service instance by name, reading configuration from config files
        
        Args:
            kb_name: Knowledge base name
            
        Returns:
            KBService instance or None if configuration doesn't match
        """
        try:
            # Read configuration directly from config
            vs_type = Configs.kb_config.default_vs_type
            embed_model = Configs.kb_config.embedding_model
            
            # Create and return service instance
            return KBServiceFactory.get_service(kb_name, vs_type, embed_model)
            
        except AttributeError as e:
            print(f"Configuration error: {e}")
            return None
        except Exception as e:
            print(f"Error creating KB service for '{kb_name}': {e}")
            return None


# Utility functions (if needed)
def get_available_vs_types() -> List[str]:
    """
    Get list of available vector store types
    
    Returns:
        List of supported vector store type strings
    """
    return [getattr(SupportedVSType, attr) for attr in dir(SupportedVSType) 
            if not attr.startswith('_')]


def validate_kb_config(kb_name: str) -> bool:
    """
    Validate if knowledge base configuration is valid
    
    Args:
        kb_name: Knowledge base name to validate
        
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        service = KBServiceFactory.get_service_by_name(kb_name)
        return service is not None
    except Exception:
        return False