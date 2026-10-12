from datetime import date, datetime, timedelta, timezone
from unittest.mock import call, patch

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.tasks.certificate_tasks import (
    finalize_job_if_complete,
    process_bulk_job_task,
    process_certificate_task,
    recover_stale_certificates,
)


def create_test_job(db, certificate_statuses=None):
    if certificate_statuses is None:
        certificate_statuses = [
            CertificateStatus.PENDING,
            CertificateStatus.PENDING,
        ]

    job = GenerationJob(
        event_name="Test Event",
        event_date=date(2026, 10, 11),
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()

    certificates = [
        Certificate(
            job_id=job.id,
            recipient_name=f"Recipient {index}",
            recipient_email=f"recipient{index}@example.com",
            status=status,
        )
        for index, status in enumerate(certificate_statuses, start=1)
    ]

    db.add_all(certificates)
    db.commit()
    db.refresh(job)

    certificate_ids = [certificate.id for certificate in certificates]

    return job.id, certificate_ids


def test_bulk_job_schedules_individual_certificate_tasks():
    with SessionLocal() as db:
        job_id, certificate_ids = create_test_job(db)

    with patch(
        "app.tasks.certificate_tasks.process_certificate_task.delay"
    ) as mock_delay:
        process_bulk_job_task.run(job_id)

    mock_delay.assert_has_calls(
        [call(certificate_id) for certificate_id in certificate_ids]
    )
    assert mock_delay.call_count == len(certificate_ids)

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)
        assert job.status == JobStatus.PROCESSING


def test_bulk_job_does_not_schedule_tasks_when_job_is_missing():
    with patch(
        "app.tasks.certificate_tasks.process_certificate_task.delay"
    ) as mock_delay:
        process_bulk_job_task.run(999999)

    mock_delay.assert_not_called()


def test_job_completes_when_all_certificates_succeed():
    with SessionLocal() as db:
        job_id, _ = create_test_job(
            db,
            [
                CertificateStatus.SUCCESS,
                CertificateStatus.SUCCESS,
            ],
        )

    finalize_job_if_complete(job_id)

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)

        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None


def test_job_completes_with_errors_when_certificate_fails():
    with SessionLocal() as db:
        job_id, _ = create_test_job(
            db,
            [
                CertificateStatus.SUCCESS,
                CertificateStatus.FAILED,
            ],
        )

    finalize_job_if_complete(job_id)

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)

        assert job.status == JobStatus.COMPLETED_WITH_ERRORS
        assert job.completed_at is not None


def test_certificate_task_retries_on_failure():
    with SessionLocal() as db:
        _, certificate_ids = create_test_job(db)

    certificate_id = certificate_ids[0]

    with (
        patch(
            "app.tasks.certificate_tasks.run_single_certificate",
            side_effect=RuntimeError("Temporary generation failure"),
        ),
        patch.object(
            process_certificate_task,
            "retry",
            side_effect=RuntimeError("Retry scheduled"),
        ) as mock_retry,
    ):
        with pytest.raises(
            RuntimeError,
            match="Retry scheduled",
        ):
            process_certificate_task.run(certificate_id)

    mock_retry.assert_called_once()


def test_certificate_task_marks_failed_after_retries_exhausted():
    with SessionLocal() as db:
        _, certificate_ids = create_test_job(db)

    certificate_id = certificate_ids[0]

    with (
        patch(
            "app.tasks.certificate_tasks.run_single_certificate",
            side_effect=RuntimeError("Generation failed"),
        ),
        patch(
            "app.tasks.certificate_tasks.mark_certificate_failed"
        ) as mock_mark_failed,
    ):
        process_certificate_task.push_request(
            retries=process_certificate_task.max_retries
        )

        try:
            with pytest.raises(
                RuntimeError,
                match="Generation failed",
            ):
                process_certificate_task.run(certificate_id)
        finally:
            process_certificate_task.pop_request()

    mock_mark_failed.assert_called_once_with(certificate_id)


def test_job_remains_processing_when_certificates_are_unfinished():
    with SessionLocal() as db:
        job_id, _ = create_test_job(
            db,
            [
                CertificateStatus.SUCCESS,
                CertificateStatus.PROCESSING,
            ],
        )

        job = db.get(GenerationJob, job_id)
        job.status = JobStatus.PROCESSING
        db.commit()

    finalize_job_if_complete(job_id)

    with SessionLocal() as db:
        job = db.get(GenerationJob, job_id)

        assert job.status == JobStatus.PROCESSING
        assert job.completed_at is None


def test_recovers_stale_processing_certificate():
    stale_time = datetime.now(timezone.utc) - timedelta(
        seconds=settings.certificate_processing_timeout_seconds + 60
    )

    with SessionLocal() as db:
        job_id, certificate_ids = create_test_job(
            db,
            [CertificateStatus.PROCESSING],
        )

        certificate = db.get(Certificate, certificate_ids[0])
        certificate.processing_started_at = stale_time
        certificate.processing_token = "stale-token-123"
        db.commit()

    with patch(
        "app.tasks.certificate_tasks.process_certificate_task.delay"
    ) as mock_delay:
        recovered_count = recover_stale_certificates.run()

    assert recovered_count == 1
    mock_delay.assert_called_once_with(certificate_ids[0])

    with SessionLocal() as db:
        certificate = db.get(Certificate, certificate_ids[0])

        assert certificate.status == CertificateStatus.PENDING
        assert certificate.processing_started_at is None
        assert certificate.processing_token is None
        assert certificate.error_code == "PROCESSING_TIMEOUT"
        assert certificate.file_path is None
        assert certificate.completed_at is None


def test_does_not_recover_recently_processing_certificate():
    recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)

    with SessionLocal() as db:
        _, certificate_ids = create_test_job(
            db,
            [CertificateStatus.PROCESSING],
        )

        certificate = db.get(Certificate, certificate_ids[0])
        certificate.processing_started_at = recent_time
        certificate.processing_token = "active-token-123"
        db.commit()

    with patch(
        "app.tasks.certificate_tasks.process_certificate_task.delay"
    ) as mock_delay:
        recovered_count = recover_stale_certificates.run()

    assert recovered_count == 0
    mock_delay.assert_not_called()

    with SessionLocal() as db:
        certificate = db.get(Certificate, certificate_ids[0])

        assert certificate.status == CertificateStatus.PROCESSING
        assert certificate.processing_token == "active-token-123"


def test_does_not_recover_processing_certificate_without_timestamp():
    with SessionLocal() as db:
        _, certificate_ids = create_test_job(
            db,
            [CertificateStatus.PROCESSING],
        )

        certificate = db.get(Certificate, certificate_ids[0])
        certificate.processing_started_at = None
        certificate.processing_token = "active-token-123"
        db.commit()

    with patch(
        "app.tasks.certificate_tasks.process_certificate_task.delay"
    ) as mock_delay:
        recovered_count = recover_stale_certificates.run()

    assert recovered_count == 0
    mock_delay.assert_not_called()

    with SessionLocal() as db:
        certificate = db.get(Certificate, certificate_ids[0])

        assert certificate.status == CertificateStatus.PROCESSING
        assert certificate.processing_token == "active-token-123"