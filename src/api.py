import json
import shutil
import os

from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel

from ingestion import ingest_multiple_documents
from vectorstore import hybrid_retrieve
from synthesis import synthesize_answer
from query_rewrite import rewrite_query_with_history
from langchain_core.messages import HumanMessage, AIMessage

app = FastAPI()

all_chunks = []
all_documents = []
chat_history = []
doc_name_lookup = {}


class QueryRequest(BaseModel):
    query: str


#upload
#query
#document
#metrics

@app.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    doc_type: str = Form("official")
):
    # Create folder if it doesn't exist
    os.makedirs("uploaded_files", exist_ok=True)

    saved_files = []

    # Save every uploaded file
    for file in files:

        file_path = f"uploaded_files/{file.filename}"

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        saved_files.append((file_path, doc_type))

    # Process the uploaded files
    documents, chunks = ingest_multiple_documents(saved_files)

    # Store documents and chunks
    all_documents.extend(documents)
    all_chunks.extend(chunks)

    # Store document names
    for document in documents:
        doc_name_lookup[document.doc_id] = document.name

    return {
        "message": f"Uploaded {len(documents)} documents",
        "chunks": len(chunks),
        "document_ids": [doc.doc_id for doc in documents]
    }
 

@app.post("/query")
async def query_documents(request: QueryRequest):
    query = request.query

    standalone_query = rewrite_query_with_history(query, chat_history)

    results = hybrid_retrieve(all_chunks, standalone_query, top_k=5)
    answer = synthesize_answer(standalone_query, results, doc_name_lookup)

    chat_history.append(HumanMessage(content=query))
    chat_history.append(AIMessage(content=answer.text))

    return {
        "answer": answer.text,
        "citations": [
            {"claim": c.claim, "doc_name": c.doc_name} for c in answer.citations
        ],
    }


@app.get("/documents")
async def list_documents():
    
    
    result = []
    for doc in all_documents:
        chunk_count = len([c for c in all_chunks if c.doc_id == doc.doc_id])
        result.append({
            "doc_id": doc.doc_id,
            "name": doc.name,
            "doc_type": doc.doc_type,
            "chunk_count": chunk_count,
        })
    return {"documents": result}


@app.get("/evaluation/metrics")
async def get_metrics():
    if not os.path.exists("evaluation_results.json"):
        return {"message": "No evaluation results found. Run the eval script first."}

    with open("evaluation_results.json", "r") as f:
        results = json.load(f)

    return results
