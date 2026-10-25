import os
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from loaders import load_doc, load_pdf, load_text
from models import Chunk, Document

LOADERS = {
    ".pdf": load_pdf,
    ".txt": load_text,
    ".md": load_text,
    ".docx": load_doc,
}
SUPPORTED_EXTENSIONS = set(LOADERS)

splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)


def get_extension(file_path: str) -> str:
    return os.path.splitext(file_path)[1].lower()


def ingest_document(file_path: str, doc_type: str) -> tuple[Document, list[Chunk]]:
    # 1. Load raw text using the right loader (case-insensitive extension)
    ext = get_extension(file_path)
    if ext not in LOADERS:
        raise ValueError(f"Unsupported file type: {file_path}")
    raw_docs = LOADERS[ext](file_path)

    # 2. Build our own Document (metadata record)
    doc_id = str(uuid.uuid4())
    document = Document(
        doc_id=doc_id,
        name=os.path.basename(file_path),
        doc_type=doc_type,
    )

    # 3. Split each page/part separately so every chunk keeps its page number
    chunks = []
    chunk_index = 0
    for raw in raw_docs:
        page = raw.metadata.get("page")
        page = page + 1 if isinstance(page, int) else None  # PyPDF pages are 0-based

        for chunk_text in splitter.split_text(raw.page_content):
            if not chunk_text.strip():
                continue
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    page=page,
                )
            )
            chunk_index += 1

    if not chunks:
        raise ValueError("No extractable text found (scanned or empty file?)")

    return document, chunks


def ingest_multiple_documents(file_list):
    """Ingest (file_path, doc_type) pairs. A bad file doesn't stop the others.

    Returns (documents, chunks, errors) where errors is a list of
    (file_path, message) tuples.
    """
    all_documents = []
    all_chunks = []
    errors = []

    for file_path, doc_type in file_list:
        try:
            document, chunks = ingest_document(file_path, doc_type)
        except Exception as e:
            errors.append((file_path, str(e)))
            continue

        all_documents.append(document)
        all_chunks.extend(chunks)

    return all_documents, all_chunks, errors
