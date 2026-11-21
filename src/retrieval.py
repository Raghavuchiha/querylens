import os

from ingestion import ingest_multiple_documents, SUPPORTED_EXTENSIONS, get_extension
from vectorstore import HybridIndex
from synthesis import synthesize_answer


def query_pipeline(query: str, doc_folder: str):
    # Load documents from a folder
    file_list = []
    for name in os.listdir(doc_folder):
        path = os.path.join(doc_folder, name)
        if os.path.isfile(path) and get_extension(path) in SUPPORTED_EXTENSIONS:
            file_list.append((path, "official"))

    documents, chunks, errors = ingest_multiple_documents(file_list)
    if not chunks:
        raise ValueError("No documents could be read: " + str(errors))

    # Search using the same index as the API
    index = HybridIndex()
    index.add_chunks(chunks)
    results = index.search(query, top_k=5)

    doc_lookup = {doc.doc_id: doc.name for doc in documents}
    return synthesize_answer(query, results, doc_lookup)
