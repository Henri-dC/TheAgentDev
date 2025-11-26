"""
Tests unitaires pour WorkspaceService.
"""
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.services.workspace_service import WorkspaceService
from app.services.npm_service import NpmService
from app.services.git_service import GitService
from app.utils.shell import CommandResult


class TestWorkspaceService:
    """Tests pour WorkspaceService."""
    
    def test_init(self):
        """Test l'initialisation du service."""
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        assert service.npm == npm_service
        assert service.git == git_service
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.WorkspaceService._setup_dev_workspace')
    @patch('app.services.workspace_service.WorkspaceService._setup_backend_workspace')
    @patch('app.services.workspace_service.WorkspaceService._setup_prod_workspace')
    @patch('app.services.workspace_service.WorkspaceService._setup_git_repositories')
    def test_setup_all(self, mock_git, mock_prod, mock_backend, mock_dev, mock_get_config, mock_config):
        """Test setup_all."""
        mock_get_config.return_value = mock_config
        mock_config.paths.prod_path = Path("/tmp/prod")
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service.setup_all()
        
        mock_dev.assert_called_once()
        mock_backend.assert_called_once()
        mock_prod.assert_called_once()
        mock_git.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.mkdir')
    @patch('app.services.workspace_service.WorkspaceService._create_new_frontend_project')
    def test_setup_dev_workspace_empty(self, mock_create, mock_mkdir, mock_get_config, mock_config, temp_dir):
        """Test _setup_dev_workspace avec répertoire vide."""
        mock_get_config.return_value = mock_config
        mock_config.paths.dev_path = temp_dir
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_dev_workspace()
        
        mock_create.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.mkdir')
    @patch('app.services.workspace_service.NpmService.has_package_json')
    @patch('app.services.workspace_service.NpmService.has_node_modules')
    @patch('app.services.workspace_service.NpmService.install')
    def test_setup_dev_workspace_existing(self, mock_install, mock_has_modules, mock_has_json, mock_mkdir, mock_get_config, mock_config, temp_dir):
        """Test _setup_dev_workspace avec projet existant."""
        mock_get_config.return_value = mock_config
        mock_config.paths.dev_path = temp_dir
        
        # Créer un fichier pour simuler un projet existant
        (temp_dir / "existing_file.txt").write_text("content")
        
        mock_has_json.return_value = True
        mock_has_modules.return_value = False
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_dev_workspace()
        
        mock_install.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    def test_create_new_frontend_project_no_framework(self, mock_get_config, mock_config):
        """Test _create_new_frontend_project sans framework."""
        mock_get_config.return_value = mock_config
        mock_config.project.frontend_framework = None
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._create_new_frontend_project()
        # Ne devrait pas lever d'exception, juste logger un warning
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.NpmService.create_vue_project')
    @patch('app.services.workspace_service.WorkspaceService._create_vite_config')
    @patch('app.services.workspace_service.NpmService.install')
    @patch('app.services.workspace_service.NpmService.install_tailwind_vue')
    @patch('app.services.workspace_service.shutil.move')
    def test_create_vue_project(self, mock_move, mock_tailwind, mock_install, mock_vite, mock_create, mock_get_config, mock_config, temp_dir):
        """Test _create_vue_project."""
        mock_get_config.return_value = mock_config
        mock_config.paths.dev_path = temp_dir
        
        mock_create.return_value = CommandResult("npm create vue", 0, "", "", str(temp_dir))
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        mock_tailwind.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        # Créer un répertoire temporaire pour simuler le projet créé
        temp_project = temp_dir / "vue-project-temp"
        temp_project.mkdir()
        (temp_project / "file.txt").write_text("content")
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        # Le code gère maintenant rmdir qui échoue en utilisant rmtree
        service._create_vue_project()
        
        mock_create.assert_called_once()
        mock_vite.assert_called_once()
        # Vérifier que les fichiers ont été déplacés
        assert mock_move.called
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.NpmService.create_react_project')
    @patch('app.services.workspace_service.WorkspaceService._clean_package_json')
    @patch('app.services.workspace_service.WorkspaceService._create_vite_config')
    @patch('app.services.workspace_service.NpmService.install')
    @patch('app.services.workspace_service.NpmService.install_tailwind_react')
    def test_create_react_project(self, mock_tailwind, mock_install, mock_vite, mock_clean, mock_create, mock_get_config, mock_config, temp_dir):
        """Test _create_react_project."""
        mock_get_config.return_value = mock_config
        mock_config.paths.dev_path = temp_dir
        
        mock_create.return_value = CommandResult("npm create vite", 0, "", "", str(temp_dir))
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        mock_tailwind.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._create_react_project()
        
        mock_create.assert_called_once()
        mock_clean.assert_called_once()
        mock_vite.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    def test_create_vite_config(self, mock_get_config, mock_config, temp_dir):
        """Test _create_vite_config."""
        mock_get_config.return_value = mock_config
        mock_config.paths.dev_path = temp_dir
        mock_config.project.frontend_framework = "react"
        mock_config.servers.backend_port = 3000
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._create_vite_config()
        
        # Vérifier que le fichier a été créé
        vite_config_path = temp_dir / 'vite.config.js'
        assert vite_config_path.exists()
        # Vérifier que le contenu contient le proxy et react
        content = vite_config_path.read_text()
        assert "3000" in content
        assert "react" in content.lower() or "React" in content
    
    @patch('app.services.workspace_service.get_config')
    def test_clean_package_json(self, mock_get_config, mock_config, temp_dir):
        """Test _clean_package_json."""
        mock_get_config.return_value = mock_config
        
        # Créer un package.json de test
        package_json_path = temp_dir / 'package.json'
        package_data = {
            "devDependencies": {
                "postcss": "^8.0.0",
                "autoprefixer": "^10.0.0",
                "tailwindcss": "^3.0.0"
            },
            "postcss": {}
        }
        package_json_path.write_text(json.dumps(package_data, indent=2))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._clean_package_json(temp_dir)
        
        # Vérifier que le fichier a été modifié
        updated_data = json.loads(package_json_path.read_text())
        # Vérifier que postcss et autoprefixer ont été supprimés
        assert "postcss" not in updated_data.get("devDependencies", {})
        assert "autoprefixer" not in updated_data.get("devDependencies", {})
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.mkdir')
    @patch('app.services.workspace_service.WorkspaceService._setup_wordpress_backend')
    @patch('app.services.workspace_service.WorkspaceService._setup_nodejs_backend')
    @patch('app.services.workspace_service.NpmService.has_package_json')
    @patch('app.services.workspace_service.NpmService.has_node_modules')
    @patch('app.services.workspace_service.NpmService.install')
    def test_setup_backend_workspace(self, mock_install, mock_has_modules, mock_has_json, mock_nodejs, mock_wordpress, mock_mkdir, mock_get_config, mock_config, temp_dir):
        """Test _setup_backend_workspace."""
        mock_get_config.return_value = mock_config
        mock_config.paths.backend_dev_path = temp_dir
        mock_config.project.wordpress_api_enabled = False
        
        mock_has_json.return_value = True
        mock_has_modules.return_value = False
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_backend_workspace()
        
        mock_nodejs.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.exists')
    @patch('app.services.workspace_service.shutil.copytree')
    @patch('app.services.workspace_service.GitService.is_git_repo')
    @patch('app.services.workspace_service.GitService.init')
    @patch('app.services.workspace_service.GitService.add_all')
    @patch('app.services.workspace_service.GitService.commit')
    @patch('app.services.workspace_service.WorkspaceService._write_wordpress_env_file')
    @patch('app.services.workspace_service.NpmService.install')
    def test_setup_wordpress_backend(self, mock_install, mock_env, mock_commit, mock_add, mock_init, mock_is_repo, mock_copytree, mock_exists, mock_get_config, mock_config, temp_dir):
        """Test _setup_wordpress_backend."""
        mock_get_config.return_value = mock_config
        mock_config.paths.backend_dev_path = temp_dir
        mock_config.paths.wordpress_backend_source = temp_dir / "source"
        
        mock_exists.return_value = True
        mock_is_repo.return_value = False
        mock_init.return_value = CommandResult("git init", 0, "", "", str(temp_dir))
        mock_add.return_value = CommandResult("git add", 0, "", "", str(temp_dir))
        mock_commit.return_value = CommandResult("git commit", 0, "", "", str(temp_dir))
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_wordpress_backend()
        
        mock_copytree.assert_called_once()
        mock_init.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.exists')
    @patch('app.services.workspace_service.json.dump')
    @patch('app.services.workspace_service.WorkspaceService._create_basic_server_js')
    @patch('app.services.workspace_service.NpmService.install')
    def test_setup_nodejs_backend(self, mock_install, mock_server, mock_dump, mock_exists, mock_get_config, mock_config, temp_dir):
        """Test _setup_nodejs_backend."""
        mock_get_config.return_value = mock_config
        mock_config.paths.backend_dev_path = temp_dir
        
        mock_exists.return_value = False  # package.json n'existe pas
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_nodejs_backend()
        
        mock_dump.assert_called_once()
        mock_server.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    def test_write_wordpress_env_file(self, mock_get_config, mock_config, temp_dir):
        """Test _write_wordpress_env_file."""
        mock_get_config.return_value = mock_config
        mock_config.paths.backend_dev_path = temp_dir
        mock_config.project.wordpress_env = {
            "WP_API_URL": "https://example.com",
            "WP_USERNAME": "admin"
        }
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._write_wordpress_env_file()
        
        # Vérifier que le fichier .env a été créé
        env_path = temp_dir / '.env'
        assert env_path.exists()
        # Vérifier que le contenu contient les variables
        content = env_path.read_text()
        assert "WP_API_URL" in content
        assert "WP_USERNAME" in content
    
    @patch('app.services.workspace_service.get_config')
    def test_create_basic_server_js(self, mock_get_config, mock_config, temp_dir):
        """Test _create_basic_server_js."""
        mock_get_config.return_value = mock_config
        mock_config.paths.backend_dev_path = temp_dir
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._create_basic_server_js()
        
        # Vérifier que le fichier server.js a été créé
        server_js_path = temp_dir / 'server.js'
        assert server_js_path.exists()
        # Vérifier que le contenu contient express
        content = server_js_path.read_text()
        assert "express" in content.lower()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.Path.mkdir')
    @patch('app.services.workspace_service.NpmService.has_package_json')
    @patch('app.services.workspace_service.NpmService.has_node_modules')
    @patch('app.services.workspace_service.NpmService.install')
    def test_setup_prod_workspace(self, mock_install, mock_has_modules, mock_has_json, mock_mkdir, mock_get_config, mock_config, temp_dir):
        """Test _setup_prod_workspace."""
        mock_get_config.return_value = mock_config
        mock_config.paths.prod_path = temp_dir
        
        mock_has_json.return_value = True
        mock_has_modules.return_value = False
        mock_install.return_value = CommandResult("npm install", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_prod_workspace()
        
        mock_install.assert_called_once()
    
    @patch('app.services.workspace_service.get_config')
    @patch('app.services.workspace_service.GitService.is_git_repo')
    @patch('app.services.workspace_service.GitService.init')
    @patch('app.services.workspace_service.GitService.add_all')
    @patch('app.services.workspace_service.GitService.commit')
    @patch('app.services.workspace_service.GitService.add_remote')
    @patch('app.services.workspace_service.GitService.fetch')
    def test_setup_git_for_workspace_new(self, mock_fetch, mock_add_remote, mock_commit, mock_add, mock_init, mock_is_repo, mock_get_config, mock_config, temp_dir):
        """Test _setup_git_for_workspace pour un nouveau repo."""
        mock_get_config.return_value = mock_config
        mock_is_repo.return_value = False
        
        mock_init.return_value = CommandResult("git init", 0, "", "", str(temp_dir))
        mock_add.return_value = CommandResult("git add", 0, "", "", str(temp_dir))
        mock_commit.return_value = CommandResult("git commit", 0, "", "", str(temp_dir))
        mock_add_remote.return_value = CommandResult("git remote add", 0, "", "", str(temp_dir))
        mock_fetch.return_value = CommandResult("git fetch", 0, "", "", str(temp_dir))
        
        npm_service = NpmService()
        git_service = GitService()
        service = WorkspaceService(npm_service, git_service)
        
        service._setup_git_for_workspace("dev", temp_dir, "https://github.com/test/repo.git")
        
        mock_init.assert_called_once()
        mock_add_remote.assert_called_once()

