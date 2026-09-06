import os

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnablePassthrough

from models import RetrievalResult, Answer


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

model = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0.3
)


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
- Each citation must reference the exact chunk_id that supports the claim.
- Never invent or modify a chunk_id.
- Use the document name associated with the cited chunk.
- If a claim is supported by multiple chunks, cite each relevant chunk.
- Do not create citations for unsupported claims.

For the citations:
- "claim" = the specific factual statement being supported.
- "doc_name" = the source document containing that chunk.

User Question:
{query}

Retrieved Documents:
{documents}
"""

# ============================================================
# BUILD DOCUMENT CONTEXT
# ============================================================

def build_documents_block(
    results: list[RetrievalResult],
    doc_name_lookup: dict[str, str]
) -> str:

    blocks = []

    for i, result in enumerate(results, start=1):

        doc_name = doc_name_lookup.get(
            result.chunk.doc_id,
            "Unknown document"
        )

        blocks.append(
            f"Document {i}\n"
            f"Source: {doc_name}\n"
            f"Content:\n{result.chunk.text}"
        )

    return "\n\n".join(blocks)

# ============================================================
# STRUCTURED OUTPUT
# ============================================================

structured_model = model.with_structured_output(Answer)


# ============================================================
# CHAIN
# ============================================================

prompt = PromptTemplate(
    template=PROMPT,
    input_variables=[
        "query",
        "documents"
    ]
)

chain = prompt | structured_model


# ============================================================
# SYNTHESIZE ANSWER
# ============================================================

def synthesize_answer(
    query: str,
    results: list[RetrievalResult],
    doc_name_lookup: dict[str, str]
) -> Answer:

    documents = build_documents_block(
        results,
        doc_name_lookup
    )

    answer = chain.invoke({
        "query": query,
        "documents": documents
    })

    return answer