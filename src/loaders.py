import os
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
)

os.environ["USER_AGENT"] = "DocumentRAGChatbot/1.0"


def load_pdf(file_path: str):
    loader = PyPDFLoader(file_path)
    return loader.load()


def load_text(file_path: str):
    loader = TextLoader(file_path, encoding="utf-8")
    return loader.load()


def load_doc(file_path: str):
    loader = Docx2txtLoader(file_path)
    return loader.load()


def load_web(url: str):
    loader = WebBaseLoader(url)
    return loader.load()