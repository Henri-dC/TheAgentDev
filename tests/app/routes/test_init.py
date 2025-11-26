"""
Tests unitaires pour app/routes/__init__.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from app.routes import register_blueprints, inject_services


class TestRegisterBlueprints:
    """Tests pour register_blueprints."""
    
    @patch.object(Flask, 'register_blueprint')
    def test_register_blueprints_registers_all(self, mock_register_blueprint):
        """Test que tous les blueprints sont enregistrés."""
        app = Flask(__name__)
        
        # Appeler register_blueprints
        register_blueprints(app)
        
        # Vérifier que register_blueprint a été appelé 4 fois
        assert mock_register_blueprint.call_count == 4
        
        # Vérifier que les blueprints sont enregistrés
        registered_blueprints = [call[0][0] for call in mock_register_blueprint.call_args_list]
        assert len(registered_blueprints) == 4


class TestInjectServices:
    """Tests pour inject_services."""
    
    @patch('app.routes.init_api_services')
    @patch('app.routes.init_project_services')
    @patch('app.routes.init_settings_services')
    def test_inject_services_calls_all_init_functions(
        self,
        mock_init_settings,
        mock_init_project,
        mock_init_api
    ):
        """Test que inject_services appelle toutes les fonctions d'initialisation."""
        mock_process = MagicMock()
        mock_git = MagicMock()
        mock_npm = MagicMock()
        mock_workspace = MagicMock()
        mock_gemini = MagicMock()
        mock_claude = MagicMock()
        mock_chroma = MagicMock()
        
        inject_services(
            process_svc=mock_process,
            git_svc=mock_git,
            npm_svc=mock_npm,
            workspace_svc=mock_workspace,
            gemini_svc=mock_gemini,
            claude_svc=mock_claude,
            chroma_svc=mock_chroma
        )
        
        # Vérifier que init_api_services a été appelé
        mock_init_api.assert_called_once_with(
            process_svc=mock_process,
            git_svc=mock_git,
            npm_svc=mock_npm,
            workspace_svc=mock_workspace,
            gemini_svc=mock_gemini,
            claude_svc=mock_claude
        )
        
        # Vérifier que init_project_services a été appelé
        mock_init_project.assert_called_once_with(
            workspace_svc=mock_workspace,
            process_svc=mock_process,
            git_svc=mock_git
        )
        
        # Vérifier que init_settings_services a été appelé
        mock_init_settings.assert_called_once_with(
            process_service=mock_process,
            workspace_service=mock_workspace
        )
    
    @patch('app.routes.init_api_services')
    @patch('app.routes.init_project_services')
    @patch('app.routes.init_settings_services')
    def test_inject_services_with_none_values(
        self,
        mock_init_settings,
        mock_init_project,
        mock_init_api
    ):
        """Test que inject_services fonctionne avec des valeurs None."""
        inject_services()
        
        # Vérifier que les fonctions sont appelées même avec None
        mock_init_api.assert_called_once()
        mock_init_project.assert_called_once()
        mock_init_settings.assert_called_once()

