"""
Tests unitaires pour ChromaService.
"""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from app.services.chroma_service import ChromaService, init_chroma_service, get_chroma_service


class TestChromaService:
    """Tests pour ChromaService."""
    
    def test_init_success(self, temp_dir):
        """Test l'initialisation réussie du service."""
        project_name = "test_project"
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService(project_name)
            
            assert service.client is not None
            assert service.collection is not None
            mock_client.assert_called_once()
    
    def test_init_failure(self, temp_dir):
        """Test la gestion d'erreur lors de l'initialisation."""
        project_name = "test_project"
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_client.side_effect = Exception("Connection failed")
            
            service = ChromaService(project_name)
            
            assert service.client is None
            assert service.collection is None
    
    def test_index_workspaces_no_collection(self, temp_dir):
        """Test index_workspaces quand la collection n'est pas disponible."""
        service = ChromaService("test")
        service.collection = None
        
        result = service.index_workspaces({})
        
        assert result["status"] == "error"
        assert "not available" in result["message"]
    
    def test_index_workspaces_empty_paths(self, temp_dir):
        """Test index_workspaces avec des chemins vides."""
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {'ids': []}
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService("test")
            result = service.index_workspaces({})
            
            assert result["status"] == "success"
            assert result["count"] == 0
    
    def test_index_workspaces_invalid_path(self, temp_dir):
        """Test index_workspaces avec un chemin invalide."""
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {'ids': []}
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService("test")
            workspace_paths = {"workspace1": "/nonexistent/path"}
            
            result = service.index_workspaces(workspace_paths)
            
            assert result["status"] == "success"
            assert result["count"] == 0
    
    def test_index_workspaces_success(self, temp_dir):
        """Test index_workspaces avec succès."""
        # Créer des fichiers de test
        test_file = temp_dir / "test.py"
        test_file.write_text("print('hello')")
        
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {'ids': []}
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService("test")
            workspace_paths = {"workspace1": str(temp_dir)}
            
            result = service.index_workspaces(workspace_paths)
            
            assert result["status"] == "success"
            assert result["count"] > 0
            mock_collection.add.assert_called_once()
    
    def test_scan_directory(self, temp_dir):
        """Test _scan_directory."""
        # Créer des fichiers de test
        (temp_dir / "test.py").write_text("print('hello')")
        (temp_dir / "test.js").write_text("console.log('hello')")
        (temp_dir / "test.txt").write_text("hello")  # Extension non autorisée
        (temp_dir / ".git").mkdir()  # Dossier à ignorer
        
        service = ChromaService("test")
        docs, metas, ids = service._scan_directory(str(temp_dir))
        
        assert len(docs) == 2  # Seulement .py et .js
        assert len(metas) == 2
        assert len(ids) == 2
    
    def test_query_no_collection(self, temp_dir):
        """Test query quand la collection n'est pas disponible."""
        service = ChromaService("test")
        service.collection = None
        
        result = service.query("test query")
        
        assert result == []
    
    def test_query_success(self, temp_dir):
        """Test query avec succès."""
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                'documents': [['doc1', 'doc2']],
                'metadatas': [[{'source': 'file1.py'}, {'source': 'file2.py'}]]
            }
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService("test")
            result = service.query("test query", n_results=2)
            
            assert len(result) == 2
            assert result[0][0] == 'doc1'
            assert result[0][1]['source'] == 'file1.py'
    
    def test_query_exception(self, temp_dir):
        """Test query avec exception."""
        with patch('app.services.chroma_service.chromadb.PersistentClient') as mock_client:
            mock_collection = MagicMock()
            mock_collection.query.side_effect = Exception("Query failed")
            mock_client_instance = MagicMock()
            mock_client_instance.get_or_create_collection.return_value = mock_collection
            mock_client.return_value = mock_client_instance
            
            service = ChromaService("test")
            result = service.query("test query")
            
            assert result == []


class TestChromaServiceFunctions:
    """Tests pour les fonctions globales."""
    
    def test_init_chroma_service(self):
        """Test init_chroma_service."""
        with patch('app.services.chroma_service.ChromaService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            result = init_chroma_service("test_project")
            
            assert result == mock_service
            mock_service_class.assert_called_once_with("test_project")
    
    def test_get_chroma_service(self):
        """Test get_chroma_service."""
        from app.services.chroma_service import chroma_service as original_service
        
        # Sauvegarder l'état original
        original_state = original_service
        
        # Tester avec None
        import app.services.chroma_service as chroma_module
        chroma_module.chroma_service = None
        assert get_chroma_service() is None
        
        # Restaurer
        chroma_module.chroma_service = original_state

