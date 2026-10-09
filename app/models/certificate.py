from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CertificateStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("generation_jobs.id"),
        nullable=False,
        index=True
    )

    recipient_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    status: Mapped[CertificateStatus] = mapped_column(
        SQLEnum(CertificateStatus),
        nullable=False,
        default=CertificateStatus.PENDING
    )

    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    job: Mapped["GenerationJob"] = relationship(
        back_populates="certificates"
    )