import json
import os
import uuid
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from ingestion import ingest_multiple_documents, SUPPORTED_EXTENSIONS, get_extension
from synthesis import synthesize_answer
from vectorstore import HybridIndex
from query_rewrite import rewrite_query_with_history
from models import Document, Chunk


app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "upload_files")
DATA_FILE = os.path.join(BASE_DIR, "index_data.json")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file

index = HybridIndex()
all_documents = []
doc_name_lookup = {}
chat_histories = {}


def save_index():
    data = {
        "documents": [doc.model_dump() for doc in all_documents],
        "chunks": [chunk.model_dump() for chunk in index.chunks],
    }
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(temp_file, DATA_FILE)


def load_index():
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        documents = [Document(**doc) for doc in data.get("documents", [])]
        chunks = [Chunk(**chunk) for chunk in data.get("chunks", [])]
        index.add_chunks(chunks)
        all_documents.extend(documents)
        for doc in documents:
            doc_name_lookup[doc.doc_id] = doc.name
    except Exception as e:
        print("Could not load previous index:", e)


load_index()


class QueryRequest(BaseModel):
    query: str
    conversation_id: str = "default"


@app.post("/upload")
def upload_documents(files: list[UploadFile] = File(...), doc_type: str = Form("official")):
    saved_files = []
    errors = []

    # Save valid files temporarily
    for file in files:
        filename = os.path.basename((file.filename or "").replace("\\", "/"))
        if get_extension(filename) not in SUPPORTED_EXTENSIONS:
            errors.append({"file": filename, "error": "Unsupported file type"})
            continue

        path = os.path.join(UPLOAD_DIR, uuid.uuid4().hex, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        size = 0
        too_large = False

        try:
            with open(path, "wb") as f:
                while True:
                    part = file.file.read(1024 * 1024)
                    if not part:
                        break
                    size += len(part)
                    if size > MAX_FILE_SIZE:
                        too_large = True
                        break
                    f.write(part)

            if too_large or size == 0:
                errors.append({"file": filename, "error": "File is empty or exceeds 10 MB"})
                os.remove(path)
            else:
                saved_files.append((path, doc_type))
        finally:
            file.file.close()

    documents, chunks, ingest_errors = ingest_multiple_documents(saved_files)
    errors.extend({"file": os.path.basename(path), "error": message} for path, message in ingest_errors)

    # Files are no longer needed after text extraction
    for path, _ in saved_files:
        if os.path.exists(path):
            os.remove(path)
        os.rmdir(os.path.dirname(path))

    if chunks:
        try:
            index.add_chunks(chunks)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Could not index documents: " + str(e))

        all_documents.extend(documents)
        for doc in documents:
            doc_name_lookup[doc.doc_id] = doc.name
        save_index()

    return {"documents": len(documents), "chunks": len(chunks), "errors": errors}


@app.post("/query")
def query_documents(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    if len(index) == 0:
        return {"answer": "Please upload a document first.", "citations": []}

    history = chat_histories.setdefault(request.conversation_id, [])
    query = rewrite_query_with_history(request.query, history[-10:])

    try:
        results = index.search(query, top_k=5)
        answer = synthesize_answer(query, results, doc_name_lookup)
    except Exception as e:
        print("Query failed:", e)
        raise HTTPException(status_code=503, detail="Could not generate an answer. Please try again.")

    history.append(HumanMessage(content=request.query))
    history.append(AIMessage(content=answer.text))

    # Keep only recent messages in memory
    chat_histories[request.conversation_id] = history[-20:]

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
    path = os.path.join(BASE_DIR, "evaluation_results.json")
    if not os.path.exists(path):
        return {"message": "No evaluation results found. Run the eval script first."}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
