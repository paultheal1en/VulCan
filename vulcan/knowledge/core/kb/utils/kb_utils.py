import importlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Generator, List, Tuple, Union

import chardet
from langchain.docstore.document import Document
from langchain.text_splitter import TextSplitter
from langchain_community.document_loaders import JSONLoader, TextLoader

from vulcan.config.config import Configs


def validate_kb_name(knowledge_base_id: str) -> bool:
    # Check for unexpected characters or path attack keywords
    if "../" in knowledge_base_id:
        return False
    return True


def get_kb_path(knowledge_base_name: str):
    return os.path.join(Configs.basic_config.KB_ROOT_PATH, knowledge_base_name)


def get_doc_path(knowledge_base_name: str):
    return os.path.join(get_kb_path(knowledge_base_name), "content")


def get_vs_path(knowledge_base_name: str, vector_name: str):
    return os.path.join(get_kb_path(knowledge_base_name), "vector_store", vector_name)


def get_file_path(knowledge_base_name: str, doc_name: str):
    doc_path = Path(get_doc_path(knowledge_base_name)).resolve()
    file_path = (doc_path / doc_name).resolve()
    if str(file_path).startswith(str(doc_path)):
        return str(file_path)


def list_kbs_from_folder():
    return [
        f
        for f in os.listdir(Configs.basic_config.KB_ROOT_PATH)
        if os.path.isdir(os.path.join(Configs.basic_config.KB_ROOT_PATH, f))
    ]


def list_files_from_folder(kb_name: str):
    doc_path = get_doc_path(kb_name)
    result = []

    def is_skiped_path(path: str):
        tail = os.path.basename(path).lower()
        for x in ["temp", "tmp", ".", "~$"]:
            if tail.startswith(x):
                return True
        return False

    def process_entry(entry):
        if is_skiped_path(entry.path):
            return

        if entry.is_symlink():
            target_path = os.path.realpath(entry.path)
            with os.scandir(target_path) as target_it:
                for target_entry in target_it:
                    process_entry(target_entry)
        elif entry.is_file():
            file_path = Path(
                os.path.relpath(entry.path, doc_path)
            ).as_posix()  # Path统一为posix格式
            result.append(file_path)
        elif entry.is_dir():
            with os.scandir(entry.path) as it:
                for sub_entry in it:
                    process_entry(sub_entry)

    with os.scandir(doc_path) as it:
        for entry in it:
            process_entry(entry)

    return result


LOADER_DICT = {
    "UnstructuredHTMLLoader": [".html", ".htm"],
    "MHTMLLoader": [".mhtml"],
    "TextLoader": [".md"],
    "UnstructuredMarkdownLoader": [".md"],
    "JSONLoader": [".json"],
    "JSONLinesLoader": [".jsonl"],
    "CSVLoader": [".csv"],
    "RapidOCRPDFLoader": [".pdf"],
    "RapidOCRDocLoader": [".docx"],
    "RapidOCRPPTLoader": [
        ".ppt",
        ".pptx",
    ],
    "RapidOCRLoader": [".png", ".jpg", ".jpeg", ".bmp"],
    "UnstructuredLoader": [
        ".eml",
        ".msg",
        ".rst",
        ".rtf",
        ".txt",
        ".xml",
        ".epub",
        ".odt",
        ".tsv",
    ],
    "UnstructuredEmailLoader": [".eml", ".msg"],
    "UnstructuredEPubLoader": [".epub"],
    "UnstructuredExcelLoader": [".xlsx", ".xls", ".xlsd"],
    "NotebookLoader": [".ipynb"],
    "UnstructuredODTLoader": [".odt"],
    "PythonLoader": [".py"],
    "UnstructuredRSTLoader": [".rst"],
    "UnstructuredRTFLoader": [".rtf"],
    "SRTLoader": [".srt"],
    "TomlLoader": [".toml"],
    "UnstructuredTSVLoader": [".tsv"],
    "UnstructuredWordDocumentLoader": [".docx"],
    "UnstructuredXMLLoader": [".xml"],
    "UnstructuredPowerPointLoader": [".ppt", ".pptx"],
    "EverNoteLoader": [".enex"],
}
SUPPORTED_EXTS = [ext for sublist in LOADER_DICT.values() for ext in sublist]


# patch json.dumps to disable ensure_ascii
def _new_json_dumps(obj, **kwargs):
    kwargs["ensure_ascii"] = False
    return _origin_json_dumps(obj, **kwargs)


if json.dumps is not _new_json_dumps:
    _origin_json_dumps = json.dumps
    json.dumps = _new_json_dumps


