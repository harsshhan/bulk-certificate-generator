from datetime import datetime, timezone

from app.worker import celery_app
from app.database import SessionLocal
from app.models.job import GenerationJob, JobStatus
from app.models.certificate import Certificate, CertificateStatus
from app.services.certificate_service import run_single_certificate
from sqlalchemy import select


def finalize_job_if_complete(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.scalar(
            select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
        )

        if job is None:
            return

        certificate_statuses = db.scalars(
            select(Certificate.status).where(Certificate.job_id == job_id)
        ).all()

        unfinished_exists = any(
            status in {
                CertificateStatus.PENDING,
                CertificateStatus.PROCESSING,
            }
            for status in certificate_statuses
        )

        if unfinished_exists:
            return

        failed_exists = any(
            status == CertificateStatus.FAILED
            for status in certificate_statuses
        )

        job.status = (
            JobStatus.COMPLETED_WITH_ERRORS
            if failed_exists
            else JobStatus.COMPLETED
        )

        job.completed_at = datetime.now(timezone.utc)

        db.commit()


def mark_certificate_failed(certificate_id: int) -> None:
    with SessionLocal() as db:
        certificate = db.get(Certificate, certificate_id)

        if certificate is None:
            return

        certificate.status = CertificateStatus.FAILED
        certificate.error_code = "RETRIES_EXHAUSTED"
        certificate.error_message = (
            "Certificate generation failed after exhausting retries"
        )
        certificate.completed_at = datetime.now(timezone.utc)

        job_id = certificate.job_id

        db.commit()

    finalize_job_if_complete(job_id)


@celery_app.task(
    name="certificates.process_bulk_job",
)
def process_bulk_job_task(job_id: int) -> None:
    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)

        if job is None:
            return

        job.status = JobStatus.PROCESSING
        job.completed_at = None

        certificate_ids = [
            certificate.id
            for certificate in job.certificates
            if certificate.status == CertificateStatus.PENDING
        ]

        db.commit()

    if not certificate_ids:
        finalize_job_if_complete(job_id)
        return

    for certificate_id in certificate_ids:
        process_certificate_task.delay(certificate_id)


@celery_app.task(
    bind=True,
    name="certificates.process_certificate",
    max_retries=3,
    retry_backoff=2,
    retry_backoff_max=30,
    retry_jitter=False,
)
def process_certificate_task(self, certificate_id: int) -> None:
    try:
        run_single_certificate(certificate_id)

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            mark_certificate_failed(certificate_id)
            raise

        raise self.retry(exc=exc)

    else:
        with SessionLocal() as db:
            certificate = db.get(Certificate, certificate_id)

            if certificate is None:
                return

            job_id = certificate.job_id

        finalize_job_if_complete(job_id)