# Bulk Certificate Generator

A REST API built with **FastAPI and PostgreSQL** that generates certificates in bulk, processes generation jobs asynchronously using **Celery and Redis**, tracks individual certificate statuses, and provides generated PDF certificates for download.

The project demonstrates asynchronous task processing, database persistence, retry mechanisms, failure handling, and recovery of interrupted certificate-generation tasks.

## Features

- **Bulk Generation:** Submit multiple recipients in a single API request.
- **Asynchronous Processing:** Process certificate-generation jobs using Celery workers.
- **Job Tracking:** Track the status and progress of each bulk generation job.
- **Individual Status Tracking:** Monitor the result of each certificate independently.
- **PDF Generation:** Generate PDF certificates using ReportLab.
- **Failure Handling:** Record individual certificate-generation failures without stopping the entire batch.
- **Automatic Retries:** Retry failed certificate-generation tasks using Celery.
- **Retry Exhaustion:** Mark certificates as failed after the configured retry limit is exhausted.
- **Certificate Downloads:** Download successfully generated certificates through a dedicated API endpoint.
- **Input Validation:** Validate requests using Pydantic schemas.
- **Database Persistence:** Store generation jobs, recipient details, statuses, processing metadata, and file paths in PostgreSQL.
- **Processing Ownership:** Use unique attempt tokens to prevent outdated workers from overwriting newer processing results.
- **Stale Task Recovery:** Detect certificates stuck in processing and return eligible certificates to the pending state.
- **Periodic Recovery:** Use Celery Beat to schedule stale-certificate recovery.
- **Database Migrations:** Manage schema changes using Alembic.
- **Automated Testing:** Test API endpoints, certificate processing, task retries, job completion, and recovery using pytest.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| FastAPI | REST API framework |
| PostgreSQL | Persistent data storage |
| SQLAlchemy | ORM and database operations |
| Pydantic | Request validation and application configuration |
| ReportLab | PDF certificate generation |
| Celery | Asynchronous task execution and retries |
| Redis | Celery message broker |
| Alembic | Database schema migrations |
| pytest | Automated testing |
| HTTPX | HTTP client used in API tests |

## Architecture

The application separates API handling, database persistence, background task execution, and PDF generation.

### System Architecture

```text
                       Client
                         |
                         v
                  FastAPI REST API
                         |
              +----------+----------+
              |                     |
              v                     v
        PostgreSQL             Redis Broker
              ^                     |
              |                     v
              |               Celery Worker
              |                     |
              |              Process Bulk Job
              |                     |
              |                     v
              |          Individual Certificate Tasks
              |                     |
              |                     v
              |              ReportLab PDF
              |               Generation
              |                     |
              +---------------------+
                                    |
                                    v
                             Update Status

                     Celery Beat Scheduler
                              |
                              v
                    Stale Certificate Recovery
                              |
                              v
                         Redis Broker
```

### Component Responsibilities

**FastAPI**
- Accepts certificate-generation requests.
- Validates incoming data.
- Creates generation jobs and certificate records.
- Enqueues asynchronous processing tasks.
- Exposes endpoints for job status, certificate results, and downloads.

**PostgreSQL**
- Stores generation jobs and certificate records.
- Tracks processing status and progress.
- Stores error information, processing timestamps, ownership tokens, and generated-file paths.

**Redis**
- Acts as the Celery message broker.
- Carries task messages between the application and workers.

**Celery Workers**
- Execute bulk-processing tasks.
- Schedule individual certificate-generation tasks.
- Generate certificates asynchronously.
- Retry failed tasks according to the configured retry policy.

**ReportLab**
- Generates PDF certificates using the predefined certificate template.

**Celery Beat**
- Periodically schedules the stale-certificate recovery task.

**Alembic**
- Manages version-controlled database schema changes.

## Processing Workflow

1. The client submits a bulk certificate-generation request.
2. FastAPI validates the request and creates a generation job.
3. The application stores the job and its associated certificate records in PostgreSQL.
4. A Celery task is submitted through Redis.
5. A Celery worker processes the bulk job and schedules individual certificate tasks.
6. Each certificate task attempts to claim a pending certificate using an atomic database update.
7. The worker generates a PDF using ReportLab.
8. The certificate status, generated-file path, and completion metadata are updated in PostgreSQL.
9. Failed generation attempts are retried according to the Celery retry policy.
10. Once all certificates reach terminal states, the job is marked as `COMPLETED` or `COMPLETED_WITH_ERRORS`.
11. The client can retrieve job progress, inspect individual certificate results, and download successful certificates.

## Failure Handling and Recovery

### Automatic Retries

Certificate-generation tasks use Celery retries to handle failures.

The current task configuration includes:

- Maximum retries: 3
- Exponential retry backoff
- Maximum retry backoff: 30 seconds
- Retry jitter disabled

After retries are exhausted, the certificate is marked as `FAILED`, provided the failure handler can still safely update its database state.

### Processing Ownership

Each certificate-processing attempt receives a unique UUID token.

