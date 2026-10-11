import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateStatus
from app.generators.certificate_generator import generate_certificate
from app.models.job import GenerationJob, JobStatus
from app.database import SessionLocal

logger = logging.getLogger(__name__)

STORAGE_DIR = Path("storage/certificates")


def process_certificate(
    certificate_id: int,
    db: Session,
    event_name: str,
    event_date: str,
) -> None:
    certificate = db.get(Certificate, certificate_id)

    if certificate is None:
        raise ValueError(f"Certificate {certificate_id} not found")

    certificate.status = CertificateStatus.PROCESSING
    db.commit()

    output_path = STORAGE_DIR / f"{certificate.id}.pdf"

    try:
        generate_certificate(
            recipient_name=certificate.recipient_name,
            event_name=event_name,
            event_date=event_date,
            output_path=str(output_path),
        )

        certificate.file_path = str(output_path)
        certificate.status = CertificateStatus.SUCCESS
        certificate.error_code = None
        certificate.error_message = None
        certificate.completed_at = datetime.now(timezone.utc)

        db.commit()

    except Exception:
        logger.exception(
            "Certificate generation failed for certificate_id=%s",
            certificate.id,
        )

        output_path.unlink(missing_ok=True)
        certificate.status = CertificateStatus.PENDING
        certificate.file_path = None
        certificate.error_code = "GENERATION_ERROR"
        certificate.error_message = "Certificate generation attempt failed"
        certificate.completed_at = None

        db.commit()

        raise


def run_single_certificate(
    certificate_id: int,
    session_factory=None,
) -> None:
    if session_factory is None:
        session_factory = SessionLocal

    with session_factory() as db:

        result = db.execute(
            update(Certificate)
            .where(
                Certificate.id == certificate_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .values(status=CertificateStatus.PROCESSING)
        )

        if result.rowcount == 0:
            db.rollback()

            certificate = db.get(Certificate, certificate_id)
            if certificate is None:
                raise ValueError(
                    f"Certificate {certificate_id} not found"
                )
            
            logger.info(
                "Skipping certificate_id=%s because its status is %s",
                certificate_id,
                certificate.status,
            )
            return
            
        db.commit()

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

        process_certificate(
            certificate_id=certificate.id,
            db=db,
            event_name=job.event_name,
            event_date=job.event_date.isoformat(),
        )