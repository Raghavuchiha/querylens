from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
#from langchain_google_genai import ChatGoogleGenerativeAI
from llm import get_llm

from models import Answer, Citation, LLMAnswer, RetrievalResult

SNIPPET_CHARS = 200

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

#model = ChatGoogleGenerativeAI(
#    model="gemini-3.6-flash",
#    temperature=0.3
#)

model = get_llm(temperature=0.3)


# ============================================================
# PROMPT
# ============================================================

PROMPT = """
You are a precise document-based research assistant.

Answer the user's question using ONLY the retrieved documents provided below.

STRICT RULES:
- Do not use outside knowledge.
- Do not make assumptions or infer unsupported facts.
- If the documents do not contain enough information, state that clearly.
- Keep the answer concise and directly relevant to the question.
- Every factual claim must be supported by the retrieved documents.
- Each citation must copy the exact chunk_id (shown as "Chunk ID") of the chunk that supports the claim.
- Never invent or modify a chunk_id.
- If a claim is supported by multiple chunks, cite each relevant chunk.
- Do not create citations for unsupported claims.

For the citations:
- "claim" = the specific factual statement being supported.
- "chunk_id" = the Chunk ID of the supporting chunk.

User Question:
{query}

Retrieved Documents:
{documents}
"""

prompt = PromptTemplate(
    template=PROMPT,
    input_variables=["query", "documents"]
)

structured_model = model.with_structured_output(LLMAnswer)
chain = prompt | structured_model


# ============================================================
# BUILD DOCUMENT CONTEXT
# ============================================================

def build_documents_block(
    results: list[RetrievalResult],
    doc_name_lookup: dict[str, str]
) -> str:

    blocks = []

    for i, result in enumerate(results, start=1):
        chunk = result.chunk
        doc_name = doc_name_lookup.get(chunk.doc_id, "Unknown document")
        page = f"Page: {chunk.page}\n" if chunk.page else ""

        blocks.append(
            f"Document {i}\n"
            f"Chunk ID: {chunk.chunk_id}\n"
            f"Source: {doc_name}\n"
            f"{page}"
            f"Content:\n{chunk.text}"
        )

    return "\n\n".join(blocks)


# ============================================================
# SYNTHESIZE ANSWER
# ============================================================

def synthesize_answer(
    query: str,
    results: list[RetrievalResult],
    doc_name_lookup: dict[str, str]
) -> Answer:

    documents = build_documents_block(results, doc_name_lookup)

    llm_answer = chain.invoke({
        "query": query,
        "documents": documents
    })

    if llm_answer is None:
        return Answer(
            text="Sorry, I couldn't generate an answer for that. Please try again.",
            citations=[]
        )

    # Keep only citations that point at a chunk we actually retrieved,
    # and fill in doc name / page / snippet from our own data (not the LLM's).
    retrieved = {r.chunk.chunk_id: r.chunk for r in results}
    citations = []
    seen = set()

    for c in llm_answer.citations:
        chunk = retrieved.get(c.chunk_id.strip())
        if chunk is None:
            continue

        key = (chunk.chunk_id, c.claim)
        if key in seen:
            continue
        seen.add(key)

        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                claim=c.claim,
                doc_name=doc_name_lookup.get(chunk.doc_id, "Unknown document"),
                page=chunk.page,
                snippet=chunk.text[:SNIPPET_CHARS],
            )
        )

    return Answer(text=llm_answer.text, citations=citations)
