from datetime import date
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.services.certificate_service import (
    process_certificate,
    run_single_certificate,
)


def create_test_job(db):
    job = GenerationJob(
        event_name="Test Event",
        event_date=date(2026, 10, 11),
        status=JobStatus.PROCESSING,
    )
    db.add(job)
    db.flush()

    certificate = Certificate(
        job_id=job.id,
        recipient_name="Alice",
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

            mock_generate.assert_called_once()

        db.refresh(certificate)

        assert certificate.status == CertificateStatus.SUCCESS
        assert certificate.file_path is not None
        assert certificate.error_code is None
        assert certificate.error_message is None
        assert certificate.completed_at is not None


def test_process_certificate_failure_is_retryable():
    with SessionLocal() as db:
        job, certificate = create_test_job(db)

        with patch(
            "app.services.certificate_service.generate_certificate",
            side_effect=OSError("Disk write failed"),
        ) as mock_generate:
            with pytest.raises(
                OSError,
                match="Disk write failed",
            ):
                process_certificate(
                    certificate_id=certificate.id,
                    db=db,
                    event_name=job.event_name,
                    event_date=job.event_date.isoformat(),
                )

            mock_generate.assert_called_once()

        db.refresh(certificate)

        assert certificate.status == CertificateStatus.PENDING
        assert certificate.file_path is None
        assert certificate.error_code == "GENERATION_ERROR"
        assert (
            certificate.error_message
            == "Certificate generation attempt failed"
        )
        assert certificate.completed_at is None


def test_run_single_certificate():
    with SessionLocal() as db:
        _, certificate = create_test_job(db)
        certificate_id = certificate.id

    with patch(
        "app.services.certificate_service.generate_certificate"
    ) as mock_generate:
        run_single_certificate(certificate_id)

        mock_generate.assert_called_once()

    with SessionLocal() as db:
        certificate = db.get(Certificate, certificate_id)

        assert certificate is not None
        assert certificate.status == CertificateStatus.SUCCESS
        assert certificate.file_path is not None
        assert certificate.completed_at is not None


def test_run_single_certificate_not_found():
    with pytest.raises(
        ValueError,
        match="Certificate 999999 not found",
    ):
        run_single_certificate(999999)