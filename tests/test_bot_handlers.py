"""
Тесты для обработчиков команд Telegram бота (src/bot/handlers.py)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram.types import Message, User as TelegramUser
from sqlalchemy import select

from src.database import User, get_session
from src.bot.handlers import cmd_start, cmd_status, cmd_set_gitlab_token, cmd_set_github_token

from tests.mocks import MockAsyncSession, MockBot, MockResult, MockGitLabClient, MockGitHubClient


# Фикстуры

@pytest.fixture
def mock_db_session():
    """Мокирование сессии БД"""
    return MockAsyncSession()


@pytest.fixture
def mock_message():
    """Мокирование объекта Message"""
    message = MagicMock(spec=Message)
    message.from_user = TelegramUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        username="telegram_user"
    )
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_get_session_generator(mock_db_session):
    """Мокирование генератора get_session"""

    async def mock_generator():
        yield mock_db_session

    return mock_generator


@pytest.fixture
def user_data():
    """Тестовый пользователь"""
    return User(
        telegram_id=123456789,
        username="telegram_user",
        first_name="Test",
        gitlab_token="fake_gitlab_token",
        github_token="fake_github_token",
        gitlab_username="gitlab_test_user",
        github_username="github_test_user"
    )


# Тесты для cmd_start

@pytest.mark.asyncio
async def test_cmd_start_new_user(mock_message, mock_db_session, mock_get_session_generator):
    """Регистрация нового пользователя"""

    # Мокируем execute для имитации отсутствия пользователя
    mock_db_session.execute.return_value = MockResult([])

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator):
        await cmd_start(mock_message)

        # Пользователь был добавлен и сессия закоммичена
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Проверяем приветственное сообщение
        mock_message.answer.assert_called_once()
        assert "Добро пожаловать в GitLab Assistant" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_start_existing_user(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Приветствие существующего пользователя"""

    # Мокируем execute для имитации существующего пользователя
    mock_db_session.execute.return_value = MockResult([user_data])

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator):
        await cmd_start(mock_message)

        # Пользователь не был добавлен
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()

        # Проверяем приветственное сообщение
        mock_message.answer.assert_called_once()
        assert "С возвращением, Test!" in mock_message.answer.call_args[0][0]


# Тесты для cmd_status

