"""
Configuration centralisée de l'application.
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

from .logging import get_logger

# Charger les variables d'environnement
load_dotenv()
logger = get_logger(__name__)


@dataclass
class ServerConfig:
    """Configuration des serveurs."""
    dev_port: int = int(os.getenv('DEV_SERVER_PORT', 5173))
    backend_port: int = int(os.getenv('BACKEND_SERVER_PORT', 3000))
    
    @property
    def dev_url(self) -> str:
        return f"http://127.0.0.1:{self.dev_port}"
    
    @property
    def backend_url(self) -> str:
        return f"http://127.0.0.1:{self.backend_port}"


@dataclass
class ProjectConfig:
    """Configuration du projet depuis project_config.json."""
    repository_url: Optional[str] = None
    dev_path: str = ""
    prod_path: Optional[str] = None
    backend_dev_path: str = ""
    frontend_framework: str = "react"
    branch_name: str = "main"
    wordpress_api_enabled: bool = False
    enable_database: bool = False
    database_url: str = "file:./dev.db"
    
    # Variables WordPress (optionnelles)
    wordpress_env: dict = field(default_factory=dict)
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> 'ProjectConfig':
        """Charge la configuration depuis le fichier JSON."""
        if not config_path.exists():
            raise FileNotFoundError(
                f"Fichier de configuration introuvable: {config_path}\n"
                "Créez project_config.json avant de lancer l'application."
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Erreur de syntaxe JSON dans {config_path}: {e}"
            )
        
        # Extraire les variables WordPress si présentes
        wordpress_keys = [
            'WP_API_URL', 'WOO_API_URL', 'WOO_CONSUMER_KEY', 
            'WOO_CONSUMER_SECRET', 'WP_USERNAME', 'WP_PASSWORD',
            'ADMIN_USERNAME', 'ADMIN_PASSWORD', 'JWT_SECRET',
            'MAILJET_API_KEY', 'MAILJET_SECRET_KEY', 'MAIL_FROM',
            'MAIL_TO_ADMIN', 'INSTAGRAM_ACCESS_TOKEN', 'RECAPTCHA_SECRET_KEY'
        ]
        wordpress_env = {k: data.get(k, '') for k in wordpress_keys if k in data}
        
        return cls(
            repository_url=data.get('repository_url'),
            dev_path=data.get('dev_path', ''),
            prod_path=data.get('prod_path'),
            backend_dev_path=data.get('backend_dev_path', ''),
            frontend_framework=data.get('frontend_framework', 'react'),
            branch_name=data.get('branch_name', 'main'),
            wordpress_api_enabled=data.get('wordpress_api_enabled', False),
            enable_database=data.get('enable_database', False),
            database_url=data.get('database_url', 'file:./dev.db'),
            wordpress_env=wordpress_env
        )
    
    def save_to_file(self, config_path: Path):
        """Sauvegarde la configuration dans le fichier JSON en préservant les clés existantes."""
        
        # Lire les données existantes pour ne pas écraser les champs non modifiés
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {} # Si le fichier n'existe pas ou est invalide, on part de zéro

        # Mettre à jour les données avec les valeurs de l'instance actuelle
        data.update({
            'repository_url': self.repository_url,
            'dev_path': self.dev_path,
            'prod_path': self.prod_path,
            'backend_dev_path': self.backend_dev_path,
            'frontend_framework': self.frontend_framework,
            'branch_name': self.branch_name,
            'wordpress_api_enabled': self.wordpress_api_enabled,
            'enable_database': self.enable_database,
            'database_url': self.database_url,
        })
        
        # Ajouter ou mettre à jour les variables d'environnement WordPress
        if self.wordpress_env:
            data.update(self.wordpress_env)
        
        # Écrire le fichier JSON mis à jour
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


@dataclass
class PathConfig:
    """Configuration des chemins."""
    base_dir: Path
    config_path: Path
    wordpress_backend_source: Path
    
    dev_path: Path
    backend_dev_path: Path
    prod_path: Optional[Path] = None
    
    @classmethod
    def from_project_config(cls, project_config: ProjectConfig) -> 'PathConfig':
        """Crée PathConfig à partir de ProjectConfig."""
        base_dir = Path().resolve()
        
        dev_path = (base_dir / project_config.dev_path).resolve()
        backend_dev_path = (base_dir / project_config.backend_dev_path).resolve()
        prod_path = (base_dir / project_config.prod_path).resolve() if project_config.prod_path else None
        
        return cls(
            base_dir=base_dir,
            config_path=Path('project_config.json'),
            wordpress_backend_source=Path(__file__).parent.parent / "templates_backend" / "wordpress_api",
            dev_path=dev_path,
            backend_dev_path=backend_dev_path,
            prod_path=prod_path
        )


@dataclass
class GeminiConfig:
    """Configuration pour l'API Gemini."""
    api_key: Optional[str] = None
    model_name: str = "gemini-2.5-pro"
    enabled: bool = False
    client: Optional[any] = None
    
    @classmethod
    def from_env(cls) -> 'GeminiConfig':
        """Initialise la configuration Gemini depuis les variables d'environnement."""
        logger.info("Configuration de Gemini...")
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            logger.warning("Clé API Gemini (GOOGLE_API_KEY) non trouvée. Service désactivé.")
            return cls(enabled=False)
        
        logger.info("Clé API Gemini trouvée.")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            logger.info("Service Gemini configuré et activé avec succès.")
            return cls(
                api_key=api_key,
                enabled=True,
                client=genai
            )
        except ImportError:
            logger.warning("Le package 'google.generativeai' n'est pas installé. Gemini est désactivé.")
            return cls(api_key=api_key, enabled=False)
        except Exception as e:
            logger.error(f"Impossible de configurer Gemini: {e}. Service désactivé.")
            return cls(api_key=api_key, enabled=False)


@dataclass
class ClaudeConfig:
    """Configuration pour l'API Claude (Anthropic)."""
    api_key: Optional[str] = None
    model_name: str = "claude-3-sonnet-20240229"
    enabled: bool = False
    
    @classmethod
    def from_env(cls) -> 'ClaudeConfig':
        """Initialise la configuration Claude depuis les variables d'environnement."""
        logger.info("Configuration de Claude...")
        api_key = os.getenv('CLAUDE_API_KEY')
        
        if not api_key:
            logger.warning("Clé API Claude (CLAUDE_API_KEY) non trouvée. Service désactivé.")
            return cls(enabled=False)
        
        logger.info("Clé API Claude trouvée. Service activé.")
        return cls(api_key=api_key, enabled=True)


class AppConfig:
    """Configuration globale de l'application."""
    
    def __init__(self):
        self.project = ProjectConfig.load_from_file(Path('project_config.json'))
        self.paths = PathConfig.from_project_config(self.project)
        self.servers = ServerConfig()
        self.gemini = GeminiConfig.from_env()
        self.claude = ClaudeConfig.from_env()
    
    def reload_project_config(self):
        """Recharge la configuration du projet."""
        self.project = ProjectConfig.load_from_file(self.paths.config_path)
        self.paths = PathConfig.from_project_config(self.project)


# Instance globale (singleton)
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Récupère l'instance de configuration (singleton)."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config():
    """Force le rechargement de la configuration."""
    global _config
    _config = None
    get_config()