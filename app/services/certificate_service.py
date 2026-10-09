import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateStatus
from app.generators.certificate_generator import generate_certificate
from app.models.job import GenerationJob, JobStatus

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

    except Exception:
        logger.exception(
            "Certificate generation failed for certificate_id=%s",
            certificate.id,
        )

        certificate.status = CertificateStatus.FAILED
        certificate.error_code = "GENERATION_ERROR"
        certificate.error_message = "Failed to generate certificate"

        output_path.unlink(missing_ok=True)

    finally:
        certificate.completed_at = datetime.now(timezone.utc)
        db.commit()

from app.models.job import GenerationJob, JobStatus


def process_bulk_job(job_id: int, db: Session) -> None:
    job = db.get(GenerationJob, job_id)

    if job is None:
        logger.error("Generation job not found: job_id=%s", job_id)
        return

    job.status = JobStatus.PROCESSING
    db.commit()

    for certificate in job.certificates:
        if certificate.status != CertificateStatus.PENDING:
            continue

        process_certificate(
            certificate_id=certificate.id,
            db=db,
            event_name=job.event_name,
            event_date=job.event_date.isoformat(),
        )

    db.refresh(job)

    failed_count = sum(
        certificate.status == CertificateStatus.FAILED
        for certificate in job.certificates
    )

    pending_count = sum(
        certificate.status in {
            CertificateStatus.PENDING,
            CertificateStatus.PROCESSING,
        }
        for certificate in job.certificates
    )

    if pending_count > 0:
        logger.error(
            "Job %s still has unfinished certificates",
            job_id,
        )
        return

    if failed_count > 0:
        job.status = JobStatus.COMPLETED_WITH_ERRORS
    else:
        job.status = JobStatus.COMPLETED

    job.completed_at = datetime.now(timezone.utc)
    db.commit()

def run_bulk_job(job_id: int) -> None:
    from app.database import SessionLocal

    with SessionLocal() as db:
        process_bulk_job(job_id, db)