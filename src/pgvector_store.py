"""Persistent, user-scoped retrieval through Supabase PostgREST."""
import os
import uuid
import requests
from fastapi import HTTPException
from models import Chunk, RetrievalResult
from vectorstore import get_embeddings, BM25Search, hybrid_search

def conversation_uuid(user_id, conversation_id):
    try:
        return str(uuid.UUID(conversation_id))
    except ValueError:
        return str(uuid.uuid5(uuid.UUID(user_id), conversation_id))

class PgVectorStore:
    def __init__(self, user_id, conversation_id, authorization):
        self.user_id = user_id
        self.conversation_id = conversation_uuid(user_id, conversation_id)
        self.url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/"
        self.headers = {"apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"],
                        "Authorization": authorization}

    def request(self, method, path, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        try:
            response = requests.request(method, self.url + path, headers=headers,
                                        timeout=60, **kwargs)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(503, "Persistent document storage unavailable.") from exc
        return response.json() if response.content else None

    def rows(self, table, select):
        rows = []
        offset = 0
        while True:
            page = self.request("GET", table, params={
                "select": select, "user_id": "eq." + self.user_id,
                "conversation_id": "eq." + self.conversation_id,
                "order": "id.asc", "offset": offset, "limit": 500})
            rows.extend(page)
            if not page:
                break
            offset += len(page)
        return rows

    def save(self, documents, chunks):
        vectors = get_embeddings().embed_documents([c.text for c in chunks])
        payload = [{"id": c.chunk_id, "document_id": c.doc_id, "content": c.text,
                    "chunk_index": c.chunk_index, "page": c.page,
                    "embedding": [float(v) for v in vector]}
                   for c, vector in zip(chunks, vectors, strict=True)]
        self.request("POST", "rpc/ql_save_upload", json={
            "p_conversation": self.conversation_id,
            "p_documents": [{"id": d.doc_id, "name": d.name, "doc_type": d.doc_type}
                            for d in documents],
            "p_chunks": payload})

    @staticmethod
    def chunk(row):
        return Chunk(chunk_id=row["id"], doc_id=row["document_id"],
                     text=row["content"], chunk_index=row["chunk_index"] or 0,
                     page=row["page"])

    def search(self, query, top_k=5):
        chunks = [self.chunk(r) for r in self.rows(
            "document_chunks", "id,document_id,content,chunk_index,page")]
        if not chunks:
            return []
        vector = get_embeddings().embed_query(query)
        rows = self.request("POST", "rpc/ql_match_chunks", json={
            "p_conversation": self.conversation_id,
            "p_embedding": [float(v) for v in vector], "p_limit": top_k})
        semantic = [RetrievalResult(chunk=self.chunk(r),
                    score=1 / (1 + float(r["distance"]))) for r in rows]
        return hybrid_search(semantic, BM25Search(chunks).search(query, top_k), top_k)

    def documents(self):
        return self.rows("documents", "id,name,doc_type")

    def delete(self, doc_id):
        rows = self.request("DELETE", "documents", params={
            "id": "eq." + doc_id, "user_id": "eq." + self.user_id,
            "conversation_id": "eq." + self.conversation_id},
            headers={"Prefer": "return=representation"})
        return bool(rows)
