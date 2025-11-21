"""
Service de gestion npm.
"""
from pathlib import Path

from app.utils.shell import run_command, CommandResult
from config.logging import get_logger

logger = get_logger(__name__)


class NpmService:
    """Gère les opérations npm."""
    
    def __init__(self):
        pass
    
    def has_package_json(self, path: Path) -> bool:
        """
        Vérifie si un répertoire contient package.json.
        
        Args:
            path: Répertoire à vérifier
        
        Returns:
            True si package.json existe, False sinon
        """
        return (path / 'package.json').exists()
    
    def has_node_modules(self, path: Path) -> bool:
        """
        Vérifie si node_modules existe.
        
        Args:
            path: Répertoire à vérifier
        
        Returns:
            True si node_modules existe, False sinon
        """
        return (path / 'node_modules').exists()
    
    def install(self, path: Path, timeout: int = 300) -> CommandResult:
        """
        Exécute npm install.
        
        Args:
            path: Répertoire du projet
            timeout: Timeout en secondes (5 minutes par défaut)
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Exécution de npm install dans {path}")
        return run_command('npm install', cwd=path, timeout=timeout)
    
    def install_packages(self, path: Path, packages: list[str], dev: bool = False, timeout: int = 180) -> CommandResult:
        """
        Installe des packages spécifiques.
        
        Args:
            path: Répertoire du projet
            packages: Liste des packages à installer
            dev: Installer en tant que devDependencies
            timeout: Timeout en secondes
        
        Returns:
            Résultat de la commande
        """
        flag = ' -D' if dev else ''
        packages_str = ' '.join(packages)
        
        logger.info(f"Installation de {packages_str}{' (dev)' if dev else ''} dans {path}")
        return run_command(f'npm install{flag} {packages_str}', cwd=path, timeout=timeout)
    
    def create_vue_project(self, path: Path, project_name: str = "vue-project-temp") -> CommandResult:
        """
        Crée un nouveau projet Vue.js.
        
        Args:
            path: Répertoire parent
            project_name: Nom du projet temporaire
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Création d'un projet Vue dans {path}")
        return run_command(
            f'npm create vue@latest {project_name} -- --default',
            cwd=path,
            timeout=180
        )
    
    def create_react_project(self, path: Path) -> CommandResult:
        """
        Crée un nouveau projet React avec Vite.
        
        Args:
            path: Répertoire où créer le projet
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Création d'un projet React dans {path}")
        # Utiliser des echo pour répondre automatiquement "No" aux prompts
        return run_command(
            'echo "No" | echo "No" | npm create --yes vite@latest . -- --template react --force',
            cwd=path,
            timeout=180
        )
    
    
    
    def run_prisma_generate(self, path: Path) -> CommandResult:
        """
        Génère le client Prisma.
        
        Args:
            path: Répertoire du projet backend
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Génération du client Prisma dans {path}")
        return run_command('npx prisma generate', cwd=path, timeout=120)
    
    def run_prisma_migrate(self, path: Path, name: str = "init") -> CommandResult:
        """
        Exécute une migration Prisma.
        
        Args:
            path: Répertoire du projet backend
            name: Nom de la migration
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Migration Prisma '{name}' dans {path}")
        return run_command(f'npx prisma migrate dev --name {name}', cwd=path, timeout=120)
    
    def init_prisma(self, path: Path, provider: str = "sqlite") -> CommandResult:
        """
        Initialise Prisma dans un projet.
        
        Args:
            path: Répertoire du projet
            provider: Provider de base de données (sqlite, postgresql, etc.)
        
        Returns:
            Résultat de la commande
        """
        logger.info(f"Initialisation de Prisma ({provider}) dans {path}")
        return run_command(
            f'npx --yes prisma init --datasource-provider {provider}',
            cwd=path,
            timeout=60
        )
    
    def install_tailwind_react(self, path) -> CommandResult:
        """
        Installe et configure Tailwind CSS (v3 standard) pour un projet React.
        """
        logger.info(f"Installation de Tailwind CSS (v3 standard) pour React dans {path}...")
        
        # 1. Installer les dépendances (tailwindcss, postcss, autoprefixer)
        result = run_command('npm install -D tailwindcss postcss autoprefixer', cwd=path)
        if result.failed:
            raise Exception(f"Échec de l'installation des dépendances Tailwind: {result.stderr}")
        
        # 2. Initialiser Tailwind (crée tailwind.config.js et postcss.config.js)
        result = run_command('npx tailwindcss init -p', cwd=path)
        if result.failed:
            raise Exception(f"Échec de l'initialisation de Tailwind: {result.stderr}")
        
        # 3. Configurer tailwind.config.js (ESM pour Vite)
        tailwind_config_content = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}"""
        try:
            with open(path / 'tailwind.config.js', 'w', encoding='utf-8') as f:
                f.write(tailwind_config_content)
            logger.info("tailwind.config.js mis à jour.")
        except IOError as e:
            raise Exception(f"Impossible d'écrire tailwind.config.js: {e}")

        # 4. Mettre à jour src/index.css avec les directives @tailwind
        index_css_path = path / 'src' / 'index.css'
        if not index_css_path.parent.exists():
            index_css_path.parent.mkdir(parents=True, exist_ok=True)
        
        tailwind_directives = """@tailwind base;
@tailwind components;
@tailwind utilities;

/* Ajoutez votre CSS personnalisé ici */
"""
        try:
            with open(index_css_path, 'w', encoding='utf-8') as f:
                f.write(tailwind_directives)
            logger.info("Directives @tailwind ajoutées à src/index.css.")
        except IOError as e:
            raise Exception(f"Impossible d'écrire dans src/index.css: {e}")
        
        return result
    
    def install_tailwind_vue(self, path: Path) -> CommandResult:
        """
        Installe et configure Tailwind CSS (v3 standard) pour un projet Vue.js.
        """
        logger.info(f"Installation de Tailwind CSS (v3 standard) pour Vue dans {path}...")
        
        # 1. Installer les dépendances
        result = run_command('npm install -D tailwindcss postcss autoprefixer', cwd=path)
        if result.failed:
            raise Exception(f"Échec de l'installation de Tailwind: {result.stderr}")
        
        # 2. Initialiser Tailwind
        result = run_command('npx tailwindcss init -p', cwd=path)
        if result.failed:
            raise Exception(f"Échec de l'initialisation de Tailwind: {result.stderr}")
        
        # 3. Configurer tailwind.config.js
        tailwind_config_content = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}"""
        try:
            with open(path / 'tailwind.config.js', 'w', encoding='utf-8') as f:
                f.write(tailwind_config_content)
            logger.info("tailwind.config.js mis à jour.")
        except IOError as e:
            raise Exception(f"Impossible d'écrire tailwind.config.js: {e}")
        
        # 4. Ajouter les directives Tailwind au CSS principal
        style_css_path = path / 'src' / 'assets' / 'main.css'
        if not style_css_path.exists():
            style_css_path = path / 'src' / 'style.css'
            if not style_css_path.exists():
                 # Fallback creation
                 style_css_path.parent.mkdir(parents=True, exist_ok=True)
        
        tailwind_directives = """@tailwind base;
@tailwind components;
@tailwind utilities;

"""
        try:
            if style_css_path.exists():
                content = style_css_path.read_text(encoding='utf-8')
                style_css_path.write_text(tailwind_directives + content, encoding='utf-8')
            else:
                style_css_path.write_text(tailwind_directives, encoding='utf-8')
            
            logger.info(f"Directives @tailwind ajoutées à {style_css_path}")
        except IOError as e:
            raise Exception(f"Impossible de modifier le fichier CSS principal: {e}")
            
        return result