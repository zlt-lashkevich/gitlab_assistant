"""
Обработчики команды /history для просмотра последних уведомлений
"""

from typing import Dict, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select, desc
from loguru import logger

from src.database import Notification, get_session

router = Router()

HISTORY_LIMIT = 10


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    """Команда /history"""
    user_id = message.from_user.id

    logger.info(f"User {user_id} requested history")

    async for session in get_session():
        result = await session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(desc(Notification.sent_at))
            .limit(HISTORY_LIMIT)
        )
        notifications = result.scalars().all()

        logger.info(f"Found {len(notifications)} notifications for user {user_id}")

        if not notifications:
            await message.answer("У вас пока нет истории уведомлений.")
            return

        # По проектам
        grouped_notifications: Dict[str, List[Notification]] = {}
        for notif in notifications:
            project_name = notif.project_name or "Общие уведомления"
            if project_name not in grouped_notifications:
                grouped_notifications[project_name] = []
            grouped_notifications[project_name].append(notif)

        # Текст сообщения
        history_text = "<b>Ваша история уведомлений (последние 10):</b>\n\n"

        for project_name, notifs in grouped_notifications.items():
            history_text += f"<b>{project_name}</b> ({len(notifs)}):\n"
            for notif in notifs:
                time_str = notif.sent_at.strftime("%d.%m %H:%M")
                event_type = notif.event_type.replace("_", " ").title()

                first_line = notif.message.split('\n')[0]
                # Убираем HTML теги для краткого описания
                summary = first_line.replace('<b>', '').replace('</b>', '')[:50]

                history_text += f"  • [{time_str}] {event_type}\n"
            history_text += "\n"

        await message.answer(
            history_text,
            parse_mode="HTML",
            reply_markup=build_history_keyboard(grouped_notifications)
        )
        return


@router.callback_query(F.data.startswith("history_detail_"))
async def show_history_detail(callback: CallbackQuery) -> None:
    """Показ деталей уведомления"""
    try:
        notification_id = int(callback.data.split("_")[-1])

        async for session in get_session():
            result = await session.execute(
                select(Notification).where(
                    Notification.id == notification_id,
                    Notification.user_id == callback.from_user.id
                )
            )
            notification = result.scalar_one_or_none()

            if not notification:
                await callback.answer("Уведомление не найдено.", show_alert=True)
                return

            await callback.message.answer(
                notification.message,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            await callback.answer()
            return

    except Exception as e:
        logger.error(f"Error showing history detail: {e}")
        await callback.answer("Произошла ошибка.", show_alert=True)


def build_history_keyboard(grouped_notifications: Dict[str, List[Notification]]) -> InlineKeyboardMarkup:
    """inline-клавиатура для просмотра деталей"""
    buttons = []

    for project_name, notifs in grouped_notifications.items():
        project_buttons = []
        for notif in notifs[:5]:  # Максимум 5 кнопок на проект
            time_str = notif.sent_at.strftime("%H:%M")
            event_type = notif.event_type.replace("_", " ").title()[:15]

            button_text = f"[{time_str}] {event_type}"
            callback_data = f"history_detail_{notif.id}"

            project_buttons.append(
                InlineKeyboardButton(text=button_text, callback_data=callback_data)
            )

        for i in range(0, len(project_buttons), 2):
            buttons.append(project_buttons[i:i + 2])

    return InlineKeyboardMarkup(inline_keyboard=buttons)