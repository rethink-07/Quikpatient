from celery import Celery

from app.config import settings

celery_app = Celery(
    "quikpatient",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "expire-sos-every-minute": {
            "task": "app.tasks.expire_sos",
            "schedule": 60.0,
        },
        "anchor-audit-chain": {
            "task": "app.tasks.anchor_audit_chain",
            "schedule": settings.audit_anchor_interval_minutes * 60.0,
        },
    },
)
