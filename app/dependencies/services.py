
"""Dependencies for providing application services."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.webhook_service import WebhookService


def get_webhook_service(
    db: Session = Depends(get_db),
) -> WebhookService:
    """Provide a webhook service with its request-scoped database session."""

    return WebhookService(db=db)
