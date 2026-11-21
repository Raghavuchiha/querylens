import { useEffect, useRef, useState } from 'react';
import {
  ArrowRight, BookOpen, ChevronRight, FileText, Trash2,
  LoaderCircle, Menu, MessageCircle, Plus, Send, Sparkles, UploadCloud, X,
} from 'lucide-react';
import { listDocuments, queryDocuments, uploadDocuments, deleteDocument } from './api';

function createConversation() {
  return { id: crypto.randomUUID(), messages: [] };
}

function savedConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem('querylens_chats'));
    if (Array.isArray(saved) && saved.length) return saved;
  } catch (error) {
    console.warn('Could not load saved conversations:', error);
  }
  return [{ id: 'default', messages: [] }];
}

const formats = ['.pdf', '.txt', '.md', '.docx'];
const prettyName = (name) => name.length > 34 ? name.slice(0, 31) + '…' : name;

export default function App() {
  const [conversations, setConversations] = useState(savedConversations);
  const [activeId, setActiveId] = useState(() => null);
  const [documents, setDocuments] = useState([]);
  const [documentError, setDocumentError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [uploadNotice, setUploadNotice] = useState('');
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [chatError, setChatError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);
  const busyRef = useRef(false);
  const currentIdRef = useRef(null);
  const currentId = activeId || conversations[0].id;
  const current = conversations.find((c) => c.id === currentId) || conversations[0];
  currentIdRef.current = currentId;

  useEffect(() => {
    try {
      localStorage.setItem('querylens_chats', JSON.stringify(conversations));
    } catch (error) {
      console.warn('Could not save conversations:', error);
    }
  }, [conversations]);

  async function refreshDocuments(id = currentId) {
    try {
      const data = await listDocuments(id);
      if (currentIdRef.current !== id) return;
      setDocuments(Array.isArray(data?.documents) ? data.documents : []);
      setDocumentError('');
    } catch (error) {
      if (currentIdRef.current === id) {
        setDocumentError('Unable to reach the document service: ' + error.message);
      }
    }
  }

  useEffect(() => {
    setDocuments([]);
    setSelectedFiles([]);
    setUploadNotice('');
    setDocumentError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    refreshDocuments(currentId);
  }, [currentId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [current?.messages.length, asking]);

  function newChat() {
    const conversation = createConversation();
    setConversations((prev) => [conversation, ...prev]);
    setActiveId(conversation.id);
    setQuestion('');
    setChatError('');
    setSidebarOpen(false);
  }

  function chooseChat(id) {
    setActiveId(id);
    setChatError('');
    setSidebarOpen(false);
  }

  function appendMessage(id, message) {
    setConversations((prev) => prev.map((c) =>
      c.id === id ? { ...c, messages: [...c.messages, message] } : c
    ));
  }

  function selectFiles(event) {
    const files = Array.from(event.target.files || []);
    const valid = files.filter((file) => formats.some((ext) => file.name.toLowerCase().endsWith(ext)));
    setSelectedFiles(valid);
    setUploadNotice(valid.length !== files.length ? 'Some files were skipped. Supported: PDF, TXT, MD, DOCX.' : '');
  }

  async function handleUpload() {
    if (!selectedFiles.length || uploading) return;
    const id = currentId;
    const files = [...selectedFiles];
    setUploading(true);
    setUploadNotice('');
    try {
      const result = await uploadDocuments(files, id);
      const errors = result?.errors || [];
      const success = Number(result?.documents || 0);
      const summary = success + ' document' + (success === 1 ? '' : 's') + ' indexed.';
      const issue = errors.length ? ' ' + errors.length + ' file(s) could not be read.' : '';
      if (currentIdRef.current === id) {
        setUploadNotice(summary + issue);
        setSelectedFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
      await refreshDocuments(id);
    } catch (error) {
      if (currentIdRef.current === id) setUploadNotice('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc) {
    if (deletingId || uploading || !window.confirm('Delete "' + doc.name + '" from this conversation?')) return;
    const id = currentId;
    setDeletingId(doc.doc_id);
    setDocumentError('');
    try {
      await deleteDocument(doc.doc_id, id);
      if (currentIdRef.current === id) {
        setUploadNotice('Deleted ' + doc.name + ' from this knowledge base.');
        await refreshDocuments(id);
      }
    } catch (error) {
      if (currentIdRef.current === id) setDocumentError('Delete failed: ' + error.message);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;
    const id = currentId;
    setAsking(true);
    setChatError('');
    setQuestion('');
    appendMessage(id, { id: crypto.randomUUID(), role: 'user', content: text });
    try {
      const result = await queryDocuments(text, id);
      appendMessage(id, {
        id: crypto.randomUUID(), role: 'assistant',
        content: result?.answer || 'No answer returned.',
        citations: Array.isArray(result?.citations) ? result.citations : [],
      });
    } catch (error) {
      setChatError('Unable to answer: ' + error.message + '. Your question remains in the chat.');
    } finally {
      setAsking(false);
      busyRef.current = false;
    }
  }

  const titleFor = (chat) => {
    const first = chat.messages.find((m) => m.role === 'user');
    return first ? prettyName(first.content) : 'New conversation';
  };

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="mobile-shade" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}
      <aside className={'sidebar ' + (sidebarOpen ? 'sidebar-open' : '')}>
        <div className="brand-row">
          <div className="brand-mark"><span>Q</span><span className="brand-star">✳</span></div>
          <span className="brand-name">query<span>lens</span></span>
          <button className="icon-button mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={20} /></button>
        </div>
        <div className="sidebar-kicker">YOUR WORKSPACE / 01</div>
        <button className="new-chat-button" onClick={newChat}><Plus size={18} strokeWidth={3} /> NEW CONVERSATION <ArrowRight size={18} /></button>

        <div className="sidebar-section-title"><span><MessageCircle size={15}/> CONVERSATIONS</span><span>{conversations.length.toString().padStart(2, '0')}</span></div>
        <div className="conversation-list">
          {conversations.map((chat) => (
            <button key={chat.id} title={titleFor(chat)} onClick={() => chooseChat(chat.id)}
              className={'conversation-button ' + (chat.id === currentId ? 'is-active' : '')}>
              <span className="conversation-dot" />
              <span>{titleFor(chat)}</span>
              {chat.id === currentId && <ChevronRight size={16} />}
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><Sparkles size={18} /><span>Find the signal.<br/>Skip the noise.</span></div>
          <div className="sidebar-foot">BUILT FOR CURIOUS MINDS <span>↗</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="Open menu" onClick={() => setSidebarOpen(true)}><Menu size={22}/></button>
            <span className="topbar-word">DOCUMENT INTELLIGENCE</span><span className="topbar-divider">/</span><span className="topbar-muted">WORKSPACE</span>
          </div>
          <div className="topbar-right"><span className="status-dot" /> LOCAL API <span className="topbar-version">V1.0</span></div>
        </header>

        <div className="page-content">
          <section className="hero">
            <div className="hero-inner">
              <span className="eyebrow"><span className="eyebrow-square"/> INTELLIGENCE, UNLOCKED.</span>
              <h1>YOUR DOCUMENTS.<br/><span>DECODED.</span></h1>
              <p>Less searching. More understanding. Drop your files, ask anything, and get answers grounded in your own documents.</p>
              <div className="hero-actions">
                <button className="primary-button" onClick={() => fileInputRef.current?.click()}><UploadCloud size={19}/> UPLOAD DOCUMENTS <ArrowRight size={19}/></button>
                <span className="hero-hint">PDF · DOCX · TXT · MD</span>
              </div>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="art-orbit art-orbit-one"/><div className="art-orbit art-orbit-two"/>
              <div className="art-card art-card-back"><span>01 / RAW DATA</span><div className="art-lines"><i/><i/><i/><i/></div></div>
              <div className="art-card art-card-front"><span>02 / ANSWERS</span><div className="art-eye">✳</div><div className="art-caption">CLARITY FOUND.</div></div>
              <div className="art-spark art-spark-one">✦</div><div className="art-spark art-spark-two">+</div>
            </div>
            <div className="hero-index">QL / 001</div>
          </section>

          <div className="work-grid">
            <section className="panel upload-panel">
              <div className="section-heading"><div><span className="mini-label">01 / KNOWLEDGE BASE</span><h2>Feed your curiosity<span className="orange-dot">.</span></h2></div><BookOpen size={23}/></div>
              <div className="upload-drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
                event.preventDefault();
                const files = Array.from(event.dataTransfer.files || []);
                setSelectedFiles(files.filter((file) => formats.some((ext) => file.name.toLowerCase().endsWith(ext))));
                setUploadNotice(files.length && !files.some((file) => formats.some((ext) => file.name.toLowerCase().endsWith(ext))) ? 'Unsupported format. Use PDF, TXT, MD or DOCX.' : '');
              }}>
                <input ref={fileInputRef} type="file" multiple accept=".pdf,.txt,.md,.docx" className="visually-hidden" onChange={selectFiles}/>
                <div className="upload-symbol"><UploadCloud size={27} strokeWidth={1.8}/></div>
                <strong>DROP THE KNOWLEDGE HERE</strong>
                <span>Drag files in or <button className="text-action" onClick={() => fileInputRef.current?.click()}>browse your computer</button></span>
                <small>PDF, DOCX, TXT, MD</small>
              </div>
              {selectedFiles.length > 0 && <div className="selected-files">
                {selectedFiles.map((file, index) => <div key={index} className="selected-file"><FileText size={16}/><span title={file.name}>{prettyName(file.name)}</span><button aria-label={'Remove ' + file.name} onClick={() => setSelectedFiles((prev) => prev.filter((_, i) => i !== index))}><X size={16}/></button></div>)}
                <button className="upload-action" disabled={uploading} onClick={handleUpload}>{uploading ? <LoaderCircle size={17} className="spin"/> : <UploadCloud size={17}/>} {uploading ? 'INDEXING…' : 'INDEX ' + selectedFiles.length + ' FILE(S)'} <ArrowRight size={17}/></button>
              </div>}
              {uploadNotice && <div role="status" className="notice">{uploadNotice}</div>}
              <div className="file-list-heading"><span>INDEXED DOCUMENTS · THIS CHAT</span><button onClick={() => refreshDocuments(currentId)} className="refresh-action">REFRESH ↗</button></div>
              {documentError && <div className="notice error" role="alert">{documentError}</div>}
              {documents.length ? <div className="indexed-docs">{documents.map((doc) => <div className="indexed-doc" key={doc.doc_id}><div className="doc-icon"><FileText size={18}/></div><div className="doc-details"><strong title={doc.name}>{prettyName(doc.name)}</strong><span>{doc.chunk_count} chunks · {doc.doc_type}</span></div><button type="button" className="doc-delete" title={'Delete ' + doc.name} aria-label={'Delete ' + doc.name} disabled={!!deletingId || uploading} onClick={() => handleDelete(doc)}>{deletingId === doc.doc_id ? <LoaderCircle size={17} className="spin"/> : <Trash2 size={17}/>}</button></div>)}</div> : <div className="empty-docs">No indexed documents yet. Start by uploading a file.</div>}
            </section>

            <section className="panel chat-panel">
              <div className="section-heading"><div><span className="mini-label">02 / ASK THE KNOWLEDGE BASE</span><h2>Ask away<span className="orange-dot">.</span></h2></div><MessageCircle size={23}/></div>
              <div className="chat-window">
                {!current.messages.length && <div className="empty-chat">
                  <div className="chat-asterisk">✳</div>
                  <h3>GOT QUESTIONS?<br/><span>WE'VE GOT CONTEXT.</span></h3>
                  <p>Ask something about your uploaded documents. Answers include citations when available.</p>
                </div>}
                {current.messages.map((message) => <div className={'message ' + message.role} key={message.id}>
                  <div className="message-label">{message.role === 'user' ? 'YOU' : 'QUERYLENS'}</div>
                  <div className="message-text">{message.content}</div>
                  {!!message.citations?.length && <div className="citations"><div className="citations-heading">SOURCE REFERENCES</div>{message.citations.map((citation, index) => <div className="citation" key={citation.chunk_id + '-' + index}><FileText size={14}/><div><strong>{citation.doc_name}{citation.page ? ' · p. ' + citation.page : ''}</strong><span>{citation.claim}</span></div></div>)}</div>}
                </div>)}
                {asking && <div className="thinking"><LoaderCircle size={16} className="spin"/> Searching your documents…</div>}
                <div ref={bottomRef}/>
              </div>
              {chatError && <div role="alert" className="chat-error">{chatError}</div>}
              <form className="ask-form" onSubmit={handleAsk}>
                <input aria-label="Ask a question" placeholder="Ask anything about your documents…" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={asking} />
                <button type="submit" disabled={asking || !question.trim()} aria-label="Send question"><Send size={19}/></button>
              </form>
              <div className="chat-footer"><span>GROUNDED IN YOUR DOCUMENTS</span><span>ASK · DISCOVER · UNDERSTAND</span></div>
            </section>
          </div>

          <footer className="page-footer"><span>QUERYLENS <span className="orange-dot">✳</span> DOCUMENT INTELLIGENCE</span><span>BUILT TO MAKE INFORMATION USEFUL.</span></footer>
        </div>
      </main>
    </div>
  );
}
