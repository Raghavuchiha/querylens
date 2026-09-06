from pydantic import BaseModel

class Document(BaseModel):
    doc_id : str
    name : str
    doc_type : str

class Chunk(BaseModel):
    chunk_id : str
    doc_id : str
    text : str
    chunk_index : int

class RetrievalResult(BaseModel):
    chunk: Chunk
    score: float

class Citation(BaseModel):
    claim: str
    doc_name: str



class Answer(BaseModel):
    text: str
    citations: list[Citation]
