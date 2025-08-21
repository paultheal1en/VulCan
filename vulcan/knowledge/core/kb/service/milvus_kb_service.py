from typing import List, Dict
from langchain.schema import Document
from pymilvus import MilvusClient

from vulcan.config.config import Configs
from vulcan.knowledge.core.embedding.embedding import get_embeddings
from vulcan.knowledge.core.kb.base import KBService, SupportedVSType # Thêm import
from vulcan.utils.log_common import build_logger

logger = build_logger("MilvusKBService")

class MilvusKBService(KBService):
    client: MilvusClient

    def do_init(self):
        try:
            milvus_config = Configs.kb_config.milvus
            self.client = MilvusClient(uri=milvus_config.get("uri"), token=milvus_config.get("password"))
            logger.info("Successfully connected to Zilliz Cloud.")
        except Exception as e:
            logger.error(f"Failed to connect to Zilliz Cloud: {e}")
            raise

    def vs_type(self) -> str:
        return SupportedVSType.MILVUS
    
    def do_search(self, query: str, top_k: int, score_threshold: float) -> List[Document]:
        try:
            embedding_func = get_embeddings() # Không cần truyền tên model nữa
            query_vector = embedding_func.embed_query(query)
            
            search_params = {"metric_type": "COSINE", "params": {}}

            results = self.client.search(
                collection_name=self.kb_name,
                data=[query_vector],
                limit=top_k,
                search_params=search_params,
                output_fields=["text", "source_path"]
            )
            
            docs = []
            if results and results[0]:
                for hit in results[0]:
                    similarity = 1 - hit.distance
                    if similarity >= score_threshold:
                        metadata = hit.entity.to_dict() if hasattr(hit.entity, 'to_dict') else hit.entity
                        metadata['relevance_score'] = similarity
                        metadata.pop("embedding", None)
                        docs.append(Document(page_content=metadata.pop('text', ''), metadata=metadata))
            return docs
        except Exception as e:
            logger.error(f"Error during Milvus search: {e}")
            if "not loaded" in str(e):
                logger.info(f"Attempting to load collection '{self.kb_name}'...")
                self.client.load_collection(self.kb_name)
                return self.do_search(query, top_k, score_threshold)
            return []
    
    # Các hàm placeholder khác
    def do_create_kb(self): pass
    def do_drop_kb(self): pass
    def do_add_doc(self, docs: List[Document], **kwargs) -> List[Dict]: return []
    def do_delete_doc(self, kb_file, **kwargs): pass
    def do_clear_vs(self): pass