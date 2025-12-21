"""
Менеджер для автоматической настройки webhooks в GitLab и GitHub
"""

from typing import Optional, List
from loguru import logger

from src.gitlab_api import GitLabClient
from src.github_api import GitHubClient
from src.config import settings


class WebhookManager:
    """Управление webhooks"""

    @staticmethod
    async def setup_gitlab_webhook(
            project_id: str,
            gitlab_token: str,
            event_types: List[str]
    ) -> Optional[int]:
        """
        Настройка webhook для проекта GitLab
        """
        if not settings.gitlab_webhook_url:
            logger.warning("GitLab webhook URL не настроен")
            return None

        try:
            async with GitLabClient(settings.gitlab_url, gitlab_token) as client:
                # существует ли уже webhook
                existing_hooks = await client.get_project_hooks(project_id)

                for hook in existing_hooks:
                    if hook.get("url") == settings.gitlab_webhook_url:
                        logger.info(f"Webhook для проекта {project_id} уже существует")
                        return hook.get("id")

                # Создаем новый

                webhook = await client.create_project_hook(
                    project_id=project_id,
                    url=settings.gitlab_webhook_url,
                    push_events=False,
                    issues_events="issue" in event_types,
                    merge_requests_events="merge_request" in event_types,
                    wiki_page_events="wiki" in event_types,
                    pipeline_events="pipeline" in event_types,
                    note_events="note" in event_types,  # Добавьте
                    token=getattr(settings, 'gitlab_webhook_secret', None)
                )

                if webhook:
                    logger.success(f"Webhook создан для проекта {project_id}")
                    return webhook.get("id")

                return None

        except Exception as e:
            logger.error(f"Ошибка при создании GitLab webhook: {e}")
            return None

    @staticmethod
    async def setup_github_webhook(
            repo_full_name: str,
            github_token: str,
            event_types: List[str]
    ) -> Optional[int]:
        """
        Настройка webhook для репозитория GitHub
        """
        if not settings.github_webhook_url:
            logger.warning("GitHub webhook URL не настроен")
            return None

        try:
            async with GitHubClient(github_token) as client:
                # Проверяем существование
                owner, repo = repo_full_name.split("/", 1)
                existing_hooks = await client.get_repository_hooks(owner, repo)

                for hook in existing_hooks:
                    hook_config = hook.get("config", {})
                    if hook_config.get("url") == settings.github_webhook_url:
                        logger.info(f"Webhook для репозитория {repo_full_name} уже существует")
                        return hook.get("id")

                # Маппинг типов событий
                github_events = []
                if "workflow" in event_types:
                    github_events.append("workflow_run")
                if "pull_request" in event_types:
                    github_events.append("pull_request")
                if "issue" in event_types:
                    github_events.append("issues")
                if "comment" in event_types:
                    github_events.extend(["issue_comment", "pull_request_review_comment"])
                if "star" in event_types:
                    github_events.append("star")

                # Создаем новый
                webhook_config = {
                    "name": "web",
                    "active": True,
                    "events": github_events if github_events else ["push"],
                    "config": {
                        "url": settings.github_webhook_url,
                        "content_type": "json",
                        "insecure_ssl": "0",
                    }
                }

                webhook = await client.create_repository_hook(
                    owner=owner,
                    repo=repo,
                    url=settings.github_webhook_url,
                    events=github_events if github_events else ["push"],
                    secret=getattr(settings, 'github_webhook_secret', None)
                )

                if webhook:
                    logger.success(f"Webhook создан для репозитория {repo_full_name}")
                    return webhook.get("id")

                return None

        except Exception as e:
            logger.error(f"Ошибка при создании GitHub webhook: {e}")
            return None

    @staticmethod
    async def remove_gitlab_webhook(
            project_id: str,
            webhook_id: int,
            gitlab_token: str
    ) -> bool:
        """
        Удаление webhook из проекта GitLab
        """
        try:
            async with GitLabClient(settings.gitlab_url, gitlab_token) as client:
                success = await client.delete_project_hook(project_id, webhook_id)

                if success:
                    logger.success(f"Webhook {webhook_id} удален из проекта {project_id}")

                return success

        except Exception as e:
            logger.error(f"Ошибка при удалении GitLab webhook: {e}")
            return False

    @staticmethod
    async def remove_github_webhook(
            repo_full_name: str,
            webhook_id: int,
            github_token: str
    ) -> bool:
        """
        Удаление webhook из репозитория GitHub
        """
        try:
            async with GitHubClient(github_token) as client:
                success = await client.delete_repository_hook(repo_full_name, webhook_id)

                if success:
                    logger.success(f"Webhook {webhook_id} удален из репозитория {repo_full_name}")

                return success

        except Exception as e:
            logger.error(f"Ошибка при удалении GitHub webhook: {e}")
            return False
