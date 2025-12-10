import asyncio
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.database import init_db
from src.bot.handlers import router as main_router
from src.bot.subscription_handlers import router as subscription_router
from src.bot.actions import router as actions_router
from src.bot.notification_settings_handlers import router as notification_settings_router
from src.webhook import set_bot_instance


async def main() -> None:
    """Главная функция запуска бота."""

    logger.info("Инициализация базы данных...")
    await init_db()
    logger.success("База данных инициализирована")

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(main_router)
    dp.include_router(subscription_router)
    dp.include_router(actions_router)
    dp.include_router(notification_settings_router)

    set_bot_instance(bot)
    
    logger.info("Запуск бота...")
    
    try:
        # Удаляем webhook на случай, если он был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запуск polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
