from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .database import Base


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    calls: Mapped[list["Call"]] = relationship("Call", back_populates="batch")
    messages: Mapped[list["BatchMessage"]] = relationship("BatchMessage", back_populates="batch")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    call_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    publisher: Mapped[str] = mapped_column(String(120))
    buyer: Mapped[str] = mapped_column(String(120))
    recording_url: Mapped[str] = mapped_column(String(600))
    caller_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    no_payout_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    billable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    conversion_barrier: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped["Batch | None"] = relationship("Batch", back_populates="calls")
    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="call")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    call_db_id: Mapped[int] = mapped_column(ForeignKey("calls.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    call: Mapped["Call"] = relationship("Call", back_populates="messages")


class BatchMessage(Base):
    __tablename__ = "batch_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped["Batch"] = relationship("Batch", back_populates="messages")
