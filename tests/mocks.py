"""
Базовые mock-утилиты
"""

from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import User, Subscription, Notification, NotificationSettings


class MockUser:
    def __init__(self, telegram_id, gitlab_username=None, github_username=None, gitlab_token=None, github_token=None):
        self.telegram_id = telegram_id
        self.gitlab_username = gitlab_username
        self.github_username = github_username
        self.gitlab_token = gitlab_token
        self.github_token = github_token


class MockNotificationSettings:
    def __init__(self, user_id, **kwargs):
        self.user_id = user_id
        self.reviewer_assignment_enabled = kwargs.get("reviewer_assignment_enabled", False)
        self.merge_enabled = kwargs.get("merge_enabled", False)
        self.pipeline_completion_enabled = kwargs.get("pipeline_completion_enabled", False)
        self.issue_assignment_enabled = kwargs.get("issue_assignment_enabled", False)
        self.mention_enabled = kwargs.get("mention_enabled", False)


class MockResult:
    """Результат запроса SQLAlchemy"""

    def __init__(self, scalars_result: List[Any]):
        self._scalars_result = scalars_result

    def scalars(self):
        return self

    def all(self):
        return self._scalars_result

    def scalar_one_or_none(self):
        return self._scalars_result[0] if self._scalars_result else None


class MockAsyncSession(AsyncSession):
    """Имитация асинхронной сессии"""

    def __init__(self, initial_data: Dict[str, List[Any]] = None):
        super().__init__(bind=MagicMock())
        self.data = initial_data if initial_data is not None else {
            "User": [],
            "Subscription": [],
            "NotificationSettings": [],
            "Notification": []
        }
        self.add = MagicMock()
        self.commit = AsyncMock()
        self.execute = AsyncMock()
        self.execute.side_effect = self._execute_with_override
        self.get = AsyncMock(side_effect=self._mock_get)

    async def _execute_with_override(self, statement):
        """Выполнение с поддержной переопределения return_value"""
        # Проверяем, если явно задано
        if hasattr(self.execute, '_return_value_set') and self.execute._return_value_set:
            return self.execute.return_value
        # Или пользуемся default реализацией
        return self._mock_execute(statement)

    def _mock_execute(self, statement):
        """Имитация выполнения запроса"""
        statement_str = str(statement)

        model_name = None

        if "users" in statement_str.lower():
            model_name = "User"
        elif "subscriptions" in statement_str.lower():
            model_name = "Subscription"
        elif "notification_settings" in statement_str.lower():
            model_name = "NotificationSettings"
        elif "notifications" in statement_str.lower():
            model_name = "Notification"

        if model_name and model_name in self.data:
            return MockResult(self.data[model_name])

        return MockResult([])

    async def _mock_get(self, model, primary_key):
        """Имитация получения объекта по первичному ключу"""
        model_name = model.__name__
        if model_name in self.data:
            for item in self.data[model_name]:
                # Первичный ключ - это telegram_id для User
                if model_name == "User" and item.telegram_id == primary_key:
                    return item
                # Для Subscription, NotificationSettings...  уточняем
                if model_name == "NotificationSettings" and item.user_id == primary_key:
                    return item
        return None


class MockGitLabClient:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.get_projects = AsyncMock(return_value=[])
        self.get_project = AsyncMock()
        self.create_webhook = AsyncMock()
        self.get_current_user = AsyncMock(return_value={"username": "gitlab_test_user"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockGitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.get_repositories = AsyncMock(return_value=[])
        self.get_repository = AsyncMock()
        self.create_webhook = AsyncMock()
        self.get_current_user = AsyncMock(return_value={"login": "github_test_user"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockBot:
    def __init__(self):
        self.send_message = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.delete_message = AsyncMock()
