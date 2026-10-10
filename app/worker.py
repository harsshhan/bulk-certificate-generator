from celery import Celery
from app.config import settings

celery_app = Celery("certificate_generator", 
broker = settings.redis_url,
include=["app.tasks.certificate_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content = ["json"],
    result_serializer = "json",
    timezone = "UTC",
    enable_utc = True
)