class JSONLinesLoader(JSONLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._json_lines = True


def get_LoaderClass(file_extension):
    for LoaderClass, extensions in LOADER_DICT.items():
        if file_extension in extensions:
            return LoaderClass


def get_loader(loader_name: str, file_path: str, loader_kwargs: Dict = None):
    """
    Get a document loader based on the loader name and file path or content.
    """
    loader_kwargs = loader_kwargs or {}
    try:
        if loader_name in [
            "RapidOCRPDFLoader",
            "RapidOCRLoader",
            "FilteredCSVLoader",
            "RapidOCRDocLoader",
            "RapidOCRPPTLoader",
        ]:
            document_loaders_module = importlib.import_module(
                "vulcan.knowledge.core.parsers"
            )
        else:
            document_loaders_module = importlib.import_module(
                "langchain_community.document_loaders"
            )
        DocumentLoader = getattr(document_loaders_module, loader_name)
    except Exception as e:
        msg = f"Failed to find loader {loader_name} for file {file_path}: {e}"
        # logger.error(f"{e.__class__.__name__}: {msg}")
        print(f"{e.__class__.__name__}: {msg}\n")
        document_loaders_module = importlib.import_module("langchain_unstructured")
        DocumentLoader = getattr(document_loaders_module, "UnstructuredLoader")

    if loader_name == "UnstructuredLoader":
        loader_kwargs.setdefault("autodetect_encoding", True)
    elif loader_name == "CSVLoader":
        if not loader_kwargs.get("encoding"):
            # If encoding is not specified, automatically identify the file encoding type to avoid encoding errors when loading files with langchain loader
            with open(file_path, "rb") as struct_file:
                encode_detect = chardet.detect(struct_file.read())
            if encode_detect is None:
                encode_detect = {"encoding": "utf-8"}
            loader_kwargs["encoding"] = encode_detect["encoding"]

    elif loader_name == "JSONLoader":
        loader_kwargs.setdefault("jq_schema", ".")
        loader_kwargs.setdefault("text_content", False)
    elif loader_name == "JSONLinesLoader":
        loader_kwargs.setdefault("jq_schema", ".")
        loader_kwargs.setdefault("text_content", False)

    loader = DocumentLoader(file_path, **loader_kwargs)
    return loader


@lru_cache()
def make_text_splitter(splitter_name, chunk_size, chunk_overlap):
    """
    Get a specific text splitter based on the parameters.
    """
    splitter_name = splitter_name or "SpacyTextSplitter"
    try:
        text_splitter_module = importlib.import_module("langchain.text_splitter")
        TextSplitter = getattr(text_splitter_module, splitter_name)

        if (
            Configs.kb_config.text_splitter_dict[splitter_name]["source"] == "tiktoken"
        ):  # Load from tiktoken
            try:
                text_splitter = TextSplitter.from_tiktoken_encoder(
                    encoding_name=Configs.kb_config.text_splitter_dict[splitter_name][
                        "tokenizer_name_or_path"
                    ],
                    pipeline="zh_core_web_sm",
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
            except:
                text_splitter = TextSplitter.from_tiktoken_encoder(
                    encoding_name=Configs.kb_config.text_splitter_dict[splitter_name][
                        "tokenizer_name_or_path"
                    ],
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
        elif (
            Configs.kb_config.text_splitter_dict[splitter_name]["source"]
            == "huggingface"
        ):  # Load from huggingface
            if (
                Configs.kb_config.text_splitter_dict[splitter_name][
                    "tokenizer_name_or_path"
                ]
                == "gpt2"
            ):
                from langchain.text_splitter import CharacterTextSplitter
                from transformers import GPT2TokenizerFast

                tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
            else:  # Character length loading
                from transformers import AutoTokenizer

                tokenizer = AutoTokenizer.from_pretrained(
                    Configs.kb_config.text_splitter_dict[splitter_name][
                        "tokenizer_name_or_path"
                    ],
                    trust_remote_code=True,
                )
            text_splitter = TextSplitter.from_huggingface_tokenizer(
                tokenizer=tokenizer,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

    except Exception as e:
        print(e)
        text_splitter_module = importlib.import_module("langchain.text_splitter")
        TextSplitter = getattr(text_splitter_module, "RecursiveCharacterTextSplitter")
        text_splitter = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    return text_splitter


class KnowledgeFile:
    def __init__(
        self,
        filename: str,
        knowledge_base_name: str,
        loader_kwargs: Dict = {},
    ):
        """
        Corresponding knowledge base directory file, must exist on disk to perform vectorization and other operations.
        """
        self.kb_name = knowledge_base_name
        self.filename = str(Path(filename).as_posix())
        self.ext = os.path.splitext(filename)[-1].lower()
        if self.ext not in SUPPORTED_EXTS:
            raise ValueError(f"Unsupported file format {self.filename}")
        self.loader_kwargs = loader_kwargs
        self.filepath = get_file_path(knowledge_base_name, filename)
        self.docs = None
        self.splited_docs = None
        self.document_loader_name = get_LoaderClass(self.ext)
        self.text_splitter_name = Configs.kb_config.text_splitter_name

    def file2docs(self, refresh: bool = False):
        if self.docs is None or refresh:
            # logger.info(f"{self.document_loader_name} used for {self.filepath}")
            print(f"{self.document_loader_name} used for {self.filepath}\n")
            loader = get_loader(
                loader_name=self.document_loader_name,
                file_path=self.filepath,
                loader_kwargs=self.loader_kwargs,
            )
            if isinstance(loader, TextLoader):
                loader.encoding = "utf8"
                self.docs = loader.load()
            else:
                self.docs = loader.load()
        return self.docs

    def docs2texts(
        self,
        docs: List[Document] = None,
        refresh: bool = False,
        chunk_size: int = Configs.kb_config.chunk_size,
        chunk_overlap: int = Configs.kb_config.overlap_size,
        text_splitter: TextSplitter = None,
    ):
        docs = docs or self.file2docs(refresh=refresh)
        if not docs:
            return []
        if self.ext not in [".csv"]:
            if text_splitter is None:
                text_splitter = make_text_splitter(
                    splitter_name=self.text_splitter_name,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                docs = text_splitter.split_documents(docs)

        if not docs:
            return []

        print(f"Document split example: {docs[0]}")
        self.splited_docs = docs
        return self.splited_docs

    def file2text(
        self,
        refresh: bool = False,
        chunk_size: int = Configs.kb_config.chunk_size,
        chunk_overlap: int = Configs.kb_config.overlap_size,
        text_splitter: TextSplitter = None,
    ):
        if self.splited_docs is None or refresh:
            docs = self.file2docs()
            self.splited_docs = self.docs2texts(
                docs=docs,
                refresh=refresh,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                text_splitter=text_splitter,
            )
        return self.splited_docs

    def file_exist(self):
        return os.path.isfile(self.filepath)

    def get_mtime(self):
        return os.path.getmtime(self.filepath)

    def get_size(self):
        return os.path.getsize(self.filepath)


def files2docs_in_thread_file2docs(
    *, file: KnowledgeFile, **kwargs
) -> Tuple[bool, Tuple[str, str, List[Document]]]:
    try:
        return True, (file.kb_name, file.filename, file.file2text(**kwargs))
    except Exception as e:
        msg = f"Failed to load document from file {file.kb_name}/{file.filename}: {e}"
        # logger.error(f"{e.__class__.__name__}: {msg}")
        print(f"{e.__class__.__name__}: {msg}\n")
        return False, (file.kb_name, file.filename, msg)


def files2docs_in_thread(
    files: List[Union[KnowledgeFile, Tuple[str, str], Dict]],
    chunk_size: int = Configs.kb_config.chunk_size,
    chunk_overlap: int = Configs.kb_config.overlap_size,
) -> Generator:
    """
    Utilize multi-threading to batch convert disk files into langchain Document.
    If the input parameter is Tuple, the form is (filename, kb_name)
    Generator returns status, (kb_name, file_name, docs | error)
    """

    kwargs_list = []
    for i, file in enumerate(files):
        kwargs = {}
        try:
            if isinstance(file, tuple) and len(file) >= 2:
                filename = file[0]
                kb_name = file[1]
                file = KnowledgeFile(filename=filename, knowledge_base_name=kb_name)
            elif isinstance(file, dict):
                filename = file.pop("filename")
                kb_name = file.pop("kb_name")
                kwargs.update(file)
                file = KnowledgeFile(filename=filename, knowledge_base_name=kb_name)
            kwargs["file"] = file
            kwargs["chunk_size"] = chunk_size
            kwargs["chunk_overlap"] = chunk_overlap
            kwargs_list.append(kwargs)
        except Exception as e:
            yield False, (kb_name, filename, str(e))

    for result in run_in_thread_pool(
        func=files2docs_in_thread_file2docs, params=kwargs_list
    ):
        yield result


def run_in_thread_pool(
    func: Callable,
    params: List[Dict] = [],
) -> Generator:
    """
    Run tasks in thread pool and return results as a generator.
    Please ensure that all operations in the task are thread-safe and that the task function uses keyword arguments.
    """
    tasks = []
    with ThreadPoolExecutor() as pool:
        for kwargs in params:
            tasks.append(pool.submit(func, **kwargs))

        for obj in as_completed(tasks):
            try:
                yield obj.result()
            except Exception as e:
                print(f"error in sub thread: {e}\n")
                # logger.exception(f"error in sub thread: {e}")
