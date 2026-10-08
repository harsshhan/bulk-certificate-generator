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