from datetime import datetime, date, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SQLEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.certificate import Certificate


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    event_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus),
        nullable=False,
        default=JobStatus.PENDING
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
    
    certificates: Mapped[list["Certificate"]] = relationship(
    back_populates="job"
    )        