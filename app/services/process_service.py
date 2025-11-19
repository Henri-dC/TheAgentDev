"""
Service de gestion des processus (serveurs dev et backend).
"""
import os
import time
import signal
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional

import requests

from config.logging import get_logger

logger = get_logger(__name__)


class ProcessService:
    """Gère le cycle de vie des processus serveurs."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._dev_process: Optional[subprocess.Popen] = None
        self._backend_process: Optional[subprocess.Popen] = None
    
    def is_port_responsive(self, port: int, path: str = '/', timeout: float = 1.0) -> bool:
        """
        Vérifie qu'un service répond sur un port.
        
        Args:
            port: Port à tester
            path: Chemin HTTP à tester
            timeout: Timeout de la requête
        
        Returns:
            True si le service répond, False sinon
        """
        url = f'http://127.0.0.1:{port}{path}'
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code < 500
        except requests.exceptions.RequestException:
            return False
    
    def _spawn_process(self, command: str, cwd: Path) -> subprocess.Popen:
        """
        Lance un processus dans un nouveau terminal visible (Windows) ou en arrière-plan (autres OS).
        
        Args:
            command: Commande à exécuter
            cwd: Répertoire de travail
        
        Returns:
            Instance Popen du processus
        """
        cwd_str = str(cwd)
        
        if os.name == 'nt':  # Windows
            # Ouvre une nouvelle fenêtre de console pour le processus.
            # CREATE_NEW_PROCESS_GROUP est conservé pour que l'arrêt via _terminate_process fonctionne.
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE
            
            proc = subprocess.Popen(
                command,
                cwd=cwd_str,
                shell=True,
                creationflags=creation_flags
            )
            logger.info(f"Processus démarré: PID={proc.pid}, cmd='{command}'")
        
        else:  # Unix/Linux
            # Comportement existant pour les autres OS : redirection vers les logs.
            log_out = cwd / 'process_out.log'
            log_err = cwd / 'process_err.log'
            out = open(log_out, 'a', encoding='utf-8')
            err = open(log_err, 'a', encoding='utf-8')
            preexec_fn = os.setsid
            
            proc = subprocess.Popen(
                command,
                cwd=cwd_str,
                shell=True,
                stdout=out,
                stderr=err,
                preexec_fn=preexec_fn
            )
            logger.info(f"Processus démarré en arrière-plan: PID={proc.pid}, cmd='{command}', logs dans {cwd_str}")
            
        return proc
    
    def _terminate_process(self, proc: Optional[subprocess.Popen]):
        """
        Termine proprement un processus et ses enfants.
        
        Args:
            proc: Instance Popen à terminer
        """
        if not proc or proc.poll() is not None:
            return
        
        pid = proc.pid
        logger.info(f"Tentative d'arrêt du groupe de processus PID={pid}")
        
        try:
            if os.name == 'nt':  # Windows
                # Utiliser taskkill est plus fiable pour tuer l'arbre de processus de npm
                logger.info(f"Utilisation de taskkill pour arrêter le processus PID={pid} et ses enfants.")
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    check=False, capture_output=True
                )
            else:  # Unix/Linux
                # Envoie SIGTERM au groupe de processus complet
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                # Attendre que le processus se termine
                proc.wait(timeout=10)
            
            logger.info(f"Processus PID={pid} terminé.")
            
        except (subprocess.TimeoutExpired, ProcessLookupError):
            logger.warning(f"Le processus PID={pid} n'a pas répondu à SIGTERM. Forçage de l'arrêt (SIGKILL).")
            if os.name != 'nt':
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Le processus a déjà disparu
        
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'arrêt du processus PID={pid}: {e}")
    
    def start_dev_server(
        self,
        project_path: Path,
        port: int,
        host: str = "127.0.0.1",
        timeout: int = 30,
        force_clean: bool = False
    ) -> bool:
        """
        Démarre le serveur de développement Vite.
        
        Args:
            project_path: Chemin du projet dev
            port: Port du serveur
            host: Hôte (généralement 127.0.0.1)
            timeout: Timeout d'attente du démarrage
            force_clean: Si True, force Vite à ré-optimiser les dépendances
        
        Returns:
            True si le serveur a démarré, False sinon
        """
        with self._lock:
            # Vérifier si déjà en cours
            if self.is_port_responsive(port):
                logger.info(f"Serveur dev déjà actif sur le port {port}")
                return True
            
            # Arrêter l'ancien processus si présent
            if self._dev_process:
                self._terminate_process(self._dev_process)
                self._dev_process = None
                
                # Attendre que le port soit libéré
                deadline = time.time() + 5  # Attendre jusqu'à 5 secondes
                while time.time() < deadline:
                    if not self.is_port_responsive(port):
                        logger.info(f"Port {port} libéré.")
                        break
                    time.sleep(0.5)
                else:
                    logger.warning(f"Port {port} toujours actif après arrêt du serveur dev. Tentative de démarrage quand même.")
            
            # Démarrer le serveur
            command = f'npm run dev -- --host {host} --port {port}'
            if force_clean:
                command += ' --force'
                logger.info("Démarrage du serveur dev avec nettoyage du cache (force).")
            
            try:
                self._dev_process = self._spawn_process(command, project_path)
                
                # Attendre que le serveur soit prêt
                deadline = time.time() + timeout
                while time.time() < deadline:
                    if self.is_port_responsive(port):
                        logger.info(f"✓ Serveur dev prêt sur http://{host}:{port}")
                        return True
                    time.sleep(0.5)
                
                logger.error(f"Timeout: le serveur dev n'est pas prêt après {timeout}s")
                return False
            
            except Exception as e:
                logger.exception(f"Erreur lors du démarrage du serveur dev: {e}")
                return False
    
    def stop_dev_server(self):
        """Arrête le serveur de développement."""
        with self._lock:
            if self._dev_process:
                self._terminate_process(self._dev_process)
                self._dev_process = None
                logger.info("Serveur dev arrêté")
    
    def start_backend_server(
        self,
        project_path: Path,
        port: int,
        timeout: int = 30
    ) -> bool:
        """
        Démarre le serveur backend Node.js.
        
        Args:
            project_path: Chemin du projet backend
            port: Port du serveur
            timeout: Timeout d'attente du démarrage
        
        Returns:
            True si le serveur a démarré, False sinon
        """
        with self._lock:
            # Vérifier si déjà en cours
            if self.is_port_responsive(port):
                logger.info(f"Serveur backend déjà actif sur le port {port}")
                return True
            
            # Arrêter l'ancien processus si présent
            if self._backend_process:
                self._terminate_process(self._backend_process)
                self._backend_process = None
            
            # Démarrer le serveur avec nodemon
            command = 'npx nodemon server.js'
            
            try:
                self._backend_process = self._spawn_process(command, project_path)
                
                # Attendre que le serveur soit prêt
                deadline = time.time() + timeout
                while time.time() < deadline:
                    if self.is_port_responsive(port):
                        logger.info(f"✓ Serveur backend prêt sur http://127.0.0.1:{port}")
                        return True
                    time.sleep(0.5)
                
                logger.error(f"Timeout: le serveur backend n'est pas prêt après {timeout}s")
                return False
            
            except Exception as e:
                logger.exception(f"Erreur lors du démarrage du serveur backend: {e}")
                return False
    
    def stop_backend_server(self):
        """Arrête le serveur backend."""
        with self._lock:
            if self._backend_process:
                self._terminate_process(self._backend_process)
                self._backend_process = None
                logger.info("Serveur backend arrêté")

    def stop_all(self):
        """Arrête tous les serveurs."""
        self.stop_dev_server()
        self.stop_backend_server()
        logger.info("Tous les serveurs arrêtés")


# Instance unique du service
process_service = ProcessService()