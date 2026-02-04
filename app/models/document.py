import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=True)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), nullable=False, default=DocumentStatus.processing)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document",
                          cascade="all, delete-orphan")
