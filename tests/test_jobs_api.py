from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.job import GenerationJob, JobStatus
from app.models.certificate import Certificate, CertificateStatus

client = TestClient(app)


def create_job_payload():
    return {
        "event_name": "Python Workshop",
        "event_date": "2026-10-07",
        "recipients": [
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
            },
            {
                "name": "Bob Smith",
                "email": "bob@example.com",
            },
        ],
    }


def create_completed_job():
    with SessionLocal() as db:
        job = GenerationJob(
            event_name="Python Workshop",
            event_date=date(2026, 10, 7),
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )

        db.add(job)
        db.flush()

        certificates = [
            Certificate(
                job_id=job.id,
                recipient_name="Alice Johnson",
                recipient_email="alice@example.com",
                status=CertificateStatus.SUCCESS,
                file_path=f"storage/certificates/{job.id}_alice.pdf",
                completed_at=datetime.now(timezone.utc),
            ),
            Certificate(
                job_id=job.id,
                recipient_name="Bob Smith",
                recipient_email="bob@example.com",
                status=CertificateStatus.SUCCESS,
                file_path=f"storage/certificates/{job.id}_bob.pdf",
                completed_at=datetime.now(timezone.utc),
            ),
        ]

        db.add_all(certificates)
        db.commit()
        db.refresh(job)

        return job.id


@patch("app.api.jobs.process_bulk_job_task.delay")
def test_create_job(mock_delay):
    response = client.post(
        "/jobs",
        json=create_job_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] > 0
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2

    mock_delay.assert_called_once_with(data["job_id"])


@patch("app.api.jobs.process_bulk_job_task.delay")
def test_get_job_status(mock_delay):
    job_id = create_completed_job()

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == job_id
    assert data["status"] == "COMPLETED"
    assert data["total_count"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0
    assert data["pending_count"] == 0


def test_get_nonexistent_job():
    response = client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@patch("app.api.jobs.process_bulk_job_task.delay")
def test_get_job_certificates(mock_delay):
    job_id = create_completed_job()

    response = client.get(f"/jobs/{job_id}/certificates")

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == job_id
    assert len(data["certificates"]) == 2

    first_certificate = data["certificates"][0]

    assert first_certificate["recipient_name"] == "Alice Johnson"
    assert first_certificate["status"] == "SUCCESS"
    assert first_certificate["download_url"] == (
        f"/certificates/{first_certificate['certificate_id']}"
    )
    assert first_certificate["error_message"] is None


def test_get_certificates_for_nonexistent_job():
    response = client.get("/jobs/999999/certificates")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"