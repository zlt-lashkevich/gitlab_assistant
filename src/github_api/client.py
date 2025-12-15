"""
Клиент для работы с GitHub API
"""

from typing import List, Dict, Optional, Any
from loguru import logger

import aiohttp
from aiohttp import ClientSession


class GitHubClient:

    def __init__(self, token: str):
        """
        Args:
            token: Personal Access Token для аутентификации
        """
        self.api_url = "https://api.github.com"
        self.token = token
        self.session: Optional[ClientSession] = None

    # Контекстные менеджеры
    async def __aenter__(self):
        """Вход"""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход"""
        if self.session:
            await self.session.close()

    async def _request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            json_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        HTTP запрос
        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: Endpoint API (без базового URL)
            params: Query параметры
            json_data: JSON данные для POST/PUT запросов

        Returns:
            Ответ от API

        Raises:
            aiohttp.ClientError: При ошибке запроса
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async with context manager.")

        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        try:
            async with self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data
            ) as response:
                response.raise_for_status()
                if response.status == 204:
                    return None

                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"GitHub API request failed: {method} {url} - {e}")
            raise

    async def get_current_user(self) -> Dict[str, Any]:
        """
        Информация о текущем пользователе
        """
        return await self._request("GET", "/user")

    async def get_repositories(
            self,
            visibility: str = "all",
            affiliation: str = "owner,collaborator,organization_member",
            sort: str = "updated",
            per_page: int = 50,
            page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Args:
            visibility: Видимость (all, public, private)
            affiliation: Тип участия (owner, collaborator, organization_member)
            sort: Сортировка (created, updated, pushed, full_name)
            per_page: Количество репозиториев на странице
            page: Номер страницы

        Returns:
            Список репозиториев
        """
        params = {
            "visibility": visibility,
            "affiliation": affiliation,
            "sort": sort,
            "per_page": per_page,
            "page": page
        }

        return await self._request("GET", "/user/repos", params=params)

    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория

        Returns:
            Информация о репозитории
        """
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_repository_hooks(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория

        Returns:
            Список webhooks
        """
        return await self._request("GET", f"/repos/{owner}/{repo}/hooks")

    async def create_repository_hook(
            self,
            owner: str,
            repo: str,
            url: str,
            events: Optional[List[str]] = None,
            secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория
            url: URL для отправки webhook
            events: Список событий (по умолчанию: push)
            secret: Секретный токен для webhook

        Returns:
            Информация о созданном webhook
        """
        if events is None:
            events = ["push", "pull_request", "issues", "issue_comment"]

        data = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": url,
                "content_type": "json",
                "insecure_ssl": "0"
            }
        }

        if secret:
            data["config"]["secret"] = secret

        return await self._request("POST", f"/repos/{owner}/{repo}/hooks", json_data=data)

    async def delete_repository_hook(self, owner: str, repo: str, hook_id: int) -> None:
        """
        Удаление webhook репозитория

        Args:
            owner: Владелец репозитория
            repo: Название репозитория
            hook_id: ID webhook
        """
        await self._request("DELETE", f"/repos/{owner}/{repo}/hooks/{hook_id}")

    async def get_pull_requests(
            self,
            owner: str,
            repo: str,
            state: str = "open",
            per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория
            state: Состояние PR (open, closed, all)
            per_page: Количество результатов на странице

        Returns:
            Список pull requests
        """
        params = {
            "state": state,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc"
        }

        return await self._request("GET", f"/repos/{owner}/{repo}/pulls", params=params)

    async def get_workflow_runs(
            self,
            owner: str,
            repo: str,
            per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория
            per_page: Количество результатов на странице

        Returns:
            Список workflow runs
        """
        params = {
            "per_page": per_page
        }

        return await self._request("GET", f"/repos/{owner}/{repo}/actions/runs", params=params)

    async def get_issues(
            self,
            owner: str,
            repo: str,
            state: str = "open",
            per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Args:
            owner: Владелец репозитория
            repo: Название репозитория
            state: Состояние issue (open, closed, all)
            per_page: Количество результатов на странице

        Returns:
            Список issues
        """
        params = {
            "state": state,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc"
        }

        return await self._request("GET", f"/repos/{owner}/{repo}/issues", params=params)
