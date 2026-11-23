import json
import os
import uuid
import threading
import requests
from dotenv import load_dotenv
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from ingestion import ingest_multiple_documents, SUPPORTED_EXTENSIONS, get_extension
from synthesis import synthesize_answer
from vectorstore import HybridIndex
from query_rewrite import rewrite_query_with_history
from models import Document, Chunk


load_dotenv()
app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "upload_files")
DATA_FILE = os.path.join(BASE_DIR, "user_index_data.json")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file

# Each conversation has its own documents and search index.
knowledge_bases = {}
chat_histories = {}
data_lock = threading.RLock()


def get_knowledge_base(user_id, conversation_id):
    key = user_id + ':' + conversation_id
    if key not in knowledge_bases:
        knowledge_bases[key] = {
            "index": HybridIndex(),
            "documents": [],
        }
    return knowledge_bases[key]


def save_index():
    data = {"knowledge_bases": {}}
    for conversation_id, base in knowledge_bases.items():
        data["knowledge_bases"][conversation_id] = {
            "documents": [doc.model_dump() for doc in base["documents"]],
            "chunks": [chunk.model_dump() for chunk in base["index"].chunks],
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

        saved_bases = data.get("knowledge_bases", {})

        for key, saved in saved_bases.items():
            if ':' not in key:
                continue
            user_id, conversation_id = key.split(':', 1)
            documents = [Document(**doc) for doc in saved.get("documents", [])]
            chunks = [Chunk(**chunk) for chunk in saved.get("chunks", [])]
            base = get_knowledge_base(user_id, conversation_id)
            base["index"].add_chunks(chunks)
            base["documents"].extend(documents)
    except Exception as e:
        print("Could not load previous indexes:", e)


load_index()


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
        with data_lock:
            base = get_knowledge_base(user_id, conversation_id)
            try:
                base["index"].add_chunks(chunks)
            except Exception as e:
                print("Indexing failed:", e)
                raise HTTPException(status_code=500, detail="Could not index the documents.")

            base["documents"].extend(documents)
            save_index()

    return {"documents": len(documents), "chunks": len(chunks), "errors": errors}


@app.post("/query")
def query_documents(request: QueryRequest, user_id: str = Depends(get_current_user)):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    with data_lock:
        base = knowledge_bases.get(user_id + ":" + request.conversation_id)
        if not base or len(base["index"]) == 0:
            return {"answer": "Please upload a document in this conversation first.", "citations": []}
        index = base["index"]
        doc_name_lookup = {doc.doc_id: doc.name for doc in base["documents"]}
        history = chat_histories.get(user_id + ":" + request.conversation_id, [])[-10:]

    try:
        query = rewrite_query_with_history(request.query, history)
        results = index.search(query, top_k=5)
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
def list_documents(conversation_id: str = "default", user_id: str = Depends(get_current_user)):
    with data_lock:
        base = knowledge_bases.get(user_id + ":" + conversation_id)
        if not base:
            return {"documents": []}

        chunk_counts = Counter(c.doc_id for c in base["index"].chunks)
        return {"documents": [
            {
                "doc_id": doc.doc_id,
                "name": doc.name,
                "doc_type": doc.doc_type,
                "chunk_count": chunk_counts.get(doc.doc_id, 0),
            }
            for doc in base["documents"]
        ]}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str, conversation_id: str = "default", user_id: str = Depends(get_current_user)):
    with data_lock:
        base = knowledge_bases.get(user_id + ':' + conversation_id)
        if not base or not any(doc.doc_id == doc_id for doc in base["documents"]):
            raise HTTPException(status_code=404, detail="Document not found in this conversation.")

        remaining_chunks = [chunk for chunk in base["index"].chunks if chunk.doc_id != doc_id]
        new_index = HybridIndex()
        try:
            new_index.add_chunks(remaining_chunks)
        except Exception as e:
            print("Could not rebuild index:", e)
            raise HTTPException(status_code=500, detail="Could not delete the document.")

        base["index"] = new_index
        base["documents"] = [doc for doc in base["documents"] if doc.doc_id != doc_id]
        chat_histories.pop(user_id + ":" + conversation_id, None)
        save_index()

    return {"message": "Document deleted."}


@app.get("/evaluation/metrics")
def get_metrics(user_id: str = Depends(get_current_user)):
    path = os.path.join(BASE_DIR, "evaluation_results.json")
    if not os.path.exists(path):
        return {"message": "No evaluation results found. Run the eval script first."}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
