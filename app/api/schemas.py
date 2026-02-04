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
