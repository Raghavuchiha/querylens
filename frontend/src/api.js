import { supabase } from './supabase';

const baseUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function request(path, options = {}) {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error('Session expired. Please sign in again.');
  const headers = new Headers(options.headers || {});
  headers.set('Authorization', 'Bearer ' + data.session.access_token);
  const response = await fetch(baseUrl + path, { ...options, headers });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Request failed (' + response.status + ').');
  }
  return payload;
}

export async function uploadDocuments(files, conversationId, docType = 'official') {
  const form = new FormData();
  files.forEach(file => form.append('files', file));
  form.append('doc_type', docType);
  form.append('conversation_id', conversationId);
  return request('/upload', { method: 'POST', body: form });
}

export function queryDocuments(query, conversationId) {
  return request('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, conversation_id: conversationId }),
  });
}

export function listDocuments(conversationId) {
  return request('/documents?conversation_id=' + encodeURIComponent(conversationId));
}

export function deleteDocument(docId, conversationId) {
  return request('/documents/' + encodeURIComponent(docId) + '?conversation_id=' + encodeURIComponent(conversationId), {
    method: 'DELETE',
  });
}
