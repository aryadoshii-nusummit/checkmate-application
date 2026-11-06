"""Dependencies for providing application services."""

from app.services.webhook_service import WebhookService


def get_webhook_service() -> WebhookService:
    """Provide a webhook service instance to API routes."""

    return WebhookService()