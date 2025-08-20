import asyncio
import json
import os
import urllib
from typing import Dict, List, Any

from fastapi import Body, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from langchain.docstore.document import Document

from config.config import Configs
from rag.kb.base import KBServiceFactory, get_kb_file_details
from rag.kb.models.kb_document_model import MatchDocument
from rag.kb.repository.knowledge_file_repository import get_file_detail
from rag.kb.utils.kb_utils import validate_kb_name, KnowledgeFile, get_file_path, run_in_thread_pool, \
    files2docs_in_thread
from server.utils.utils import BaseResponse, ListResponse
from utils.log_common import build_logger
from io import BytesIO


logger = build_logger()

def search_docs(
        query: str = Body("", description="User input", examples=["hello"]),
        knowledge_base_name: str = Body(
            ..., description="Knowledge base name", examples=["samples"]
        ),
        top_k: int = Body(Configs.kb_config.top_k, description="Number of matches"),
        score_threshold: float = Body(
            Configs.kb_config.score_threshold,
            description="Knowledge base matching relevance threshold, value range is 0-1,"
                        "The smaller the SCORE, the higher the relevance,"
                        "a value of 2 is equivalent to no filtering, recommended to set around 0.5.",
            ge=0.0,
            le=2.0,
        ),
        file_name: str = Body("", description="File name, supports SQL wildcards"),
        metadata: dict = Body({}, description="Filter based on metadata, only supports one level key"),
) -> List[Dict]:
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    data = []
    if kb is not None:
        if query:
            docs = kb.search_docs(query, top_k, score_threshold)
            data = [MatchDocument(**{"id": str(x.metadata.get("pk")), **{k: v for k, v in x.dict().items() if k != "id"}}) for x in docs]
        elif file_name or metadata:
            data = kb.list_docs(file_name=file_name, metadata=metadata)
            for d in data:
                if "vector" in d.metadata:
                    del d.metadata["vector"]
    return [x.dict() for x in data]


def list_files(knowledge_base_name: str) -> ListResponse:
    if not validate_kb_name(knowledge_base_name):
        return ListResponse(code=403, msg="Don't attack me", data=[])

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return ListResponse(
            code=404, msg=f"Knowledge base {knowledge_base_name} not found", data=[]
        )
    else:
        all_docs = get_kb_file_details(knowledge_base_name)
        return ListResponse(data=all_docs)


def _save_files_in_thread(
        files: List[UploadFile], knowledge_base_name: str, override: bool
):
    """
    Save uploaded files to the corresponding knowledge base directory through multi-threading.
    Generator returns save results: {"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        """
        Save a single file.
        """
        try:
            filename = file.filename
            file_path = get_file_path(
                knowledge_base_name=knowledge_base_name, doc_name=filename
            )
            data = {"knowledge_base_name": knowledge_base_name, "file_name": filename}

            file_content = file.file.read()  # 读取上传文件的内容
            if (
                    os.path.isfile(file_path)
                    and not override
                    and os.path.getsize(file_path) == len(file_content)
            ):
                file_status = f"File {filename} already exists."
                return dict(code=404, msg=file_status, data=data)

            if not os.path.isdir(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            with open(file_path, "wb") as f:
                f.write(file_content)
            return dict(code=200, msg=f"Successfully uploaded file {filename}", data=data)
        except Exception as e:
            msg = f"Failed to upload file {filename}, error message: {e}"
            logger.error(f"{e.__class__.__name__}: {msg}")
            return dict(code=500, msg=msg, data=data)

    params = [
        {"file": file, "knowledge_base_name": knowledge_base_name, "override": override}
        for file in files
    ]
    for result in run_in_thread_pool(save_file, params=params):
        yield result


def upload_docs(
        files: List[UploadFile] = File(..., description="Upload files, support multiple files"),
        knowledge_base_name: str = Form(
            ..., description="Knowledge base name", examples=["samples"]
        ),
        override: bool = Form(False, description="Override existing files"),
        to_vector_store: bool = Form(True, description="Whether to vectorize after uploading files"),
        chunk_size: int = Form(Configs.kb_config.chunk_size, description="Maximum length of a single text segment in the knowledge base"),
        chunk_overlap: int = Form(Configs.kb_config.overlap_size, description="Overlap length of adjacent text segments in the knowledge base"),
        docs: str = Form("", description="Custom docs, need to be converted to json string"),
        not_refresh_vs_cache: bool = Form(False, description="Do not save vector store (for FAISS)"),
) -> BaseResponse:
    """
    API interface: upload files and/or vectorize
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")

    docs = json.loads(docs) if docs else {}
    failed_files = {}
    file_names = list(docs.keys())

    # 先将上传的文件保存到磁盘
    for result in _save_files_in_thread(
            files, knowledge_base_name=knowledge_base_name, override=override
    ):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)

    # 对保存的文件进行向量化
    if to_vector_store:
        result = update_docs(
            knowledge_base_name=knowledge_base_name,
            file_names=file_names,
            override_custom_docs=True,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            docs=docs,
            not_refresh_vs_cache=True,
        )
        failed_files.update(result.data["failed_files"])
        if not not_refresh_vs_cache:
            kb.save_vector_store()

    return BaseResponse(
        code=200, msg="Successfully uploaded and vectorized files", data={"failed_files": failed_files}
    )

