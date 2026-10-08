from datetime import date
from pydantic import BaseModel, EmailStr, Field
from app.models.job import JobStatus
from app.schemas.certificate import CertificateResponse

class Recipient(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    
class CreateGenerationJobRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=255)
    event_date: date
    recipients: list[Recipient] = Field(
        min_length=1)


class CreateGenerationJobResponse(BaseModel):
    job_id: int
    status: JobStatus
    total_count: int

class JobStatusResponse(BaseModel):
    job_id: int
    status: JobStatus
    total_count: int
    successful_count: int
    failed_count: int
    pending_count: int

class JobCertificatesResponse(BaseModel):
    job_id: int
    certificates: list[CertificateResponse]