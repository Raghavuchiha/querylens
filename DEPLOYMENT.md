# Deploy QueryLens (test deployment)

## Backend — Render
1. Import GitHub repo `Raghavuchiha/querylens` to Render as a **Blueprint** using root `render.yaml`.
2. Supply `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `GROQ_API_KEY` as **Render environment variables**. Never add real keys to Git.
3. Set `CORS_ORIGINS` to the exact Vercel frontend origin (for example `https://querylens.vercel.app`); update once Vercel assigns the URL. Do not include trailing slash.
4. After deployment, test `https://YOUR-RENDER-APP.onrender.com/docs`. The backend may struggle on free-tier RAM because sentence-transformers/PyTorch loads locally.

## Frontend — Vercel
1. Import the same GitHub repo. Set Root Directory to `frontend`, Framework Preset `Vite`, Build Command `npm run build`, Output Directory `dist`.
2. Add Production environment variables:
   - `VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co`
   - `VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...`
   - `VITE_API_URL=https://YOUR-RENDER-APP.onrender.com`
3. Deploy and copy the frontend URL. Add it to Render `CORS_ORIGINS`, then redeploy/restart Render.
4. In Supabase Authentication → URL Configuration, add the frontend URL as Site URL/allowed redirect. Keep localhost redirect for local development.
5. Test signup, email confirmation, upload, query, delete, logout and account separation.

## Important: Not ready for public user data
- Vector indexes and documents still persist in local `src/user_index_data.json`. Render free instances do **not** retain local uploaded data across restarts or deploys; migrate to Supabase pgvector before public release.
- Frontend conversation history is only in browser localStorage, not synced across devices.
- Rate limiting, quotas and BYOK user-provided Groq keys are **not implemented**.
- The current embedding model may exceed free Render memory or cause a slow first start. Verify deployment logs and resource use.
- Avoid uploading private or sensitive files to a test deployment.