@pytest.mark.asyncio
async def test_cmd_status_no_user(mock_message, mock_db_session, mock_get_session_generator):
    """Статус незарегистрированного пользователя"""

    mock_db_session.execute.return_value = MockResult([])

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator):
        await cmd_status(mock_message)

        mock_message.answer.assert_called_once()
        assert "Вы не зарегистрированы" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_status_with_tokens(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Статус с установленными токенами"""

    user_data.gitlab_token = "fake_gitlab_token"
    user_data.github_token = "fake_github_token"
    user_data.gitlab_username = "test_gitlab"
    user_data.github_username = "test_github"
    user_data.subscriptions = [MagicMock(), MagicMock()]  # Имитация подписок

    mock_db_session.execute.return_value = MockResult([user_data])

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator):
        await cmd_status(mock_message)

        status_text = mock_message.answer.call_args[0][0]
        assert "GitLab: Установлен (test_gitlab)" in status_text
        assert "GitHub: Установлен (test_github)" in status_text
        assert "Активных подписок: 2" in status_text


# Тесты для cmd_set_gitlab_token

@pytest.mark.asyncio
async def test_cmd_set_gitlab_token_invalid_format(mock_message):
    """Неверный формат команды"""
    mock_message.text = "/set_gitlab_token"
    await cmd_set_gitlab_token(mock_message)
    mock_message.answer.assert_called_once()
    assert "Неверный формат команды" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_set_gitlab_token_success(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Успешная установка GitLab токена"""
    # Очистим токены для теста
    user_data.gitlab_token = None
    user_data.gitlab_username = None

    mock_message.text = "/set_gitlab_token fake_token"
    mock_db_session.execute.return_value = MockResult([user_data])

    # Мокируем GitLabClient
    mock_gitlab_client = MockGitLabClient("http://gitlab.com", "fake_token")
    mock_gitlab_client.get_current_user.return_value = {"username": "new_gitlab_user"}

    with (patch('src.bot.handlers.get_session', new=mock_get_session_generator), \
            patch('src.gitlab_api.client.GitLabClient', return_value=mock_gitlab_client)):
        await cmd_set_gitlab_token(mock_message)

        # Токен и username должны быть сохранены
        assert user_data.gitlab_token == "fake_token"
        assert user_data.gitlab_username == "new_gitlab_user"
        mock_db_session.commit.assert_called_once()

        # Проверяем сообщения
        mock_message.delete.assert_called_once()
        mock_message.answer.assert_called_once()
        assert "успешно установлен! Ваш GitLab username: " in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_set_gitlab_token_api_failure(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Ошибка API при установке токена GitLab"""
    # Очистим токены для теста
    user_data.gitlab_token = None
    user_data.gitlab_username = None

    mock_message.text = "/set_gitlab_token fake_token"
    mock_db_session.execute.return_value = MockResult([user_data])

    # Мокируем GitLabClient для имитации ошибки
    mock_gitlab_client = MockGitLabClient("http://gitlab.com", "fake_token")
    mock_gitlab_client.get_current_user.side_effect = Exception("API Error")

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator), \
            patch('src.gitlab_api.client.GitLabClient', return_value=mock_gitlab_client):
        await cmd_set_gitlab_token(mock_message)

        # Токен и username НЕ должны быть сохранены
        assert user_data.gitlab_token is None
        assert user_data.gitlab_username is None
        mock_db_session.commit.assert_not_called()

        # Проверяем сообщения
        mock_message.delete.assert_called_once()
        mock_message.answer.assert_called_once()
        assert "Ошибка при проверке токена GitLab: API Error" in mock_message.answer.call_args[0][0]


# Тесты для cmd_set_github_token

@pytest.mark.asyncio
async def test_cmd_set_github_token_success(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Успешная установка GitHub токена"""
    # Очистим токены для теста
    user_data.github_token = None
    user_data.github_username = None

    mock_message.text = "/set_github_token fake_token"
    mock_db_session.execute.return_value = MockResult([user_data])

    # Мокируем GitHubClient
    mock_github_client = MockGitHubClient("fake_token")
    mock_github_client.get_current_user.return_value = {"login": "new_github_user"}

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator), \
            patch('src.github_api.client.GitHubClient', return_value=mock_github_client):
        await cmd_set_github_token(mock_message)

        # Токен и username должны быть сохранены
        assert user_data.github_token == "fake_token"
        assert user_data.github_username == "new_github_user"
        mock_db_session.commit.assert_called_once()

        # Проверяем сообщения
        mock_message.delete.assert_called_once()
        mock_message.answer.assert_called_once()
        assert "успешно установлен! Ваш GitHub username: " in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_set_github_token_api_failure(mock_message, mock_db_session, mock_get_session_generator, user_data):
    """Ошибка API при установке токена GitHub."""
    # Очистим токены для теста
    user_data.github_token = None
    user_data.github_username = None

    mock_message.text = "/set_github_token fake_token"
    mock_db_session.execute.return_value = MockResult([user_data])

    # Мокируем GitHubClient для имитации ошибки
    mock_github_client = MockGitHubClient("fake_token")
    mock_github_client.get_current_user.side_effect = Exception("API Error")

    with patch('src.bot.handlers.get_session', new=mock_get_session_generator), \
            patch('src.github_api.client.GitHubClient', return_value=mock_github_client):
        await cmd_set_github_token(mock_message)

        # Токен и username НЕ должны быть сохранены
        assert user_data.github_token is None
        assert user_data.github_username is None
        mock_db_session.commit.assert_not_called()

        # Проверяем сообщения
        mock_message.delete.assert_called_once()
        mock_message.answer.assert_called_once()
        assert "Ошибка при проверке токена GitHub: API Error" in mock_message.answer.call_args[0][0]
