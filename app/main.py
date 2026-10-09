from fastapi import FastAPI
from app.api.jobs import router as jobs_router
from app.api.certificates import router as certificates_router

app = FastAPI(title="Bulk Certificate Generator API", version="1.0.0")

app.include_router(jobs_router)
app.include_router(certificates_router)
