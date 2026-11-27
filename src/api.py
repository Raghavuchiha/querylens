import json
import os
import uuid
import threading
import requests
from dotenv import load_dotenv
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from ingestion import ingest_multiple_documents, SUPPORTED_EXTENSIONS, get_extension
from synthesis import synthesize_answer
from pgvector_store import PgVectorStore
from query_rewrite import rewrite_query_with_history
from models import Document, Chunk


load_dotenv()
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# Set CORS_ORIGINS to the deployed Vercel origin (comma-separated for multiple).
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "upload_files")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file

# Chat history remains process-local; documents and vectors are durable.
chat_histories = {}
data_lock = threading.RLock()


def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in.")

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured.")

    try:
        response = requests.get(
            url + "/auth/v1/user",
            headers={"apikey": key, "Authorization": authorization},
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Unable to verify login.")

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Login expired. Please sign in again.")

    user_id = response.json().get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user session.")
    return user_id


class QueryRequest(BaseModel):
    query: str
    conversation_id: str = "default"


@app.post("/upload")
def upload_documents(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("official"),
    conversation_id: str = Form("default"),
    user_id: str = Depends(get_current_user),
    authorization: str = Header(...),
):
    saved_files = []
    errors = []

    for file in files:
        filename = os.path.basename((file.filename or "").replace("\\", "/"))
        if get_extension(filename) not in SUPPORTED_EXTENSIONS:
            errors.append({"file": filename, "error": "Unsupported file type"})
            file.file.close()
            continue

        folder = os.path.join(UPLOAD_DIR, uuid.uuid4().hex)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        size = 0

        try:
            with open(path, "wb") as f:
                while True:
                    part = file.file.read(1024 * 1024)
                    if not part:
                        break
                    size += len(part)
                    if size > MAX_FILE_SIZE:
                        break
                    f.write(part)

            if size == 0 or size > MAX_FILE_SIZE:
                errors.append({"file": filename, "error": "File is empty or exceeds 10 MB"})
                os.remove(path)
                os.rmdir(folder)
            else:
                saved_files.append((path, doc_type))
        finally:
            file.file.close()

    try:
        documents, chunks, ingest_errors = ingest_multiple_documents(saved_files)
    finally:
        for path, _ in saved_files:
            if os.path.exists(path):
                os.remove(path)
            os.rmdir(os.path.dirname(path))

    errors.extend({"file": os.path.basename(path), "error": message} for path, message in ingest_errors)

    if chunks:
        store = PgVectorStore(user_id, conversation_id, authorization)
        store.save(documents, chunks)

    return {"documents": len(documents), "chunks": len(chunks), "errors": errors}


@app.post("/query")
def query_documents(request: QueryRequest, user_id: str = Depends(get_current_user), authorization: str = Header(...)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    store = PgVectorStore(user_id, request.conversation_id, authorization)
    documents = store.documents()
    if not documents:
        return {"answer": "Please upload a document in this conversation first.", "citations": []}
    doc_name_lookup = {doc["id"]: doc["name"] for doc in documents}
    with data_lock:
        history = chat_histories.get(user_id + ":" + request.conversation_id, [])[-10:]

    try:
        query = rewrite_query_with_history(request.query, history)
        results = store.search(query, top_k=5)
        if not results:
            return {"answer": "Please upload a document in this conversation first.", "citations": []}
        answer = synthesize_answer(query, results, doc_name_lookup)
    except Exception as e:
        print("Query failed:", e)
        raise HTTPException(status_code=503, detail="Could not generate an answer. Please try again.")

    with data_lock:
        history = chat_histories.setdefault(user_id + ":" + request.conversation_id, [])
        history.append(HumanMessage(content=request.query))
        history.append(AIMessage(content=answer.text))
        chat_histories[user_id + ":" + request.conversation_id] = history[-20:]

    return {"answer": answer.text, "citations": [c.model_dump() for c in answer.citations]}


@app.get("/documents")
def list_documents(conversation_id: str = "default", user_id: str = Depends(get_current_user), authorization: str = Header(...)):
    store = PgVectorStore(user_id, conversation_id, authorization)
    counts = Counter(r["document_id"] for r in store.rows("document_chunks", "document_id,id"))
    return {"documents": [
        {"doc_id": d["id"], "name": d["name"], "doc_type": d["doc_type"],
         "chunk_count": counts.get(d["id"], 0)}
        for d in store.documents()
    ]}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str, conversation_id: str = "default", user_id: str = Depends(get_current_user), authorization: str = Header(...)):
    store = PgVectorStore(user_id, conversation_id, authorization)
    if not store.delete(doc_id):
        raise HTTPException(404, "Document not found in this conversation.")
    with data_lock:
        chat_histories.pop(user_id + ":" + conversation_id, None)
    return {"message": "Document deleted."}


@app.get("/evaluation/metrics")
def get_metrics(user_id: str = Depends(get_current_user)):
    path = os.path.join(BASE_DIR, "evaluation_results.json")
    if not os.path.exists(path):
        return {"message": "No evaluation results found. Run the eval script first."}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
