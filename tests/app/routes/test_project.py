"""
Tests unitaires pour app/routes/project.py.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from flask import Flask
from pathlib import Path

from app.routes.project import (
    init_services,
    get_existing_projects,
    project_selection,
    reset_project,
    select_project,
    create_project
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
        'workspace': MagicMock(),
        'process': MagicMock(),
        'git': MagicMock()
    }


@pytest.fixture
def client(app, mock_services):
    """Créer un client de test Flask."""
    init_services(
        workspace_svc=mock_services['workspace'],
        process_svc=mock_services['process'],
        git_svc=mock_services['git']
    )
    from app.routes.project import project_bp
    from app.routes.settings import settings_bp, init_services as init_settings_services
    # Initialiser les services pour settings
    init_settings_services(process_service=mock_services['process'], workspace_service=mock_services['workspace'])
    app.register_blueprint(project_bp)
    app.register_blueprint(settings_bp)
    return app.test_client()


class TestInitServices:
    """Tests pour init_services."""
    
    def test_init_services_sets_global_variables(self, mock_services):
        """Test que init_services définit les variables globales."""
        init_services(
            workspace_svc=mock_services['workspace'],
            process_svc=mock_services['process'],
            git_svc=mock_services['git']
        )
        
        from app.routes.project import (
            _workspace_service,
            _process_service,
            _git_service
        )
        
        assert _workspace_service == mock_services['workspace']
        assert _process_service == mock_services['process']
        assert _git_service == mock_services['git']


class TestGetExistingProjects:
    """Tests pour get_existing_projects."""
    
    @patch('app.routes.project.os.path.exists')
    @patch('app.routes.project.os.listdir')
    @patch('app.routes.project.os.path.isdir')
    def test_get_existing_projects_success(
        self,
        mock_isdir,
        mock_listdir,
        mock_exists
    ):
        """Test get_existing_projects avec succès."""
        mock_exists.return_value = True
        mock_listdir.return_value = ['project1', 'project2', 'IA', '.git', 'workspace']
        mock_isdir.side_effect = lambda x: x.endswith(('project1', 'project2', 'IA', '.git', 'workspace'))
        
        projects = get_existing_projects()
        
        # Vérifier que les projets exclus ne sont pas dans la liste
        assert 'IA' not in projects
        assert '.git' not in projects
        assert 'workspace' not in projects
        # Vérifier que les projets valides sont présents
        assert 'project1' in projects or 'project2' in projects
    
    @patch('app.routes.project.os.path.exists')
    def test_get_existing_projects_no_base_path(self, mock_exists):
        """Test get_existing_projects sans chemin de base."""
        mock_exists.return_value = False
        
        projects = get_existing_projects()
        
        assert projects == []


class TestProjectSelection:
    """Tests pour project_selection."""
    
    @patch('app.routes.project.get_existing_projects')
    @patch('app.routes.project.render_template')
    def test_project_selection_renders_template(
        self,
        mock_render,
        mock_get_projects,
        client
    ):
        """Test que project_selection rend le bon template."""
        mock_get_projects.return_value = ['project1', 'project2']
        
        response = client.get('/')
        
        assert response.status_code == 200
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args[0][0] == 'project_selection.html'
        assert 'projects' in call_args[1]


class TestResetProject:
    """Tests pour reset_project."""
    
    def test_reset_project_stops_servers(self, client, mock_services):
        """Test que reset_project arrête les serveurs."""
        response = client.get('/reset')
        
        assert response.status_code == 302  # Redirect
        mock_services['process'].stop_all.assert_called_once()


class TestSelectProject:
    """Tests pour select_project."""
    
    @patch('app.routes.project.reload_config')
    @patch('app.services.chroma_service.init_chroma_service')
    @patch('app.routes.project.open')
    @patch('app.routes.project.os.path.join')
    def test_select_project_success(
        self,
        mock_join,
        mock_open,
        mock_init_chroma,
        mock_reload,
        client,
        mock_services,
        temp_dir
    ):
        """Test select_project avec succès."""
        mock_join.return_value = str(temp_dir / 'test_project')
        
        # Créer un fichier de configuration mock
        config_data = {
            'dev_path': '',
            'prod_path': '',
            'backend_dev_path': ''
        }
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        mock_file.read.return_value = json.dumps(config_data)
        mock_file.seek.return_value = None
        mock_file.truncate.return_value = None
        mock_open.return_value = mock_file
        
        response = client.post(
            '/select-project',
            data={'project_name': 'test_project'}
        )
        
        assert response.status_code == 302  # Redirect
        mock_services['process'].stop_all.assert_called_once()
        mock_reload.assert_called_once()
    
    def test_select_project_missing_name(self, client):
        """Test select_project sans nom de projet."""
        response = client.post('/select-project', data={})
        
        assert response.status_code == 302  # Redirect avec flash message


class TestCreateProject:
    """Tests pour create_project."""
    
    @patch('app.routes.project.reload_config')
    @patch('app.services.chroma_service.init_chroma_service')
    @patch('app.routes.project.os.makedirs')
    @patch('app.routes.project.os.path.exists')
    @patch('app.routes.project.os.path.join')
    @patch('app.routes.project.open')
    def test_create_project_success(
        self,
        mock_open,
        mock_join,
        mock_exists,
        mock_makedirs,
        mock_init_chroma,
        mock_reload,
        client,
        mock_services,
        temp_dir
    ):
        """Test create_project avec succès."""
        mock_join.return_value = str(temp_dir / 'new_project')
        mock_exists.return_value = False
        
        # Créer un fichier de configuration mock
        config_data = {
            'dev_path': '',
            'prod_path': '',
            'backend_dev_path': ''
        }
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.__exit__.return_value = None
        mock_file.read.return_value = json.dumps(config_data)
        mock_file.seek.return_value = None
        mock_file.truncate.return_value = None
        mock_open.return_value = mock_file
        
        response = client.post(
            '/create-project',
            data={'new_project_name': 'new_project'}
        )
        
        assert response.status_code == 302  # Redirect
        mock_services['process'].stop_all.assert_called_once()
        assert mock_makedirs.call_count >= 3  # dev, prod, backend_dev
        assert mock_services['git'].init.call_count == 3
    
    @patch('app.routes.project.os.path.exists')
    @patch('app.routes.project.os.path.join')
    def test_create_project_already_exists(
        self,
        mock_join,
        mock_exists,
        client
    ):
        """Test create_project avec projet existant."""
        mock_join.return_value = '/tmp/existing_project'
        mock_exists.return_value = True
        
        response = client.post(
            '/create-project',
            data={'new_project_name': 'existing_project'}
        )
        
        assert response.status_code == 302  # Redirect avec flash message
    
    def test_create_project_empty_name(self, client):
        """Test create_project avec nom vide."""
        response = client.post(
            '/create-project',
            data={'new_project_name': ''}
        )
        
        assert response.status_code == 302  # Redirect avec flash message

