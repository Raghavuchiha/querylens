# QueryLens React Frontend

A small Vite + React interface for the existing QueryLens FastAPI backend. Visual style inspired by the retro cream/orange/pixel-accent design language at lifeatflytbase.com; all UI components are original.

## Features that actually work
- Upload PDF, DOCX, TXT, and Markdown files via `POST /upload`.
- Display indexed documents and chunk counts via `GET /documents`.
- Ask questions via `POST /query`, with per-conversation IDs and visible source citations.
- Switch between conversations in the current browser session.
- Loading indicators, upload feedback, and API errors.

Conversation UI history is in React memory only, and backend indexes are in server memory. Both will reset upon restarts; there is no account/login or deletion feature because the backend does not support them.

## Run locally

1. Start the original FastAPI server from the repository's `src` folder:
   ```bash
   uvicorn api:app --reload --port 8000
   ```
2. From `frontend`:
   ```bash
   npm install
   npm run dev
   ```
3. Open the Vite localhost URL. Vite proxies `/api/*` to `http://127.0.0.1:8000`, avoiding any backend changes.

## Deployment

When the frontend and API use different hosts, set `VITE_API_URL` to the public backend URL before building. Cross-origin deployment requires backend CORS configuration; that is deliberately **not** changed here. The development proxy is local only.

## Scope

No mock document data, fake response streaming, fake authentication, decorative action buttons, or unused routes. The current backend does not provide a document deletion endpoint.

## Separate knowledge bases

Every chat has its own documents. Adding a new conversation creates a new empty knowledge base. Documents are listed and queried using that conversation's ID, and each indexed document has a Delete button that removes it from retrieval. Documents are persisted server-side in `src/index_data.json`, grouped by conversation ID. Conversation IDs and visible messages are saved in browser localStorage; backend follow-up history still resets after a server restart. The initial chat uses the old `default` knowledge base to preserve existing indexed documents.

There is still no authentication: this is intended for personal local use, not a public multi-user deployment. Deleting a document removes its indexed data but does not erase old messages or Git history.

## Supabase email/password login

Enable Email auth and email confirmations in Supabase → Authentication.
Set `http://localhost:5173` as the Site URL under URL Configuration.

Copy `frontend/.env.example` to `frontend/.env`, fill in the Supabase project URL and publishable key.
Copy `src/.env.example` to `src/.env`, fill in the same Supabase URL and publishable key, and keep your existing LLM API key.

Run `npm install` once in `frontend`, then `npm run dev`. Start FastAPI with `cd src && uvicorn api:app --reload`.

FastAPI verifies access tokens with Supabase Auth for each API call and namespaces documents/chats by the authenticated user ID. Old `src/index_data.json` files are not imported because they have no verified ownership. Reupload your documents after login.

**Not production-ready yet:** User data still lives in a local JSON file (`src/user_index_data.json`), not Supabase pgvector. Deploying to an ephemeral host can lose that file. Add durable storage, CORS, and rate limits before a public launch.
