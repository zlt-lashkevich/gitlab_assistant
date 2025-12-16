"""
Модуль для работы с GitLab API
"""

from src.gitlab_api.client import GitLabClient
from src.gitlab_api.actions import GitLabActions

__all__ = ["GitLabClient", "GitLabActions"]
