"""
Tests unitaires pour app/routes/api.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from pathlib import Path

from app.routes.api import (
    init_services,
    clear_history,
    main_page,
    index_project,
    propose_changes,
    approve_changes,
    push_changes,
    rollback_changes,
    undo_change,
    confirm_change,
    setup_and_start,
    _execute_file_action,
    _execute_shell_action
)
from app.utils.shell import CommandResult
from app.models.actions import ActionType, FileAction, ShellCommandAction
from app.utils.exceptions import GitError


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
        'git': MagicMock(),
        'npm': MagicMock(),
        'workspace': MagicMock(),
        'gemini': MagicMock(),
        'claude': MagicMock()
    }


@pytest.fixture
def client(app, mock_services):
    """Créer un client de test Flask."""
    init_services(
        process_svc=mock_services['process'],
        git_svc=mock_services['git'],
        npm_svc=mock_services['npm'],
        workspace_svc=mock_services['workspace'],
        gemini_svc=mock_services['gemini'],
        claude_svc=mock_services['claude']
    )
    from app.routes.api import api_bp
    app.register_blueprint(api_bp)
    return app.test_client()


class TestInitServices:
    """Tests pour init_services."""
    
    def test_init_services_sets_global_variables(self, mock_services):
        """Test que init_services définit les variables globales."""
        init_services(
            process_svc=mock_services['process'],
            git_svc=mock_services['git'],
            npm_svc=mock_services['npm'],
            workspace_svc=mock_services['workspace'],
            gemini_svc=mock_services['gemini'],
            claude_svc=mock_services['claude']
        )
        
        from app.routes.api import (
            _process_service,
            _git_service,
            _npm_service,
            _workspace_service,
            _gemini_service,
            _claude_service
        )
        
        assert _process_service == mock_services['process']
        assert _git_service == mock_services['git']
        assert _npm_service == mock_services['npm']
        assert _workspace_service == mock_services['workspace']
        assert _gemini_service == mock_services['gemini']
        assert _claude_service == mock_services['claude']


class TestClearHistory:
    """Tests pour clear_history."""
    
    def test_clear_history_clears_prompt_history(self, client):
        """Test que clear_history vide l'historique."""
        from app.routes.api import _prompt_history
        
        # Ajouter des éléments à l'historique
        _prompt_history.append({"role": "user", "content": "test"})
        assert len(_prompt_history) > 0
        
        # Appeler la route
        response = client.post('/api/clear_history')
        
        # Vérifier que l'historique est vide
        assert len(_prompt_history) == 0
        assert response.status_code == 200
        assert b'Historique vid' in response.data


class TestMainPage:
    """Tests pour main_page."""
    
    @patch('app.routes.api.get_config')
    @patch('app.routes.api.render_template')
    def test_main_page_renders_template(self, mock_render, mock_get_config, client, mock_services):
        """Test que main_page rend le bon template."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.gemini.enabled = True
        mock_config.claude.enabled = True
        mock_get_config.return_value = mock_config
        
        mock_services['gemini'].is_available.return_value = True
        mock_services['claude'].is_available.return_value = True
        
        response = client.get('/main')
        
        assert response.status_code == 200
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args[0][0] == 'index.html'
        assert 'project_name' in call_args[1]
        assert 'ai_services' in call_args[1]


class TestIndexProject:
    """Tests pour index_project."""
    
    @patch('app.routes.api.get_chroma_service')
    @patch('app.routes.api.get_config')
    def test_index_project_success(self, mock_get_config, mock_get_chroma, client):
        """Test index_project avec succès."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.paths.backend_dev_path = Path("test/backend_dev")
        mock_get_config.return_value = mock_config
        
        mock_chroma = MagicMock()
        mock_chroma.index_workspaces.return_value = {
            'status': 'success',
            'count': 10
        }
        mock_get_chroma.return_value = mock_chroma
        
        response = client.post('/api/index_project')
        
        assert response.status_code == 200
        assert b'indexed' in response.data.lower()
        mock_chroma.index_workspaces.assert_called_once()
    
    @patch('app.routes.api.get_chroma_service')
    def test_index_project_no_chroma_service(self, mock_get_chroma, client):
        """Test index_project sans service ChromaDB."""
        mock_get_chroma.return_value = None
        
        response = client.post('/api/index_project')
        
        assert response.status_code == 500
        assert b'not initialized' in response.data.lower()
    
    @patch('app.routes.api.get_chroma_service')
    @patch('app.routes.api.get_config')
    def test_index_project_error(self, mock_get_config, mock_get_chroma, client):
        """Test index_project avec erreur."""
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        mock_chroma = MagicMock()
        mock_chroma.index_workspaces.return_value = {
            'status': 'error',
            'message': 'Test error'
        }
        mock_get_chroma.return_value = mock_chroma
        
        response = client.post('/api/index_project')
        
        assert response.status_code == 500


