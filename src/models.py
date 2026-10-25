from pydantic import BaseModel
from typing import Optional

class Document(BaseModel):
    doc_id : str
    name : str
    doc_type : str

class Chunk(BaseModel):
    chunk_id : str
    doc_id : str
    text : str
    chunk_index : int
    page: int | None = None

class RetrievalResult(BaseModel):
    chunk: Chunk
    score: float

class LLMCitation(BaseModel):
    chunk_id: str
    claim: str


class LLMAnswer(BaseModel):
    text: str
    citations: list[LLMCitation]


class Citation(BaseModel):
    chunk_id: str
    claim: str
    doc_name: str
    page: Optional[int] = None
    snippet: str = ""


class Answer(BaseModel):
    text: str
    citations: list[Citation]
