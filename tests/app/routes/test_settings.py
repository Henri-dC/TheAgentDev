"""
Tests unitaires pour app/routes/settings.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from pathlib import Path

from app.routes.settings import (
    init_services,
    settings_page,
    get_settings,
    save_settings,
    start_project,
    _write_backend_env_file
)


@pytest.fixture
def app():
    """Créer une application Flask pour les tests."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    return app


@pytest.fixture
def mock_services():
    """Créer des mocks pour tous les services."""
    return {
        'process': MagicMock(),
        'workspace': MagicMock()
    }


@pytest.fixture
def client(app, mock_services):
    """Créer un client de test Flask."""
    init_services(
        process_service=mock_services['process'],
        workspace_service=mock_services['workspace']
    )
    from app.routes.settings import settings_bp
    app.register_blueprint(settings_bp)
    return app.test_client()


class TestInitServices:
    """Tests pour init_services."""
    
    def test_init_services_sets_global_variables(self, mock_services):
        """Test que init_services définit les variables globales."""
        init_services(
            process_service=mock_services['process'],
            workspace_service=mock_services['workspace']
        )
        
        from app.routes.settings import process_svc, workspace_svc
        
        assert process_svc == mock_services['process']
        assert workspace_svc == mock_services['workspace']


class TestSettingsPage:
    """Tests pour settings_page."""
    
    @patch('app.routes.settings.render_template')
    def test_settings_page_renders_template(self, mock_render, client):
        """Test que settings_page rend le bon template."""
        response = client.get('/settings')
        
        assert response.status_code == 200
        mock_render.assert_called_once_with('settings.html')


class TestGetSettings:
    """Tests pour get_settings."""
    
    @patch('app.routes.settings.get_config')
    def test_get_settings_success(self, mock_get_config, client):
        """Test get_settings avec succès."""
        mock_config = MagicMock()
        mock_config.project.repository_url = "https://github.com/test/repo.git"
        mock_config.project.dev_path = "/tmp/test/dev"
        mock_config.project.prod_path = "/tmp/test/prod"
        mock_config.project.backend_dev_path = "/tmp/test/backend_dev"
        mock_config.project.frontend_framework = "react"
        mock_config.project.branch_name = "main"
        mock_config.project.wordpress_api_enabled = False
        mock_config.project.enable_database = False
        mock_config.project.database_url = "file:./test.db"
        mock_config.project.wordpress_env = {}
        mock_get_config.return_value = mock_config
        
        response = client.get('/api/get_settings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'repository_url' in data
        assert 'dev_path' in data
        assert 'frontend_framework' in data
    
    @patch('app.routes.settings.get_config')
    def test_get_settings_error(self, mock_get_config, client):
        """Test get_settings avec erreur."""
        mock_get_config.side_effect = Exception("Config error")
        
        response = client.get('/api/get_settings')
        
        assert response.status_code == 500
        assert 'error' in response.get_json()


class TestSaveSettings:
    """Tests pour save_settings."""
    
    @patch('app.routes.settings.reload_config')
    @patch('app.routes.settings.get_config')
    def test_save_settings_success(
        self,
        mock_get_config,
        mock_reload,
        client
    ):
        """Test save_settings avec succès."""
        mock_config = MagicMock()
        mock_config.project = MagicMock()
        mock_config.project.save_to_file = MagicMock()
        mock_get_config.return_value = mock_config
        
        settings_data = {
            'frontend_framework': 'vue',
            'repository_url': 'https://github.com/test/repo.git',
            'wordpress_api_enabled': False,
            'enable_database': False,
            'database_url': 'file:./test.db',
            'branch_name': 'main'
        }
        
        response = client.post(
            '/api/save_settings',
            json=settings_data
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        mock_config.project.save_to_file.assert_called_once()
        mock_reload.assert_called_once()
    
    def test_save_settings_no_data(self, client):
        """Test save_settings sans données."""
        response = client.post('/api/save_settings', json={})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
    
    @patch('app.routes.settings.get_config')
    def test_save_settings_error(self, mock_get_config, client):
        """Test save_settings avec erreur."""
        mock_get_config.side_effect = Exception("Config error")
        
        response = client.post(
            '/api/save_settings',
            json={'frontend_framework': 'react'}
        )
        
        assert response.status_code == 500


class TestStartProject:
    """Tests pour start_project."""
    
    @patch('app.routes.settings.get_config')
    def test_start_project_success(
        self,
        mock_get_config,
        client,
        mock_services
    ):
        """Test start_project avec succès."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = "/tmp/test/dev"
        mock_config.paths.backend_dev_path = "/tmp/test/backend_dev"
        mock_config.servers.dev_port = 5173
        mock_config.servers.backend_port = 3000
        mock_get_config.return_value = mock_config
        
        response = client.post('/api/start_project')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        mock_services['process'].stop_all.assert_called_once()
        mock_services['workspace'].setup_all.assert_called_once()
        mock_services['process'].start_dev_server.assert_called_once()
        mock_services['process'].start_backend_server.assert_called_once()
    
    @patch('app.routes.settings.get_config')
    def test_start_project_error(
        self,
        mock_get_config,
        client,
        mock_services
    ):
        """Test start_project avec erreur."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        mock_services['workspace'].setup_all.side_effect = Exception("Setup error")
        
        response = client.post('/api/start_project')
        
        assert response.status_code == 500
        data = response.get_json()
        assert data['status'] == 'error'


class TestWriteBackendEnvFile:
    """Tests pour _write_backend_env_file."""
    
    def test_write_backend_env_file_success(self, temp_dir):
        """Test _write_backend_env_file avec succès."""
        mock_config = MagicMock()
        mock_config.paths.backend_dev_path = temp_dir
        
        wordpress_env = {
            'WP_API_URL': 'https://example.com/wp-json',
            'WP_USERNAME': 'admin',
            'WP_PASSWORD': 'password'
        }
        
        _write_backend_env_file(mock_config, wordpress_env)
        
        env_file = temp_dir / '.env'
        assert env_file.exists()
        content = env_file.read_text()
        assert 'WP_API_URL' in content
        assert 'WP_USERNAME' in content
    
    @patch('app.routes.settings.logger')
    def test_write_backend_env_file_error(self, mock_logger, temp_dir):
        """Test _write_backend_env_file avec erreur."""
        mock_config = MagicMock()
        # Utiliser un chemin qui ne peut pas être écrit
        mock_config.paths.backend_dev_path = Path('/invalid/path/that/does/not/exist')
        
        wordpress_env = {'WP_API_URL': 'https://example.com'}
        
        with pytest.raises(Exception):
            _write_backend_env_file(mock_config, wordpress_env)

