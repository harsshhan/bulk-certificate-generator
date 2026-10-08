from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_job():
    response = client.post(
        "/jobs",
        json={
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
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] > 0
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2

def test_get_job_status():
    create_response = client.post(
        "/jobs",
        json={
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
        },
    )

    job_id = create_response.json()["job_id"]

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == job_id
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2
    assert data["successful_count"] == 0
    assert data["failed_count"] == 0
    assert data["pending_count"] == 2

def test_get_nonexistent_job():
    response = client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

def test_get_job_certificates():
    create_response = client.post(
        "/jobs",
        json={
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
        },
    )

    job_id = create_response.json()["job_id"]

    response = client.get(f"/jobs/{job_id}/certificates")

    assert response.status_code == 200

    data = response.json()

    assert data["job_id"] == job_id
    assert len(data["certificates"]) == 2

    first_certificate = data["certificates"][0]

    assert first_certificate["recipient_name"] == "Alice Johnson"
    assert first_certificate["status"] == "PENDING"
    assert first_certificate["download_url"] is None
    assert first_certificate["error_message"] is None


def test_get_certificates_for_nonexistent_job():
    response = client.get("/jobs/999999/certificates")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"