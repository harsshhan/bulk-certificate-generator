import pytest
from pydantic import ValidationError

from app.models.certificate import CertificateStatus
from app.models.job import JobStatus
from app.schemas.certificate import CertificateResponse
from app.schemas.job import (
    CreateGenerationJobRequest,
    CreateGenerationJobResponse,
)

def test_valid_generation_job_request():
    request = CreateGenerationJobRequest(
        event_name="Python Workshop",
        event_date="2026-10-07",
        recipients=[
            {
                "name": "Alice Johnson",
                "email": "alice@example.com",
            }
        ],
    )
    assert request.event_name == "Python Workshop"
    assert len(request.recipients) == 1

def test_invalid_email():
    with pytest.raises(ValidationError):
        CreateGenerationJobRequest(
            event_name="Python Workshop",
            event_date="2026-10-07",
            recipients=[
                {
                    "name": "Alice Johnson",
                    "email": "not-an-email",
                }
            ],
        )

def test_empty_recipients():
    with pytest.raises(ValidationError):
        CreateGenerationJobRequest(
            event_name="Python Workshop",
            event_date="2026-10-07",
            recipients=[],
        )

def test_empty_event_name():
    with pytest.raises(ValidationError):
        CreateGenerationJobRequest(
            event_name="",
            event_date="2026-10-07",
            recipients=[
                {
                    "name": "Alice Johnson",
                    "email": "alice@example.com",
                }
            ],
        )


# CertificateResponse tests

def test_successful_certificate_response():
    response = CertificateResponse(
        certificate_id=1,
        recipient_name="Alice Johnson",
        status=CertificateStatus.SUCCESS,
        download_url="/certificates/1",
    )

    assert response.certificate_id == 1
    assert response.status == CertificateStatus.SUCCESS
    assert response.download_url == "/certificates/1"
    assert response.error_message is None


def test_failed_certificate_response():
    response = CertificateResponse(
        certificate_id=2,
        recipient_name="Bob Smith",
        status=CertificateStatus.FAILED,
        error_message="Failed to save certificate file",
    )

    assert response.status == CertificateStatus.FAILED
    assert response.download_url is None
    assert response.error_message == "Failed to save certificate file"


def test_invalid_certificate_status():
    with pytest.raises(ValidationError):
        CertificateResponse(
            certificate_id=3,
            recipient_name="Charlie",
            status="INVALID",
        )


def test_generation_job_response():
    response = CreateGenerationJobResponse(
        job_id=10,
        status=JobStatus.PENDING,
        total_count=5,
    )

    assert response.job_id == 10
    assert response.status == JobStatus.PENDING
    assert response.total_count == 5