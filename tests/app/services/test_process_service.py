"""
Tests unitaires pour ProcessService.
"""
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import requests

from app.services.process_service import ProcessService


class TestProcessService:
    """Tests pour ProcessService."""
    
    def test_init(self):
        """Test l'initialisation du service."""
        service = ProcessService()
        assert service._dev_process is None
        assert service._backend_process is None
    
    @patch('app.services.process_service.requests.get')
    def test_is_port_responsive_true(self, mock_get):
        """Test is_port_responsive retourne True."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        service = ProcessService()
        result = service.is_port_responsive(5173)
        
        assert result is True
        mock_get.assert_called_once()
    
    @patch('app.services.process_service.requests.get')
    def test_is_port_responsive_false(self, mock_get):
        """Test is_port_responsive retourne False."""
        mock_get.side_effect = requests.exceptions.RequestException()
        
        service = ProcessService()
        result = service.is_port_responsive(5173)
        
        assert result is False
    
    @patch('app.services.process_service.requests.get')
    def test_is_port_responsive_500_error(self, mock_get):
        """Test is_port_responsive avec erreur 500."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        service = ProcessService()
        result = service.is_port_responsive(5173)
        
        assert result is False
    
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.time.sleep')
    def test_start_dev_server_success(self, mock_sleep, mock_is_responsive, mock_popen, temp_dir):
        """Test start_dev_server avec succès."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        mock_popen.return_value = mock_process
        
        # Simuler que le port devient responsive après un délai
        mock_is_responsive.side_effect = [False, True]
        
        service = ProcessService()
        result = service.start_dev_server(temp_dir, 5173)
        
        assert result is True
        assert service._dev_process is not None
    
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.time.sleep')
    def test_start_dev_server_port_already_used(self, mock_sleep, mock_is_responsive, mock_popen, temp_dir):
        """Test start_dev_server quand le port est déjà utilisé."""
        mock_is_responsive.return_value = True
        
        service = ProcessService()
        result = service.start_dev_server(temp_dir, 5173, force_clean=False)
        
        assert result is True
        # Ne devrait pas créer de nouveau processus
        mock_popen.assert_not_called()
    
    @patch('app.services.process_service.subprocess.run')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.ProcessService._kill_process_on_port')
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.time.sleep')
    def test_start_dev_server_force_clean(self, mock_sleep, mock_popen, mock_kill, mock_is_responsive, mock_run, temp_dir):
        """Test start_dev_server avec force_clean."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        mock_popen.return_value = mock_process
        
        mock_is_responsive.side_effect = [True, False, True]
        
        service = ProcessService()
        result = service.start_dev_server(temp_dir, 5173, force_clean=True)
        
        assert result is True
        mock_kill.assert_called_once()
    
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.time.sleep')
    def test_start_dev_server_timeout(self, mock_sleep, mock_is_responsive, mock_popen, temp_dir):
        """Test start_dev_server avec timeout."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        mock_popen.return_value = mock_process
        
        # Le port ne devient jamais responsive
        mock_is_responsive.return_value = False
        
        service = ProcessService()
        result = service.start_dev_server(temp_dir, 5173, timeout=1)
        
        assert result is False
    
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.time.sleep')
    def test_start_dev_server_exception(self, mock_sleep, mock_is_responsive, mock_popen, temp_dir):
        """Test start_dev_server avec exception."""
        # Le port n'est pas responsive au début, donc on essaie de démarrer
        mock_is_responsive.return_value = False
        mock_popen.side_effect = Exception("Failed to start")
        
        service = ProcessService()
        result = service.start_dev_server(temp_dir, 5173)
        
        assert result is False
    
    @patch('app.services.process_service.subprocess.run')
    def test_stop_dev_server(self, mock_run, temp_dir):
        """Test stop_dev_server."""
        service = ProcessService()
        
        # Créer un processus mock
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        service._dev_process = mock_process
        
        service.stop_dev_server()
        
        assert service._dev_process is None
    
    @patch('app.services.process_service.subprocess.Popen')
    @patch('app.services.process_service.ProcessService.is_port_responsive')
    @patch('app.services.process_service.time.sleep')
    def test_start_backend_server_success(self, mock_sleep, mock_is_responsive, mock_popen, temp_dir):
        """Test start_backend_server avec succès."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 5678
        mock_popen.return_value = mock_process
        
        mock_is_responsive.side_effect = [False, True]
        
        service = ProcessService()
        result = service.start_backend_server(temp_dir, 3000)
        
        assert result is True
        assert service._backend_process is not None
    
    @patch('app.services.process_service.subprocess.run')
    def test_stop_backend_server(self, mock_run, temp_dir):
        """Test stop_backend_server."""
        service = ProcessService()
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 5678
        service._backend_process = mock_process
        
        service.stop_backend_server()
        
        assert service._backend_process is None
    
    @patch('app.services.process_service.ProcessService.stop_dev_server')
    @patch('app.services.process_service.ProcessService.stop_backend_server')
    def test_stop_all(self, mock_stop_backend, mock_stop_dev):
        """Test stop_all."""
        service = ProcessService()
        service.stop_all()
        
        mock_stop_dev.assert_called_once()
        mock_stop_backend.assert_called_once()
    
    @patch('app.services.process_service.subprocess.run')
    def test_kill_process_on_port_windows(self, mock_run, temp_dir):
        """Test _kill_process_on_port sur Windows."""
        mock_run.return_value = Mock(stdout="TCP    0.0.0.0:5173           0.0.0.0:0              LISTENING       1234")
        
        with patch('os.name', 'nt'):
            service = ProcessService()
            service._kill_process_on_port(5173)
            
            # Vérifier que taskkill a été appelé
            assert mock_run.call_count >= 1
    
    @patch('app.services.process_service.subprocess.run')
    def test_kill_process_on_port_linux(self, mock_run, temp_dir):
        """Test _kill_process_on_port sur Linux."""
        with patch('os.name', 'posix'):
            service = ProcessService()
            service._kill_process_on_port(5173)
            
            # Vérifier que fuser a été appelé
            assert mock_run.call_count >= 1
    
    @patch('app.services.process_service.subprocess.run')
    def test_terminate_process_windows(self, mock_run, temp_dir):
        """Test _terminate_process sur Windows."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        
        with patch('os.name', 'nt'):
            service = ProcessService()
            service._terminate_process(mock_process)
            
            # Vérifier que taskkill a été appelé
            assert mock_run.call_count >= 1
    
    def test_terminate_process_linux(self, temp_dir):
        """Test _terminate_process sur Linux."""
        import app.services.process_service as process_module
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 1234
        mock_process.wait.return_value = None
        
        # Créer des mocks pour os.killpg et os.getpgid qui n'existent pas sur Windows
        # Utiliser patch.object avec create=True pour créer les attributs s'ils n'existent pas
        with patch.object(process_module.os, 'name', 'posix'):
            with patch.object(process_module.os, 'getpgid', return_value=1234, create=True) as mock_getpgid:
                with patch.object(process_module.os, 'killpg', create=True) as mock_killpg:
                    service = ProcessService()
                    service._terminate_process(mock_process)
                    
                    # Vérifier que killpg a été appelé
                    mock_killpg.assert_called()
                    mock_getpgid.assert_called()

