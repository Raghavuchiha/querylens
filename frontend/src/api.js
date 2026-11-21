const baseUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function request(path, options = {}) {
  const response = await fetch(baseUrl + path, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Request failed (' + response.status + ').');
  }
  return payload;
}

export async function uploadDocuments(files, docType = 'official') {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  form.append('doc_type', docType);
  return request('/upload', { method: 'POST', body: form });
}

export function queryDocuments(query, conversationId) {
  return request('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, conversation_id: conversationId }),
  });
}

export function listDocuments() {
  return request('/documents');
}
