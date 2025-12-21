"""
Модуль для работы с webhooks
"""

from src.webhook.server import WebhookServer
from src.webhook.notifier import send_notification, set_bot_instance

__all__ = ["WebhookServer", "send_notification", "set_bot_instance"]
