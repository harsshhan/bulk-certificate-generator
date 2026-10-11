from datetime import date
from unittest.mock import call, patch
import pytest

from app.database import SessionLocal
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.tasks.certificate_tasks import (
    finalize_job_if_complete,
    process_bulk_job_task,
    process_certificate_task,
)


def create_test_job(
    db,
    certificate_statuses=None,
):

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
        job_id, certificate_ids = create_test_job(
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
        job_id, certificate_ids = create_test_job(
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
        job_id, certificate_ids = create_test_job(db)

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