def update_docs(
        knowledge_base_name: str = Body(
            ..., description="Knowledge base name", examples=["samples"]
        ),
        file_names: List[str] = Body(
            ..., description="File names, supports multiple files", examples=[["file_name1", "text.txt"]]
        ),
        chunk_size: int = Body(Configs.kb_config.chunk_size, description="Maximum length of a single text segment in the knowledge base"),
        chunk_overlap: int = Body(Configs.kb_config.overlap_size, description="Overlap length of adjacent text segments in the knowledge base"),
        override_custom_docs: bool = Body(False, description="Override previous custom docs"),
        docs: str = Body("", description="Custom docs, need to be converted to json string"),
        not_refresh_vs_cache: bool = Body(False, description="Do not save vector store (for FAISS)"),
) -> BaseResponse:
    """
    Update knowledge base documents
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")

    failed_files = {}
    kb_files = []
    docs = json.loads(docs) if docs else {}

    # 生成需要加载docs的文件列表
    for file_name in file_names:
        file_detail = get_file_detail(kb_name=knowledge_base_name, filename=file_name)
        # 如果该文件之前使用了自定义docs，则根据参数决定略过或覆盖
        if file_detail.get("custom_docs") and not override_custom_docs:
            continue
        if file_name not in docs:
            try:
                kb_files.append(
                    KnowledgeFile(
                        filename=file_name, knowledge_base_name=knowledge_base_name
                    )
                )
            except Exception as e:
                msg = f"Failed to load document {file_name}, error: {e}"
                logger.error(f"{e.__class__.__name__}: {msg}")
                failed_files[file_name] = msg

    # 从文件生成docs，并进行向量化。
    # 这里利用了KnowledgeFile的缓存功能，在多线程中加载Document，然后传给KnowledgeFile
    for status, result in files2docs_in_thread(
            kb_files,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
    ):
        if status:
            kb_name, file_name, new_docs = result
            kb_file = KnowledgeFile(
                filename=file_name, knowledge_base_name=knowledge_base_name
            )
            kb_file.splited_docs = new_docs
            kb.update_doc(kb_file, not_refresh_vs_cache=True)
        else:
            kb_name, file_name, error = result
            failed_files[file_name] = error

    # 将自定义的docs进行向量化
    for file_name, v in docs.items():
        try:
            v = [x if isinstance(x, Document) else Document(**x) for x in v]
            kb_file = KnowledgeFile(
                filename=file_name, knowledge_base_name=knowledge_base_name
            )
            kb.update_doc(kb_file, docs=v, not_refresh_vs_cache=True)
        except Exception as e:
            msg = f"Failed to add custom docs for {file_name}, error: {e}"
            logger.error(f"{e.__class__.__name__}: {msg}")
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(
        code=200, msg=f"Successfully updated documents", data={"failed_files": failed_files}
    )


def delete_docs(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        file_names: List[str] = Body(..., examples=[["file_name.md", "test.txt"]]),
        delete_content: bool = Body(False),
        not_refresh_vs_cache: bool = Body(False, description="Do not save vector store (for FAISS)"),
) -> BaseResponse:
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    knowledge_base_name = urllib.parse.unquote(knowledge_base_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")

    failed_files = {}
    for file_name in file_names:
        if not kb.exist_doc(file_name):
            failed_files[file_name] = f"File {file_name} not found"

        try:
            kb_file = KnowledgeFile(
                filename=file_name, knowledge_base_name=knowledge_base_name
            )
            kb.delete_doc(kb_file, delete_content, not_refresh_vs_cache=True)
        except Exception as e:
            msg = f"Failed to delete file {file_name}, error: {e}"
            logger.error(f"{e.__class__.__name__}: {msg}")
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(
        code=200, msg=f"Successfully deleted files", data={"failed_files": failed_files}
    )


def update_info(
        knowledge_base_name: str = Body(
            ..., description="Knowledge base name", examples=["samples"]
        ),
        kb_info: str = Body(..., description="Knowledge base description", examples=["This is a knowledge base"]),
):
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")
    kb.update_info(kb_info)

    return BaseResponse(code=200, msg=f"Successfully updated knowledge base info", data={"kb_info": kb_info})




def download_doc(
        knowledge_base_name: str = Query(
            ..., description="Knowledge base name", examples=["samples"]
        ),
        file_name: str = Query(..., description="File name", examples=["test.txt"]),
        preview: bool = Query(False, description="Is: preview in browser; No: download"),
):
    """
    下载知识库文档
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"Knowledge base {knowledge_base_name} not found")

    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = None

    try:
        kb_file = KnowledgeFile(
            filename=file_name, knowledge_base_name=knowledge_base_name
        )

        if os.path.exists(kb_file.filepath):
            return FileResponse(
                path=kb_file.filepath,
                filename=kb_file.filename,
                media_type="multipart/form-data",
                content_disposition_type=content_disposition_type,
            )
    except Exception as e:
        msg = f"Failed to read file {kb_file.filename}, error: {e}"
        logger.error(f"{e.__class__.__name__}: {msg}")
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"Failed to read file {kb_file.filename}")


