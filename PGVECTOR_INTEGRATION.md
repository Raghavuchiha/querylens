# QueryLens pgvector integration

The web API on this branch uses the existing Supabase conversations, documents and document_chunks tables. The connected QueryLens database has vector(384), owner-scoped RLS and the ql_save_upload and ql_match_chunks RPC functions. The RPC functions must exist in any other deployment database.

The API forwards the authenticated user's bearer token and publishable key, not a service-role key. Existing frontend API routes and payloads are unchanged. Upload is transactional, deletion cascades to chunks, and semantic ranking uses squared L2 distance. BM25 is rebuilt from persisted chunk text per query and RRF combines both rankings. No persistent FAISS index is needed for the web API; the standalone retrieval pipeline still uses FAISS.

## Deployment checklist
- Ensure SUPABASE_URL points to the QueryLens project and SUPABASE_PUBLISHABLE_KEY belongs to that same project.
- Retain GROQ_API_KEY, GROQ_MODEL and CORS_ORIGINS.
- Back up any existing user_index_data.json before switching deployments. Legacy local documents are not migrated automatically; re-upload or migrate them before relying on the new backend.
- Verify authenticated upload, listing, query/citations, follow-up, deletion, and retrieval after a restart using a test account.
- Chat history remains process-local on the backend; frontend conversation history is still browser-local.
- BM25 currently reads all chunk text for the selected conversation, which is a scaling limitation.
- The database uses exact filtered vector search, not HNSW or IVF.
