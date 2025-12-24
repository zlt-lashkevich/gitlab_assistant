"""
Обработчики команд подписки на проекты
"""

from typing import Dict, Any, List
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database import User, Subscription, get_session
from src.bot.states import SubscriptionStates, UnsubscriptionStates
from src.bot.keyboards import (
    get_platform_keyboard,
    get_projects_keyboard,
    get_events_keyboard,
    get_confirmation_keyboard,
    get_subscriptions_keyboard
)
from src.gitlab_api import GitLabClient
from src.github_api import GitHubClient
from src.config import settings
from src.webhook.manager import WebhookManager

router = Router()


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, state: FSMContext) -> None:
    """Запуск процесса подписки"""
    telegram_id = message.from_user.id

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            return

        # Ищем токены
        if not user.gitlab_token and not user.github_token:
            await message.answer(
                "У вас не установлены токены доступа.\n\n"
                "Используйте команды:\n"
                "/set\\_gitlab\\_token  — для GitLab\n"
                "/set\\_github\\_token  — для GitHub"
            )
            return

        await state.set_state(SubscriptionStates.choosing_platform)

        platforms_text = "Выберите платформу:\n\n"

        if user.gitlab_token:
            platforms_text += "🐈 GitLab — доступен\n"
        else:
            platforms_text += "🐈 GitLab — токен не установлен\n"

        if user.github_token:
            platforms_text += "🐈‍⬛ GitHub — доступен\n"
        else:
            platforms_text += "🐈‍⬛ GitHub — токен не установлен\n"

        await message.answer(
            platforms_text,
            reply_markup=get_platform_keyboard(),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("platform:"), SubscriptionStates.choosing_platform)
async def process_platform_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор платформы"""
    platform = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    await state.update_data(platform=platform)

    async for session in get_session():
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Список проектов
        try:
            if platform == "gitlab":
                if not user.gitlab_token:
                    await callback.answer("GitLab токен не установлен", show_alert=True)
                    return

                async with GitLabClient(settings.gitlab_url, user.gitlab_token) as client:
                    projects = await client.get_projects(per_page=50)

            else:  # github
                if not user.github_token:
                    await callback.answer("GitHub токен не установлен", show_alert=True)
                    return

                async with GitHubClient(user.github_token) as client:
                    projects = await client.get_repositories(per_page=50)

            if not projects:
                await callback.message.edit_text(
                    f"У вас нет доступных проектов на {platform.upper()}.\n\n"
                    "Используйте /cancel для отмены."
                )
                return

            # Сохраняем проекты в состоянии
            await state.update_data(projects=projects)
            await state.set_state(SubscriptionStates.choosing_project)

            platform_name = "GitLab" if platform == "gitlab" else "GitHub"
            await callback.message.edit_text(
                f"Выберите проект из {platform_name}:\n\n"
                f"Найдено проектов: {len(projects)}",
                reply_markup=get_projects_keyboard(projects, platform, page=0),
                parse_mode="HTML"
            )

            await callback.answer()

        except Exception as e:
            logger.error(f"Error fetching projects: {e}")
            await callback.message.edit_text(
                f"Ошибка при получении списка проектов:\n{str(e)}\n\n"
                "Проверьте правильность токена и попробуйте снова."
            )
            await state.clear()


@router.callback_query(F.data.startswith("page:"), SubscriptionStates.choosing_project)
async def process_page_navigation(callback: CallbackQuery, state: FSMContext) -> None:
    """Навигация по страницам проектов"""
    _, platform, page_str = callback.data.split(":")
    page = int(page_str)

    data = await state.get_data()
    projects = data.get("projects", [])

    if not projects:
        await callback.answer("Список проектов пуст", show_alert=True)
        return

    platform_name = "GitLab" if platform == "gitlab" else "GitHub"
    await callback.message.edit_text(
        f"Выберите проект из {platform_name}:\n\n"
        f"Найдено проектов: {len(projects)}\n"
        f"Страница: {page + 1}",
        reply_markup=get_projects_keyboard(projects, platform, page=page),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("project:"), SubscriptionStates.choosing_project)
async def process_project_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор проекта"""
    _, platform, project_id = callback.data.split(":", 2)

    data = await state.get_data()
    projects = data.get("projects", [])

    # ищем проект ранее выбранный
    selected_project = None
    for project in projects:
        if platform == "gitlab":
            if str(project.get("id")) == project_id:
                selected_project = project
                break
        else:
            if project.get("full_name") == project_id:
                selected_project = project
                break

    if not selected_project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    # сохраняем его
    await state.update_data(
        selected_project=selected_project,
        project_id=project_id
    )
    await state.set_state(SubscriptionStates.choosing_events)

    if platform == "gitlab":
        project_name = selected_project.get("name_with_namespace", selected_project.get("name"))
    else:
        project_name = selected_project.get("full_name")

    await callback.message.edit_text(
        f"Выбран проект: {project_name}\n\n"
        f"Выберите типы событий для отслеживания:\n\n"
        f"Нажмите на кнопки с событиями, которые хотите отслеживать.\n"
        f"Когда закончите, нажмите Готово.",
        reply_markup=get_events_keyboard(platform),
        parse_mode="HTML"
    )

    # список выбранных событий
    await state.update_data(selected_events=[])
    await callback.answer()


