"""
Тесты для обработчиков webhook событий.
"""

import pytest
from src.webhook.handlers import (
    _map_gitlab_event_type,
    _map_github_event_type,
    _format_gitlab_message,
    _format_github_message
)


class TestGitLabEventMapping:
    """Тесты маппинга событий GitLab."""
    
    def test_pipeline_hook(self):
        """Тест маппинга Pipeline Hook."""
        assert _map_gitlab_event_type("Pipeline Hook") == "pipeline"
    
    def test_merge_request_hook(self):
        """Тест маппинга Merge Request Hook."""
        assert _map_gitlab_event_type("Merge Request Hook") == "merge_request"
    
    def test_issue_hook(self):
        """Тест маппинга Issue Hook."""
        assert _map_gitlab_event_type("Issue Hook") == "issue"
    
    def test_wiki_page_hook(self):
        """Тест маппинга Wiki Page Hook."""
        assert _map_gitlab_event_type("Wiki Page Hook") == "wiki"
    
    def test_note_hook(self):
        """Тест маппинга Note Hook."""
        assert _map_gitlab_event_type("Note Hook") == "note"
    
    def test_unknown_event(self):
        """Тест неизвестного события."""
        assert _map_gitlab_event_type("Unknown Event") == ""


class TestGitHubEventMapping:
    """Тесты маппинга событий GitHub."""
    
    def test_workflow_run(self):
        """Тест маппинга workflow_run."""
        assert _map_github_event_type("workflow_run", {}) == "workflow"
    
    def test_pull_request(self):
        """Тест маппинга pull_request."""
        assert _map_github_event_type("pull_request", {}) == "pull_request"
    
    def test_issues(self):
        """Тест маппинга issues."""
        assert _map_github_event_type("issues", {}) == "issue"
    
    def test_issue_comment(self):
        """Тест маппинга issue_comment."""
        assert _map_github_event_type("issue_comment", {}) == "comment"
    
    def test_star(self):
        """Тест маппинга star."""
        assert _map_github_event_type("star", {}) == "star"
    
    def test_unknown_event(self):
        """Тест неизвестного события."""
        assert _map_github_event_type("unknown_event", {}) == ""


class TestGitLabMessageFormatting:
    """Тесты форматирования сообщений GitLab."""
    
    def test_pipeline_success(self):
        """Тест форматирования успешного pipeline."""
        data = {
            "project": {
                "name": "test-project",
                "web_url": "https://gitlab.com/test/project"
            },
            "object_attributes": {
                "id": 123,
                "status": "success",
                "ref": "main"
            }
        }
        
        message = _format_gitlab_message("Pipeline Hook", data)
        
        assert "✅" in message
        assert "Pipeline success" in message
        assert "test-project" in message
        assert "main" in message
    
    def test_merge_request_opened(self):
        """Тест форматирования открытого MR."""
        data = {
            "project": {
                "name": "test-project",
                "web_url": "https://gitlab.com/test/project"
            },
            "object_attributes": {
                "action": "open",
                "title": "Test MR",
                "url": "https://gitlab.com/test/project/-/merge_requests/1"
            },
            "user": {
                "name": "John Doe"
            }
        }
        
        message = _format_gitlab_message("Merge Request Hook", data)
        
        assert "🆕" in message
        assert "Merge Request open" in message
        assert "Test MR" in message
        assert "John Doe" in message


class TestGitHubMessageFormatting:
    """Тесты форматирования сообщений GitHub."""
    
    def test_workflow_success(self):
        """Тест форматирования успешного workflow."""
        data = {
            "repository": {
                "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo"
            },
            "workflow_run": {
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/owner/repo/actions/runs/123"
            }
        }
        
        message = _format_github_message("workflow_run", data)
        
        assert "✅" in message
        assert "Workflow success" in message
        assert "owner/repo" in message
        assert "CI" in message
    
    def test_pull_request_opened(self):
        """Тест форматирования открытого PR."""
        data = {
            "action": "opened",
            "repository": {
                "full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo"
            },
            "pull_request": {
                "title": "Test PR",
                "html_url": "https://github.com/owner/repo/pull/1",
                "user": {
                    "login": "johndoe"
                },
                "merged": False
            }
        }
        
        message = _format_github_message("pull_request", data)
        
        assert "🆕" in message
        assert "Pull Request opened" in message
        assert "Test PR" in message
        assert "johndoe" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
