"""
Обработчики команд бота
"""

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.gitlab_api import GitLabClient
from src.github_api import GitHubClient
from loguru import logger
from src.gitlab_api.client import GitLabClient
from src.github_api.client import GitHubClient
from src.config import settings

from src.database import User, get_session

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Команда /start
    """
    telegram_id = message.from_user.id

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            session.add(user)
            await session.commit()

            welcome_text = (
                f"Привет, {message.from_user.first_name}!\n\n"
                "Добро пожаловать в GitLab Assistant — ваш персональный помощник "
                "для отслеживания событий в GitLab и GitHub.\n\n"
                "Используйте /help для просмотра доступных команд."
            )
        else:
            welcome_text = (
                f"С возвращением, {message.from_user.first_name}! \n\n"
                "Используйте /help для просмотра доступных команд."
            )

        await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Команда /help"""
    help_text = (
        "*Доступные команды:*\n\n"
        "🔹 *Основные:*\n"
        "/start \u2014 Начать работу с ботом\n"
        "/help \u2014 Показать это сообщение\n"
        "/status \u2014 Показать ваш статус и подписки\n\n"
        "🔹 *Настройка токенов:*\n"
        "/set\\_gitlab\\_token \\<token\\> \u2014 Установить GitLab токен\n"
        "/set\\_github\\_token \\<token\\> \u2014 Установить GitHub токен\n\n"
        "🔹 *Подписки:*\n"
        "/subscribe \u2014 Подписаться на события проекта\n"
        "/unsubscribe \u2014 Отписаться от проекта\n"
        "/list\\_subscriptions \u2014 Показать все подписки\n\n"
        "🔹 *Уведомления:*\n"
        "/notifications \u2014 Управление типами уведомлений\n\n"
        "/history \u2014 Показать последние уведомления\n\n"
        "*Персонализированные уведомления:*\n"
        "\u2022 Упоминания в комментариях MR/Issue\n"
        "\u2022 Назначение ревьюером\n"
        "\u2022 Завершение пайплайнов (только ваши MR)\n"
        "\u2022 Мердж ваших MR\n"
        "\u2022 Изменение лейблов в Issue\n\n"
        "*Интерактивные действия:*\n"
        "В уведомлениях доступны кнопки:\n"
        "\u2022 Approve MR\n"
        "\u2022 Merge MR\n"
        "\u2022 Перезапуск pipeline\n"
        "\u2022 Назначить ревьюера"
    )
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """Команда /status"""
    telegram_id = message.from_user.id

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            return

        status_text = f"**Ваш статус:**\n\n"
        status_text += f"Пользователь: {user.first_name or 'N/A'}\n"
        status_text += f"Telegram ID: `{user.telegram_id}`\n\n"

        status_text += "**Токены:**\n"
        status_text += f"GitLab: {'Установлен' if user.gitlab_token else 'Не установлен'} ({user.gitlab_username or 'N/A'})\n"
        status_text += f"GitHub: {'Установлен' if user.github_token else 'Не установлен'} ({user.github_username or 'N/A'})\n\n"

        status_text += f"Активных подписок: {len(user.subscriptions)}\n"

        await message.answer(status_text, parse_mode="HTML")

# в командах с токенами удаляем сообщение от пользователя из соображений безопасности
@router.message(Command("set_gitlab_token"))
async def cmd_set_gitlab_token(message: Message) -> None:
    """Команда /set_gitlab_token"""
    telegram_id = message.from_user.id

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Неверный формат команды.\n"
            "Используйте: <code>/set_gitlab_token glpat-xxxxxxxxxxxx</code>\n\n",
            parse_mode="HTML"
        )
        return

    token = parts[1].strip()

    gitlab_username = None
    try:
        from src.gitlab_api.client import GitLabClient
        from src.config import settings
        async with GitLabClient(settings.gitlab_url, token) as client:
            user_info = await client.get_current_user()
            gitlab_username = user_info.get("username")
            if not gitlab_username:
                await message.answer("Не удалось получить имя пользователя GitLab. Проверьте права токена.")
                return

    except Exception as e:
        await message.answer(f"Ошибка при проверке токена GitLab: {e}. Проверьте токен и URL GitLab.")
        await message.delete()
        return

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            return

        user.gitlab_token = token
        user.gitlab_username = gitlab_username
        await session.commit()


        await message.delete()
        await message.answer(f"GitLab токен успешно установлен! Ваш GitLab username: **{gitlab_username}**",
                             parse_mode="HTML")


@router.message(Command("set_github_token"))
async def cmd_set_github_token(message: Message) -> None:
    """Команда /set_github_token"""
    telegram_id = message.from_user.id

    # Извлекаем токен
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Неверный формат команды.\n"
            "Используйте: <code>/set_github_token ghp_xxxxxxxxxxxx</code>\n\n",
            parse_mode="HTML"
        )
        return

    token = parts[1].strip()

    github_username = None
    try:
        from src.github_api.client import GitHubClient
        async with GitHubClient(token) as client:
            user_info = await client.get_current_user()
            github_username = user_info.get("login")  # GitHub использует "login" для username
            if not github_username:
                await message.answer("Не удалось получить имя пользователя GitHub. Проверьте права токена.")
                return

    except Exception as e:
        await message.answer(f"Ошибка при проверке токена GitHub: {e}. Проверьте токен и права доступа.")
        await message.delete()
        return

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            return
        user.github_token = token
        user.github_username = github_username
        await session.commit()

        await message.delete()
        await message.answer(f"GitHub токен успешно установлен! Ваш GitHub username: **{github_username}**",
                             parse_mode="HTML")


@router.message(Command("list_subscriptions"))
async def cmd_list_subscriptions(message: Message) -> None:
    """Команда /list_subscriptions"""
    telegram_id = message.from_user.id

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            return

        if not user.subscriptions:
            await message.answer("У вас пока нет активных подписок.\n\nИспользуйте /subscribe для добавления.")
            return

        subs_text = "<b>Ваши подписки:</b>\n\n"
        for idx, sub in enumerate(user.subscriptions, 1):
            status = "✅" if sub.is_active else "❌"
            subs_text += f"{idx}. {status} **{sub.project_name}**\n"
            subs_text += f"   Платформа: {sub.platform.upper()}\n"
            subs_text += f"   События: {sub.event_types}\n\n"

        await message.answer(subs_text, parse_mode="HTML")

