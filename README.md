# Bulk Certificate Generator

A REST API built with **FastAPI and PostgreSQL** that generates certificates in bulk, processes generation jobs in the background, tracks individual certificate statuses, and provides generated PDF certificates for download.

## Features

- **Bulk Generation:** Submit multiple recipients in a single API request.
- **Background Processing:** Generate certificates asynchronously using FastAPI BackgroundTasks.
- **Job Tracking:** Track the status and progress of each bulk generation job.
- **Individual Status Tracking:** Monitor the result of each certificate independently.
- **PDF Generation:** Generate downloadable PDF certificates using ReportLab.
- **Error Handling:** Handle individual certificate generation failures without stopping the entire batch.
- **Certificate Downloads:** Download successfully generated certificates through a dedicated API endpoint.
- **Input Validation:** Validate requests using Pydantic schemas.
- **Database Persistence:** Store generation jobs, recipient details, statuses, and file paths in PostgreSQL.
- **Automated Testing:** Test schemas, API endpoints, PDF generation, and background processing using Pytest.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| FastAPI | REST API framework |
| PostgreSQL | Persistent data storage |
| SQLAlchemy | ORM and database operations |
| Pydantic | Request validation and application configuration |
| ReportLab | PDF certificate generation |
| Pytest | Automated testing |
| HTTPX | HTTP client used in API tests |

## Architecture

The application separates API handling, database models, business logic, and PDF generation.

```text
Client
  |
  v
FastAPI REST API
  |
  +---- POST /jobs
  |       |
  |       v
  |   Validate Request
  |       |
  |       v
  |   Save Job and Certificates
  |       |
  |       v
  |   Schedule Background Task
  |
  +---- GET /jobs/{job_id}
  |       |
  |       v
  |   Return Job Status and Progress
  |
  +---- GET /jobs/{job_id}/certificates
  |       |
  |       v
  |   Return Individual Certificate Results
  |
  +---- GET /certificates/{certificate_id}
          |
          v
      Return Generated PDF
```

### Background Processing Flow

1. The client submits a job containing event information and recipient details.
2. The API validates the request and creates a generation job.
3. The job and associated certificate records are persisted in PostgreSQL.
4. FastAPI schedules a background task to process the job.
5. Each certificate is generated and its status is updated in the database.
6. If one certificate fails, processing continues for the remaining recipients.
7. The job is marked as completed after all certificates have finished processing.
8. The client can retrieve the results and download successful certificates.

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
│   ├── config.py
│   ├── database.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_schemas.py
│   ├── test_jobs_api.py
│   ├── test_certificate_service.py
│   ├── test_certificate_generator.py
│   └── test_certificate_api.py
├── storage/
│   └── certificates/
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

*The structure above reflects the intended organization of the application. If any filenames differ in your repository, update the tree accordingly.*

## Prerequisites

Ensure the following are installed:

- Python 3.11 or later
- PostgreSQL
- pip

## Setup and Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd bulk-certificate-generator
```

Replace `<your-repository-url>` with your repository's actual URL.

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on macOS or Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the PostgreSQL databases

Create a development database:

```bash
createdb certificate_generator
```

Create a separate database for automated tests:

```bash
createdb certificate_generator_test
```

If the databases already exist, you do not need to recreate them.

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://<username>@localhost:5432/certificate_generator
TEST_DATABASE_URL=postgresql://<username>@localhost:5432/certificate_generator_test
```

Replace `<username>` with your PostgreSQL username.

If your PostgreSQL configuration requires a password, configure the connection URL accordingly.

**Important:** Never commit `.env` or database credentials to version control.

The application uses `DATABASE_URL` for normal operation and `TEST_DATABASE_URL` for automated tests.

### 6. Start the application

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

## API Endpoints

### 1. Create a Generation Job

**Endpoint:** `POST /jobs`

Creates a generation job for multiple recipients and schedules certificate generation in the background.

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

The response illustrates the initial job state. Certificate generation proceeds in the background, so the status may change shortly after the response.

### 2. Get Job Status

