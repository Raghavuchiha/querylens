import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from collections import Counter

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from ingestion import SUPPORTED_EXTENSIONS, get_extension, ingest_multiple_documents
from query_rewrite import rewrite_query_with_history
from synthesis import synthesize_answer
from vectorstore import HybridIndex

app = FastAPI()

UPLOAD_DIR = "uploaded_files"
TOP_K = 5
MAX_HISTORY_MESSAGES = 10  # keep an even number so history starts with a user turn

# In-memory state (lost on restart; fine for a demo, use a DB for production)
index = HybridIndex()
all_documents = []
doc_name_lookup = {}
seen_hashes = {}  # sha256 of file content -> doc_id (used to skip duplicates)
chat_histories = {}  # conversation_id -> list of messages
upload_lock = threading.Lock()


class QueryRequest(BaseModel):
    query: str
    conversation_id: str = "default"


def safe_filename(name: str) -> str:
    """Strip any directory part and unsafe characters from an uploaded filename."""
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name


@app.post("/upload")
def upload_documents(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("official")
):
    saved_files = []  # (path, doc_type)
    path_info = {}    # path -> (original filename, content hash)
    batch_hashes = set()
    skipped = []
    errors = []

    with upload_lock:
        for file in files:
            filename = safe_filename(file.filename)

            if not filename or get_extension(filename) not in SUPPORTED_EXTENSIONS:
                errors.append(
                    {"file": file.filename, "error": "Unsupported or invalid file type"}
                )
                continue

            content = file.file.read()
            content_hash = hashlib.sha256(content).hexdigest()

            if content_hash in seen_hashes or content_hash in batch_hashes:
                skipped.append({"file": filename, "reason": "Already uploaded"})
                continue

            # Each upload gets its own folder: no name collisions, no path tricks
            folder = os.path.join(UPLOAD_DIR, uuid.uuid4().hex)
            os.makedirs(folder, exist_ok=True)
            file_path = os.path.join(folder, filename)

            with open(file_path, "wb") as f:
                f.write(content)

            batch_hashes.add(content_hash)
            saved_files.append((file_path, doc_type))
            path_info[file_path] = (filename, content_hash)

        documents, chunks, ingest_errors = ingest_multiple_documents(saved_files)

        failed_paths = {path for path, _ in ingest_errors}
        for path, message in ingest_errors:
            errors.append({"file": path_info[path][0], "error": message})
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)  # don't keep unusable files

        index.add_chunks(chunks)
        all_documents.extend(documents)

        # documents come back in the same order as the files that ingested fine
        ok_paths = [p for p, _ in saved_files if p not in failed_paths]
        for path, document in zip(ok_paths, documents):
            doc_name_lookup[document.doc_id] = document.name
            seen_hashes[path_info[path][1]] = document.doc_id

    if not documents and (errors or skipped):
        raise HTTPException(
            status_code=400,
            detail={"message": "No documents were added", "errors": errors, "skipped": skipped},
        )

    return {
        "message": f"Uploaded {len(documents)} documents",
        "chunks": len(chunks),
        "document_ids": [doc.doc_id for doc in documents],
        "skipped": skipped,
        "errors": errors,
    }


@app.post("/query")
def query_documents(request: QueryRequest):
    if len(index) == 0:
        return {
            "answer": "No documents have been uploaded yet. Please upload a document first.",
            "citations": [],
        }

    query = request.query
    history = chat_histories.setdefault(request.conversation_id, [])

    try:
        standalone_query = rewrite_query_with_history(
            query, history[-MAX_HISTORY_MESSAGES:]
        )
        results = index.search(standalone_query, top_k=TOP_K)
        answer = synthesize_answer(standalone_query, results, doc_name_lookup)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Query failed: {e}")

    history.append(HumanMessage(content=query))
    history.append(AIMessage(content=answer.text))

    return {
        "answer": answer.text,
        "citations": [c.model_dump() for c in answer.citations],
    }


@app.get("/documents")
def list_documents():
    chunk_counts = Counter(c.doc_id for c in index.chunks)

    return {
        "documents": [
            {
                "doc_id": doc.doc_id,
                "name": doc.name,
                "doc_type": doc.doc_type,
                "chunk_count": chunk_counts.get(doc.doc_id, 0),
            }
            for doc in all_documents
        ]
    }


@app.get("/evaluation/metrics")
def get_metrics():
    if not os.path.exists("evaluation_results.json"):
        return {"message": "No evaluation results found. Run the eval script first."}

    with open("evaluation_results.json", "r") as f:
        return json.load(f)
