## Render Free deployment: lightweight embeddings

QueryLens now uses the ONNX-based **FastEmbed** implementation of `sentence-transformers/all-MiniLM-L6-v2` rather than PyTorch Sentence Transformers. This retains the MiniLM 384-dimensional embedding model and FAISS + BM25 + RRF architecture. It reduces the startup/install footprint on a 512 MB Render instance.

The first embedding operation downloads the ONNX model into the server cache. Render Free may still run out of memory depending on available resources and document size; check live memory metrics and logs.

For testing, start with a tiny TXT or small PDF. Documents are still persisted to local `user_index_data.json`, which is **ephemeral on Render Free**. Persistent Supabase pgvector storage and BYOK Groq keys have not been implemented.

The `/health` route returns a lightweight server readiness response without loading the embedding model.
