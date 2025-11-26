"""
Tests unitaires pour GitService.
"""
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.services.git_service import GitService
from app.utils.shell import CommandResult


class TestGitService:
    """Tests pour GitService."""
    
    def test_init(self):
        """Test l'initialisation du service."""
        service = GitService()
        assert service is not None
    
    def test_is_git_repo_true(self, temp_dir):
        """Test is_git_repo retourne True."""
        (temp_dir / ".git").mkdir()
        service = GitService()
        
        assert service.is_git_repo(temp_dir) is True
    
    def test_is_git_repo_false(self, temp_dir):
        """Test is_git_repo retourne False."""
        service = GitService()
        
        assert service.is_git_repo(temp_dir) is False
    
    @patch('app.services.git_service.run_command')
    def test_init_success(self, mock_run_command, temp_dir):
        """Test init avec succès."""
        mock_run_command.return_value = CommandResult(
            command="git init",
            returncode=0,
            stdout="Initialized",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.init(temp_dir)
        
        assert result.success is True
        assert mock_run_command.call_count == 2  # init + branch -M
    
    @patch('app.services.git_service.run_command')
    def test_init_failure(self, mock_run_command, temp_dir):
        """Test init avec échec."""
        mock_run_command.return_value = CommandResult(
            command="git init",
            returncode=1,
            stdout="",
            stderr="Error",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.init(temp_dir)
        
        assert result.success is False
    
    @patch('app.services.git_service.run_command')
    def test_add_all(self, mock_run_command, temp_dir):
        """Test add_all."""
        mock_run_command.return_value = CommandResult(
            command="git add .",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.add_all(temp_dir)
        
        assert result.success is True
        mock_run_command.assert_called_once_with('git add .', cwd=temp_dir)
    
    @patch('app.services.git_service.run_command')
    def test_commit(self, mock_run_command, temp_dir):
        """Test commit."""
        mock_run_command.return_value = CommandResult(
            command="git commit",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.commit(temp_dir, "Test commit")
        
        assert result.success is True
        mock_run_command.assert_called_once()
        assert 'git commit' in mock_run_command.call_args[0][0]
        assert 'Test commit' in mock_run_command.call_args[0][0]
    
    @patch('app.services.git_service.run_command')
    def test_commit_allow_empty(self, mock_run_command, temp_dir):
        """Test commit avec allow_empty."""
        mock_run_command.return_value = CommandResult(
            command="git commit",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.commit(temp_dir, "Empty commit", allow_empty=True)
        
        assert result.success is True
        assert '--allow-empty' in mock_run_command.call_args[0][0]
    
    @patch('app.services.git_service.run_command')
    def test_status(self, mock_run_command, temp_dir):
        """Test status."""
        mock_run_command.return_value = CommandResult(
            command="git status",
            returncode=0,
            stdout="On branch main",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.status(temp_dir)
        
        assert result.success is True
        assert "On branch main" in result.stdout
    
    @patch('app.services.git_service.run_command')
    def test_status_short(self, mock_run_command, temp_dir):
        """Test status avec format court."""
        mock_run_command.return_value = CommandResult(
            command="git status -s",
            returncode=0,
            stdout="M file.py",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.status(temp_dir, short=True)
        
        assert result.success is True
        assert "-s" in mock_run_command.call_args[0][0]
    
    @patch('app.services.git_service.run_command')
    def test_diff(self, mock_run_command, temp_dir):
        """Test diff."""
        mock_run_command.return_value = CommandResult(
            command="git diff",
            returncode=0,
            stdout="diff content",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.diff(temp_dir)
        
        assert result.success is True
        assert "diff content" in result.stdout
    
    @patch('app.services.git_service.run_command')
    def test_diff_name_only(self, mock_run_command, temp_dir):
        """Test diff avec name_only."""
        mock_run_command.return_value = CommandResult(
            command="git diff --name-only",
            returncode=0,
            stdout="file1.py\nfile2.py",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.diff(temp_dir, name_only=True)
        
        assert result.success is True
        assert "--name-only" in mock_run_command.call_args[0][0]
    
    @patch('app.services.git_service.run_command')
    def test_get_changed_files(self, mock_run_command, temp_dir):
        """Test get_changed_files."""
        # Mock pour diff (modifiés)
        mock_run_command.side_effect = [
            CommandResult("git diff", 0, "file1.py\nfile2.py", "", str(temp_dir)),
            CommandResult("git diff", 0, "file3.py", "", str(temp_dir)),
            CommandResult("git ls-files", 0, "file4.py", "", str(temp_dir))
        ]
        
        service = GitService()
        files = service.get_changed_files(temp_dir)
        
        assert len(files) > 0
        assert "file1.py" in files or "file2.py" in files or "file3.py" in files or "file4.py" in files
    
    @patch('app.services.git_service.run_command')
    def test_is_empty_repo_true(self, mock_run_command, temp_dir):
        """Test is_empty_repo retourne True."""
        mock_run_command.return_value = CommandResult(
            command="git rev-parse HEAD",
            returncode=1,
            stdout="",
            stderr="fatal: ambiguous argument",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        assert service.is_empty_repo(temp_dir) is True
    
    @patch('app.services.git_service.run_command')
    def test_is_empty_repo_false(self, mock_run_command, temp_dir):
        """Test is_empty_repo retourne False."""
        mock_run_command.return_value = CommandResult(
            command="git rev-parse HEAD",
            returncode=0,
            stdout="abc123",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        assert service.is_empty_repo(temp_dir) is False
    
    @patch('app.services.git_service.run_command')
    def test_checkout(self, mock_run_command, temp_dir):
        """Test checkout."""
        mock_run_command.side_effect = [
            CommandResult("git rev-parse HEAD", 0, "abc123", "", str(temp_dir)),
            CommandResult("git checkout", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        result = service.checkout(temp_dir, "main")
        
        assert result.success is True
    
    @patch('app.services.git_service.run_command')
    def test_checkout_empty_repo(self, mock_run_command, temp_dir):
        """Test checkout sur un repo vide."""
        mock_run_command.side_effect = [
            CommandResult("git rev-parse HEAD", 1, "", "fatal", str(temp_dir)),
            CommandResult("git checkout -b", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        result = service.checkout(temp_dir, "main")
        
        assert result.success is True
        assert "-b" in mock_run_command.call_args_list[-1][0][0]
    
    @patch('app.services.git_service.run_command')
    def test_get_current_branch(self, mock_run_command, temp_dir):
        """Test get_current_branch."""
        mock_run_command.return_value = CommandResult(
            command="git rev-parse",
            returncode=0,
            stdout="main",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        branch = service.get_current_branch(temp_dir)
        
        assert branch == "main"
    
    @patch('app.services.git_service.run_command')
    def test_get_current_branch_none(self, mock_run_command, temp_dir):
        """Test get_current_branch retourne None."""
        mock_run_command.side_effect = [
            CommandResult("git rev-parse", 1, "", "", str(temp_dir)),
            CommandResult("git symbolic-ref", 1, "", "", str(temp_dir))
        ]
        
        service = GitService()
        branch = service.get_current_branch(temp_dir)
        
        assert branch is None
    
    @patch('app.services.git_service.run_command')
    def test_branch_exists_true(self, mock_run_command, temp_dir):
        """Test branch_exists retourne True."""
        mock_run_command.return_value = CommandResult(
            command="git branch",
            returncode=0,
            stdout="main",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        assert service.branch_exists(temp_dir, "main") is True
    
    @patch('app.services.git_service.run_command')
    def test_branch_exists_false(self, mock_run_command, temp_dir):
        """Test branch_exists retourne False."""
        mock_run_command.return_value = CommandResult(
            command="git branch",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        assert service.branch_exists(temp_dir, "nonexistent") is False
    
    @patch('app.services.git_service.run_command')
    def test_create_branch(self, mock_run_command, temp_dir):
        """Test create_branch."""
        mock_run_command.side_effect = [
            CommandResult("git rev-parse HEAD", 0, "abc123", "", str(temp_dir)),
            CommandResult("git branch", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        result = service.create_branch(temp_dir, "feature")
        
        assert result.success is True
    
    @patch('app.services.git_service.run_command')
    def test_stash(self, mock_run_command, temp_dir):
        """Test stash."""
        mock_run_command.side_effect = [
            CommandResult("git rev-parse HEAD", 0, "abc123", "", str(temp_dir)),
            CommandResult("git stash", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        result = service.stash(temp_dir)
        
        assert result.success is True
    
    @patch('app.services.git_service.run_command')
    def test_stash_empty_repo(self, mock_run_command, temp_dir):
        """Test stash sur un repo vide."""
        from app.utils.shell import CommandResult
        
        mock_run_command.return_value = CommandResult(
            command="git rev-parse HEAD",
            returncode=1,
            stdout="",
            stderr="fatal",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.stash(temp_dir)
        
        assert result.success is True
        assert "Skipped" in result.stdout
    
    @patch('app.services.git_service.run_command')
    def test_add_remote(self, mock_run_command, temp_dir):
        """Test add_remote."""
        mock_run_command.return_value = CommandResult(
            command="git remote add",
            returncode=0,
            stdout="",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        result = service.add_remote(temp_dir, "origin", "https://github.com/test/repo.git")
        
        assert result.success is True
    
    @patch('app.services.git_service.run_command')
    def test_get_remote_url(self, mock_run_command, temp_dir):
        """Test get_remote_url."""
        mock_run_command.return_value = CommandResult(
            command="git remote get-url",
            returncode=0,
            stdout="https://github.com/test/repo.git",
            stderr="",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        url = service.get_remote_url(temp_dir, "origin")
        
        assert url == "https://github.com/test/repo.git"
    
    @patch('app.services.git_service.run_command')
    def test_get_remote_url_none(self, mock_run_command, temp_dir):
        """Test get_remote_url retourne None."""
        mock_run_command.return_value = CommandResult(
            command="git remote get-url",
            returncode=1,
            stdout="",
            stderr="error",
            cwd=str(temp_dir)
        )
        
        service = GitService()
        url = service.get_remote_url(temp_dir, "origin")
        
        assert url is None
    
    @patch('app.services.git_service.run_command')
    def test_set_remote_url_new(self, mock_run_command, temp_dir):
        """Test set_remote_url pour un nouveau remote."""
        mock_run_command.side_effect = [
            CommandResult("git remote get-url", 1, "", "", str(temp_dir)),
            CommandResult("git remote add", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        success = service.set_remote_url(temp_dir, "origin", "https://github.com/test/repo.git")
        
        assert success is True
    
    @patch('app.services.git_service.run_command')
    def test_set_remote_url_update(self, mock_run_command, temp_dir):
        """Test set_remote_url pour mettre à jour un remote existant."""
        mock_run_command.side_effect = [
            CommandResult("git remote get-url", 0, "https://old.url", "", str(temp_dir)),
            CommandResult("git remote remove", 0, "", "", str(temp_dir)),
            CommandResult("git remote add", 0, "", "", str(temp_dir))
        ]
        
        service = GitService()
        success = service.set_remote_url(temp_dir, "origin", "https://new.url")
        
        assert success is True

