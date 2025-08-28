from typing import Dict, List

from langchain.schema import Document
from pymilvus import MilvusClient

from vulcan.config.config import Configs
from vulcan.knowledge.core.embedding.embedding import get_embeddings
from vulcan.knowledge.core.kb.base import KBService, SupportedVSType  



class MilvusKBService(KBService):
    client: MilvusClient

    def do_init(self):
        try:
            uri = Configs.kb_config.ZILLIZ_CLOUD_URI or Configs.kb_config.milvus.get(
                "uri"
            )
            token = (
                Configs.kb_config.ZILLIZ_CLOUD_TOKEN
                or Configs.kb_config.milvus.get("password")
            )
            print(f"URI: {uri}\n TOKEN:{token}\n")
            self.client = MilvusClient(uri=uri, token=token)
            print("Successfully connected to Zilliz Cloud.\n")
        except Exception as e:
            print(f"Failed to connect to Zilliz Cloud: {e}\n")
            raise

    def vs_type(self) -> str:
        return SupportedVSType.MILVUS

    def do_search(
        self, query: str, top_k: int, score_threshold: float, context_window: int = 2
    ) -> List[Document]:
        try:
            embedding_func = get_embeddings()
            query_vector = embedding_func.encode(
                [query], convert_to_tensor=False
            ).tolist()

            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

            results = self.client.search(
                collection_name=self.kb_name,
                data=query_vector,
                anns_field="embedding",
                limit=top_k,
                search_params=search_params,
                output_fields=[
                    "text",
                    "source_path",
                    "file_type",
                    "chunk_idx",
                    "doc_id",
                ],
            )

            docs = []
            if results and results[0]:
                for hit in results[0]:
                    try:
                        similarity = 1 - hit.distance
                        if similarity >= score_threshold:
                            entity = hit.entity
                            doc_id = entity.get("doc_id")
                            chunk_idx = entity.get("chunk_idx")
                            source_path = entity.get("source_path")
                            file_type = entity.get("file_type", "unknown")

                            entity_data = hit.data.get("entity", {})
                            # Query các chunk liền kề
                            start_idx = max(0, chunk_idx - context_window)
                            end_idx = chunk_idx + context_window
                            expr = f'doc_id == "{doc_id}" and chunk_idx >= {start_idx} and chunk_idx <= {end_idx}'
                            context_chunks = self.client.query(
                                collection_name=self.kb_name,
                                filter=expr,
                                output_fields=["chunk_idx", "text"],
                            )

                            # Sort by chunk index
                            context_chunks.sort(key=lambda x: x["chunk_idx"])

                            # Combine all context text
                            full_context = "\n\n".join(
                                [chunk["text"] for chunk in context_chunks]
                            )

                            # Create metadata
                            metadata = {
                                "source_collection": self.kb_name,
                                "source_path": source_path,
                                "file_type": file_type,
                                "relevance_score": similarity,
                                "chunk_position": f"{chunk_idx + 1}/{context_chunks[-1]['chunk_idx'] + 1 if context_chunks else '?'}",
                                "total_context_chunks": len(context_chunks),
                            }
                            metadata["id"] = hit.id
                            # Create Document object
                            docs.append(
                                Document(page_content=full_context, metadata=metadata)
                            )
                    except Exception as e:
                        print(f"Error processing a Milvus search hit: {e}\n")
                        continue 

            return docs
        except Exception as e:
            print(f"Error during Milvus search: {e}")
            if "not loaded" in str(e):
                print(f"Attempting to load collection '{self.kb_name}'...\n")
                self.client.load_collection(self.kb_name)
                return self.do_search(query, top_k, score_threshold)
            return []

    # Các hàm placeholder khác
    def do_create_kb(self):
        pass

    def do_drop_kb(self):
        pass

    def do_add_doc(self, docs: List[Document], **kwargs) -> List[Dict]:
        return []

    def do_delete_doc(self, kb_file, **kwargs):
        pass

    def do_clear_vs(self):
        pass
