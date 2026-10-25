import re
import threading
from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LangchainDocument
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

from models import Chunk, RetrievalResult

DEFAULT_TOP_K = 5
RRF_K = 60


@lru_cache(maxsize=1)
def get_embeddings():
    # Loaded lazily so importing this module stays fast
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


# ---------- Semantic search (FAISS) ----------

def chunk_to_lc_doc(chunk: Chunk) -> LangchainDocument:
    return LangchainDocument(
        page_content=chunk.text,
        metadata={
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "chunk_index": chunk.chunk_index,
            "page": chunk.page,
        },
    )


def semantic_search(vectorstore, query, top_k=DEFAULT_TOP_K):
    results = vectorstore.similarity_search_with_score(query, k=top_k)

    final_results = []
    for document, distance in results:
        chunk = Chunk(
            chunk_id=document.metadata["chunk_id"],
            doc_id=document.metadata["doc_id"],
            text=document.page_content,
            chunk_index=document.metadata["chunk_index"],
            page=document.metadata.get("page"),
        )
        final_results.append(
            RetrievalResult(chunk=chunk, score=1 / (1 + float(distance)))
        )

    return final_results


# ---------- Keyword search (BM25) ----------

class BM25Search:

    def __init__(self, chunks):
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(chunk.text) for chunk in chunks])

    def search(self, query, top_k=DEFAULT_TOP_K):
        scores = self.bm25.get_scores(tokenize(query))

        scored_chunks = sorted(
            zip(self.chunks, scores), key=lambda x: x[1], reverse=True
        )

        return [
            RetrievalResult(chunk=chunk, score=float(score))
            for chunk, score in scored_chunks[:top_k]
        ]


# ---------- Hybrid combination (Reciprocal Rank Fusion) ----------

def hybrid_search(semantic_results, bm25_results, top_k=DEFAULT_TOP_K):
    scores = {}
    chunks = {}

    for ranked_list in (semantic_results, bm25_results):
        for rank, result in enumerate(ranked_list, start=1):
            chunk_id = result.chunk.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank)
            chunks[chunk_id] = result.chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [
        RetrievalResult(chunk=chunks[chunk_id], score=score)
        for chunk_id, score in ranked[:top_k]
    ]


# ---------- Persistent (in-process) index, built at upload time ----------

class HybridIndex:
    """FAISS + BM25 index that is updated on upload, not rebuilt on every query."""

    def __init__(self):
        self._lock = threading.Lock()
        self._vectorstore = None
        self._bm25 = None
        self.chunks: list[Chunk] = []

    def __len__(self):
        return len(self.chunks)

    def add_chunks(self, chunks: list[Chunk]):
        if not chunks:
            return

        lc_docs = [chunk_to_lc_doc(c) for c in chunks]

        with self._lock:
            all_chunks = self.chunks + chunks
            bm25 = BM25Search(all_chunks)  # cheap: no embeddings involved

            if self._vectorstore is None:
                self._vectorstore = FAISS.from_documents(lc_docs, get_embeddings())
            else:
                self._vectorstore.add_documents(lc_docs)  # embeds only the new chunks

            self.chunks = all_chunks
            self._bm25 = bm25

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
        with self._lock:
            if not self.chunks:
                return []

            sem_results = semantic_search(self._vectorstore, query, top_k=top_k)
            bm25_results = self._bm25.search(query, top_k=top_k)

        return hybrid_search(sem_results, bm25_results, top_k=top_k)
