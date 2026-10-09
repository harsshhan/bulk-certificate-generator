from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus

client = TestClient(app)

def create_certificate(db, status, file_path=None):
    job = GenerationJob(
        event_name="Python Workshop",
        event_date="2026-10-07",
        status=JobStatus.COMPLETED,
    )
    db.add(job)
    db.flush()

    certificate = Certificate(
        job_id=job.id,
        recipient_name="Alice Johnson",
        recipient_email="alice@example.com",
        status=status,
        file_path=file_path,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return certificate

def test_download_certificate_success(tmp_path):
    pdf_path = tmp_path / "certificate.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nTest PDF content")

    with SessionLocal() as db:
        certificate = create_certificate(
            db,
            status=CertificateStatus.SUCCESS,
            file_path=str(pdf_path),
        )
        certificate_id = certificate.id

    response = client.get(f"/certificates/{certificate_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4\nTest PDF content"

def test_download_nonexistent_certificate():
    response = client.get("/certificates/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Certificate not found"

def test_download_pending_certificate():
    with SessionLocal() as db:
        certificate = create_certificate(
            db,
            status=CertificateStatus.PENDING,
        )
        certificate_id = certificate.id

    response = client.get(f"/certificates/{certificate_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Certificate is not available for download"
    )

def test_download_certificate_file_missing(tmp_path):
    missing_file = tmp_path / "missing_certificate.pdf"

    with SessionLocal() as db:
        certificate = create_certificate(
            db,
            status=CertificateStatus.SUCCESS,
            file_path=str(missing_file),
        )
        certificate_id = certificate.id

    response = client.get(f"/certificates/{certificate_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Certificate file not found"