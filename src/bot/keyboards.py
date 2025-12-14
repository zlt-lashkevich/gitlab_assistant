"""
Клавиатуры для бота
"""

from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_platform_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора платформы
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="GitLab", callback_data="platform:gitlab")
    builder.button(text="GitHub", callback_data="platform:github")
    builder.button(text="Отмена", callback_data="cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_projects_keyboard(
    projects: List[dict],
    platform: str,
    page: int = 0,
    per_page: int = 10
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком проектов/репозиториев
    """
    builder = InlineKeyboardBuilder()
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_projects = projects[start_idx:end_idx]

    for project in page_projects:
        if platform == "gitlab":
            project_id = project.get("id")
            project_name = project.get("name_with_namespace", project.get("name"))
        else:
            project_id = project.get("full_name")
            project_name = project.get("full_name")

        display_name = project_name[:50] + "..." if len(project_name) > 50 else project_name
        builder.button(text=display_name, callback_data=f"project:{platform}:{project_id}")

    builder.adjust(1)

    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(text="Назад", callback_data=f"page:{platform}:{page-1}")
        )
    if end_idx < len(projects):
        navigation_buttons.append(
            InlineKeyboardButton(text="Вперед", callback_data=f"page:{platform}:{page+1}")
        )

    if navigation_buttons:
        builder.row(*navigation_buttons)

    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def get_events_keyboard(platform: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора типов событий
    """
    builder = InlineKeyboardBuilder()
    if platform == "gitlab":
        events = [
            ("Pipeline", "event:pipeline"),
            ("Merge Request", "event:merge_request"),
            ("Issue", "event:issue"),
            ("Wiki", "event:wiki"),
            ("Комментарии", "event:note"),
        ]
    else:
        events = [
            ("Workflow (Actions)", "event:workflow"),
            ("Pull Request", "event:pull_request"),
            ("Issue", "event:issue"),
            ("Комментарии", "event:comment"),
            ("Stars", "event:star"),
        ]

    for text, callback_data in events:
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="Выбрать все", callback_data="events:all"),
        InlineKeyboardButton(text="Сбросить", callback_data="events:reset")
    )
    builder.row(
        InlineKeyboardButton(text="Готово", callback_data="events:done"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def get_confirmation_keyboard(action: str = "subscribe") -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data=f"confirm:{action}")
    builder.button(text="Отмена", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


def get_subscriptions_keyboard(subscriptions: List[Dict]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком подписок для удаления
    """
    builder = InlineKeyboardBuilder()
    for sub in subscriptions:
        sub_id = sub.get("id")
        project_name = sub.get("project_name", "Unknown")
        platform = sub.get("platform", "unknown")
        emoji = "Lab" if platform == "gitlab" else "Hub"
        display_name = project_name[:40] + "..." if len(project_name) > 40 else project_name
        builder.button(text=f'{emoji} {display_name}', callback_data=f"unsub:{sub_id}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return builder.as_markup()


def get_history_keyboard(grouped_notifications: Dict[str, List[Notification]]) -> InlineKeyboardMarkup:
    """
    inline-клавиатурf для просмотра деталей уведомлений
    """
    builder = InlineKeyboardBuilder()
    for project_name, notifs in grouped_notifications.items():
        project_buttons = []
        for notif in notifs:
            time_str = notif.sent_at.strftime("%H:%M")
            event_type = notif.event_type.replace("_", " ").title()
            button_text = f'[{time_str}] {event_type}'
            callback_data = f"history_detail_{notif.id}"
            project_buttons.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))

        rows = [project_buttons[i:i + 2] for i in range(0, len(project_buttons), 2)]
        for row in rows:
            builder.row(*row)

    return builder.as_markup()
