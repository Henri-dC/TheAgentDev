"""
Tests unitaires pour app/__init__.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from app import create_app


class TestCreateApp:
    """Tests pour create_app."""
    
    @patch('app.setup_logging')
    @patch('app.get_config')
    @patch('app.ProcessService')
    @patch('app.GitService')
    @patch('app.NpmService')
    @patch('app.WorkspaceService')
    @patch('app.GeminiService')
    @patch('app.ClaudeService')
    @patch('app.register_blueprints')
    @patch('app.inject_services')
    def test_create_app_initializes_services(
        self,
        mock_inject_services,
        mock_register_blueprints,
        mock_claude_service_class,
        mock_gemini_service_class,
        mock_workspace_service_class,
        mock_npm_service_class,
        mock_git_service_class,
        mock_process_service_class,
        mock_get_config,
        mock_setup_logging
    ):
        """Test que create_app initialise tous les services."""
        # Mock de la configuration
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        
        # Mock des services
        mock_process_service = MagicMock()
        mock_git_service = MagicMock()
        mock_npm_service = MagicMock()
        mock_workspace_service = MagicMock()
        mock_gemini_service = MagicMock()
        mock_claude_service = MagicMock()
        
        mock_process_service_class.return_value = mock_process_service
        mock_git_service_class.return_value = mock_git_service
        mock_npm_service_class.return_value = mock_npm_service
        mock_workspace_service_class.return_value = mock_workspace_service
        mock_gemini_service_class.return_value = mock_gemini_service
        mock_claude_service_class.return_value = mock_claude_service
        
        # Créer l'application
        app = create_app()
        
        # Vérifier que setup_logging a été appelé
        mock_setup_logging.assert_called_once_with(log_level="DEBUG")
        
        # Vérifier que get_config a été appelé
        mock_get_config.assert_called_once()
        
        # Vérifier que tous les services ont été instanciés
        mock_process_service_class.assert_called_once()
        mock_git_service_class.assert_called_once()
        mock_npm_service_class.assert_called_once()
        mock_gemini_service_class.assert_called_once_with(mock_config)
        mock_claude_service_class.assert_called_once_with(mock_config)
        mock_workspace_service_class.assert_called_once_with(
            mock_npm_service,
            mock_git_service
        )
        
        # Vérifier que inject_services a été appelé avec les bons services
        mock_inject_services.assert_called_once_with(
            process_svc=mock_process_service,
            git_svc=mock_git_service,
            npm_svc=mock_npm_service,
            workspace_svc=mock_workspace_service,
            gemini_svc=mock_gemini_service,
            claude_svc=mock_claude_service
        )
        
        # Vérifier que register_blueprints a été appelé
        mock_register_blueprints.assert_called_once_with(app)
        
        # Vérifier que l'application est une instance Flask
        assert isinstance(app, Flask)
        assert app.secret_key == 'dev_secret_key'
    
    @patch('app.setup_logging')
    @patch('app.get_config')
    @patch('app.ProcessService')
    @patch('app.GitService')
    @patch('app.NpmService')
    @patch('app.WorkspaceService')
    @patch('app.GeminiService')
    @patch('app.ClaudeService')
    @patch('app.register_blueprints')
    @patch('app.inject_services')
    def test_create_app_configures_flask(
        self,
        mock_inject_services,
        mock_register_blueprints,
        mock_claude_service_class,
        mock_gemini_service_class,
        mock_workspace_service_class,
        mock_npm_service_class,
        mock_git_service_class,
        mock_process_service_class,
        mock_get_config,
        mock_setup_logging
    ):
        """Test que create_app configure Flask correctement."""
        mock_get_config.return_value = MagicMock()
        
        app = create_app()
        
        # Vérifier la configuration Flask
        assert app.secret_key == 'dev_secret_key'
        # Note: Les dossiers template_folder et static_folder sont relatifs
        # et peuvent ne pas exister dans l'environnement de test

