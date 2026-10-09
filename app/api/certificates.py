from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.certificate import Certificate, CertificateStatus

router = APIRouter(prefix='/certificates', tags=['Certificates'])

@router.get("/{certificate_id}")
def download_certificate(certificate_id: int, db: Session = Depends(get_db)):
    certificate = db.get(Certificate, certificate_id)

    if certificate is None:
        raise HTTPException(status_code = 404, detail = "Certificate not found")
    
    if certificate.status != CertificateStatus.SUCCESS:
        raise HTTPException(status_code = 409, detail = "Certificate is not available for download")

    if not certificate.file_path:
        raise HTTPException(
            status_code=404, detail="Certificate file not found",
        )

    file_path = Path(certificate.file_path)
    if not file_path.is_file():
        raise HTTPException(
            status_code=404, detail="Certificate file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate_{certificate.id}.pdf",
    )