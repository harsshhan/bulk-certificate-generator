import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateStatus
from app.generators.certificate_generator import generate_certificate
from app.models.job import GenerationJob, JobStatus
from app.database import SessionLocal
from uuid import uuid4

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/certificates")


def process_certificate(
    certificate_id: int,
    db: Session,
    event_name: str,
    event_date: str,
    processing_token: str,
) -> None:
    certificate = db.get(Certificate, certificate_id)

    if certificate is None:
        raise ValueError(f"Certificate {certificate_id} not found")

    owns_certificate = db.query(Certificate.id).filter(
        Certificate.id == certificate_id,
        Certificate.status == CertificateStatus.PROCESSING,
        Certificate.processing_token == processing_token,
    ).first()

    if owns_certificate is None:
        logger.info(
            "Skipping certificate_id=%s because processing ownership was lost",
            certificate_id,
        )
        return

    output_dir = STORAGE_DIR / "attempts"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{certificate_id}-{processing_token}.pdf"

    try:
        generate_certificate(
            recipient_name=certificate.recipient_name,
            event_name=event_name,
            event_date=event_date,
            output_path=str(output_path),
        )

    except Exception:
        logger.exception(
            "Certificate generation failed for certificate_id=%s",
            certificate_id,
        )

        output_path.unlink(missing_ok=True)

        try:
            result = db.execute(
                update(Certificate)
                .where(
                    Certificate.id == certificate_id,
                    Certificate.status == CertificateStatus.PROCESSING,
                    Certificate.processing_token == processing_token,
                )
                .values(
                    status=CertificateStatus.PENDING,
                    file_path=None,
                    error_code="GENERATION_ERROR",
                    error_message="Certificate generation attempt failed",
                    completed_at=None,
                    processing_started_at=None,
                    processing_token=None,
                )
            )

            db.commit()

            if result.rowcount == 0:
                logger.info(
                    "Certificate %s was no longer owned by this attempt",
                    certificate_id,
                )

        except Exception:
            db.rollback()
            logger.exception(
                "Could not reset certificate %s after generation failure",
                certificate_id,
            )
            raise

        raise

    try:
        result = db.execute(
            update(Certificate)
            .where(
                Certificate.id == certificate_id,
                Certificate.status == CertificateStatus.PROCESSING,
                Certificate.processing_token == processing_token,
            )
            .values(
                status=CertificateStatus.SUCCESS,
                file_path=str(output_path),
                error_code=None,
                error_message=None,
                completed_at=datetime.now(timezone.utc),
                processing_started_at=None,
                processing_token=None,
            )
        )

        if result.rowcount != 1:
            db.rollback()

            output_path.unlink(missing_ok=True)

            logger.info(
                "Discarded output for certificate_id=%s because "
                "processing ownership was lost",
                certificate_id,
            )
            return

        db.commit()

    except Exception:
        db.rollback()

        logger.exception(
            "Could not finalize certificate_id=%s after generation",
            certificate_id,
        )
        raise


def run_single_certificate(
    certificate_id: int,
    session_factory=None,
) -> None:
    if session_factory is None:
        session_factory = SessionLocal

    processing_token = str(uuid4())
    processing_started_at = datetime.now(timezone.utc)

    with session_factory() as db:
        # Read the certificate and its job before claiming it.
        certificate = db.get(Certificate, certificate_id)

        if certificate is None:
            raise ValueError(
                f"Certificate {certificate_id} not found"
            )

        job = db.get(GenerationJob, certificate.job_id)

        if job is None:
            raise ValueError(
                f"Generation job not found for certificate {certificate_id}"
            )

        result = db.execute(
            update(Certificate)
            .where(
                Certificate.id == certificate_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .values(
                status=CertificateStatus.PROCESSING,
                processing_started_at=processing_started_at,
                processing_token=processing_token,
            )
        )

        if result.rowcount != 1:
            db.rollback()

            logger.info(
                "Skipping certificate_id=%s because it is no longer pending",
                certificate_id,
            )
            return

        db.commit()

        process_certificate(
            certificate_id=certificate_id,
            db=db,
            event_name=job.event_name,
            event_date=job.event_date.isoformat(),
            processing_token=processing_token,
        )