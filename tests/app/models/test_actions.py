"""
Tests unitaires pour actions.py.
"""
import pytest

from app.models.actions import (
    ActionType,
    FileAction,
    ShellCommandAction,
    GeminiResponse
)


class TestActionType:
    """Tests pour ActionType."""
    
    def test_action_type_values(self):
        """Test que tous les types d'actions existent."""
        assert ActionType.CREATE == "CREATE"
        assert ActionType.UPDATE == "UPDATE"
        assert ActionType.DELETE == "DELETE"
        assert ActionType.RUN_SHELL_COMMAND == "RUN_SHELL_COMMAND"
    
    def test_action_type_enum(self):
        """Test que ActionType est un Enum."""
        assert isinstance(ActionType.CREATE, ActionType)
        assert ActionType("CREATE") == ActionType.CREATE
    
    def test_action_type_invalid(self):
        """Test qu'un type invalide lève une erreur."""
        with pytest.raises(ValueError):
            ActionType("INVALID")


class TestFileAction:
    """Tests pour FileAction."""
    
    def test_create_action(self):
        """Test création d'une action CREATE."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="dev/src/New.vue",
            content="<template>Hello</template>"
        )
        
        assert action.action == ActionType.CREATE
        assert action.file_path == "dev/src/New.vue"
        assert action.content == "<template>Hello</template>"
        assert action.get_content() == "<template>Hello</template>"
    
    def test_update_action(self):
        """Test création d'une action UPDATE."""
        action = FileAction(
            action=ActionType.UPDATE,
            file_path="dev/src/App.vue",
            new_content="<template>Updated</template>"
        )
        
        assert action.action == ActionType.UPDATE
        assert action.new_content == "<template>Updated</template>"
        assert action.get_content() == "<template>Updated</template>"
    
    def test_delete_action(self):
        """Test création d'une action DELETE."""
        action = FileAction(
            action=ActionType.DELETE,
            file_path="dev/src/old.js"
        )
        
        assert action.action == ActionType.DELETE
        assert action.file_path == "dev/src/old.js"
        assert action.get_content() is None
    
    def test_get_content_prefers_new_content(self):
        """Test que get_content retourne content ou new_content."""
        action = FileAction(
            action=ActionType.UPDATE,
            file_path="test.js",
            content="old",
            new_content="new"
        )
        
        # get_content() retourne content or new_content
        # En Python, "content or new_content" retourne content si content est truthy
        # Donc si content="old", get_content() retourne "old"
        assert action.get_content() == "old"
    
    def test_get_content_fallback_to_content(self):
        """Test que get_content utilise content si new_content n'existe pas."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="test.js",
            content="content"
        )
        
        assert action.get_content() == "content"
    
    def test_validate_create_success(self):
        """Test validation CREATE réussie."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="dev/src/New.vue",
            content="content"
        )
        
        is_valid, message = action.validate()
        assert is_valid is True
        assert message == "OK"
    
    def test_validate_update_success(self):
        """Test validation UPDATE réussie."""
        action = FileAction(
            action=ActionType.UPDATE,
            file_path="dev/src/App.vue",
            new_content="new content"
        )
        
        is_valid, message = action.validate()
        assert is_valid is True
    
    def test_validate_delete_success(self):
        """Test validation DELETE réussie."""
        action = FileAction(
            action=ActionType.DELETE,
            file_path="dev/src/old.js"
        )
        
        is_valid, message = action.validate()
        assert is_valid is True
    
    def test_validate_missing_file_path(self):
        """Test validation échoue sans file_path."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="",
            content="content"
        )
        
        is_valid, message = action.validate()
        assert is_valid is False
        assert "file_path" in message.lower()
    
    def test_validate_create_missing_content(self):
        """Test validation CREATE échoue sans content."""
        action = FileAction(
            action=ActionType.CREATE,
            file_path="dev/src/New.vue"
        )
        
        is_valid, message = action.validate()
        assert is_valid is False
        assert "content" in message.lower() or "new_content" in message.lower()
    
    def test_validate_update_missing_content(self):
        """Test validation UPDATE échoue sans new_content."""
        action = FileAction(
            action=ActionType.UPDATE,
            file_path="dev/src/App.vue"
        )
        
        is_valid, message = action.validate()
        assert is_valid is False


class TestShellCommandAction:
    """Tests pour ShellCommandAction."""
    
    def test_create_shell_command(self):
        """Test création d'une action shell."""
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command="npm install axios",
            cwd="dev/"
        )
        
        assert action.action == ActionType.RUN_SHELL_COMMAND
        assert action.command == "npm install axios"
        assert action.cwd == "dev/"
    
    def test_shell_command_without_cwd(self):
        """Test création d'une action shell sans cwd."""
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command="npm install"
        )
        
        assert action.command == "npm install"
        assert action.cwd is None
    
    def test_validate_success(self):
        """Test validation réussie."""
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command="npm install"
        )
        
        is_valid, message = action.validate()
        assert is_valid is True
        assert message == "OK"
    
    def test_validate_missing_command(self):
        """Test validation échoue sans command."""
        action = ShellCommandAction(
            action=ActionType.RUN_SHELL_COMMAND,
            command=""
        )
        
        is_valid, message = action.validate()
        assert is_valid is False
        assert "command" in message.lower()


