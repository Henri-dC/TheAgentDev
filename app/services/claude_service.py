import fnmatch
import json
import os
from pathlib import Path
from typing import Dict, List

import anthropic
from config.settings import AppConfig
from app.models.actions import GeminiResponse
from config.logging import get_logger

logger = get_logger(__name__)


class ClaudeService:
    """Gère les interactions avec l'API Claude (Anthropic)."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.client = None
        if self.config.claude.enabled and self.config.claude.api_key:
            try:
                self.client = anthropic.Anthropic(api_key=self.config.claude.api_key)
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation du client Anthropic: {e}")
        elif not config.claude.enabled:
            logger.warning("Claude n'est pas activé dans la configuration.")
        else:
            logger.warning("CLAUDE_API_KEY n'est pas configurée.")

    def is_available(self) -> bool:
        """Vérifie si Claude est disponible."""
        return self.config.claude.enabled and self.client is not None

    def generate_changes_with_context(
        self,
        prompt: str,
        rag_context: str,
        file_tree: str,
        history: List[Dict[str, str]]
    ) -> GeminiResponse:
        """
        Génère des changements de code via Claude en utilisant un contexte RAG et un historique.
        """
        if not self.is_available():
            raise Exception("Claude n'est pas disponible. Vérifiez la configuration.")

        system_prompt, user_prompt = self._build_prompts(
            prompt,
            file_tree,
            rag_context,
            self.config.project.frontend_framework,
            self.config.project.wordpress_api_enabled
        )

        # Construire les messages en incluant l'historique
        messages = history + [{"role": "user", "content": user_prompt}]

        logger.info("Appel à l'API Claude avec contexte RAG et historique...")
        try:
            message = self.client.messages.create(
                model=self.config.claude.model_name,
                max_tokens=8000,
                system=system_prompt,
                messages=messages
            )
            
            response_text = message.content[0].text.strip()
            logger.debug(f"Réponse Claude (brute): {response_text[:500]}...")

            json_data = self._extract_json(response_text)
            return GeminiResponse.from_dict(json_data)

        except Exception as e:
            logger.exception(f"Erreur lors de l'appel à Claude: {e}")
            raise

    def _extract_json(self, response_text: str) -> dict:
        """Extrait le JSON de la réponse en cherchant le bloc le plus externe."""
        logger.debug(f"Réponse Claude complète pour extraction JSON: {response_text}")

        json_str = response_text
        
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
            logger.error(f"JSON invalide de Claude: {e}. Tentative de parsing: '{json_str}'. Réponse brute complète: '{response_text}'")
            raise ValueError(f"Réponse JSON invalide de Claude: {e}")

    def _build_prompts(
        self,
        user_prompt: str,
        file_tree: str,
        context_str: str,
        frontend_framework: str,
        wordpress_api_enabled: bool
    ) -> tuple[str, str]:
        """Construit les prompts système et utilisateur pour Claude."""
        
        framework_instructions = self._get_framework_instructions(frontend_framework)
        backend_instructions = self._get_backend_instructions(wordpress_api_enabled)
        backend_url = self.config.servers.backend_url

        system_prompt = f"""Tu es un assistant expert en développement full-stack. Ta mission est de comprendre la demande de l'utilisateur et de la traduire en une série d'actions précises sous forme de JSON pour modifier un projet web.

<project_architecture>
- **app.py**: Un serveur Flask en Python qui sert de contrôleur principal.
{framework_instructions}
- **Serveur Backend (Node.js)**: Dans `backend_dev`. Il gère la logique métier. Le frontend communique avec lui via `{backend_url}`.
{backend_instructions}
</project_architecture>

<instructions>
Génère une réponse JSON unique et valide pour effectuer les changements.
Le JSON doit contenir "explanation" (en français) et "actions" (une liste d'opérations).

Opérations valides:
1. `UPDATE`: {{"action": "UPDATE", "file_path": "dev/src/App.vue", "new_content": "..."}}
2. `CREATE`: {{"action": "CREATE", "file_path": "dev/src/components/New.vue", "content": "..."}}
3. `DELETE`: {{"action": "DELETE", "file_path": "dev/src/old.js"}}
4. `RUN_SHELL_COMMAND`: {{"action": "RUN_SHELL_COMMAND", "command": "npm install axios", "cwd": "dev/"}}

Règles critiques :
- `file_path` doit être préfixé par 'dev/' ou 'backend_dev/'.
- Le contenu (`content` ou `new_content`) doit être le contenu **intégral** du fichier.
- Échappe correctement les caractères spéciaux dans les chaînes JSON (`\"`, `\\`, `\n`).
- Ta réponse ne doit contenir **QUE** le bloc JSON, sans texte ou formatage supplémentaire.
- **Tailwind CSS v4** est utilisé pour les projets React :
  - Utilisez la syntaxe `@import "tailwindcss";` dans le CSS principal.
  - La configuration du thème se fait via des variables CSS ou le bloc `@theme` dans le CSS, PAS dans `tailwind.config.js`.
</instructions>
"""

        context_section_title = "relevant_file_extracts"

        user_prompt_full = f"""<user_request>
{user_prompt}
</user_request>

<project_structure>
{file_tree}
</project_structure>

<{context_section_title}>
{context_str}
</{context_section_title}>
"""
        return system_prompt, user_prompt_full

    def _get_framework_instructions(self, framework: str) -> str:
        if framework == 'vue':
            return "- **Serveur Frontend (Vite + Vue.js)**: Dans `dev`. Utilise la Composition API de Vue 3."
        elif framework == 'react':
            return "- **Serveur Frontend (Vite + React)**: Dans `dev`. Utilise les Hooks de React."
        else:
            return f"- **Serveur Frontend ({framework})**: Dans `dev`."
        
    def _get_backend_instructions(self, wordpress_api_enabled) -> str:
        if wordpress_api_enabled:
             return "- Le backend utilise une API WordPress/WooCommerce. Ne modifie pas `server.js` ou `.env` sans instruction explicite."
        return ""

    def _parse_gitignore(self, gitignore_path: Path) -> List[str]:
        if not gitignore_path.exists():
            return []
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]

    def _is_binary(self, file_path: Path) -> bool:
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True

    def collect_project_files(self) -> tuple[Dict[str, str], List[str]]:
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
