from datetime import date

from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus

from unittest.mock import patch

from app.database import SessionLocal
from app.services.certificate_service import (
    process_certificate,
    process_bulk_job,
)

def create_test_job(db):
    job = GenerationJob(
        event_name="Python Workshop",
        event_date=date(2026, 10, 7),
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    certificate = Certificate(
        job_id=job.id,
        recipient_name="Alice Johnson",
        recipient_email="alice@example.com",
        status=CertificateStatus.PENDING,
    )
    db.add(certificate)
    db.commit()
    db.refresh(job)
    db.refresh(certificate)

    return job, certificate

def test_process_certificate_success():
    with SessionLocal() as db:
        job, certificate = create_test_job(db)

        with patch(
            "app.services.certificate_service.generate_certificate"
        ) as mock_generate:
            process_certificate(
                certificate_id=certificate.id,
                db=db,
                event_name=job.event_name,
                event_date=job.event_date.isoformat(),
            )

        db.refresh(certificate)

        assert certificate.status == CertificateStatus.SUCCESS
        assert certificate.file_path is not None
        assert certificate.error_message is None
        assert certificate.completed_at is not None

        mock_generate.assert_called_once()

def test_process_certificate_failure():
    with SessionLocal() as db:
        job, certificate = create_test_job(db)

        with patch(
            "app.services.certificate_service.generate_certificate",
            side_effect=OSError("Disk write failed"),
        ) as mock_generate:
            process_certificate(
                certificate_id=certificate.id,
                db=db,
                event_name=job.event_name,
                event_date=job.event_date.isoformat(),
            )

        db.refresh(certificate)

        assert certificate.status == CertificateStatus.FAILED
        assert certificate.error_code == "GENERATION_ERROR"
        assert certificate.error_message == "Failed to generate certificate"
        assert certificate.completed_at is not None
        assert certificate.file_path is None

        mock_generate.assert_called_once()
    
def test_bulk_job_completes_when_all_certificates_succeed():
    with SessionLocal() as db:
        job, first_certificate = create_test_job(db)

        second_certificate = Certificate(
            job_id=job.id,
            recipient_name="Bob Smith",
            recipient_email="bob@example.com",
            status=CertificateStatus.PENDING,
        )
        db.add(second_certificate)
        db.commit()
        db.refresh(second_certificate)

        with patch(
            "app.services.certificate_service.generate_certificate"
        ) as mock_generate:
            process_bulk_job(job.id, db)

        db.refresh(job)
        db.refresh(first_certificate)
        db.refresh(second_certificate)

        assert first_certificate.status == CertificateStatus.SUCCESS
        assert second_certificate.status == CertificateStatus.SUCCESS

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None

        assert mock_generate.call_count == 2
        
def test_bulk_job_continues_when_certificate_fails():
    with SessionLocal() as db:
        job, first_certificate = create_test_job(db)

        second_certificate = Certificate(
            job_id=job.id,
            recipient_name="Bob Smith",
            recipient_email="bob@example.com",
            status=CertificateStatus.PENDING,
        )
        db.add(second_certificate)
        db.commit()
        db.refresh(second_certificate)

        def generate_with_one_failure(
            recipient_name,
            event_name,
            event_date,
            output_path,
        ):
            if recipient_name == "Alice Johnson":
                raise OSError("Simulated PDF generation failure")

        with patch(
            "app.services.certificate_service.generate_certificate",
            side_effect=generate_with_one_failure,
        ):
            process_bulk_job(job.id, db)

        db.refresh(job)
        db.refresh(first_certificate)
        db.refresh(second_certificate)

        assert first_certificate.status == CertificateStatus.FAILED
        assert second_certificate.status == CertificateStatus.SUCCESS
        assert job.status == JobStatus.COMPLETED_WITH_ERRORS
        assert job.completed_at is not None