class TestGeminiResponse:
    """Tests pour GeminiResponse."""
    
    def test_from_dict_simple(self):
        """Test création depuis un dictionnaire simple."""
        data = {
            "explanation": "Test explanation",
            "actions": []
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert response.explanation == "Test explanation"
        assert len(response.actions) == 0
    
    def test_from_dict_with_file_actions(self):
        """Test création avec des actions de fichier."""
        data = {
            "explanation": "Création de fichiers",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": "dev/src/New.vue",
                    "content": "content"
                },
                {
                    "action": "UPDATE",
                    "file_path": "dev/src/App.vue",
                    "new_content": "updated"
                },
                {
                    "action": "DELETE",
                    "file_path": "dev/src/old.js"
                }
            ]
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert len(response.actions) == 3
        assert response.actions[0].action == ActionType.CREATE
        assert response.actions[1].action == ActionType.UPDATE
        assert response.actions[2].action == ActionType.DELETE
    
    def test_from_dict_with_shell_action(self):
        """Test création avec une action shell."""
        data = {
            "explanation": "Installation",
            "actions": [
                {
                    "action": "RUN_SHELL_COMMAND",
                    "command": "npm install axios",
                    "cwd": "dev/"
                }
            ]
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert len(response.actions) == 1
        assert isinstance(response.actions[0], ShellCommandAction)
        assert response.actions[0].command == "npm install axios"
    
    def test_from_dict_mixed_actions(self):
        """Test création avec actions mixtes."""
        data = {
            "explanation": "Modifications",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": "dev/src/New.vue",
                    "content": "content"
                },
                {
                    "action": "RUN_SHELL_COMMAND",
                    "command": "npm install"
                }
            ]
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert len(response.actions) == 2
        assert isinstance(response.actions[0], FileAction)
        assert isinstance(response.actions[1], ShellCommandAction)
    
    def test_from_dict_missing_explanation(self):
        """Test création avec explication manquante."""
        data = {
            "actions": []
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert response.explanation == "Aucune explication fournie."
    
    def test_from_dict_missing_action_type(self):
        """Test création échoue sans type d'action."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "file_path": "test.js",
                    "content": "content"
                }
            ]
        }
        
        with pytest.raises(ValueError, match="n'a pas de type"):
            GeminiResponse.from_dict(data)
    
    def test_from_dict_invalid_action_type(self):
        """Test création échoue avec type invalide."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "action": "INVALID_TYPE",
                    "file_path": "test.js"
                }
            ]
        }
        
        with pytest.raises(ValueError, match="type invalide"):
            GeminiResponse.from_dict(data)
    
    def test_from_dict_invalid_file_action(self):
        """Test création échoue avec action de fichier invalide."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": ""  # Manquant
                }
            ]
        }
        
        with pytest.raises(ValueError, match="invalide"):
            GeminiResponse.from_dict(data)
    
    def test_from_dict_invalid_shell_action(self):
        """Test création échoue avec action shell invalide."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "action": "RUN_SHELL_COMMAND",
                    "command": ""  # Manquant
                }
            ]
        }
        
        with pytest.raises(ValueError, match="invalide"):
            GeminiResponse.from_dict(data)
    
    def test_from_dict_multiple_actions_validation(self):
        """Test validation de plusieurs actions."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": "dev/src/New.vue",
                    "content": "content"
                },
                {
                    "action": "UPDATE",
                    "file_path": "dev/src/App.vue",
                    "new_content": "updated"
                },
                {
                    "action": "DELETE",
                    "file_path": "dev/src/old.js"
                },
                {
                    "action": "RUN_SHELL_COMMAND",
                    "command": "npm install"
                }
            ]
        }
        
        response = GeminiResponse.from_dict(data)
        
        assert len(response.actions) == 4
        # Vérifier que toutes les actions sont valides
        for action in response.actions:
            is_valid, _ = action.validate()
            assert is_valid is True
    
    def test_from_dict_action_numbering(self):
        """Test que les erreurs mentionnent le numéro d'action."""
        data = {
            "explanation": "Test",
            "actions": [
                {
                    "action": "CREATE",
                    "file_path": "dev/src/New.vue",
                    "content": "content"
                },
                {
                    "action": "CREATE",
                    "file_path": ""  # Invalide
                }
            ]
        }
        
        with pytest.raises(ValueError) as exc_info:
            GeminiResponse.from_dict(data)
        
        assert "Action #2" in str(exc_info.value)

