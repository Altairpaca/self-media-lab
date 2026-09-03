from celery import Celery

from .config import settings
from .db import init_db
from .pipeline import ingest_job

celery_app = Celery("media_lab", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True


@celery_app.task(name="media_lab.ingest")
def run_ingest(job_id: int) -> None:
    init_db()
    ingest_job(job_id)
