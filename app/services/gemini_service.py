import fnmatch
import json
import os
from pathlib import Path
from typing import Dict, List, Set

# Importations de configuration/modèles (présumées existantes)
from config.settings import AppConfig
from app.models.actions import GeminiResponse
from config.logging import get_logger

logger = get_logger(__name__)


class GeminiService:
    """Gère les interactions avec l'API Gemini en utilisant les system_instructions."""

    def __init__(self, config: AppConfig):
        self.config = config
        
        if not config.gemini.enabled:
            logger.warning("Gemini n'est pas activé ou configuré")
    
    def is_available(self) -> bool:
        """Vérifie si Gemini est disponible."""
        return self.config.gemini.enabled and self.config.gemini.client is not None
    
    def generate_changes(
        self,
        prompt: str,
        project_files: Dict[str, str],
        file_tree: str
    ) -> GeminiResponse:
        """
        Génère des changements de code via Gemini sans historique, en utilisant system_instruction.
        """
        if not self.is_available():
            raise Exception(
                "Gemini n'est pas disponible. Vérifiez la configuration."
            )
        
        # 1. Construire le prompt utilisateur (contexte dynamique)
        context_str = self._build_context(project_files)
        user_prompt = self._build_user_prompt(
            prompt,
            file_tree,
            context_str,
            history=[] # Pas d'historique dans cette version
        )
        
        # 2. Définir les instructions système permanentes
        system_instructions = self._get_system_instructions()
        
        # Appeler l'API
        logger.info(f"PROMPT UTILISATEUR ENVOYÉ À GEMINI:\n{user_prompt}")
        logger.info("Appel à l'API Gemini avec System Instructions...")
        try:
            model = self.config.gemini.client.GenerativeModel(
                model_name=self.config.gemini.model_name,
                system_instruction=system_instructions
            )
            response = model.generate_content(
                contents=user_prompt
            )
            
            # Parser la réponse
            response_text = response.text.strip()
            logger.debug(f"Réponse Gemini (brute): {response_text[:500]}...")
            
            # Extraire le JSON
            json_data = self._extract_json(response_text)
            
            # Convertir en GeminiResponse
            return GeminiResponse.from_dict(json_data)
        
        except Exception as e:
            logger.exception(f"Erreur lors de l'appel Gemini: {e}")
            raise
    
    def generate_changes_with_context(
        self,
        prompt: str,
        rag_context: str,
        file_tree: str,
        history: List[Dict[str, str]]
    ) -> GeminiResponse:
        """
        Génère des changements de code via Gemini en utilisant un contexte RAG et un historique,
        avec les instructions système.
        """
        if not self.is_available():
            raise Exception("Gemini n'est pas disponible.")

        # 1. Construire le prompt utilisateur (contexte dynamique)
        user_prompt = self._build_user_prompt(
            prompt,
            file_tree,
            rag_context, # Utilise le contexte RAG
            history
        )
        
        # 2. Définir les instructions système permanentes
        system_instructions = self._get_system_instructions()
        
        logger.info("Appel à l'API Gemini avec contexte RAG et historique (et System Instructions)...")
        try:
            model = self.config.gemini.client.GenerativeModel(
                model_name=self.config.gemini.model_name,
                system_instruction=system_instructions
            )
            response = model.generate_content(
                contents=user_prompt
            )
            response_text = response.text.strip()
            logger.debug(f"Réponse Gemini (brute): {response_text[:500]}...")
            
            json_data = self._extract_json(response_text)
            return GeminiResponse.from_dict(json_data)
        
        except Exception as e:
            logger.exception(f"Erreur lors de l'appel Gemini: {e}")
            raise

    # --- MÉTHODES PRIVÉES DE CONTEXTE ---

    def _get_system_instructions(self) -> str:
        """
        Retourne les instructions système permanentes (Rôle, Architecture, Règles) 
        qui étaient auparavant dans le meta-prompt.
        """
        framework_instructions = self._get_framework_instructions(self.config.project.frontend_framework)
        backend_instructions = self._get_backend_instructions(self.config.project.wordpress_api_enabled)
        backend_url = self.config.servers.backend_url
        
        return f"""<role>
Tu es un assistant expert en développement full-stack. Ta mission est de comprendre la demande de l'utilisateur et de la traduire en une série d'actions précises sous forme de JSON pour modifier un projet web.
</role>

<project_architecture>
- **app.py**: Un serveur Flask en Python qui sert de contrôleur principal.
{framework_instructions}
- **Serveur Backend (Node.js)**: Dans `backend_dev`. Il gère la logique métier. Le frontend communique avec lui via `{backend_url}`.
{backend_instructions}
</project_architecture>

<json_format_instructions>
Génère une réponse JSON unique et valide pour effectuer les changements.
Le JSON doit contenir \"explanation\" (en français) et \"actions\" (une liste d'opérations).

Opérations valides:
1. `UPDATE`: {{"action": "UPDATE", "file_path": "dev/src/App.vue", "new_content": "..."}}
2. `CREATE`: {{"action": "CREATE", "file_path": "dev/src/components/New.vue", "content": "..."}}
3. `DELETE`: {{"action": "DELETE", "file_path": "dev/src/old.js"}}
4. `RUN_SHELL_COMMAND`: {{"action": "RUN_SHELL_COMMAND", "command": "npm install axios", "cwd": "dev/"}}

Règles critiques :
- `file_path` doit être préfixé par 'dev/' ou 'backend_dev/'.
- Le contenu (`content` ou `new_content`) doit être le contenu **intégral** du fichier.
- Échappe correctement les caractères spéciaux dans les chaînes JSON (`\\\"`, `\\\\`, `\\n`).
- Ta réponse ne doit contenir **QUE** le bloc JSON.
- Tailwind doit être importé de cette manière :
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  ```
  N'utilisez JAMAIS la syntaxe `@import "tailwindcss";`.
</json_format_instructions>
"""

    def _build_user_prompt(
        self,
        user_prompt: str,
        file_tree: str,
        context_str: str,
        history: List[Dict[str, str]]
    ) -> str:
        """Construit le prompt utilisateur contenant le contexte dynamique."""
        
        context_section_title = "file_contents"
        if "--- File:" in context_str: 
            context_section_title = "relevant_file_extracts"

        history_str = "\n".join([f"<turn role='{turn['role']}'>\n{turn['content']}\n</turn>" for turn in history])

        return f"""<conversation_history>
{history_str}
</conversation_history>

<user_request>
{user_prompt}
</user_request>

<project_structure>
{file_tree}
</project_structure>

<{context_section_title}>
{context_str}
</{context_section_title}>
"""

    def _build_context(self, project_files: Dict[str, str]) -> str:
        """Construit le contexte des fichiers pour Gemini."""
        parts = []
        for path, content in project_files.items():
            parts.append(f"--- {path} ---\n{content}")
        return "\n\n".join(parts)
    
    def _extract_json(self, response_text: str) -> dict:
        """Extrait le JSON de la réponse Gemini en cherchant le bloc le plus externe."""
        logger.debug(f"Réponse Gemini complète pour extraction JSON: {response_text}")

        json_str = response_text
        
        # Logique d'extraction du JSON inchangée
        if '```json' in response_text:
            start_index = response_text.find('```json') + len('```json')
            end_index = response_text.rfind('```')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_str = response_text[start_index:end_index].strip()
        elif '```' in response_text:
            start_index = response_text.find('```') + len('```')
            end_index = response_text.rfind('```')
            if start_index != -1 and end_index != -1 and start_index < end_index:
                json_str = response_text[start_index:end_index].strip()
        
        if not json_str.startswith('{') or not json_str.endswith('}'):
            json_start = json_str.find('{')
            json_end = json_str.rfind('}')
            if json_start != -1 and json_end != -1 and json_start < json_end:
                json_str = json_str[json_start:json_end+1]
            else:
                json_str = response_text.strip()

        try:
            logger.debug(f"Tentative de parsing JSON (extrait): {json_str}")
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON invalide de Gemini: {e}. Tentative de parsing: '{json_str}'. Réponse brute complète: '{response_text}'")
            raise ValueError(f"Réponse JSON invalide de Gemini: {e}")
    
    # --- MÉTHODES PRIVÉES DE CONFIGURATION ET D'ANALYSE DE FICHIERS ---
    
    def _get_framework_instructions(self, framework: str) -> str:
        # ... (contenu inchangé) ...
        if framework == 'vue':
            return "- **Serveur Frontend (Vite + Vue.js)**: Dans `dev`. Utilise la Composition API de Vue 3."
        elif framework == 'react':
            return "- **Serveur Frontend (Vite + React)**: Dans `dev`. Utilise les Hooks de React."
        else:
            return f"- **Serveur Frontend ({framework})**: Dans `dev`."
        
    def _get_backend_instructions(self, wordpress_api_enabled) -> str:
        # ... (contenu inchangé) ...
        if wordpress_api_enabled:
             return "- Le backend utilise une API WordPress/WooCommerce. Ne modifie pas `server.js` ou `.env` sans instruction explicite."
        return ""

    def _parse_gitignore(self, gitignore_path: Path) -> List[str]:
        """Parse un fichier .gitignore et retourne une liste de patterns."""
        if not gitignore_path.exists():
            return []
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]

    def _is_binary(self, file_path: Path) -> bool:
        """Vérifie si un fichier est probablement binaire."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True

    def collect_project_files(self) -> tuple[Dict[str, str], List[str]]:
        """
        Collecte tous les fichiers pertinents du projet en respectant .gitignore.
        """
        workspaces = {
            'dev': self.config.paths.dev_path,
            'backend_dev': self.config.paths.backend_dev_path
        }
        
        default_excluded_dirs = {'node_modules', 'dist', '__pycache__', '.vite', '.git', '.vscode', '.idea'}
        
        project_files = {}
        file_paths = []
        
        for prefix, base_path in workspaces.items():
            if not base_path.exists():
                continue

            gitignore_patterns = self._parse_gitignore(base_path / '.gitignore')
            
            for root, dirs, files in os.walk(base_path, topdown=True):
                root_path = Path(root)
                
                excluded_here = set()
                for d in dirs:
                    dir_path_rel = (root_path / d).relative_to(base_path)
                    if d in default_excluded_dirs or any(fnmatch.fnmatch(str(dir_path_rel), p) for p in gitignore_patterns):
                        excluded_here.add(d)
                dirs[:] = [d for d in dirs if d not in excluded_here]

                for filename in files:
                    if filename == '.gitignore': continue

                    file_path_abs = root_path / filename
                    file_path_rel = file_path_abs.relative_to(base_path)

                    if any(fnmatch.fnmatch(str(file_path_rel), p) for p in gitignore_patterns):
                        continue
                    
                    if self._is_binary(file_path_abs):
                        continue

                    file_path_rel_normalized = f"{prefix}/{str(file_path_rel).replace('\\', '/')}"
                    
                    try:
                        with open(file_path_abs, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        project_files[file_path_rel_normalized] = content
                        file_paths.append(file_path_rel_normalized)
                    
                    except Exception as e:
                        logger.warning(f"Impossible de lire {file_path_abs}: {e}")
        
        return project_files, file_paths