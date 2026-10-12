"""
Simple orchestration layer - just the core logic
"""
from ingestion import ingest_multiple_documents, load_documents_from_folder
from vectorstore import hybrid_retrieve
from synthesis import synthesize_answer


def query_pipeline(query: str, doc_folder: str):
    """
    One function that does everything in order
    """

    # Step 1: Load documents
    print(" Loading documents...")
    file_list = load_documents_from_folder(doc_folder, "pdf")
    documents, chunks = ingest_multiple_documents(file_list)

    # Step 2: Search
    print("🔍 Searching...")
    results = hybrid_retrieve(chunks, query)

    # Step 3: Generate answer
    print("Generating answer...")
    doc_lookup = {doc.doc_id: doc.name for doc in documents}
    answer = synthesize_answer(query, results, doc_lookup)

    return answer