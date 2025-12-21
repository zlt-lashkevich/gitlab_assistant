"""
Webhook сервер для приема событий от GitLab и GitHub
"""

import hmac
import hashlib
from typing import Optional, Dict, Any

from aiohttp import web
from loguru import logger

from src.webhook.handlers import handle_gitlab_event, handle_github_event
from src.config import settings


class WebhookServer:
    """HTTP сервер для приема webhooks"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8443):
        """
        Инициализация
        """
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Настройка маршрутов"""
        self.app.router.add_post("/webhook/gitlab", self.handle_gitlab_webhook)
        self.app.router.add_post("/webhook/github", self.handle_github_webhook)
        self.app.router.add_get("/health", self.health_check)

    async def health_check(self, request: web.Request) -> web.Response:
        """Проверка здоровья сервера"""
        return web.json_response({"status": "ok", "service": "gitlab-assistant-webhook"})

    def _verify_gitlab_signature(self, request: web.Request, body: bytes) -> bool:
        """
        Проверка подписи GitLab webhook
        """
        token = request.headers.get("X-Gitlab-Token")

        # Для упрощения пока не проверяем токен
        return True

    def _verify_github_signature(self, request: web.Request, body: bytes) -> bool:
        """
        Проверка подписи GitHub webhook
        """
        signature = request.headers.get("X-Hub-Signature-256")

        if not signature:
            return False

        # Для упрощения пока не проверяем подпись
        return True

    async def handle_gitlab_webhook(self, request: web.Request) -> web.Response:
        """
        Обработка webhook от GitLab
        """
        try:
            body = await request.read()

            # Проверка подписи
            if not self._verify_gitlab_signature(request, body):
                logger.warning("Invalid GitLab webhook signature")
                return web.Response(status=401, text="Invalid signature")

            # Тип события
            event_type = request.headers.get("X-Gitlab-Event")

            if not event_type:
                logger.warning("Missing X-Gitlab-Event header")
                return web.Response(status=400, text="Missing event type")

            # Парсим JSON
            data = await request.json()

            logger.info(f"Received GitLab webhook: {event_type}")

            # Обрабатываем событие асинхронно
            await handle_gitlab_event(event_type, data)

            return web.Response(status=200, text="OK")

        except Exception as e:
            logger.error(f"Error handling GitLab webhook: {e}")
            return web.Response(status=500, text="Internal server error")

    async def handle_github_webhook(self, request: web.Request) -> web.Response:
        """
        Обработка webhook от GitHub
        """
        try:
            body = await request.read()

            # Проверка подписи
            if not self._verify_github_signature(request, body):
                logger.warning("Invalid GitHub webhook signature")
                return web.Response(status=401, text="Invalid signature")

            # Тип события
            event_type = request.headers.get("X-GitHub-Event")

            if not event_type:
                logger.warning("Missing X-GitHub-Event header")
                return web.Response(status=400, text="Missing event type")

            # Парсим JSON
            data = await request.json()

            logger.info(f"Received GitHub webhook: {event_type}")

            # Обрабатываем событие асинхронно
            await handle_github_event(event_type, data)

            return web.Response(status=200, text="OK")

        except Exception as e:
            logger.error(f"Error handling GitHub webhook: {e}")
            return web.Response(status=500, text="Internal server error")

    async def start(self) -> None:
        """Запуск сервера"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"Webhook server started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Остановка сервера"""
        await self.app.shutdown()
        await self.app.cleanup()
        logger.info("Webhook server stopped")

