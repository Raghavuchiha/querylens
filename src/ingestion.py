import uuid
import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import Document, Chunk
from loaders import load_pdf, load_text, load_doc


def load_documents_from_folder(folder_path, doc_type):
    file_list = []
    all_files = os.listdir(folder_path)

    for file_name in all_files:
        full_path = os.path.join(folder_path, file_name)
        file_list.append((full_path, doc_type))

    return file_list


def ingest_document(file_path: str, doc_type: str) -> tuple[Document, list[Chunk]]:
    # 1. Load raw text using the right loader based on file extension
    if file_path.endswith(".pdf"):
        raw_docs = load_pdf(file_path)
    elif file_path.endswith(".txt") or file_path.endswith(".md"):
        raw_docs = load_text(file_path)
    elif file_path.endswith(".docx"):
        raw_docs = load_doc(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_path}")

    # 2. Combine all pages/parts into one big string
    full_text = "\n".join([d.page_content for d in raw_docs])

    # 3. Build our own Document (metadata record)
    doc_id = str(uuid.uuid4())
    document = Document(
        doc_id=doc_id,
        name=file_path.split("/")[-1],
        doc_type=doc_type,
    )

    # 4. Split into overlapping chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=128,
    )
    text_chunks = splitter.split_text(full_text)

    # 5. Wrap each piece of text into our Chunk model
    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                text=chunk_text,
                chunk_index=i,
            )
        )

    return document, chunks


def ingest_multiple_documents(file_list):
    all_documents = []
    all_chunks = []

    for item in file_list:
        file_path = item[0]
        doc_type = item[1]

        result = ingest_document(file_path, doc_type)
        document = result[0]
        chunks = result[1]

        all_documents.append(document)

        for chunk in chunks:
            all_chunks.append(chunk)

    return all_documents, all_chunks