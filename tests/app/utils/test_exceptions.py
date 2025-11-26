"""
Tests unitaires pour exceptions.py.
"""
import pytest

from app.utils.exceptions import GitError


class TestGitError:
    """Tests pour GitError."""
    
    def test_init_basic(self):
        """Test initialisation basique."""
        error = GitError("Test error")
        
        assert str(error) == "Test error (exit code: None)\nNone"
        assert error.stderr is None
        assert error.returncode is None
    
    def test_init_with_stderr(self):
        """Test initialisation avec stderr."""
        error = GitError("Test error", stderr="Error message")
        
        assert "Test error" in str(error)
        assert "Error message" in str(error)
        assert error.stderr == "Error message"
    
    def test_init_with_returncode(self):
        """Test initialisation avec returncode."""
        error = GitError("Test error", returncode=1)
        
        assert "Test error" in str(error)
        assert "exit code: 1" in str(error)
        assert error.returncode == 1
    
    def test_init_complete(self):
        """Test initialisation complète."""
        error = GitError(
            "Git command failed",
            stderr="fatal: not a git repository",
            returncode=128
        )
        
        assert "Git command failed" in str(error)
        assert "fatal: not a git repository" in str(error)
        assert "exit code: 128" in str(error)
        assert error.stderr == "fatal: not a git repository"
        assert error.returncode == 128
    
    def test_inheritance(self):
        """Test que GitError hérite de Exception."""
        error = GitError("Test")
        
        assert isinstance(error, Exception)
        assert issubclass(GitError, Exception)
    
    def test_raise_and_catch(self):
        """Test lever et capturer GitError."""
        with pytest.raises(GitError) as exc_info:
            raise GitError("Test error", stderr="error", returncode=1)
        
        assert exc_info.value.stderr == "error"
        assert exc_info.value.returncode == 1