When a worker claims a pending certificate, the application stores the token and processing timestamp in PostgreSQL.

Database updates that finalize an attempt are conditional on the certificate still being in the `PROCESSING` state and the token matching the current attempt.

This prevents an outdated worker from overwriting the database state established by a newer attempt.

Each attempt also writes its PDF to a unique output path to avoid different attempts writing to the same file.

### Stale Certificate Recovery

A worker may terminate unexpectedly while processing a certificate. Without recovery, that certificate could remain in the `PROCESSING` state indefinitely.

The application records a processing timestamp when a certificate is claimed.

The periodic recovery task:

1. Identifies certificates whose processing timestamps exceed the configured timeout.
2. Locks eligible database records to reduce conflicts between concurrent recovery workers.
3. Resets stale certificates to `PENDING`.
4. Clears their processing timestamp and ownership token.
5. Records a processing-timeout error.
6. Enqueues new certificate-processing tasks.

The timeout is configurable through the `CERTIFICATE_PROCESSING_TIMEOUT_SECONDS` environment variable.

Recovery depends on the Celery worker, Celery Beat, Redis, and PostgreSQL being available.

**Reliability limitation:** Updating PostgreSQL and enqueueing a task in Redis are separate operations. If the database reset succeeds but task enqueueing fails, a certificate can remain pending without a queued task. A transactional outbox or equivalent durable dispatch mechanism would be needed to eliminate this gap.

## Job and Certificate Statuses

### Job Statuses

| Status | Description |
|---|---|
| `PENDING` | The job is waiting to be processed. |
| `PROCESSING` | The job has unfinished certificates. |
| `COMPLETED` | All certificates completed successfully. |
| `COMPLETED_WITH_ERRORS` | Processing finished with one or more failed certificates. |

### Certificate Statuses

| Status | Description |
|---|---|
| `PENDING` | The certificate is waiting to be processed or retried. |
| `PROCESSING` | A worker currently owns the processing attempt. |
| `SUCCESS` | The PDF was generated successfully. |
| `FAILED` | Processing failed after retries were exhausted. |

Job completion is determined by the states of the certificates associated with that job.

## Project Structure

```text
bulk-certificate-generator/
├── app/
│   ├── api/
│   │   ├── jobs.py
│   │   └── certificates.py
│   ├── generators/
│   │   └── certificate_generator.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── job.py
│   │   └── certificate.py
│   ├── schemas/
│   │   └── job.py
│   ├── services/
│   │   └── certificate_service.py
│   ├── tasks/
│   │   └── certificate_tasks.py
│   ├── config.py
│   ├── database.py
│   ├── worker.py
│   └── main.py
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_jobs_api.py
│   ├── test_certificate_service.py
│   ├── test_certificate_generator.py
|   ├── test_certificate_api.py
│   └── test_celery_tasks.py
├── storage/
│   └── certificates/
│       └── attempts/
├── alembic.ini
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```


## Prerequisites

Install the following before running the application:

- Python 3.11 or later
- PostgreSQL
- Redis
- pip

