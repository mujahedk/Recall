from datetime import datetime
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str | None
    status: str
    page_count: int | None
    error: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkOut(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    page_start: int | None
    page_end: int | None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkCreateResult(BaseModel):
    document_id: int
    deleted_existing: int
    created: int


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    document_id: int | None = None  # optional filter


class CitationHit(BaseModel):
    doc_id: int
    doc_title: str
    chunk_id: int
    score: float
    page_start: int | None
    page_end: int | None
    snippet: str


class QueryResponse(BaseModel):
    query: str
    top_k: int
    hits: list[CitationHit]


class AnswerRequest(BaseModel):
    query: str
    top_k: int = 6
    document_id: int | None = None  # optional filter


class AnswerCitation(BaseModel):
    n: int
    doc_id: int
    doc_title: str
    chunk_id: int
    page_start: int | None
    page_end: int | None
    snippet: str
    score: float = 0.0


class AnswerResponse(BaseModel):
    query: str
    answer: str
    citations: list[AnswerCitation]