class TestProposeChanges:
    """Tests pour propose_changes."""
    
    @patch('app.routes.api.get_chroma_service')
    @patch('app.routes.api.get_config')
    @patch('app.routes.api._execute_file_action')
    @patch('app.routes.api._execute_shell_action')
    @patch('app.routes.api.time.sleep')
    def test_propose_changes_success(
        self,
        mock_sleep,
        mock_exec_shell,
        mock_exec_file,
        mock_get_config,
        mock_get_chroma,
        client,
        mock_services,
        temp_dir
    ):
        """Test propose_changes avec succès."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.paths.backend_dev_path = Path("test/backend_dev")
        mock_config.paths.base_dir = Path("test")
        mock_config.servers.dev_port = 5173
        mock_config.servers.backend_port = 3000
        mock_config.claude.enabled = True
        mock_config.gemini.enabled = False
        mock_get_config.return_value = mock_config
        
        mock_chroma = MagicMock()
        mock_chroma.query.return_value = []
        mock_get_chroma.return_value = mock_chroma
        
        mock_services['claude'].is_available.return_value = True
        mock_services['claude'].collect_project_files.return_value = ([], [])
        
        from app.models.actions import GeminiResponse
        mock_response = GeminiResponse(
            explanation="Test explanation",
            actions=[
                FileAction(
                    action=ActionType.CREATE,
                    file_path="dev/src/Test.vue",
                    content="<template>Test</template>"
                )
            ]
        )
        mock_services['claude'].generate_changes_with_context.return_value = mock_response
        
        mock_exec_file.return_value = {'workspace': 'dev', 'filename': 'Test.vue'}
        mock_services['git'].diff.return_value = CommandResult(
            command="git diff",
            returncode=0,
            stdout="diff output",
            stderr="",
            cwd=str(temp_dir)
        )
        
        response = client.post(
            '/api/propose_changes',
            json={'prompt': 'Create a test file'}
        )
        
        assert response.status_code == 200
        assert b'explanation' in response.data
    
    def test_propose_changes_missing_prompt(self, client):
        """Test propose_changes sans prompt."""
        response = client.post('/api/propose_changes', json={})
        
        assert response.status_code == 400
        assert b'prompt' in response.data.lower()
    
    @patch('app.routes.api.get_chroma_service')
    def test_propose_changes_no_chroma(self, mock_get_chroma, client):
        """Test propose_changes sans ChromaDB."""
        mock_get_chroma.return_value = None
        
        response = client.post(
            '/api/propose_changes',
            json={'prompt': 'test'}
        )
        
        assert response.status_code == 500


class TestApproveChanges:
    """Tests pour approve_changes."""
    
    @patch('app.routes.api.get_config')
    @patch('app.routes.api.shutil.copytree')
    @patch('app.routes.api.shutil.rmtree')
    def test_approve_changes_success(
        self,
        mock_rmtree,
        mock_copytree,
        mock_get_config,
        client,
        mock_services
    ):
        """Test approve_changes avec succès."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.paths.prod_path = Path("test/prod")
        mock_config.servers.dev_port = 5173
        mock_get_config.return_value = mock_config
        
        mock_services['process'].stop_dev_server.return_value = None
        mock_services['process'].start_dev_server.return_value = None
        
        # Simuler que prod existe
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.iterdir', return_value=[]):
                response = client.post('/api/approve_changes')
        
        assert response.status_code == 200
        assert b'approuv' in response.data.lower() or b'copi' in response.data.lower()
    
    @patch('app.routes.api.get_config')
    def test_approve_changes_no_prod_path(self, mock_get_config, client, mock_services):
        """Test approve_changes sans prod_path."""
        mock_config = MagicMock()
        mock_config.paths.prod_path = None
        mock_get_config.return_value = mock_config
        
        response = client.post('/api/approve_changes')
        
        assert response.status_code == 500


class TestPushChanges:
    """Tests pour push_changes."""
    
    @patch('app.routes.api.get_config')
    def test_push_changes_success(self, mock_get_config, client, mock_services):
        """Test push_changes avec succès."""
        mock_config = MagicMock()
        mock_config.paths.prod_path = Path("test/prod")
        mock_config.project.branch_name = "main"
        mock_get_config.return_value = mock_config
        
        from app.utils.shell import CommandResult
        
        mock_services['git'].is_git_repo.return_value = True
        mock_services['git'].get_current_branch.return_value = "main"
        mock_services['git'].add_all.return_value = CommandResult(
            command="git add .",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(mock_config.paths.prod_path)
        )
        mock_services['git'].commit.return_value = CommandResult(
            command="git commit",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(mock_config.paths.prod_path)
        )
        mock_services['git'].push.return_value = CommandResult(
            command="git push",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(mock_config.paths.prod_path)
        )
        
        response = client.post('/api/push_changes')
        
        assert response.status_code == 200
        assert b'push' in response.data.lower()
    
    @patch('app.routes.api.get_config')
    def test_push_changes_not_git_repo(self, mock_get_config, client, mock_services):
        """Test push_changes sans dépôt Git."""
        mock_config = MagicMock()
        mock_config.paths.prod_path = Path("test/prod")
        mock_get_config.return_value = mock_config
        
        mock_services['git'].is_git_repo.return_value = False
        
        response = client.post('/api/push_changes')
        
        assert response.status_code == 400


