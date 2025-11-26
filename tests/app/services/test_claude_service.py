"""
Tests unitaires pour ClaudeService.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.services.claude_service import ClaudeService
from app.models.actions import GeminiResponse, ActionType


class TestClaudeService:
    """Tests pour ClaudeService."""
    
    def test_init_enabled(self, mock_config, mock_claude_config):
        """Test l'initialisation avec Claude activé."""
        mock_config.claude = mock_claude_config
        
        with patch('app.services.claude_service.anthropic.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            
            service = ClaudeService(mock_config)
            
            assert service.config == mock_config
            assert service.client is not None
    
    def test_init_disabled(self, mock_config):
        """Test l'initialisation avec Claude désactivé."""
        mock_config.claude.enabled = False
        
        service = ClaudeService(mock_config)
        
        assert service.client is None
    
    def test_init_no_api_key(self, mock_config):
        """Test l'initialisation sans clé API."""
        mock_config.claude.api_key = None
        mock_config.claude.enabled = True
        
        service = ClaudeService(mock_config)
        
        assert service.client is None
    
    def test_is_available_true(self, mock_config, mock_claude_config):
        """Test is_available retourne True."""
        mock_config.claude = mock_claude_config
        mock_config.claude.enabled = True
        
        with patch('app.services.claude_service.anthropic.Anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            
            service = ClaudeService(mock_config)
            assert service.is_available() is True
    
    def test_is_available_false(self, mock_config):
        """Test is_available retourne False."""
        mock_config.claude.enabled = False
        
        service = ClaudeService(mock_config)
        assert service.is_available() is False
    
    def test_generate_changes_with_context_success(self, mock_config, mock_claude_config):
        """Test generate_changes_with_context avec succès."""
        mock_config.claude = mock_claude_config
        
        # Mock de la réponse Claude
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps({
            "explanation": "Test explanation",
            "actions": [
                {
                    "action": "UPDATE",
                    "file_path": "dev/src/App.vue",
                    "new_content": "new content"
                }
            ]
        }))]
        
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message
        
        with patch('app.services.claude_service.anthropic.Anthropic', return_value=mock_client):
            service = ClaudeService(mock_config)
            result = service.generate_changes_with_context(
                prompt="Test prompt",
                rag_context="Context",
                file_tree="Tree",
                history=[]
            )
            
            assert isinstance(result, GeminiResponse)
            assert result.explanation == "Test explanation"
            assert len(result.actions) == 1
    
    def test_generate_changes_with_context_not_available(self, mock_config):
        """Test generate_changes_with_context quand Claude n'est pas disponible."""
        mock_config.claude.enabled = False
        
        service = ClaudeService(mock_config)
        
        with pytest.raises(Exception, match="n'est pas disponible"):
            service.generate_changes_with_context(
                prompt="Test",
                rag_context="Context",
                file_tree="Tree",
                history=[]
            )
    
    def test_extract_json_from_code_block(self, mock_config, mock_claude_config):
        """Test _extract_json avec bloc de code JSON."""
        mock_config.claude = mock_claude_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = f"```json\n{json.dumps(json_content)}\n```"
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._extract_json(response_text)
            
            assert result == json_content
    
    def test_extract_json_from_code_block_no_lang(self, mock_config, mock_claude_config):
        """Test _extract_json avec bloc de code sans langage."""
        mock_config.claude = mock_claude_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = f"```\n{json.dumps(json_content)}\n```"
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._extract_json(response_text)
            
            assert result == json_content
    
    def test_extract_json_direct(self, mock_config, mock_claude_config):
        """Test _extract_json avec JSON direct."""
        mock_config.claude = mock_claude_config
        
        json_content = {"explanation": "Test", "actions": []}
        response_text = json.dumps(json_content)
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._extract_json(response_text)
            
            assert result == json_content
    
    def test_extract_json_invalid(self, mock_config, mock_claude_config):
        """Test _extract_json avec JSON invalide."""
        mock_config.claude = mock_claude_config
        
        response_text = "This is not JSON"
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            
            with pytest.raises(ValueError, match="JSON invalide"):
                service._extract_json(response_text)
    
    def test_build_prompts(self, mock_config, mock_claude_config):
        """Test _build_prompts."""
        mock_config.claude = mock_claude_config
        mock_config.project.frontend_framework = "react"
        mock_config.project.wordpress_api_enabled = False
        # backend_url est une propriété calculée, on modifie backend_port à la place
        mock_config.servers.backend_port = 3000
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            system_prompt, user_prompt = service._build_prompts(
                user_prompt="Test",
                file_tree="Tree",
                context_str="Context",
                frontend_framework="react",
                wordpress_api_enabled=False
            )
            
            assert "react" in system_prompt.lower() or "React" in system_prompt
            assert "Test" in user_prompt
            assert "Tree" in user_prompt
            assert "Context" in user_prompt
    
    def test_get_framework_instructions_vue(self, mock_config, mock_claude_config):
        """Test _get_framework_instructions pour Vue."""
        mock_config.claude = mock_claude_config
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._get_framework_instructions("vue")
            
            assert "Vue" in result or "vue" in result
    
    def test_get_framework_instructions_react(self, mock_config, mock_claude_config):
        """Test _get_framework_instructions pour React."""
        mock_config.claude = mock_claude_config
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._get_framework_instructions("react")
            
            assert "React" in result or "react" in result
    
    def test_get_backend_instructions_wordpress(self, mock_config, mock_claude_config):
        """Test _get_backend_instructions avec WordPress."""
        mock_config.claude = mock_claude_config
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._get_backend_instructions(True)
            
            assert "WordPress" in result or "wordpress" in result.lower()
    
    def test_get_backend_instructions_no_wordpress(self, mock_config, mock_claude_config):
        """Test _get_backend_instructions sans WordPress."""
        mock_config.claude = mock_claude_config
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            result = service._get_backend_instructions(False)
            
            assert result == ""
    
    def test_parse_gitignore(self, mock_config, mock_claude_config, temp_dir):
        """Test _parse_gitignore."""
        mock_config.claude = mock_claude_config
        gitignore_path = temp_dir / ".gitignore"
        gitignore_path.write_text("node_modules/\n*.log\n# Comment")
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            patterns = service._parse_gitignore(gitignore_path)
            
            assert "node_modules/" in patterns
            assert "*.log" in patterns
            assert "# Comment" not in patterns  # Les commentaires sont ignorés
    
    def test_parse_gitignore_not_exists(self, mock_config, mock_claude_config, temp_dir):
        """Test _parse_gitignore avec fichier inexistant."""
        mock_config.claude = mock_claude_config
        gitignore_path = temp_dir / ".gitignore"
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            patterns = service._parse_gitignore(gitignore_path)
            
            assert patterns == []
    
    def test_is_binary(self, mock_config, mock_claude_config, temp_dir):
        """Test _is_binary."""
        mock_config.claude = mock_claude_config
        
        # Fichier texte
        text_file = temp_dir / "test.txt"
        text_file.write_text("Hello World")
        
        # Fichier binaire (avec null byte)
        binary_file = temp_dir / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02')
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            
            assert service._is_binary(text_file) is False
            assert service._is_binary(binary_file) is True
    
    @patch('app.services.claude_service.os.walk')
    @patch('app.services.claude_service.fnmatch.fnmatch')
    def test_collect_project_files(self, mock_fnmatch, mock_walk, mock_config, mock_claude_config, temp_dir):
        """Test collect_project_files."""
        mock_config.claude = mock_claude_config
        mock_config.paths.dev_path = temp_dir
        mock_config.paths.backend_dev_path = temp_dir
        
        # Mock os.walk
        mock_walk.return_value = [
            (str(temp_dir), [], ["test.py", "test.js"])
        ]
        
        # Mock fnmatch pour ne pas exclure
        mock_fnmatch.return_value = False
        
        # Créer les fichiers
        (temp_dir / "test.py").write_text("print('hello')")
        (temp_dir / "test.js").write_text("console.log('hello')")
        
        with patch('app.services.claude_service.anthropic.Anthropic'):
            service = ClaudeService(mock_config)
            project_files, file_paths = service.collect_project_files()
            
            assert len(project_files) > 0
            assert len(file_paths) > 0

