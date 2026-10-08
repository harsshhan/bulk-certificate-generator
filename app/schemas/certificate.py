from pydantic import BaseModel

from app.models.certificate import CertificateStatus

class CertificateResponse(BaseModel):
    certificate_id: int
    recipient_name: str
    status: CertificateStatus
    download_url: str | None = None
    error_message: str | None = None