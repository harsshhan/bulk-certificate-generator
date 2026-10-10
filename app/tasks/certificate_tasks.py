from app.worker import celery_app
from app.services.certificate_service import run_bulk_job

@celery_app.task(name="certificates.process_bulk_job")
def process_bulk_job_task(job_id: int) -> None:
    run_bulk_job(job_id)