**Endpoint:** `GET /jobs/{job_id}`

Returns the current job status and progress, including the total number of certificates and their processing results.

Example response:

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

*The response is illustrative; use the live API documentation to confirm the exact response schema.*

### 3. Get Certificate Results for a Job

**Endpoint:** `GET /jobs/{job_id}/certificates`

Returns the individual certificate records associated with a job, including their statuses and download URLs when available.

Example result:

```json
{
  "certificate_id": 1,
  "recipient_name": "Alice Johnson",
  "status": "SUCCESS",
  "download_url": "/certificates/1",
  "error_message": null
}
```

The endpoint's actual response structure depends on the response schema defined in the application.

### 4. Download a Certificate

**Endpoint:** `GET /certificates/{certificate_id}`

Downloads the generated PDF for a successfully generated certificate.

Example:

```bash
curl -OJ http://127.0.0.1:8000/certificates/1
```

The API verifies that the certificate exists, has been generated successfully, and has an available PDF file before returning it.

## Job and Certificate Statuses

### Job Statuses

| Status | Description |
|---|---|
| `PENDING` | The job is waiting to be processed. |
| `PROCESSING` | The job is being processed. |
| `COMPLETED` | All certificates were generated successfully. |
| `COMPLETED_WITH_ERRORS` | Processing finished, but one or more certificates failed. |

### Certificate Statuses

| Status | Description |
|---|---|
| `PENDING` | The certificate has not been processed yet. |
| `PROCESSING` | Certificate generation is in progress. |
| `SUCCESS` | The PDF was generated successfully. |
| `FAILED` | Certificate generation failed. |

Individual certificate statuses are used to calculate the overall job progress.

## Error Handling

The application distinguishes between request validation failures and errors encountered during certificate generation.

- Invalid requests are rejected before a generation job is created.
- Individual generation failures are recorded against the affected certificate.
- A failed certificate does not prevent the remaining certificates from being processed.
- Failed certificates receive an error code and a safe error message.
- Detailed exceptions are logged for debugging.
- A PDF is available for download only when the certificate has been generated successfully and its file exists.

## Database Design

The application uses two primary database entities.

### GenerationJob

Stores information about a bulk generation request.

Typical fields include:

- Job ID
- Event name
- Event date
- Job status
- Creation timestamp
- Completion timestamp

### Certificate

Stores the result of generating an individual certificate.

Typical fields include:

- Certificate ID
- Associated job ID
- Recipient name
- Recipient email
- Certificate status
- Generated PDF file path
- Error code and message
- Creation timestamp
- Completion timestamp

The relationship is one-to-many: a generation job can contain multiple certificate records.

The database stores certificate metadata and file paths, while the generated PDF files are stored on disk.

## Testing

Automated tests cover request validation, API behavior, PDF generation, background processing, and certificate downloads.

Run the complete test suite:

```bash
pytest -v
```

Run a specific test module:

```bash
pytest -v tests/test_jobs_api.py
```

The project uses a separate PostgreSQL database for testing to avoid modifying development data during test execution.

The test fixture resets the test database tables before each test. **Do not configure `TEST_DATABASE_URL` to point to your development or production database.**

## Design Decisions

### FastAPI BackgroundTasks

FastAPI's built-in `BackgroundTasks` provides a straightforward way to process certificate generation after returning the API response.

It keeps the implementation simple for this assignment. However, background tasks run within the application process and are not a durable job queue.

For production workloads involving large batches, retries, guaranteed execution, or multiple workers, a dedicated task queue such as Celery or a similar distributed processing system would be more appropriate.

### Individual Failure Handling

Each certificate is processed independently. This prevents one generation failure from terminating the entire batch and allows the application to report partial success.

### Separate Development and Test Databases

Keeping test data separate from development data reduces the risk of automated tests accidentally deleting or modifying application records.

### PDF Storage

Generated PDF files are stored locally, and their paths are saved in PostgreSQL. For a distributed production deployment, object storage such as Amazon S3 would be a more scalable option.