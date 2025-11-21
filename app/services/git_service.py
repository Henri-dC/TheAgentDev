"""
Service de gestion Git.
"""
from pathlib import Path
from typing import List, Optional

from app.utils.shell import run_command, CommandResult
from config.logging import get_logger

logger = get_logger(__name__)


class GitService:
    """Gère les opérations Git."""
    
    def __init__(self):
        pass
    
    def is_git_repo(self, path: Path) -> bool:
        """
        Vérifie si un répertoire est un dépôt Git.
        
        Args:
            path: Chemin à vérifier
        
        Returns:
            True si c'est un dépôt Git, False sinon
        """
        return (path / '.git').exists()
    
    def init(self, path: Path) -> CommandResult:
        """
        Initialise un nouveau dépôt Git.
        
        Args:
            path: Répertoire où initialiser le dépôt
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Initialisation d'un dépôt Git dans {path}")
        return run_command('git init', cwd=path)
    
    def add_all(self, path: Path) -> CommandResult:
        """
        Ajoute tous les fichiers à l'index Git.
        
        Args:
            path: Répertoire du dépôt
        
        Returns:
            Résultat de la commande
        """
        return run_command('git add .', cwd=path)
    
    def commit(self, path: Path, message: str, allow_empty: bool = False) -> CommandResult:
        """
        Crée un commit.
        
        Args:
            path: Répertoire du dépôt
            message: Message du commit
            allow_empty: Autoriser les commits vides
        
        Returns:
            Résultat de la commande
        """
        flag = ' --allow-empty' if allow_empty else ''
        return run_command(f'git commit -m "{message}"{flag}', cwd=path)
    
    def status(self, path: Path, short: bool = True) -> CommandResult:
        """
        Obtient le statut Git.
        
        Args:
            path: Répertoire du dépôt
            short: Format court (-s)
        
        Returns:
            Résultat de la commande
        """
        flag = ' -s' if short else ''
        return run_command(f'git status{flag}', cwd=path)
    
    def diff(self, path: Path, name_only: bool = False, filter_type: Optional[str] = None) -> CommandResult:
        """
        Obtient le diff Git.
        
        Args:
            path: Répertoire du dépôt
            name_only: Afficher seulement les noms de fichiers
            filter_type: Filtrer par type (A=ajouté, M=modifié, D=supprimé, etc.)
        
        Returns:
            Résultat de la commande
        """
        cmd = 'git diff'
        if name_only:
            cmd += ' --name-only'
        if filter_type:
            cmd += f' --diff-filter={filter_type}'
        
        return run_command(cmd, cwd=path)
    
    def get_changed_files(self, path: Path) -> List[str]:
        """
        Récupère la liste des fichiers modifiés/ajoutés/supprimés.
        
        Args:
            path: Répertoire du dépôt
        
        Returns:
            Liste des fichiers modifiés
        """
        # Fichiers modifiés/ajoutés
        modified = self.diff(path, name_only=True, filter_type='ACMRT')
        modified_files = [f.strip() for f in modified.stdout.split('\n') if f.strip()]
        
        # Fichiers supprimés
        deleted = self.diff(path, name_only=True, filter_type='D')
        deleted_files = [f.strip() for f in deleted.stdout.split('\n') if f.strip()]
        
        # Fichiers non suivis
        untracked = run_command('git ls-files --others --exclude-standard', cwd=path)
        untracked_files = [f.strip() for f in untracked.stdout.split('\n') if f.strip()]
        
        # Combiner et dédupliquer
        all_files = set(modified_files + deleted_files + untracked_files)
        return list(all_files)
    
    def is_empty_repo(self, path: Path) -> bool:
        """
        Vérifie si le dépôt est vide (aucun commit).
        """
        return run_command('git rev-parse HEAD', cwd=path).failed

    def checkout(self, path: Path, branch: str) -> CommandResult:
        """
        Change de branche.
        
        Args:
            path: Répertoire du dépôt
            branch: Nom de la branche
            
        Returns:
            Résultat de la commande
        """
        logger.info(f"Git checkout {branch} dans {path}")
        
        # Si le repo est vide, on ne peut pas checkout une branche existante au sens classique
        if self.is_empty_repo(path):
            # Si on veut aller sur 'main' et qu'on est sur 'master' (défaut) ou autre
            # On utilise checkout -b pour renommer la branche racine courante
            return run_command(f'git checkout -b {branch}', cwd=path)
            
        return run_command(f'git checkout {branch}', cwd=path, check=True)

    def fetch(self, path: Path, remote: str = 'origin') -> CommandResult:
        """
        Récupère les modifications depuis un dépôt distant.
        
        Args:
            path: Répertoire du dépôt
            remote: Nom du remote
            
        Returns:
            Résultat de la commande
        """
        logger.info(f"Git fetch {remote} dans {path}")
        # Fetch peut échouer si le remote est vide ou n'existe pas encore
        return run_command(f'git fetch {remote}', cwd=path)

    def reset_hard(self, path: Path, target: Optional[str] = None) -> CommandResult:
        """
        Reset hard (annule tous les changements).
        
        Args:
            path: Répertoire du dépôt
            target: Cible du reset (commit, branche, etc.)
        
        Returns:
            Résultat de la commande
        """
        if self.is_empty_repo(path):
            logger.warning(f"Reset hard ignoré sur dépôt vide: {path}")
            return CommandResult(True, "Skipped reset on empty repo", "")

        command = 'git reset --hard'
        if target:
            command += f' {target}'
        logger.warning(f"Exécution de '{command}' dans {path}")
        return run_command(command, cwd=path)
    
    def clean(self, path: Path, force: bool = True, directories: bool = True) -> CommandResult:
        """
        Nettoie les fichiers non suivis.
        
        Args:
            path: Répertoire du dépôt
            force: Force le nettoyage (-f)
            directories: Inclure les répertoires (-d)
        
        Returns:
            Résultat de la commande
        """
        flags = ''
        if force:
            flags += 'f'
        if directories:
            flags += 'd'
        
        logger.warning(f"Git clean -{flags} dans {path}")
        return run_command(f'git clean -{flags}', cwd=path)

    def get_current_branch(self, path: Path) -> Optional[str]:
        """
        Récupère le nom de la branche courante.

        Args:
            path: Répertoire du dépôt

        Returns:
            Nom de la branche ou None
        """
        result = run_command('git rev-parse --abbrev-ref HEAD', cwd=path)
        if result.success:
            return result.stdout.strip()
        # Cas dépôt vide (HEAD pointe vers refs/heads/main mais pas de commit)
        # git symbolic-ref --short HEAD fonctionne souvent mieux
        result = run_command('git symbolic-ref --short HEAD', cwd=path)
        if result.success:
            return result.stdout.strip()
        return None

    def branch_exists(self, path: Path, branch: str) -> bool:
        """
        Vérifie si une branche existe localement.

        Args:
            path: Répertoire du dépôt
            branch: Nom de la branche

        Returns:
            True si elle existe, False sinon
        """
        result = run_command(f'git branch --list {branch}', cwd=path)
        return bool(result.success and result.stdout.strip())

    def create_branch(self, path: Path, branch: str, start_point: Optional[str] = None) -> CommandResult:
        """
        Crée une nouvelle branche.

        Args:
            path: Répertoire du dépôt
            branch: Nom de la branche
            start_point: Point de départ (optionnel)

        Returns:
            Résultat de la commande
        """
        if start_point:
            cmd = f'git branch {branch} {start_point}'
        else:
            # Si pas de point de départ, et repo vide, checkout -b est nécessaire
            if self.is_empty_repo(path):
                logger.info(f"Dépôt vide, utilisation de checkout -b pour {branch}")
                return run_command(f'git checkout -b {branch}', cwd=path)
            cmd = f'git branch {branch}'
            
        logger.info(f"Création de la branche {branch} dans {path}")
        return run_command(cmd, cwd=path)

    def stash(self, path: Path, message: str = "Gemini CLI temporary changes") -> CommandResult:
        """
        Met de côté les changements actuels.

        Args:
            path: Répertoire du dépôt
            message: Message pour le stash

        Returns:
            Résultat de la commande
        """
        if self.is_empty_repo(path):
            logger.info("Stash ignoré car le dépôt est vide (pas de HEAD).")
            return CommandResult(True, "Skipped stash on empty repo", "")

        logger.info(f"Git stash dans {path} avec le message: {message}")
        return run_command(f'git stash save "{message}"', cwd=path)

    def stash_pop(self, path: Path) -> CommandResult:
        """
        Restaure les derniers changements mis de côté et les supprime du stash.

        Args:
            path: Répertoire du dépôt

        Returns:
            Résultat de la commande
        """
        logger.info(f"Git stash pop dans {path}")
        return run_command('git stash pop', cwd=path)

    def stash_drop(self, path: Path) -> CommandResult:
        """
        Supprime le dernier stash.

        Args:
            path: Répertoire du dépôt

        Returns:
            Résultat de la commande
        """
        logger.info(f"Git stash drop dans {path}")
        return run_command('git stash drop', cwd=path)

    def add_remote(self, path: Path, name: str, url: str) -> CommandResult:
        """
        Ajoute un dépôt distant.
        
        Args:
            path: Répertoire du dépôt
            name: Nom du remote (généralement 'origin')
            url: URL du dépôt distant
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Ajout du remote '{name}' : {url}")
        return run_command(f'git remote add {name} {url}', cwd=path)
    
    def remove_remote(self, path: Path, name: str) -> CommandResult:
        """
        Supprime un dépôt distant.
        
        Args:
            path: Répertoire du dépôt
            name: Nom du remote à supprimer
        
        Returns:
            Résultat de la commande
        """
        return run_command(f'git remote remove {name}', cwd=path)
    
    def get_remote_url(self, path: Path, name: str = 'origin') -> Optional[str]:
        """
        Récupère l'URL d'un remote.
        
        Args:
            path: Répertoire du dépôt
            name: Nom du remote
        
        Returns:
            URL du remote ou None si inexistant
        """
        result = run_command(f'git remote get-url {name}', cwd=path)
        
        if result.success:
            return result.stdout.strip()
        return None
    
    def set_remote_url(self, path: Path, name: str, url: str) -> bool:
        """
        Définit ou met à jour l'URL d'un remote.
        
        Args:
            path: Répertoire du dépôt
            name: Nom du remote
            url: Nouvelle URL
        
        Returns:
            True si réussi, False sinon
        """
        current_url = self.get_remote_url(path, name)
        
        if current_url:
            # Remote existe, le supprimer puis le recréer
            self.remove_remote(path, name)
        
        result = self.add_remote(path, name, url)
        return result.success
    
    def pull(
        self,
        path: Path,
        remote: str = 'origin',
        branch: str = 'main',
        allow_unrelated_histories: bool = False
    ) -> CommandResult:
        """
        Pull depuis un dépôt distant.
        
        Args:
            path: Répertoire du dépôt
            remote: Nom du remote
            branch: Branche à pull
            allow_unrelated_histories: Autoriser la fusion d'historiques non liés
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Git pull {remote} {branch} dans {path}")
        command = f'git pull {remote} {branch}'
        if allow_unrelated_histories:
            command += ' --allow-unrelated-histories'
        return run_command(command, cwd=path, check=True)
    
    def push(
        self,
        path: Path,
        remote: str = 'origin',
        branch: str = 'main',
        set_upstream: bool = False
    ) -> CommandResult:
        """
        Push vers un dépôt distant.
        
        Args:
            path: Répertoire du dépôt
            remote: Nom du remote
            branch: Branche à push
            set_upstream: Définir l'upstream (-u)
        
        Returns:
            Résultat de la commande
        """
        flag = '-u ' if set_upstream else ''
        logger.info(f"Git push {flag}{remote} {branch} depuis {path}")
        return run_command(f'git push {flag}{remote} {branch}', cwd=path, check=True)