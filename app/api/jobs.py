from fastapi import APIRouter, Depends, HTTPException
from app.schemas.job import (CreateGenerationJobRequest, CreateGenerationJobResponse, JobStatusResponse, JobCertificatesResponse)
from app.models.certificate import Certificate
from app.schemas.certificate import CertificateResponse
from app.models.job import GenerationJob
from sqlalchemy.orm import Session
from app.database import get_db



router = APIRouter(prefix="/jobs", tags= ["Jobs"])

@router.post("")
def create_job(request: CreateGenerationJobRequest, db: Session = Depends(get_db), response_model=CreateGenerationJobResponse):

    job = GenerationJob(
        event_name=request.event_name,
        event_date=request.event_date,
    )
    db.add(job)
    db.flush()

    for recipient in request.recipients:
        certificate = Certificate(
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            job_id=job.id
        )
        db.add(certificate)
    
    db.commit()

    return CreateGenerationJobResponse(job_id=job.id, status=job.status, total_count=len(request.recipients))

@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    successful_count = sum(
        certificate.status.value == "SUCCESS"
        for certificate in job.certificates
    )

    failed_count = sum(
        certificate.status.value == "FAILED"
        for certificate in job.certificates
    )

    pending_count = sum(
        certificate.status.value in {"PENDING", "PROCESSING"}
        for certificate in job.certificates
    )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total_count=len(job.certificates),
        successful_count=successful_count,
        failed_count=failed_count,
        pending_count=pending_count,
    )

@router.get(
    "/{job_id}/certificates",
    response_model=JobCertificatesResponse,
)
def get_job_certificates(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    certificates = [
        CertificateResponse(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            status=certificate.status,
            download_url=(
                f"/certificates/{certificate.id}"
                if certificate.status.value == "SUCCESS"
                else None
            ),
            error_message=certificate.error_message,
        )
        for certificate in job.certificates
    ]

    return JobCertificatesResponse(
        job_id=job.id,
        certificates=certificates,
    )