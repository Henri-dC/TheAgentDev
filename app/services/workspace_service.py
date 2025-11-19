"""
Service de gestion des workspaces (dev, backend_dev, prod).
"""
import json
import shutil
from pathlib import Path
from typing import Optional

from config.settings import get_config
from app.services.npm_service import NpmService
from app.services.git_service import GitService
from config.logging import get_logger

logger = get_logger(__name__)


class WorkspaceService:
    """Gère la configuration et l\'initialisation des workspaces."""
    
    def __init__(self, npm_service: NpmService, git_service: GitService):
        self.npm = npm_service
        self.git = git_service
    
    def setup_all(self):
        """Configure tous les workspaces (dev, backend_dev, prod si défini)."""
        logger.info("=== Initialisation des workspaces ===")
        
        try:
            self._setup_dev_workspace()
            self._setup_backend_workspace()
            
            prod_path = get_config().paths.prod_path
            if prod_path:
                self._setup_prod_workspace()
            
            self._setup_git_repositories()
            
            logger.info("=== Workspaces prêts ===")
        
        except Exception as e:
            logger.exception(f"Erreur lors de la configuration des workspaces: {e}")
            raise
    
    def _setup_dev_workspace(self):
        """Configure le workspace de développement (frontend)."""
        logger.info("Configuration du workspace dev...")
        
        dev_path = Path(get_config().paths.dev_path)
        dev_path.mkdir(parents=True, exist_ok=True)
        
        if not any(dev_path.iterdir()):
            self._create_new_frontend_project()
        else:
            logger.info("Workspace dev existe déjà")
            if self.npm.has_package_json(dev_path) and not self.npm.has_node_modules(dev_path):
                logger.info("Installation des dépendances npm pour dev...")
                result = self.npm.install(dev_path)
                if result.failed:
                    raise Exception(f"Installation npm échouée: {result.stderr}")
    
    def _create_new_frontend_project(self):
        """Crée un nouveau projet frontend (React ou Vue)."""
        config = get_config()
        framework = config.project.frontend_framework
        dev_path = Path(config.paths.dev_path)
        
        if not framework:
            logger.warning("Aucun framework configuré. Allez sur /settings pour en choisir un.")
            return
        
        logger.info(f"Création d\'un nouveau projet {framework}...")
        
        if framework == 'vue':
            self._create_vue_project()
        elif framework == 'react':
            self._create_react_project()
        else:
            raise ValueError(f"Framework non supporté: {framework}")
    
    def _create_vue_project(self):
        """Crée un projet Vue.js."""
        dev_path = Path(get_config().paths.dev_path)
        project_name = "vue-project-temp"
        
        result = self.npm.create_vue_project(dev_path, project_name)
        if result.failed:
            raise Exception(f"Création du projet Vue échouée: {result.stderr}")
        
        temp_project_path = dev_path / project_name
        if temp_project_path.exists():
            for item in temp_project_path.iterdir():
                shutil.move(str(item), str(dev_path / item.name))
            temp_project_path.rmdir()
        else:
            raise Exception(f"Le projet Vue n\'a pas été créé dans {temp_project_path}")
        
        self._create_vite_config()
        self.npm.install(dev_path)
        self.npm.install_tailwind_vue(dev_path)
        logger.info("Projet Vue créé avec succès")
    
    def _create_react_project(self):
        """Crée un projet React avec Vite et Tailwind CSS."""
        dev_path = Path(get_config().paths.dev_path)
        
        result = self.npm.create_react_project(dev_path)
        if result.failed:
            raise Exception(f"Création du projet React échouée: {result.stderr}")
        
        self._create_vite_config()
        
        result = self.npm.install(dev_path)
        if result.failed:
            raise Exception(f"Installation des dépendances échouée: {result.stderr}")
        
        result = self.npm.install_tailwind_react(dev_path)
        if result.failed:
            raise Exception(f"Installation de Tailwind échouée: {result.stderr}")

    def _create_vite_config(self):
        """Crée un fichier vite.config.js avec un proxy vers le backend."""
        config = get_config()
        dev_path = Path(config.paths.dev_path)
        vite_config_path = dev_path / 'vite.config.js'
        backend_port = config.servers.backend_port

        # Déterminer le plugin à utiliser (vue ou react)
        plugin_import = "import vue from '@vitejs/plugin-vue';" if config.project.frontend_framework == 'vue' else "import react from '@vitejs/plugin-react';"
        plugin_call = "vue()" if config.project.frontend_framework == 'vue' else "react()"

        vite_config_content = f"""
import {{ defineConfig }} from 'vite';
{plugin_import}

// https://vitejs.dev/config/
export default defineConfig({{
  plugins: [
    {plugin_call}
  ],
  server: {{
    proxy: {{
      '/api': {{
        target: 'http://127.0.0.1:{backend_port}',
        changeOrigin: true,
        secure: false,
      }},
    }},
  }},
}});
"""
        try:
            vite_config_path.write_text(vite_config_content, encoding='utf-8')
            logger.info(f"vite.config.js créé avec proxy vers le port {backend_port}")
        except IOError as e:
            logger.error(f"Impossible d'écrire vite.config.js: {e}")
            raise


    def _setup_backend_workspace(self):
        """Configure le workspace backend."""
        logger.info("Configuration du workspace backend_dev...")
        
        config = get_config()
        backend_path = Path(config.paths.backend_dev_path)
        backend_path.mkdir(parents=True, exist_ok=True)
        
        if config.project.wordpress_api_enabled:
            self._setup_wordpress_backend()
        else:
            self._setup_nodejs_backend()
        
        if self.npm.has_package_json(backend_path) and not self.npm.has_node_modules(backend_path):
            logger.info("Installation des dépendances npm pour backend_dev...")
            result = self.npm.install(backend_path)
            if result.failed:
                raise Exception(f"Installation npm backend échouée: {result.stderr}")
        
        if config.project.enable_database:
            self._setup_prisma_for_backend()
    
    def _setup_wordpress_backend(self):
        """Configure le backend WordPress."""
        config = get_config()
        backend_path = Path(config.paths.backend_dev_path)
        source_path = Path(config.paths.wordpress_backend_source)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Template WordPress introuvable: {source_path}")
        
        logger.info(f"Copie du backend WordPress depuis {source_path}...")
        
        if backend_path.exists() and any(backend_path.iterdir()):
            for item in backend_path.iterdir():
                if item.name == '.git':
                    continue # Ignorer le répertoire .git
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        
        # Copier le contenu du template, en ignorant le .git s'il existe dans la source
        def ignore_git(src, names):
            ignored_names = []
            if '.git' in names:
                ignored_names.append('.git')
            return set(ignored_names)

        shutil.copytree(source_path, backend_path, dirs_exist_ok=True, ignore=ignore_git)
        
        # Initialiser un nouveau dépôt Git si ce n'est pas déjà fait
        if not self.git.is_git_repo(backend_path):
            self.git.init(backend_path)
            self.git.add_all(backend_path)
            self.git.commit(backend_path, "Initial commit for WordPress backend", allow_empty=True)
        
        self._write_wordpress_env_file()
        result = self.npm.install(backend_path)
        if result.failed:
            raise Exception(f"Installation npm backend échouée: {result.stderr}")
        logger.info("Backend WordPress configuré")
    
    def _write_wordpress_env_file(self):
        """Écrit le fichier .env pour le backend WordPress."""
        config = get_config()
        backend_path = Path(config.paths.backend_dev_path)
        env_path = backend_path / '.env'
        
        with open(env_path, 'w', encoding='utf-8') as f:
            for key, value in config.project.wordpress_env.items():
                f.write(f"{key}={value}\n")
        
        logger.info(f"Fichier .env créé dans {backend_path}")
    
    def _setup_nodejs_backend(self):
        """Configure un backend Node.js basique."""
        config = get_config()
        backend_path = Path(config.paths.backend_dev_path)
        package_json_path = backend_path / 'package.json'
        
        if not package_json_path.exists():
            logger.info("Création d\'un projet Node.js basique pour backend_dev...")
            
            package_json = {
                "name": "backend-dev-server",
                "version": "1.0.0",
                "main": "server.js",
                "scripts": {"start": "nodemon server.js"},
                "dependencies": {"express": "^4.18.2", "cors": "^2.8.5"},
                "devDependencies": {"nodemon": "^2.0.22"}
            }
            
            if config.project.enable_database:
                package_json["dependencies"]["@prisma/client"] = "^5.17.0"
                package_json["devDependencies"]["prisma"] = "^5.17.0"
            
            with open(package_json_path, 'w', encoding='utf-8') as f:
                json.dump(package_json, f, indent=4)
            
            self._create_basic_server_js()
            
            result = self.npm.install(backend_path)
            if result.failed:
                raise Exception(f"Installation npm backend échouée: {result.stderr}")
    
    def _create_basic_server_js(self):
        """Crée un fichier server.js basique."""
        backend_path = Path(get_config().paths.backend_dev_path)
        server_js_path = backend_path / 'server.js'
        
        server_js_content = """const express = require('express');
const cors = require('cors');
const app = express();
const port = 3000;

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {
    res.send('Hello from the backend server!');
});

app.listen(port, () => {
    console.log(`Backend server listening at http://localhost:${port}`);
});
"""
        server_js_path.write_text(server_js_content, encoding='utf-8')
        logger.info("server.js créé")
    
    def _setup_prisma_for_backend(self):
        """Configure Prisma pour le backend."""
        backend_path = Path(get_config().paths.backend_dev_path)
        prisma_schema_path = backend_path / 'prisma' / 'schema.prisma'
        
        if not prisma_schema_path.exists():
            logger.info("Initialisation de Prisma...")
            result = self.npm.init_prisma(backend_path, provider='sqlite')
            if result.failed:
                logger.warning(f"Initialisation Prisma échouée: {result.stderr}")
                return
        
        env_path = backend_path / '.env'
        self._update_database_url_in_env(env_path)
        self._add_default_prisma_models(prisma_schema_path)
        
        logger.info("Lancement de la première migration Prisma...")
        result = self.npm.run_prisma_migrate(backend_path, name="initial_setup")
        if result.failed:
            logger.warning(f"Migration Prisma échouée: {result.stderr}")

        logger.info("Génération du client Prisma...")
        result = self.npm.run_prisma_generate(backend_path)
        if result.failed:
            logger.error(f"Génération du client Prisma échouée: {result.stderr}")
            return
        
        self._add_prisma_to_server_js()
        logger.info("Prisma configuré avec succès")
    
    def _update_database_url_in_env(self, env_path: Path):
        """Met à jour DATABASE_URL dans le fichier .env."""
        database_url = get_config().project.database_url
        
        if env_path.exists():
            lines = env_path.read_text(encoding='utf-8').splitlines()
            updated_lines = [line for line in lines if not line.startswith('DATABASE_URL=')]
            updated_lines.append(f'DATABASE_URL="{database_url}"')
            env_path.write_text('\n'.join(updated_lines) + '\n', encoding='utf-8')
        else:
            env_path.write_text(f'DATABASE_URL="{database_url}"\n', encoding='utf-8')
        
        logger.info(f"DATABASE_URL mise à jour dans {env_path}")
    
    def _add_default_prisma_models(self, schema_path: Path):
        """Ajoute des modèles par défaut au schema Prisma."""
        if not schema_path.exists() or 'model User' in schema_path.read_text(encoding='utf-8'):
            return
        
        default_models = """
model User {
  id      Int      @id @default(autoincrement())
  email   String   @unique
  name    String?
  posts   Post[]
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  content   String?
  published Boolean  @default(false)
  author    User     @relation(fields: [authorId], references: [id])
  authorId  Int
}
"""
        with open(schema_path, 'a', encoding='utf-8') as f:
            f.write(default_models)
        logger.info("Modèles Prisma par défaut ajoutés")
    
    def _add_prisma_to_server_js(self):
        """Ajoute l\'intégration Prisma à server.js."""
        backend_path = Path(get_config().paths.backend_dev_path)
        server_js_path = backend_path / 'server.js'
        
        if not server_js_path.exists() or 'PrismaClient' in server_js_path.read_text(encoding='utf-8'):
            return
        
        content = server_js_path.read_text(encoding='utf-8')
        prisma_code = """
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

process.on('beforeExit', async () => {
    await prisma.$disconnect();
});

app.get('/api/users', async (req, res) => {
    try {
        const users = await prisma.user.findMany();
        res.json(users);
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: 'Erreur lors de la récupération des utilisateurs.' });
    }
});
"""
        insert_pos = content.find('app.listen(port,')
        if insert_pos != -1:
            new_content = content[:insert_pos] + prisma_code + '\n' + content[insert_pos:]
            server_js_path.write_text(new_content, encoding='utf-8')
            logger.info("Prisma ajouté à server.js")
    
    def _setup_prod_workspace(self):
        """Configure le workspace de production."""
        logger.info("Configuration du workspace prod...")
        
        prod_path = Path(get_config().paths.prod_path)
        prod_path.mkdir(parents=True, exist_ok=True)
        
        if self.npm.has_package_json(prod_path) and not self.npm.has_node_modules(prod_path):
            logger.info("Installation des dépendances npm pour prod...")
            result = self.npm.install(prod_path)
            if result.failed:
                logger.warning(f"Installation npm prod échouée: {result.stderr}")
    
    def _setup_git_repositories(self):
        """Initialise les dépôts Git pour dev et backend_dev."""
        logger.info("Configuration des dépôts Git...")
        
        config = get_config()
        repo_url = config.project.repository_url
        workspaces = [
            ('dev', Path(config.paths.dev_path)),
            ('backend_dev', Path(config.paths.backend_dev_path))
        ]
        
        for name, path in workspaces:
            self._setup_git_for_workspace(name, path, repo_url)
    
    def _setup_git_for_workspace(self, name: str, path: Path, repo_url: Optional[str]):
        """Configure Git pour un workspace spécifique."""
        if not self.git.is_git_repo(path):
            logger.info(f"Initialisation de Git pour {name}...")
            self.git.init(path)
            self.git.add_all(path)
            self.git.commit(path, "Initial commit", allow_empty=True)
            if repo_url:
                self.git.add_remote(path, 'origin', repo_url)
        else:
            logger.info(f"Dépôt Git existant pour {name}")
            if repo_url and self.git.get_remote_url(path, 'origin') != repo_url:
                self.git.set_remote_url(path, 'origin', repo_url)