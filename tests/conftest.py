"""
Fixtures communes pour les tests.
"""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

from config.settings import AppConfig, ProjectConfig, PathConfig, ServerConfig, GeminiConfig, ClaudeConfig


@pytest.fixture
def temp_dir():
    """Crée un répertoire temporaire pour les tests."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_config():
    """Crée une configuration mock pour les tests."""
    project_config = ProjectConfig(
        repository_url="https://github.com/test/repo.git",
        dev_path=str(Path("/tmp/test/dev")),
        backend_dev_path=str(Path("/tmp/test/backend_dev")),
        prod_path=str(Path("/tmp/test/prod")),
        frontend_framework="react",
        branch_name="main",
        wordpress_api_enabled=False,
        enable_database=False,
        database_url="file:./test.db"
    )
    
    paths = PathConfig(
        base_dir=Path("/tmp"),
        config_path=Path("/tmp/project_config.json"),
        wordpress_backend_source=Path("/tmp/templates_backend/wordpress_api"),
        dev_path=Path("/tmp/test/dev"),
        backend_dev_path=Path("/tmp/test/backend_dev"),
        prod_path=Path("/tmp/test/prod")
    )
    
    config = Mock(spec=AppConfig)
    config.project = project_config
    config.paths = paths
    config.servers = ServerConfig(dev_port=5173, backend_port=3000)
    config.gemini = GeminiConfig(enabled=False)
    config.claude = ClaudeConfig(enabled=False)
    
    return config


@pytest.fixture
def mock_gemini_config():
    """Crée une configuration Gemini mock activée."""
    return GeminiConfig(
        api_key="test_api_key",
        model_name="gemini-2.5-pro",
        enabled=True,
        client=MagicMock()
    )


@pytest.fixture
def mock_claude_config():
    """Crée une configuration Claude mock activée."""
    return ClaudeConfig(
        api_key="test_api_key",
        model_name="claude-3-sonnet-20240229",
        enabled=True
    )


@pytest.fixture
def mock_command_result():
    """Crée un mock CommandResult."""
    from app.utils.shell import CommandResult
    
    def _create(success=True, stdout="", stderr="", returncode=0):
        return CommandResult(
            command="test_command",
            returncode=returncode if success else 1,
            stdout=stdout,
            stderr=stderr,
            cwd="/tmp"
        )
    return _create

