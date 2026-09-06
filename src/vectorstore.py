from langchain_core.documents import Document as LangchainDocument
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi
from models import Chunk, RetrievalResult

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


# ---------- Semantic search (FAISS) ----------

def chunks_to_vectorstore(chunks: list[Chunk]):
    lc_docs = [
        LangchainDocument(
            page_content=c.text,
            metadata={
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "chunk_index": c.chunk_index,
            },
        )
        for c in chunks
    ]
    return FAISS.from_documents(lc_docs, embeddings)


def semantic_search(vectorstore, query, top_k=5):

    results = vectorstore.similarity_search_with_score(
        query,
        k=top_k
    )

    final_results = []

    for document, distance in results:

        chunk = Chunk(
            chunk_id=document.metadata["chunk_id"],
            doc_id=document.metadata["doc_id"],
            text=document.page_content,
            chunk_index=document.metadata["chunk_index"]
        )

        score = 1 / (1 + distance)

        final_results.append(
            RetrievalResult(
                chunk=chunk,
                score=score
            )
        )

    return final_results


# ---------- Keyword search (BM25) ----------

class BM25Search:

    def __init__(self, chunks):
        self.chunks = chunks
        documents = [chunk.text.lower().split() for chunk in chunks]
        self.bm25 = BM25Okapi(documents)

    def search(self, query, top_k=5):
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        scored_chunks = list(zip(self.chunks, scores))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        results = []
        for chunk, score in scored_chunks[:top_k]:
            results.append(RetrievalResult(chunk=chunk, score=score))

        return results


# ---------- Hybrid combination (Reciprocal Rank Fusion) ----------

def hybrid_search(semantic_results, bm25_results, top_k=5):

    k = 60

    scores = {}
    chunks = {}

    # Semantic ranking
    for rank, result in enumerate(semantic_results, start=1):

        chunk_id = result.chunk.chunk_id

        score = 1 / (k + rank)

        scores[chunk_id] = scores.get(chunk_id, 0) + score
        chunks[chunk_id] = result.chunk

    # BM25 ranking
    for rank, result in enumerate(bm25_results, start=1):

        chunk_id = result.chunk.chunk_id

        score = 1 / (k + rank)

        scores[chunk_id] = scores.get(chunk_id, 0) + score
        chunks[chunk_id] = result.chunk

    # Sort by RRF score
    ranked_chunks = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Return top K
    results = []

    for chunk_id, score in ranked_chunks[:top_k]:

        results.append(
            RetrievalResult(
                chunk=chunks[chunk_id],
                score=score
            )
        )

    return results


# ---------- Single entry point ----------

def hybrid_retrieve(chunks: list[Chunk], query: str, top_k: int = 3) -> list[RetrievalResult]:
    vectorstore = chunks_to_vectorstore(chunks)
    sem_results = semantic_search(vectorstore, query, top_k=top_k)

    bm25 = BM25Search(chunks)
    bm25_results = bm25.search(query, top_k=top_k)

    return hybrid_search(sem_results, bm25_results)