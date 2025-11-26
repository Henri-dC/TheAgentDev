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
    
    def _kill_process_on_port(self, port: int):
        """
        Tue le processus qui écoute sur le port donné (Windows/Linux).
        """
        logger.info(f"Tentative de libération forcée du port {port}...")
        try:
            if os.name == 'nt':
                # Windows : trouver le PID via netstat
                # netstat -ano | findstr :<port>
                result = subprocess.run(
                    f'netstat -ano | findstr :{port}',
                    shell=True, capture_output=True, text=True
                )
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        # format: PROTO LocalAddress ForeignAddress State PID
                        # Ex: TCP    0.0.0.0:5173           0.0.0.0:0              LISTENING       1234
                        if len(parts) >= 5 and str(port) in parts[1]:
                            pid = parts[-1]
                            logger.info(f"Processus trouvé sur le port {port} : PID={pid}. Arrêt forcé...")
                            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            else:
                # Linux/Unix : fuser ou lsof
                subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
                
        except Exception as e:
            logger.error(f"Erreur lors du kill sur le port {port}: {e}")

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
        """
        with self._lock:
            # Vérifier si le port est occupé
            if self.is_port_responsive(port):
                # Si un nettoyage forcé est demandé, on tue tout ce qui bouge
                if force_clean:
                    logger.warning(f"Port {port} occupé. Nettoyage forcé demandé...")
                    self._kill_process_on_port(port)
                    time.sleep(1)
                else:
                    # Sinon, on suppose que c'est soit notre processus, soit un serveur lancé manuellement
                    # par l'utilisateur (ce qui est le cas ici). On fait confiance et on se connecte dessus.
                    logger.info(f"Un service répond déjà sur le port {port}. Utilisation du serveur existant (manuel ou interne).")
                    return True
            
            # S'assurer que tout ancien processus suivi est bien mort
            if self._dev_process:
                self._terminate_process(self._dev_process)
                self._dev_process = None
            
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
            
            # Sécurité supplémentaire : si le port répond toujours, on force le kill
            # (Port par défaut Vite = 5173, ou lire depuis config si accessible, ici on suppose le port standard ou on l'ajoute en paramètre si besoin, 
            # mais pour simplifier, stop_all appelle souvent stop_dev_server sans args)
            # Idéalement, on devrait stocker le port utilisé.
            # Pour l'instant, on suppose que stop_all ou le changement de projet va rappeler start_dev_server qui fera le ménage via _kill_process_on_port.
            logger.info("Serveur dev arrêté (instance interne).")
    
    def start_backend_server(
        self,
        project_path: Path,
        port: int,
        timeout: int = 30
    ) -> bool:
        """
        Démarre le serveur backend Node.js.
        """
        with self._lock:
            # Même logique pour le backend
            if self.is_port_responsive(port):
                if self._backend_process and self._backend_process.poll() is None:
                    logger.info(f"Serveur backend déjà actif sur le port {port}")
                    return True
                
                logger.warning(f"Port {port} (backend) occupé par un zombie. Nettoyage...")
                self._kill_process_on_port(port)
                time.sleep(1)
            
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