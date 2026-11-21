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