## Setup and Installation

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd bulk-certificate-generator
```

Replace `<your-repository-url>` with your repository's actual URL.

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on macOS or Linux:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create PostgreSQL Databases

Create a development database:

```bash
createdb certificate_generator
```

Create a separate test database:

```bash
createdb certificate_generator_test
```

If the databases already exist, you do not need to recreate them.

### 5. Configure Environment Variables

Create a .env file in the project root and configure the required environment variables.

For example:

```env
DATABASE_URL=postgresql://<username>@localhost:5432/certificate_generator
TEST_DATABASE_URL=postgresql://<username>@localhost:5432/certificate_generator_test
```

Replace `<username>` with your PostgreSQL username.

If your PostgreSQL configuration requires a password, configure the connection URL accordingly.

The application uses these settings for database connectivity, background processing, and stale-certificate recovery.

**Important:** Never commit `.env` or real credentials to version control.

### 6. Apply Database Migrations

```bash
alembic upgrade head
```

Alembic applies the database schema migrations included in the repository.

Use a separate database when running tests. Do not point the test database configuration at a development or production database.

### 7. Start Redis

Start your local Redis service.

Verify that it is available:

```bash
redis-cli ping
```

Expected response:

```text
PONG
```

### 8. Start the FastAPI Application

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### 9. Start a Celery Worker

Open a separate terminal, activate the virtual environment, and run:

```bash
celery -A app.worker:celery_app worker --loglevel=info --pool=solo
```

The solo pool is used for local development on macOS. Other worker pools can be configured depending on the deployment environment.

It executes tasks sequentially within the worker. Other pool configurations can be evaluated if additional concurrency is required.

### 10. Start Celery Beat

Open another terminal and run:

```bash
celery -A app.worker:celery_app beat --loglevel=info
```

Celery Beat schedules the periodic stale-certificate recovery task configured in `app/worker.py`.

The FastAPI application, Redis, Celery worker, and Celery Beat must be running for the complete asynchronous workflow to operate.

## API Endpoints

The following endpoints describe the API interface documented for this project. Use the running application's `/docs` page to verify the exact request and response schemas.

### 1. Create a Generation Job

**Endpoint:** `POST /jobs`

Creates a generation job for multiple recipients and queues asynchronous processing.

Example request:

```json
{
  "event_name": "Python Workshop",
  "event_date": "2026-10-09",
  "recipients": [
    {
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com"
    },
    {
      "recipient_name": "Bob Smith",
      "recipient_email": "bob@example.com"
    }
  ]
}
```

Example response:

```json
{
  "job_id": 1,
  "status": "PENDING",
  "total_count": 2
}
```

The response represents the initial state. The job status may change shortly after the request returns.

### 2. Get Job Status

**Endpoint:** `GET /jobs/{job_id}`

Returns the current job status and progress, including the total number of certificates and their processing results.

Illustrative response:

```json
{
  "job_id": 1,
  "event_name": "Python Workshop",
  "status": "COMPLETED",
  "total_count": 2,
  "success_count": 2,
  "failed_count": 0,
  "pending_count": 0
}
```

The actual response depends on the application's response schema.

### 3. Get Certificate Results for a Job

**Endpoint:** `GET /jobs/{job_id}/certificates`

Returns individual certificate records associated with a job, including their statuses and download URLs when available.

Illustrative result:

```json
{
  "certificate_id": 1,
  "recipient_name": "Alice Johnson",
  "status": "SUCCESS",
  "download_url": "/certificates/1",
  "error_message": null
}
```

The endpoint's actual response structure depends on the schema defined in the application.

### 4. Download a Certificate

**Endpoint:** `GET /certificates/{certificate_id}`

Downloads the generated PDF for a successfully generated certificate.

Example:

```bash
curl -OJ http://127.0.0.1:8000/certificates/1
```

The API should verify that the certificate exists, has been generated successfully, and has an available PDF file before returning it.

## Database Design

The application uses two primary database entities.

### GenerationJob

Represents a bulk certificate-generation request.

Typical fields include:

- Job ID
- Event name
- Event date
- Job status
- Creation timestamp
- Completion timestamp

### Certificate

Represents an individual certificate belonging to a generation job.

Typical fields include:

- Certificate ID
- Associated job ID
- Recipient name and email
- Certificate status
- Generated PDF path
- Error code and message
- Creation and completion timestamps
- Processing start timestamp
- Processing ownership token

The relationship is one-to-many: a generation job can contain multiple certificates.

PostgreSQL stores the metadata and file paths, while generated PDF files are stored on disk.

## Testing

The project uses pytest for automated testing.

Run the complete test suite:

```bash
pytest -v
```

Run a specific test module:

```bash
pytest -v tests/test_celery_tasks.py
```

Tests cover areas including:

- Request and schema validation.
- API endpoint behavior.
- PDF generation.
- Certificate-processing success and failure.
- Bulk task scheduling.
- Celery retries and retry exhaustion.
- Job completion.
- Processing-token handling.
- Stale certificate recovery.
- Processing timestamp and token cleanup.

A dedicated PostgreSQL test database should be configured before running database tests.

The test fixtures may reset database tables, so **never configure `TEST_DATABASE_URL` to point to a development or production database**.

## Design Decisions

### Why Celery and Redis?

Bulk PDF generation can take longer than a typical API request.

Celery separates certificate generation from API request handling and supports task retries and independent workers. Redis acts as the message broker between the application and workers.

### Why PostgreSQL?

Job and certificate statuses must persist independently of the API and worker processes. PostgreSQL provides durable storage for generation jobs, certificate metadata, processing state, and error information.

### Why Individual Certificate Tasks?

Processing certificates independently makes it possible to track each recipient's result and retry failed certificates without regenerating every successful certificate.

### Why Processing Tokens?

A unique token identifies the currently authorized processing attempt.

Conditional database updates prevent outdated attempts from overwriting the state established by newer attempts.

### Why Celery Beat?

Celery Beat schedules periodic recovery work so abandoned processing attempts can be detected and returned to the pending state.

### Why Alembic?

Alembic provides version-controlled database schema changes that can be applied consistently across environments.

### Why Local PDF Storage?

Local filesystem storage keeps the project simple and avoids requiring a separate object-storage service. A distributed production deployment would typically use shared or object storage.

## Limitations

- Redis is required for asynchronous task processing.
- Generated PDFs are stored on the local filesystem.
- The local Celery worker uses the `solo` pool for development simplicity.
- Database transactions and Redis task enqueueing are separate operations. A broker failure after a successful database commit can leave a pending certificate without a queued task.
- The implementation does not include a transactional outbox for durable task dispatch.
- Production deployment automation, authentication, authorization, and advanced monitoring are outside the current project scope unless implemented separately.

## Future Improvements

Possible enhancements include:

- Docker-based deployment.
- CI pipelines for automated testing.
- Cloud object storage for generated certificates.
- A transactional outbox for reliable task dispatch.
- Production worker scaling and monitoring.