"""
Tests unitaires pour shell.py.
"""
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.utils.shell import CommandResult, CommandExecutor, get_executor, run_command
from app.utils.exceptions import GitError


class TestCommandResult:
    """Tests pour CommandResult."""
    
    def test_success_true(self):
        """Test success retourne True pour returncode 0."""
        result = CommandResult(
            command="test",
            returncode=0,
            stdout="output",
            stderr="",
            cwd="/tmp"
        )
        assert result.success is True
        assert result.failed is False
    
    def test_success_false(self):
        """Test success retourne False pour returncode != 0."""
        result = CommandResult(
            command="test",
            returncode=1,
            stdout="",
            stderr="error",
            cwd="/tmp"
        )
        assert result.success is False
        assert result.failed is True


class TestCommandExecutor:
    """Tests pour CommandExecutor."""
    
    def test_init_default_timeout(self):
        """Test initialisation avec timeout par défaut."""
        executor = CommandExecutor()
        assert executor.default_timeout == 300
    
    def test_init_custom_timeout(self):
        """Test initialisation avec timeout personnalisé."""
        executor = CommandExecutor(default_timeout=600)
        assert executor.default_timeout == 600
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_success(self, mock_run, temp_dir):
        """Test run avec succès."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        result = executor.run("echo test", cwd=temp_dir)
        
        assert result.success is True
        assert result.stdout == "Success"
        assert result.returncode == 0
        mock_run.assert_called_once()
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_failure(self, mock_run, temp_dir):
        """Test run avec échec."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        result = executor.run("false", cwd=temp_dir)
        
        assert result.success is False
        assert result.stderr == "Error"
        assert result.returncode == 1
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_with_check_success(self, mock_run, temp_dir):
        """Test run avec check=True et succès."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        result = executor.run("echo test", cwd=temp_dir, check=True)
        
        assert result.success is True
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_with_check_failure(self, mock_run, temp_dir):
        """Test run avec check=True et échec."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error"
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        
        with pytest.raises(GitError) as exc_info:
            executor.run("false", cwd=temp_dir, check=True)
        
        assert exc_info.value.returncode == 1
        assert "Error" in str(exc_info.value)
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_timeout(self, mock_run, temp_dir):
        """Test run avec timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("test", 10)
        
        executor = CommandExecutor()
        result = executor.run("sleep 100", cwd=temp_dir, timeout=10)
        
        assert result.success is False
        assert result.returncode == -1
        assert "Timeout" in result.stderr
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_exception(self, mock_run, temp_dir):
        """Test run avec exception."""
        mock_run.side_effect = Exception("Unexpected error")
        
        executor = CommandExecutor()
        result = executor.run("test", cwd=temp_dir)
        
        assert result.success is False
        assert result.returncode == -1
        assert "Unexpected error" in result.stderr
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_custom_timeout(self, mock_run, temp_dir):
        """Test run avec timeout personnalisé."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        executor = CommandExecutor(default_timeout=300)
        result = executor.run("test", cwd=temp_dir, timeout=60)
        
        assert result.success is True
        # Vérifier que le timeout personnalisé a été utilisé
        call_args = mock_run.call_args
        assert call_args[1]['timeout'] == 60
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_check(self, mock_run, temp_dir):
        """Test run_check."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        result = executor.run_check("echo test", cwd=temp_dir)
        
        assert result.success is True
        # Vérifier que check=True a été passé
        call_args = mock_run.call_args
        # run_check appelle run avec check=True
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_path_object(self, mock_run, temp_dir):
        """Test run avec Path object comme cwd."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        executor = CommandExecutor()
        result = executor.run("test", cwd=Path(temp_dir))
        
        assert result.success is True
        # Vérifier que le Path a été converti en string
        call_args = mock_run.call_args
        assert call_args[1]['cwd'] == str(temp_dir)
    
    @patch('app.utils.shell.subprocess.run')
    def test_run_git_error_reraises(self, mock_run, temp_dir):
        """Test que GitError est relancée."""
        git_error = GitError("Git error", stderr="error", returncode=1)
        mock_run.side_effect = git_error
        
        executor = CommandExecutor()
        
        with pytest.raises(GitError):
            executor.run("git test", cwd=temp_dir)


class TestShellFunctions:
    """Tests pour les fonctions globales."""
    
    def test_get_executor_singleton(self):
        """Test que get_executor retourne un singleton."""
        executor1 = get_executor()
        executor2 = get_executor()
        
        assert executor1 is executor2
        assert isinstance(executor1, CommandExecutor)
    
    @patch('app.utils.shell.get_executor')
    def test_run_command(self, mock_get_executor, temp_dir):
        """Test run_command."""
        mock_executor = MagicMock()
        mock_result = CommandResult(
            command="test",
            returncode=0,
            stdout="Success",
            stderr="",
            cwd=str(temp_dir)
        )
        mock_executor.run.return_value = mock_result
        mock_get_executor.return_value = mock_executor
        
        result = run_command("echo test", cwd=temp_dir)
        
        assert result.success is True
        mock_executor.run.assert_called_once_with("echo test", temp_dir, None, False)
    
    @patch('app.utils.shell.get_executor')
    def test_run_command_with_timeout(self, mock_get_executor, temp_dir):
        """Test run_command avec timeout."""
        mock_executor = MagicMock()
        mock_result = CommandResult(
            command="test",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        mock_executor.run.return_value = mock_result
        mock_get_executor.return_value = mock_executor
        
        result = run_command("test", cwd=temp_dir, timeout=60)
        
        mock_executor.run.assert_called_once_with("test", temp_dir, 60, False)
    
    @patch('app.utils.shell.get_executor')
    def test_run_command_with_check(self, mock_get_executor, temp_dir):
        """Test run_command avec check=True."""
        mock_executor = MagicMock()
        mock_result = CommandResult(
            command="test",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        mock_executor.run.return_value = mock_result
        mock_get_executor.return_value = mock_executor
        
        result = run_command("test", cwd=temp_dir, check=True)
        
        mock_executor.run.assert_called_once_with("test", temp_dir, None, True)

