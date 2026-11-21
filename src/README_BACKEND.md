# QueryLens backend

This is the same small FastAPI + FAISS + BM25 application. The existing API routes and retrieval approach were kept.

## Start

From the repository root:

```bash
pip install -r requirements.txt
cd src
uvicorn api:app --reload --port 8000
```

Set `NVIDIA_API_KEY` in an environment variable or local `.env` file.

## What was fixed
- Upload validation (supported extensions, empty files, 10 MB limit)
- Uploaded files are deleted after text extraction
- Upload errors use the format expected by the React frontend
- The index's document/chunk data is saved to `src/index_data.json` after upload and loaded on restart (embeddings are rebuilt on restart)
- The standalone retrieval function now calls existing functions
- Removed the duplicate API request model
- Evaluation endpoint can load JSON results
- Query rewriting falls back to the original question if it fails
- Model calls have a timeout and limited retries
- Added missing basic runtime dependencies

## Scope and limitations

This is still **a local, single-user interview project**, not a secure multi-user service. There is no authentication or per-user document isolation. Do not expose this API publicly with private documents.

Saved chat histories are still in memory, while the indexed documents are saved to a local JSON file. Run only one API worker: separate processes would have separate in-memory indexes. Documents in `src/uploaded_files/` were already committed in older revisions, and this change does not remove them from Git history.

Optional evaluation dependencies: `pip install ragas datasets pandas langchain-google-genai`.

To remove saved indexes during testing, stop the API and delete `src/index_data.json`.
