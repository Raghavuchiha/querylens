# 🔎 QueryLens

### Multi-Document RAG Assistant with Hybrid Retrieval, Conversational Query Rewriting & Grounded Citations

<p align="center">
  <strong>Upload your documents → Ask questions → Retrieve the right context → Generate a grounded answer → See exactly where it came from.</strong>
</p>

<p align="center">
  <img src="assets/querylens-architecture.png" alt="QueryLens architecture and RAG pipeline" width="900"/>
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-Vector_Search-4B8BBE?style=for-the-badge)
![BM25](https://img.shields.io/badge/BM25-Keyword_Search-6C63FF?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Gemini-LLM-4285F4?style=for-the-badge&logo=google&logoColor=white)

</p>

<p align="center">

![RAG](https://img.shields.io/badge/Architecture-RAG-111827?style=flat-square)
![Hybrid Retrieval](https://img.shields.io/badge/Retrieval-Hybrid%20%7C%20FAISS%20%2B%20BM25-111827?style=flat-square)
![RRF](https://img.shields.io/badge/Ranking-Reciprocal%20Rank%20Fusion-111827?style=flat-square)
![Citations](https://img.shields.io/badge/Answers-Grounded%20Citations-111827?style=flat-square)

</p>

---

## 🎬 What is QueryLens?

QueryLens is a **multi-document Retrieval-Augmented Generation (RAG) assistant** designed to answer questions from the documents you provide instead of relying on the model's general knowledge.

The idea is simple:

> **Don't ask the LLM to remember everything. Give it the right evidence first.**

You can upload multiple documents such as:

- 📄 PDF
- 📝 DOCX
- 📃 TXT
- 🗒️ Markdown (`.md`)

QueryLens processes those documents, creates searchable chunks, indexes them using **both semantic and keyword retrieval**, combines the results using **Reciprocal Rank Fusion (RRF)**, and finally asks Gemini to generate a structured answer with citations.

The result is a RAG workflow that is designed to be:

- 🎯 **Relevant** — retrieve context related to the question
- 🔍 **Searchable** — combine semantic and exact keyword matching
- 🧠 **Conversational** — rewrite follow-up questions using chat history
- 📚 **Grounded** — answer only from retrieved document context
- 🔗 **Traceable** — return document, page, chunk ID and source snippet
- 🛡️ **Validated** — reject citations that don't correspond to retrieved chunks

---

# ✨ Why QueryLens?

A basic RAG pipeline often looks like:

```text
Document
   ↓
Embedding
   ↓
Vector Search
   ↓
LLM
```

QueryLens goes a little further.

It combines:

```text
                 ┌─────────────────────┐
                 │      Documents      │
                 └──────────┬──────────┘
                            ↓
                  ┌──────────────────┐
                  │ Load + Chunking  │
                  └────────┬─────────┘
                           ↓
              ┌────────────┴────────────┐
              ↓                         ↓
       Semantic Search             Keyword Search
            FAISS                      BM25
              ↓                         ↓
              └────────────┬────────────┘
                           ↓
                    Reciprocal Rank
                       Fusion
                           ↓
                  Top Relevant Chunks
                           ↓
                    Gemini LLM
                           ↓
                 Structured Answer
                           ↓
                 Validated Citations
```

The important part is the **hybrid retrieval layer**.

Semantic search is good at understanding meaning.

Keyword search is good at finding exact terms.

QueryLens uses both.

---

# 🧠 Core RAG Pipeline

## 1. Document Upload

The user uploads one or more supported files.

```text
PDF / DOCX / TXT / MD
          ↓
     File validation
          ↓
   Duplicate detection
          ↓
       Safe storage
```

Files are checked for:

- supported extension
- valid filename
- duplicate content using SHA-256
- ingestion errors

Each upload is stored inside a unique directory to avoid filename collisions and path traversal issues.

---

## 2. Document Loading

QueryLens uses dedicated loaders:

| File Type | Loader |
|---|---|
| `.pdf` | `PyPDFLoader` |
| `.docx` | `Docx2txtLoader` |
| `.txt` | `TextLoader` |
| `.md` | `TextLoader` |

The raw document content is then passed to the ingestion pipeline.

---

## 3. Page-Aware Chunking

Documents are split using:

```text
RecursiveCharacterTextSplitter
chunk_size = 512
chunk_overlap = 128
```

The important design decision is that chunking happens **page-by-page**.

This allows QueryLens to preserve page information for PDF sources.

Each chunk receives:

```text
chunk_id
doc_id
chunk_index
page
text
```

That metadata becomes extremely useful later when generating citations.

---

# 🔎 4. Hybrid Retrieval

This is the heart of QueryLens.

Instead of depending only on vector similarity, QueryLens combines two retrieval strategies.

## Semantic Retrieval — FAISS

Each chunk is converted into an embedding using:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The embeddings are stored in FAISS.

Semantic search helps when the question and document use different wording but have similar meaning.

Example:

```text
Question:
"What caused the company's revenue to decline?"

Document:
"Annual income decreased because operating expenses increased."
```

A semantic retriever can understand that these concepts are related even though the exact words differ.

---

## Keyword Retrieval — BM25

BM25 looks at lexical overlap.

For example:

```text
Query:
"OAuth 2.0 refresh token"

Document:
"OAuth 2.0 refresh tokens expire after..."
```

Keyword retrieval is particularly useful for:

- technical terms
- product names
- IDs
- acronyms
- exact phrases
- rare terminology

---

# 🧮 5. Reciprocal Rank Fusion

The two retrieval systems produce ranked lists.

QueryLens combines them using **Reciprocal Rank Fusion (RRF)**.

The basic scoring idea is:

```text
RRF(d) = Σ 1 / (k + rank(d))
```

where:

- `d` = document/chunk
- `rank(d)` = position in a retrieval list
- `k` = RRF constant
- QueryLens uses `k = 60`

Conceptually:

```text
FAISS results
     │
     ├── Rank 1 ─────┐
     ├── Rank 2      │
     ├── Rank 3      ├──→ RRF → Final ranking
     └── ...         │
                    │
BM25 results        │
     ├── Rank 1 ────┤
     ├── Rank 2     │
     ├── Rank 3 ────┘
     └── ...
```

This allows a chunk that performs well across both retrieval systems to receive a stronger final ranking.

---

# 💬 6. Conversational Query Rewriting

Follow-up questions are often incomplete.

For example:

```text
User:
What is the company's revenue?

User:
What about 2025?
```

The second question is ambiguous by itself.

QueryLens keeps conversation history per `conversation_id` and uses Gemini to rewrite the follow-up into a standalone query.

Conceptually:

```text
Conversation History
        +
Current Question
        ↓
Query Rewriter
        ↓
Standalone Query
        ↓
Hybrid Retrieval
```

This means retrieval can operate on a clearer query instead of blindly searching the incomplete follow-up question.

---

# 🤖 7. Grounded Answer Generation

After retrieval, QueryLens sends only the selected chunks to Gemini.

The prompt explicitly instructs the model to:

- use only retrieved documents
- avoid outside knowledge
- avoid unsupported assumptions
- state when the documents don't contain enough information
- support factual claims with citations
- use the exact retrieved `chunk_id`

This makes the generation stage **document-grounded rather than open-ended**.

---

# 🔗 8. Validated Citations

One of the important parts of QueryLens is that citations are not blindly trusted from the LLM.

The model returns:

```text
chunk_id
claim
```

QueryLens then checks whether that `chunk_id` actually exists in the retrieved results.

Invalid citations are discarded.

The application enriches valid citations using its own data:

```text
Chunk ID
Document
Page
Source snippet
Claim
```

So the LLM does not get to invent arbitrary source metadata.

The final citation flow is:

```text
Retrieved Chunks
      ↓
Gemini
      ↓
LLM citation
      ↓
Validate chunk_id
      ↓
Match against retrieved data
      ↓
Add document/page/snippet
      ↓
Return citation
```

---

# 🏗️ Architecture

```text
┌───────────────────────┐
│       Streamlit       │
│       Frontend        │
└───────────┬───────────┘
            │ HTTP
            ▼
┌───────────────────────┐
│       FastAPI         │
│       Backend         │
├───────────────────────┤
│ /upload               │
│ /query                │
│ /documents            │
│ /evaluation/metrics   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│     Ingestion Layer   │
│ PDF / DOCX / TXT / MD │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Page-aware Chunking   │
│ 512 chars / 128 overlap│
└───────────┬───────────┘
            │
       ┌────┴─────┐
       ▼          ▼
   ┌───────┐   ┌───────┐
   │ FAISS │   │ BM25  │
   │Semantic│  │Keyword│
   └───┬───┘   └───┬───┘
       └─────┬─────┘
             ▼
          RRF Fusion
             │
             ▼
      Top-K Relevant Chunks
             │
             ▼
      Query Rewriting
       + Gemini LLM
             │
             ▼
     Structured LLMAnswer
             │
             ▼
     Citation Validation
             │
             ▼
       Grounded Response
```

### Architecture diagram

The detailed architecture diagram used in this repository is available at:

```text
assets/querylens-architecture.png
```

---

# 🛠️ Tech Stack

## Backend

- **Python**
- **FastAPI**
- **Pydantic**
- **Uvicorn**

## Frontend

- **Streamlit**
- **Requests**

## RAG / LLM

- **Google Gemini**
- **LangChain Core**
- **LangChain Google GenAI**
- **LangChain HuggingFace**

## Retrieval

- **FAISS**
- **BM25**
- **Sentence Transformers**
- **Reciprocal Rank Fusion**

## Document Processing

- **PyPDF**
- **Docx2txt**
- **Recursive Character Text Splitter**

## Evaluation

- **RAGAS**
- **Hugging Face Datasets**
- **Pandas**

---

# 📁 Project Structure

```text
querylens-main/
│
├── src/
│   ├── api.py
│   │   └── FastAPI application and API endpoints
│   │
│   ├── app.py
│   │   └── Streamlit chat interface
│   │
│   ├── ingestion.py
│   │   └── File ingestion + document chunking
│   │
│   ├── loaders.py
│   │   └── PDF / DOCX / TXT / MD loaders
│   │
│   ├── vectorstore.py
│   │   └── FAISS + BM25 + RRF hybrid retrieval
│   │
│   ├── query_rewrite.py
│   │   └── Conversational query rewriting
│   │
│   ├── synthesis.py
│   │   └── Gemini answer generation + citation validation
│   │
│   ├── models.py
│   │   └── Pydantic data models
│   │
│   └── Evaluation.py
│       └── RAGAS evaluation pipeline
│
├── assets/
│   └── querylens-architecture.png
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 🚀 Getting Started

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd querylens-main
```

> Replace `<YOUR_GITHUB_REPOSITORY_URL>` with your GitHub repository URL.

---

## 2. Create a virtual environment

### Windows

```bash
python -m venv lens
lens\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv lens
source lens/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Gemini API key

Create a `.env` file:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
```

Never commit `.env` to GitHub.

It is already included in `.gitignore`.

---

# ▶️ Run QueryLens

QueryLens uses two processes:

### Terminal 1 — FastAPI

```bash
cd src
uvicorn api:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

### Terminal 2 — Streamlit

```bash
cd src
streamlit run app.py
```

Then open the Streamlit URL shown in your terminal.

---

# 🔌 API Reference

## `POST /upload`

Upload one or multiple documents.

### Form fields

```text
files
doc_type
```

Example:

```text
files = research.pdf
doc_type = official
```

The endpoint:

1. validates the extension
2. reads the file
3. calculates SHA-256
4. skips duplicates
5. stores the file
6. loads the document
7. creates chunks
8. updates FAISS
9. updates BM25
10. returns document IDs and errors

---

## `POST /query`

Ask a question about uploaded documents.

### Request

```json
{
  "query": "What are the main findings?",
  "conversation_id": "demo-conversation"
}
```

### Response

```json
{
  "answer": "The main findings are ...",
  "citations": [
    {
      "chunk_id": "abc123",
      "claim": "The study found...",
      "doc_name": "research.pdf",
      "page": 7,
      "snippet": "The study found..."
    }
  ]
}
```

---

## `GET /documents`

Returns uploaded documents and their chunk counts.

Example response:

```json
{
  "documents": [
    {
      "doc_id": "document-id",
      "name": "research.pdf",
      "doc_type": "official",
      "chunk_count": 24
    }
  ]
}
```

---

## `GET /evaluation/metrics`

Returns previously generated RAGAS evaluation results.

If no evaluation file exists:

```json
{
  "message": "No evaluation results found. Run the eval script first."
}
```

---

# 🧪 Evaluation

QueryLens includes a RAGAS evaluation script:

```text
src/Evaluation.py
```

It evaluates:

- **Answer Relevancy**
- **Faithfulness**

The evaluation pipeline takes:

```text
User Question
      +
Retrieved Context
      +
Generated Answer
      +
Reference Answer
      ↓
    RAGAS
      ↓
Evaluation Metrics
```

Results are appended to:

```text
evaluation_results.json
```

The API can expose those results through:

```text
GET /evaluation/metrics
```

---

# 🧩 Design Decisions

## Why RAG instead of directly asking Gemini?

The required information is often contained inside the user's documents.

Sending the question directly to an LLM can produce an answer that is:

- less relevant
- not grounded in the provided document
- unable to reference the exact source

RAG solves this by injecting relevant external knowledge into the LLM's context without fine-tuning the model.

---

## Why hybrid retrieval?

A pure vector search system can miss exact terms.

A pure keyword system can miss semantic relationships.

For example:

```text
Vector search:
"authentication failure"
        ≈
"login credentials were rejected"
```

while BM25 is excellent at:

```text
"OAuth2"
"JWT"
"RFC 7519"
"CLF-C02"
"QueryLens"
```

Combining them provides a stronger retrieval signal.

---

## Why RRF?

FAISS and BM25 produce different score scales.

Comparing their raw scores directly is not ideal.

RRF avoids the need to normalize those scores by combining their **rank positions**.

That makes the fusion simple, stable and easy to reason about.

---

## Why rewrite conversational queries?

Consider:

```text
Q1: What was the company's revenue in 2024?

Q2: What about 2025?
```

Q2 is not a complete retrieval query.

Query rewriting transforms it into something closer to:

```text
What was the company's revenue in 2025?
```

The retriever can then work with a meaningful standalone question.

---

# 🛡️ Reliability & Safety Features

QueryLens includes several defensive mechanisms.

### Duplicate detection

Files are hashed using SHA-256.

```text
same content
    ↓
same hash
    ↓
skip duplicate
```

### Filename sanitization

Uploaded filenames are sanitized before being written to disk.

### Unique upload directories

Every upload gets its own UUID-based directory.

### Unsupported file handling

Unsupported formats are rejected instead of being ingested.

### Partial batch failure handling

If one document fails, other valid documents can still be ingested.

### Citation validation

The application verifies that an LLM-generated citation refers to a retrieved chunk.

### Structured LLM output

Gemini is asked to produce a validated Pydantic structure instead of arbitrary JSON.

---

# ⚡ Performance Design

A key design decision is that the FAISS index is **updated during upload**, rather than rebuilt for every query.

### Upload

```text
New chunks
   ↓
Create embeddings
   ↓
Add to FAISS
   ↓
Rebuild BM25 over current chunks
```

### Query

```text
Question
   ↓
Existing FAISS index
      +
Existing BM25 index
   ↓
Hybrid retrieval
```

This avoids repeatedly embedding the entire corpus for every question.

---

# 🗂️ Current State Management

The current implementation intentionally keeps application state **in process memory**.

That includes:

```text
FAISS index
BM25 index
uploaded document metadata
duplicate hashes
conversation histories
```

This makes the project simple and excellent for:

- local development
- demos
- portfolio projects
- experimentation
- RAG learning

However, restarting the backend clears this state.

For production deployment, this could be replaced with persistent storage such as:

```text
PostgreSQL
+
Persistent vector database
+
Object storage
+
Redis / database-backed sessions
```

---

# 🧠 What I Learned Building QueryLens

This project is not just a "chat with PDF" application.

The interesting engineering problems are inside the pipeline:

### 1. Retrieval matters more than blindly increasing model size

A better context often produces a better answer than simply using a larger model.

### 2. Semantic search and keyword search have different strengths

Neither should automatically be treated as the universal solution.

### 3. Citation generation needs validation

An LLM can generate a plausible-looking citation.

That does not mean the citation is real.

### 4. Conversational retrieval is different from normal retrieval

A follow-up question often needs rewriting before retrieval.

### 5. RAG is an end-to-end system

The quality depends on:

```text
Loading
  ↓
Chunking
  ↓
Embedding
  ↓
Retrieval
  ↓
Ranking
  ↓
Prompting
  ↓
Generation
  ↓
Citation validation
```

A weak stage can affect the final answer.

---

# 🔮 Future Improvements

Potential next steps:

- [ ] Persistent vector database
- [ ] PostgreSQL document metadata
- [ ] User authentication
- [ ] Per-user document collections
- [ ] Persistent conversations
- [ ] Streaming Gemini responses
- [ ] Document deletion endpoint
- [ ] Chunk inspection/debug endpoint
- [ ] Better OCR support for scanned PDFs
- [ ] Reranking model after hybrid retrieval
- [ ] Query/result caching
- [ ] Background document ingestion
- [ ] Async FastAPI endpoints
- [ ] Better evaluation dataset management
- [ ] Retrieval precision/recall dashboard
- [ ] Deployment with Docker
- [ ] Cloud object storage
- [ ] Production observability and logging

---

# 🧪 Example Questions

Once documents are uploaded, try questions like:

```text
What are the main objectives of this document?

Summarize the methodology.

What were the key findings?

Which section discusses the limitations?

What changed between 2024 and 2025?

According to the document, why did this happen?

What does the document say about authentication?

Compare the two uploaded documents.
```

For conversational retrieval:

```text
What was the revenue in 2024?

What about 2025?

Why did it change?

Does the document mention the reason?
```

---

# 📸 Project Highlights

### Multi-document understanding

```text
📄 report.pdf
📄 research.docx
📄 notes.txt
📄 specification.md
        ↓
     QueryLens
        ↓
   One searchable
   knowledge space
```

### Hybrid retrieval

```text
         User Query
             │
       ┌─────┴─────┐
       ▼           ▼
     FAISS        BM25
   semantic     keyword
       │           │
       └─────┬─────┘
             ▼
            RRF
             ▼
      Relevant Context
```

### Grounded generation

```text
Retrieved Evidence
        ↓
      Gemini
        ↓
Structured Answer
        ↓
Citation Validation
        ↓
Trustworthy Response
```

---

# 🎥 Demo

> **Demo video coming soon.**

A recommended portfolio demo flow:

```text
0:00  Project introduction
0:20  Upload multiple documents
0:40  Show document processing
1:00  Ask a factual question
1:20  Show citations
1:40  Ask a follow-up question
2:00  Explain hybrid retrieval
2:30  Show architecture
3:00  Explain RRF + citation validation
```

This is especially useful for a portfolio/GitHub repository because it shows both the **product** and the **engineering behind it**.

---

# 💼 Portfolio / Interview Summary

### One-line version

> **QueryLens is a multi-document RAG assistant that combines FAISS semantic search, BM25 keyword retrieval and Reciprocal Rank Fusion to generate grounded Gemini answers with validated document-level citations.**

### Short technical version

> Built a FastAPI + Streamlit RAG system supporting PDF, DOCX, TXT and Markdown documents. Implemented page-aware chunking, MiniLM embeddings, FAISS + BM25 hybrid retrieval, RRF ranking, conversational query rewriting, structured Gemini output and citation validation.

### Interview explanation

```text
User uploads documents
        ↓
Documents are loaded and split into page-aware chunks
        ↓
Chunks are embedded into FAISS
and indexed with BM25
        ↓
User asks a question
        ↓
Follow-up questions are rewritten
using conversation history
        ↓
FAISS + BM25 retrieve relevant chunks
        ↓
RRF combines both rankings
        ↓
Top chunks are passed to Gemini
        ↓
Gemini returns structured answer + chunk IDs
        ↓
QueryLens validates those chunk IDs
        ↓
Final answer + source citations
```

---

# 👨‍💻 Author

**Raghav Mandloi**

Computer Science Engineering  
Backend Systems • AI/ML • Cloud Engineering

### Focus Areas

- Python
- FastAPI
- Backend Engineering
- RAG Systems
- Generative AI
- LLM Applications
- Vector Search
- Hybrid Retrieval
- PostgreSQL
- AWS / Cloud
- Docker
- Kubernetes

---

# ⭐ If You Find This Project Interesting

If this project helped you understand RAG, hybrid retrieval or grounded LLM applications:

**⭐ Star the repository**  
**🍴 Fork it**  
**🧠 Explore the retrieval pipeline**  
**💬 Open an issue with ideas or improvements**

---

## 📜 License

Add your preferred license here, for example:

```text
MIT License
```

---

<p align="center">
  <strong>QueryLens</strong>
  <br/>
  <em>Retrieve the evidence. Understand the context. Generate the answer. Verify the source.</em>
</p>
