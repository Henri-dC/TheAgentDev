"""
Tests unitaires pour GeminiService.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.services.gemini_service import GeminiService
from app.models.actions import GeminiResponse, ActionType


class TestGeminiService:
    """Tests pour GeminiService."""
    
    def test_init_enabled(self, mock_config, mock_gemini_config):
        """Test l'initialisation avec Gemini activé."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        
        assert service.config == mock_config
    
    def test_init_disabled(self, mock_config):
        """Test l'initialisation avec Gemini désactivé."""
        mock_config.gemini.enabled = False
        
        service = GeminiService(mock_config)
        
        assert service.config == mock_config
    
    def test_is_available_true(self, mock_config, mock_gemini_config):
        """Test is_available retourne True."""
        mock_config.gemini = mock_gemini_config
        mock_config.gemini.enabled = True
        mock_config.gemini.client = MagicMock()
        
        service = GeminiService(mock_config)
        assert service.is_available() is True
    
    def test_is_available_false(self, mock_config):
        """Test is_available retourne False."""
        mock_config.gemini.enabled = False
        
        service = GeminiService(mock_config)
        assert service.is_available() is False
    
    def test_generate_changes_success(self, mock_config, mock_gemini_config):
        """Test generate_changes avec succès."""
        mock_config.gemini = mock_gemini_config
        
        # Mock de la réponse Gemini
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "explanation": "Test explanation",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": "dev/src/New.vue",
                    "content": "new content"
                }
            ]
        })
        
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        
        mock_client = MagicMock()
        mock_client.GenerativeModel.return_value = mock_model
        mock_config.gemini.client = mock_client
        
        service = GeminiService(mock_config)
        result = service.generate_changes(
            prompt="Test prompt",
            project_files={"dev/src/App.vue": "content"},
            file_tree="Tree"
        )
        
        assert isinstance(result, GeminiResponse)
        assert result.explanation == "Test explanation"
        assert len(result.actions) == 1
    
    def test_generate_changes_not_available(self, mock_config):
        """Test generate_changes quand Gemini n'est pas disponible."""
        mock_config.gemini.enabled = False
        
        service = GeminiService(mock_config)
        
        with pytest.raises(Exception, match="n'est pas disponible"):
            service.generate_changes(
                prompt="Test",
                project_files={},
                file_tree="Tree"
            )
    
    def test_generate_changes_with_context_success(self, mock_config, mock_gemini_config):
        """Test generate_changes_with_context avec succès."""
        mock_config.gemini = mock_gemini_config
        
        json_content = {
            "explanation": "Test explanation",
            "actions": [
                {
                    "action": "UPDATE",
                    "file_path": "dev/src/App.vue",
                    "new_content": "updated content"
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.text = json.dumps(json_content)
        
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        
        mock_client = MagicMock()
        mock_client.GenerativeModel.return_value = mock_model
        mock_config.gemini.client = mock_client
        
        service = GeminiService(mock_config)
        result = service.generate_changes_with_context(
            prompt="Test prompt",
            rag_context="Context",
            file_tree="Tree",
            history=[]
        )
        
        assert isinstance(result, GeminiResponse)
        assert len(result.actions) == 1
    
    def test_generate_changes_with_context_not_available(self, mock_config):
        """Test generate_changes_with_context quand Gemini n'est pas disponible."""
        mock_config.gemini.enabled = False
        
        service = GeminiService(mock_config)
        
        with pytest.raises(Exception, match="n'est pas disponible"):
            service.generate_changes_with_context(
                prompt="Test",
                rag_context="Context",
                file_tree="Tree",
                history=[]
            )
    
    def test_get_system_instructions(self, mock_config, mock_gemini_config):
        """Test _get_system_instructions."""
        mock_config.gemini = mock_gemini_config
        mock_config.project.frontend_framework = "react"
        mock_config.project.wordpress_api_enabled = False
        # backend_url est une propriété calculée, on modifie backend_port à la place
        mock_config.servers.backend_port = 3000
        
        service = GeminiService(mock_config)
        instructions = service._get_system_instructions()
        
        assert "react" in instructions.lower() or "React" in instructions
        assert "JSON" in instructions
    
    def test_build_user_prompt(self, mock_config, mock_gemini_config):
        """Test _build_user_prompt."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        prompt = service._build_user_prompt(
            user_prompt="Test request",
            file_tree="Project structure",
            context_str="File contents",
            history=[]
        )
        
        assert "Test request" in prompt
        assert "Project structure" in prompt
        assert "File contents" in prompt
    
    def test_build_user_prompt_with_history(self, mock_config, mock_gemini_config):
        """Test _build_user_prompt avec historique."""
        mock_config.gemini = mock_gemini_config
        
        history = [
            {"role": "user", "content": "Previous request"},
            {"role": "assistant", "content": "Previous response"}
        ]
        
        service = GeminiService(mock_config)
        prompt = service._build_user_prompt(
            user_prompt="New request",
            file_tree="Tree",
            context_str="Context",
            history=history
        )
        
        assert "Previous request" in prompt
        assert "Previous response" in prompt
        assert "New request" in prompt
    
    def test_build_context(self, mock_config, mock_gemini_config):
        """Test _build_context."""
        mock_config.gemini = mock_gemini_config
        
        project_files = {
            "dev/src/App.vue": "Vue content",
            "dev/src/main.js": "JS content"
        }
        
        service = GeminiService(mock_config)
        context = service._build_context(project_files)
        
        assert "App.vue" in context
        assert "main.js" in context
        assert "Vue content" in context
        assert "JS content" in context
    
    def test_extract_json_from_code_block(self, mock_config, mock_gemini_config):
        """Test _extract_json avec bloc de code JSON."""
        mock_config.gemini = mock_gemini_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = f"```json\n{json.dumps(json_content)}\n```"
        
        service = GeminiService(mock_config)
        result = service._extract_json(response_text)
        
        assert result == json_content
    
    def test_extract_json_from_code_block_no_lang(self, mock_config, mock_gemini_config):
        """Test _extract_json avec bloc de code sans langage."""
        mock_config.gemini = mock_gemini_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = f"```\n{json.dumps(json_content)}\n```"
        
        service = GeminiService(mock_config)
        result = service._extract_json(response_text)
        
        assert result == json_content
    
    def test_extract_json_direct(self, mock_config, mock_gemini_config):
        """Test _extract_json avec JSON direct."""
        mock_config.gemini = mock_gemini_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = json.dumps(json_content)
        
        service = GeminiService(mock_config)
        result = service._extract_json(response_text)
        
        assert result == json_content
    
    def test_extract_json_invalid(self, mock_config, mock_gemini_config):
        """Test _extract_json avec JSON invalide."""
        mock_config.gemini = mock_gemini_config
        
        response_text = "This is not JSON"
        
        service = GeminiService(mock_config)
        
        with pytest.raises(ValueError, match="JSON invalide"):
            service._extract_json(response_text)
    
    def test_get_framework_instructions_vue(self, mock_config, mock_gemini_config):
        """Test _get_framework_instructions pour Vue."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        result = service._get_framework_instructions("vue")
        
        assert "Vue" in result or "vue" in result
    
    def test_get_framework_instructions_react(self, mock_config, mock_gemini_config):
        """Test _get_framework_instructions pour React."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        result = service._get_framework_instructions("react")
        
        assert "React" in result or "react" in result
    
    def test_get_backend_instructions_wordpress(self, mock_config, mock_gemini_config):
        """Test _get_backend_instructions avec WordPress."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        result = service._get_backend_instructions(True)
        
        assert "WordPress" in result or "wordpress" in result.lower()
    
    def test_get_backend_instructions_no_wordpress(self, mock_config, mock_gemini_config):
        """Test _get_backend_instructions sans WordPress."""
        mock_config.gemini = mock_gemini_config
        
        service = GeminiService(mock_config)
        result = service._get_backend_instructions(False)
        
        assert result == ""
    
    def test_parse_gitignore(self, mock_config, mock_gemini_config, temp_dir):
        """Test _parse_gitignore."""
        mock_config.gemini = mock_gemini_config
        gitignore_path = temp_dir / ".gitignore"
        gitignore_path.write_text("node_modules/\n*.log\n# Comment")
        
        service = GeminiService(mock_config)
        patterns = service._parse_gitignore(gitignore_path)
        
        assert "node_modules/" in patterns
        assert "*.log" in patterns
        assert "# Comment" not in patterns
    
    def test_is_binary(self, mock_config, mock_gemini_config, temp_dir):
        """Test _is_binary."""
        mock_config.gemini = mock_gemini_config
        
        # Fichier texte
        text_file = temp_dir / "test.txt"
        text_file.write_text("Hello World")
        
        # Fichier binaire
        binary_file = temp_dir / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02')
        
        service = GeminiService(mock_config)
        
        assert service._is_binary(text_file) is False
        assert service._is_binary(binary_file) is True
    
    @patch('app.services.gemini_service.os.walk')
    @patch('app.services.gemini_service.fnmatch.fnmatch')
    def test_collect_project_files(self, mock_fnmatch, mock_walk, mock_config, mock_gemini_config, temp_dir):
        """Test collect_project_files."""
        mock_config.gemini = mock_gemini_config
        mock_config.paths.dev_path = temp_dir
        mock_config.paths.backend_dev_path = temp_dir
        
        mock_walk.return_value = [
            (str(temp_dir), [], ["test.py", "test.js"])
        ]
        
        mock_fnmatch.return_value = False
        
        (temp_dir / "test.py").write_text("print('hello')")
        (temp_dir / "test.js").write_text("console.log('hello')")
        
        service = GeminiService(mock_config)
        project_files, file_paths = service.collect_project_files()
        
        assert len(project_files) > 0
        assert len(file_paths) > 0