class TestRollbackUndoConfirm:
    """Tests pour rollback, undo et confirm."""
    
    def test_rollback_changes(self, client):
        """Test rollback_changes."""
        response = client.post('/api/rollback_changes')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data
        assert 'désactivé' in data['message'].lower() or 'desactiv' in data['message'].lower()
    
    def test_undo_change(self, client):
        """Test undo_change."""
        response = client.post('/api/undo_change')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data
        assert 'désactivé' in data['message'].lower() or 'desactiv' in data['message'].lower()
    
    def test_confirm_change(self, client):
        """Test confirm_change."""
        response = client.post('/api/confirm_change')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data
        assert 'désactivé' in data['message'].lower() or 'desactiv' in data['message'].lower()


class TestSetupAndStart:
    """Tests pour setup_and_start."""
    
    @patch('app.routes.api.get_config')
    @patch('app.services.chroma_service.init_chroma_service')
    def test_setup_and_start_success(
        self,
        mock_init_chroma,
        mock_get_config,
        client,
        mock_services
    ):
        """Test setup_and_start avec succès."""
        mock_config = MagicMock()
        mock_paths = MagicMock()
        # Utiliser un mock complet pour dev_path avec parent
        mock_dev_path = MagicMock()
        mock_parent = MagicMock()
        mock_parent.name = "test_project"
        mock_dev_path.parent = mock_parent
        mock_paths.dev_path = mock_dev_path
        mock_paths.backend_dev_path = Path("test/backend_dev")
        mock_config.paths = mock_paths
        mock_config.servers.dev_port = 5173
        mock_config.servers.backend_port = 3000
        mock_get_config.return_value = mock_config
        
        response = client.post('/api/setup_and_start')
        
        assert response.status_code == 200
        mock_services['workspace'].setup_all.assert_called_once()
        mock_services['process'].start_dev_server.assert_called_once()
        mock_services['process'].start_backend_server.assert_called_once()


class TestExecuteFileAction:
    """Tests pour _execute_file_action."""
    
    def test_execute_file_action_create(self, temp_dir):
        """Test _execute_file_action pour CREATE."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="dev/src/Test.vue",
            content="<template>Test</template>"
        )
        
        allowed_workspaces = {
            'dev': temp_dir / 'dev',
            'backend_dev': temp_dir / 'backend_dev'
        }
        (temp_dir / 'dev').mkdir(parents=True)
        
        result = _execute_file_action(action, allowed_workspaces, temp_dir)
        
        assert result['workspace'] == 'dev'
        assert result['filename'] == 'Test.vue'
        assert (temp_dir / 'dev' / 'src' / 'Test.vue').exists()
    
    def test_execute_file_action_delete(self, temp_dir):
        """Test _execute_file_action pour DELETE."""
        test_file = temp_dir / 'dev' / 'src' / 'Test.vue'
        test_file.parent.mkdir(parents=True)
        test_file.write_text("content")
        
        action = FileAction(
            action=ActionType.DELETE,
            file_path="dev/src/Test.vue"
        )
        
        allowed_workspaces = {
            'dev': temp_dir / 'dev',
            'backend_dev': temp_dir / 'backend_dev'
        }
        
        result = _execute_file_action(action, allowed_workspaces, temp_dir)
        
        assert not test_file.exists()
        assert result['workspace'] == 'dev'


class TestExecuteShellAction:
    """Tests pour _execute_shell_action."""
    
    @patch('app.utils.shell.run_command')
    @patch('app.routes.api.get_config')
    def test_execute_shell_action_success(self, mock_get_config, mock_run_command):
        """Test _execute_shell_action avec succès."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.paths.backend_dev_path = Path("test/backend_dev")
        mock_config.paths.base_dir = Path("test")
        mock_get_config.return_value = mock_config
        
        mock_result = MagicMock()
        mock_result.failed = False
        mock_run_command.return_value = mock_result
        
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command="npm install",
            cwd="dev/"
        )
        
        errors = []
        _execute_shell_action(action, mock_config, errors)
        
        assert len(errors) == 0
        mock_run_command.assert_called_once()
    
    @patch('app.utils.shell.run_command')
    @patch('app.routes.api.get_config')
    def test_execute_shell_action_failure(self, mock_get_config, mock_run_command):
        """Test _execute_shell_action avec échec."""
        mock_config = MagicMock()
        mock_config.paths.dev_path = Path("test/dev")
        mock_config.paths.backend_dev_path = Path("test/backend_dev")
        mock_config.paths.base_dir = Path("test")
        mock_get_config.return_value = mock_config
        
        mock_result = MagicMock()
        mock_result.failed = True
        mock_result.returncode = 1
        mock_result.stderr = "Error message"
        mock_run_command.return_value = mock_result
        
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command="npm install",
            cwd="dev/"
        )
        
        errors = []
        _execute_shell_action(action, mock_config, errors)
        
        assert len(errors) > 0