@router.callback_query(F.data.startswith("event:"), SubscriptionStates.choosing_events)
async def process_event_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    """Переключение события"""
    event_type = callback.data.split(":")[1]

    data = await state.get_data()
    selected_events: List[str] = data.get("selected_events", [])

    if event_type in selected_events:
        selected_events.remove(event_type)
    else:
        selected_events.append(event_type)

    await state.update_data(selected_events=selected_events)

    events_text = ", ".join(selected_events) if selected_events else "не выбраны"
    await callback.answer(f"Выбранные события: {events_text}", show_alert=False)


@router.callback_query(F.data == "events:all", SubscriptionStates.choosing_events)
async def process_select_all_events(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор всех событий."""
    data = await state.get_data()
    platform = data.get("platform")

    if platform == "gitlab":
        all_events = ["pipeline", "merge_request", "issue", "wiki", "note"]
    else:
        all_events = ["workflow", "pull_request", "issue", "comment", "star"]

    await state.update_data(selected_events=all_events)
    await callback.answer("Выбраны все события", show_alert=False)


@router.callback_query(F.data == "events:reset", SubscriptionStates.choosing_events)
async def process_reset_events(callback: CallbackQuery, state: FSMContext) -> None:
    """Сброс выбранных событий"""
    await state.update_data(selected_events=[])
    await callback.answer("События сброшены", show_alert=False)


@router.callback_query(F.data == "events:done", SubscriptionStates.choosing_events)
async def process_events_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Завершение выбора событий"""
    data = await state.get_data()
    selected_events = data.get("selected_events", [])

    if not selected_events:
        await callback.answer("Выберите хотя бы одно событие", show_alert=True)
        return

    platform = data.get("platform")
    selected_project = data.get("selected_project")

    if platform == "gitlab":
        project_name = selected_project.get("name_with_namespace", selected_project.get("name"))
    else:
        project_name = selected_project.get("full_name")

    events_text = ", ".join(selected_events)

    await state.set_state(SubscriptionStates.confirming)

    confirmation_text = (
        f"Подтверждение подписки:\n\n"
        f"Платформа: {platform.upper()}\n"
        f"Проект: {project_name}\n"
        f"События: {events_text}\n\n"
        f"Подтвердите создание подписки."
    )

    await callback.message.edit_text(
        confirmation_text,
        reply_markup=get_confirmation_keyboard("subscribe"),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data == "confirm:subscribe", SubscriptionStates.confirming)
async def process_subscribe_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение подписки"""
    telegram_id = callback.from_user.id
    data = await state.get_data()

    platform = data.get("platform")
    project_id = data.get("project_id")
    selected_project = data.get("selected_project")
    selected_events = data.get("selected_events", [])

    if platform == "gitlab":
        project_name = selected_project.get("name_with_namespace", selected_project.get("name"))
    else:
        project_name = selected_project.get("full_name")

    events_str = ",".join(selected_events)

    async for session in get_session():
        # Вдруг уже есть такая подписка
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == telegram_id,
                Subscription.platform == platform,
                Subscription.project_id == str(project_id)
            )
        )
        existing_sub = result.scalar_one_or_none()

        if existing_sub:
            # Обновляем существующую подписку
            existing_sub.event_types = events_str
            existing_sub.is_active = True
            await session.commit()

            await callback.message.edit_text(
                f"Подписка обновлена!\n\n"
                f"Проект: {project_name}\n"
                f"События: {events_str}\n\n"
                f"Вы будете получать уведомления о выбранных событиях.",
                parse_mode="HTML"
            )
        else:
            # Или создаем новую
            subscription = Subscription(
                user_id=telegram_id,
                platform=platform,
                project_id=str(project_id),
                project_name=project_name,
                event_types=events_str,
                is_active=True
            )
            session.add(subscription)
            await session.commit()

            # Настраиваем webhook
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user:
                if platform == "gitlab" and user.gitlab_token:
                    webhook_id = await WebhookManager.setup_gitlab_webhook(
                        project_id=str(project_id),
                        gitlab_token=user.gitlab_token,
                        event_types=selected_events
                    )
                    if webhook_id:
                        subscription.webhook_id = str(webhook_id)
                        await session.commit()
                elif platform == "github" and user.github_token:
                    webhook_id = await WebhookManager.setup_github_webhook(
                        repo_full_name=project_id,
                        github_token=user.github_token,
                        event_types=selected_events
                    )
                    if webhook_id:
                        subscription.webhook_id = str(webhook_id)
                        await session.commit()

            await callback.message.edit_text(
                f"Подписка создана!\n\n"
                f"Проект: {project_name}\n"
                f"События: {events_str}\n\n"
                f"Вы будете получать уведомления о выбранных событиях.",
                parse_mode="HTML"
            )

    await state.clear()
    await callback.answer()


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message, state: FSMContext) -> None:
    """Запуск процесса отписки"""
    telegram_id = message.from_user.id

    async for session in get_session():
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == telegram_id,
                Subscription.is_active == True
            )
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            await message.answer(
                "У вас нет активных подписок.\n\n"
                "Используйте /subscribe для создания подписки."
            )
            return

        # Показываем как список словарей для клавиатуры
        subs_list = [
            {
                "id": sub.id,
                "project_name": sub.project_name,
                "platform": sub.platform
            }
            for sub in subscriptions
        ]

        await state.set_state(UnsubscriptionStates.choosing_subscription)
        await state.update_data(subscriptions=subs_list)

        await message.answer(
            "Выберите подписку для удаления:",
            reply_markup=get_subscriptions_keyboard(subs_list),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("unsub:"), UnsubscriptionStates.choosing_subscription)
async def process_unsubscribe_choice(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор подписки для удаления"""
    sub_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    subscriptions = data.get("subscriptions", [])

    # ищем эту подписку
    selected_sub = None
    for sub in subscriptions:
        if sub["id"] == sub_id:
            selected_sub = sub
            break

    if not selected_sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await state.update_data(selected_subscription_id=sub_id)
    await state.set_state(UnsubscriptionStates.confirming)

    platform_emoji = "🐈" if selected_sub["platform"] == "gitlab" else "🐈‍⬛"

    await callback.message.edit_text(
        f"Подтвердите удаление подписки:\n\n"
        f"{platform_emoji} {selected_sub['project_name']}\n\n"
        f"Вы больше не будете получать уведомления от этого проекта.",
        reply_markup=get_confirmation_keyboard("unsubscribe"),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data == "confirm:unsubscribe", UnsubscriptionStates.confirming)
async def process_unsubscribe_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение отписки"""
    data = await state.get_data()
    sub_id = data.get("selected_subscription_id")

    async for session in get_session():
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            await callback.answer("Подписка не найдена", show_alert=True)
            return

        project_name = subscription.project_name

        from html import escape

        safe_name = escape(project_name)

        # Удаляем
        await session.delete(subscription)
        await session.commit()

        await callback.message.edit_text(
            f"Подписка удалена!\n\n"
            f"Проект: {safe_name}\n\n"
            f"Вы больше не будете получать уведомления от этого проекта.",
            parse_mode="HTML"
        )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def process_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена текущей операции"""
    await state.clear()
    await callback.message.edit_text("Операция отменена.")
    await callback.answer()
