from fastapi import APIRouter, Depends
from app.schemas.job import (CreateGenerationJobRequest, CreateGenerationJobResponse)
from app.models.certificate import Certificate
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
