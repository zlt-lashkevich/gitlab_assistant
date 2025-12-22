"""
Точка входа в GitLab Assistant
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from src.config import settings
from src.bot import main as bot_main
from src.webhook import WebhookServer


def setup_logging() -> None:
    """Настройка логирования"""
    logger.remove()  # Удаляем стандартный

    # Добавляем для консоли
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # Добавляем обработчик для файла
    logger.add(
        "logs/gitlab_assistant_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


async def main() -> None:
    """Главная функция приложения"""
    setup_logging()

    logger.info("=" * 60)
    logger.info("GitLab Assistant запускается...")
    logger.info(f"Режим отладки: {settings.debug}")
    logger.info(f"Уровень логирования: {settings.log_level}")
    logger.info("=" * 60)

    try:
        # Создаем и запускаем webhook сервер
        webhook_server = WebhookServer(
            host=settings.webhook_host,
            port=settings.webhook_port
        )
        await webhook_server.start()
        logger.success(f"Webhook сервер запущен на {settings.webhook_host}:{settings.webhook_port}")

        # Запускаем бота (блокирующий вызов)
        await bot_main()
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
