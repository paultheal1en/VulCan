from typing import Optional
from strands import tool
from rich.console import Console

# Import các thành phần cần thiết từ hệ thống RAG và Configs
from vulcan.config.config import Configs
from vulcan.knowledge.core.kb.base import KBServiceFactory
from vulcan.knowledge.core.reranker.reranker import LangchainReranker

console = Console()

# Biến cache để lưu các đối tượng đã được khởi tạo, tránh tải lại liên tục
_kb_service_cache = {}
_reranker_model_cache = None

@tool
def query_knowledge_base(
    query: str,
    knowledge_base_name: Optional[str] = None
) -> str:
    """
    Searches the specified knowledge base for information on a specific topic.
    Use this when you encounter a technology, tool, vulnerability, or error message
    that you need more information about before proceeding with your plan.

    Args:
        query: Your specific question (e.g., "what are common exploits for Apache 2.4.52?").
        knowledge_base_name: The name of the knowledge base to search. If None, uses the default from config.
    """
    global _reranker_model_cache

    console.print(f"[cyan]KB Tool: Received query for knowledge base.[/cyan]")
    console.print(f"  Query: '{query}'")

    kb_name = knowledge_base_name or Configs.kb_config.kb_name
    if not kb_name:
        return "Error: No knowledge base name specified and no default is configured."
    
    console.print(f"  Target KB: '{kb_name}'")

    try:
        # 1. Tải KB Service (từ cache hoặc tạo mới)
        if kb_name not in _kb_service_cache:
            kb_service = KBServiceFactory.get_service_by_name(kb_name)
            if not kb_service:
                return f"Error: Knowledge base '{kb_name}' not found."
            _kb_service_cache[kb_name] = kb_service
        
        kb_service = _kb_service_cache[kb_name]
        
        # 2. Thực hiện tìm kiếm ban đầu (Retrieval)
        console.print(f"  Step 1: Retrieving top {Configs.kb_config.top_k} documents...")
        docs = kb_service.search_docs(
            query=query,
            top_k=Configs.kb_config.top_k,
            score_threshold=Configs.kb_config.score_threshold
        )

        if not docs:
            return f"No relevant information found in knowledge base '{kb_name}' for query: '{query}'"
        
        console.print(f"  Found {len(docs)} initial documents.")

        # 3. Sắp xếp lại (Reranking) để tìm kết quả tốt nhất
        console.print(f"  Step 2: Reranking results to find top {Configs.kb_config.top_n}...")
        if _reranker_model_cache is None:
            # Thêm import ở đây để tránh lỗi import không tìm thấy
            from langchain_core.documents import Document # Thêm import
            _reranker_model_cache = LangchainReranker(
                name_or_path=Configs.kb_config.rerank_model_name,
                top_n=Configs.kb_config.top_n
            )

        # Chuyển đổi docs nhận được từ Milvus thành định dạng Langchain Document
        docs_for_reranker = [Document(page_content=doc.page_content, metadata=doc.metadata) for doc in docs]
        reranked_docs = _reranker_model_cache.compress_documents(documents=docs_for_reranker, query=query)
        if not reranked_docs:
            return f"No highly relevant information found after reranking for query: '{query}'"

        console.print(f"  Reranking complete. Best match found.")
        
        # 4. Định dạng kết quả trả về cho Agent
        best_doc = reranked_docs[0]
        source = best_doc.metadata.get('source', 'N/A')
        content = best_doc.page_content
        
        formatted_result = f"**Relevant Information from Knowledge Base (Source: {source}):**\n\n---\n{content}\n---"
        
        return formatted_result

    except Exception as e:
        import traceback
        console.print(f"[red]Error querying knowledge base: {e}[/red]")
        console.print(traceback.format_exc())
        return f"Error querying knowledge base: An internal error occurred."