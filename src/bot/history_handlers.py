"""
Обработчики команды /history для просмотра последних уведомлений.
"""

from typing import Dict, List, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import Notification
from src.bot.keyboards import get_history_keyboard

router = Router()

HISTORY_LIMIT = 10  # Количество последних уведомлений для показа

@router.message(Command("history"))
async def cmd_history(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /history."""
    user_id = message.from_user.id
    
    # 1. Получаем последние уведомления
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.sent_at))
        .limit(HISTORY_LIMIT)
    )
    notifications = result.scalars().all()
    
    if not notifications:
        await message.answer("У вас пока нет истории уведомлений.")
        return
    
    # 2. Группируем по проекту
    grouped_notifications: Dict[str, List[Notification]] = {}
    for notif in notifications:
        project_name = notif.project_name or "Общие уведомления"
        if project_name not in grouped_notifications:
            grouped_notifications[project_name] = []
        grouped_notifications[project_name].append(notif)
        
    # 3. Формируем сообщение
    history_text = "📚 **Ваша история уведомлений (последние 10):**\n\n"
    
    for project_name, notifs in grouped_notifications.items():
        history_text += f"**{project_name}** ({len(notifs)}):\n"
        for notif in notifs:
            # Извлекаем тип события и время
            time_str = notif.sent_at.strftime("%H:%M:%S")
            event_type = notif.event_type.replace("_", " ").title()
            
            # Извлекаем краткое содержание сообщения
            summary = notif.message.split('\n')[0].replace('*', '').replace('**', '')
            
            history_text += f"  - [{time_str}] {event_type}: {summary}\n"
        history_text += "\n"
        
    # 4. Отправляем сообщение с кнопкой "Показать детали"
    await message.answer(
        history_text,
        parse_mode="HTML",
        reply_markup=get_history_keyboard(grouped_notifications)
    )

@router.callback_query(F.data.startswith("history_detail_"))
async def show_history_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    """Обработчик для показа деталей уведомления."""
    try:
        # Получаем ID уведомления из callback_data
        notification_id = int(callback.data.split("_")[-1])
        
        # Ищем уведомление в БД
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == callback.from_user.id
            )
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            await callback.answer("Уведомление не найдено или недоступно.", show_alert=True)
            return
        
        # Отправляем полное сообщение уведомления
        await callback.message.answer(
            notification.message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer("Произошла ошибка при получении деталей.", show_alert=True)
        logger.error(f"Error showing history detail: {e}")

# Обновление клавиатуры для истории
def get_history_keyboard(grouped_notifications: Dict[str, List[Notification]]):
    """
    Создает inline-клавиатуру для просмотра деталей уведомлений.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    for project_name, notifs in grouped_notifications.items():
        # Добавляем кнопку для каждого проекта
        project_buttons = []
        for notif in notifs:
            time_str = notif.sent_at.strftime("%H:%M")
            event_type = notif.event_type.replace("_", " ").title()
            
            # Кнопка: [Время] Тип события
            button_text = f"[{time_str}] {event_type}"
            callback_data = f"history_detail_{notif.id}"
            
            project_buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
        
        # Группируем кнопки по 2 в ряд
        for i in range(0, len(project_buttons), 2):
            buttons.append(project_buttons[i:i+2])
            
    return InlineKeyboardMarkup(inline_keyboard=buttons)
