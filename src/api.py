import os
import uuid 
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from ingestion import ingest_multiple_documents, Document, Chunk,SUPPORTED_EXTENSIONS,get_extension
from synthesis import synthesize_answer
from vectorstore import HybridIndex
from langchain_core.messages import AIMessage, HumanMessage
from query_rewrite import rewrite_query_with_history
from collections import Counter



app = FastAPI()
UPLOAD_DIR = "upload_files"

index = HybridIndex()
all_documents = []
doc_name_lookup = {}
chat_histories = {} 


class QueryRequest(BaseModel):
    query: str
    conversation_id: str = "default"

@app.post("/upload")
def upload_documents(files: list[UploadFile] = File(...), doc_type: str = Form("official")):
    saved_files = []

    # 1. Save each file
    for file in files:
        if get_extension(file.filename) not in SUPPORTED_EXTENSIONS:
            continue
        folder = os.path.join(UPLOAD_DIR, uuid.uuid4().hex)
        os.makedirs(folder)
        path = os.path.join(folder, os.path.basename(file.filename))
        with open(path, "wb") as f:
            f.write(file.file.read())
        saved_files.append((path, doc_type))

    # 2. Ingest (your existing function)
    documents, chunks, errors = ingest_multiple_documents(saved_files)

    # 3. Add to the search index (your existing method)
    index.add_chunks(chunks)

    # 4. Remember the documents
    all_documents.extend(documents)
    for doc in documents:
        doc_name_lookup[doc.doc_id] = doc.name

    return {"documents": len(documents), "chunks": len(chunks), "errors": errors}



class QueryRequest(BaseModel):
    query: str
    conversation_id: str = "default"

@app.post("/query")
def query_documents(request: QueryRequest):
    if len(index) == 0:
        return {"answer": "Please upload a document first.", "citations": []}

    history = chat_histories.setdefault(request.conversation_id, [])

    # 1. Turn follow-up into a standalone question
    query = rewrite_query_with_history(request.query, history[-10:])

    # 2. Search and answer
    results = index.search(query, top_k=5)
    answer = synthesize_answer(query, results, doc_name_lookup)

    # 3. Save this turn
    history.append(HumanMessage(content=request.query))
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
