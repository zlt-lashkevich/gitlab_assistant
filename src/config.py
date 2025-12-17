"""
Конфигурация приложения GitLab Assistant
Использует pydantic-settings для валидации и загрузки переменных окружения
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Bot
    telegram_bot_token: str = Field(..., description="Telegram Bot API токен")

    # GitLab
    gitlab_url: str = Field(default="https://gitlab.com", description="URL GitLab инстанса")
    gitlab_private_token: str = Field(default="", description="GitLab Personal Access Token")

    # GitHub
    github_token: str = Field(default="", description="GitHub Personal Access Token")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./gitlab_assistant.db",
        description="URL подключения к базе данных"
    )

    # Webhook
    webhook_host: str = Field(default="0.0.0.0", description="Хост для прослушивания webhook сервера")
    webhook_port: int = Field(default=8443, description="Порт для webhook сервера")
    webhook_public_url: str = Field(default="", description="Публичный URL для webhooks (https://your-domain.com)")

    # Logging
    log_level: str = Field(default="INFO", description="Уровень логирования")

    # Application
    debug: bool = Field(default=False, description="Режим отладки")

    @property
    def gitlab_webhook_url(self) -> str:
        """Полный URL для GitLab webhook"""
        if not self.webhook_public_url:
            return ""
        return f"{self.webhook_public_url}/webhook/gitlab"

    @property
    def github_webhook_url(self) -> str:
        """Полный URL для GitHub webhook"""
        if not self.webhook_public_url:
            return ""
        return f"{self.webhook_public_url}/webhook/github"


# Глобальный экземпляр настроек
settings = Settings()
