"""
Routes API principales pour la gestion du projet.
"""
import os
import time
import shutil
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template

from config.settings import get_config
from config.logging import get_logger
from app.services.process_service import ProcessService
from app.services.git_service import GitService
from app.services.npm_service import NpmService
from app.services.workspace_service import WorkspaceService
from app.services.gemini_service import GeminiService
from app.services.claude_service import ClaudeService
from app.services.chroma_service import ChromaService
from app.utils.validators import validate_file_path, ValidationError
from app.utils.exceptions import GitError
from app.models.actions import ActionType, FileAction, ShellCommandAction

logger = get_logger(__name__)

api_bp = Blueprint('api', __name__)

# Services
_process_service: ProcessService = None
_git_service: GitService = None
_npm_service: NpmService = None
_workspace_service: WorkspaceService = None
_gemini_service: GeminiService = None
_claude_service: ClaudeService = None

# Historique de la conversation en mémoire
_prompt_history: list = []


def init_services(process_svc, git_svc, npm_svc, workspace_svc, gemini_svc, claude_svc):
    """Initialise les services (appelé depuis l'app factory)."""
    global _process_service, _git_service, _npm_service, _workspace_service, _gemini_service, _claude_service
    _process_service = process_svc
    _git_service = git_svc
    _npm_service = npm_svc
    _workspace_service = workspace_svc
    _gemini_service = gemini_svc
    _claude_service = claude_svc


@api_bp.route('/api/clear_history', methods=['POST'])
def clear_history():
    """Vide l'historique de la conversation."""
    global _prompt_history
    _prompt_history.clear()
    logger.info("Historique de la conversation vidé.")
    return jsonify({'message': 'Historique vidé avec succès.'})


@api_bp.route('/')
def index():
    """Page d'accueil (redirige vers la page principale de l'IDE)."""
    return redirect(url_for('api.main_page'))


@api_bp.route('/main')
def main_page():
    """Affiche la page principale de l'application (IDE)."""
    config = get_config()
    logger.info(f"Chargement de la page principale. Projet actuel: {config.paths.dev_path}")
    project_name = Path(config.paths.dev_path).parent.name
    
    # Déterminer quels services d'IA sont actifs
    ai_services = {
        'gemini_enabled': config.gemini.enabled and _gemini_service.is_available(),
        'claude_enabled': config.claude.enabled and _claude_service.is_available()
    }
    
    return render_template('index.html', project_name=project_name, ai_services=ai_services)


from app.services.chroma_service import get_chroma_service

# ... (le reste des importations)

# ... (le reste du fichier jusqu'à la route)

@api_bp.route('/api/index_project', methods=['POST'])
def index_project():
    """Scanne et indexe tous les workspaces du projet dans ChromaDB."""
    chroma_service = get_chroma_service()
    if not chroma_service:
        return jsonify({'error': 'ChromaDB service is not initialized.'}), 500
    
    try:
        config = get_config()
        workspaces = {
            "frontend": config.paths.dev_path,
            "backend": config.paths.backend_dev_path
        }
        
        logger.info("Indexing all project workspaces...")
        result = chroma_service.index_workspaces(workspaces)

        if result['status'] == 'error':
             return jsonify({
                 'error': 'An error occurred during indexing.',
                 'details': result.get('message')
            }), 500

        total_indexed = result.get('count', 0)
        return jsonify({'message': f'Successfully indexed {total_indexed} documents.'})

    except Exception as e:
        logger.exception("Error during project indexing")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/propose_changes', methods=['POST'])
def propose_changes():
    """
    Génère des changements de code via l'IA en utilisant ChromaDB et l'historique.
    """
    global _prompt_history
    prompt = request.json.get('prompt')
    if not prompt:
        return jsonify({'error': 'Le prompt est manquant.'}), 400
    
    chroma_service = get_chroma_service()
    if not chroma_service:
        return jsonify({'error': 'ChromaDB service is not initialized.'}), 500

    logger.info(f"Requête reçue: '{prompt}'")
    
    try:
        config = get_config()
        
        # Sauvegarde préventive des changements locaux
        try:
             _git_service.stash(config.paths.dev_path, "Sauvegarde avant modification IA")
        except Exception as e:
             logger.warning(f"Impossible de stash les changements: {e}")

        # Sélectionner le service d'IA actif
        ai_service = None
        if config.claude.enabled:
            ai_service = _claude_service
            logger.info("Utilisation de Claude Service.")
        elif config.gemini.enabled:
            ai_service = _gemini_service
            logger.info("Utilisation de Gemini Service.")
        
        if not ai_service or not ai_service.is_available():
            return jsonify({'error': "Aucun service d'IA n'est configuré ou disponible."}), 500

        # 1. Interroger ChromaDB pour obtenir un contexte pertinent
        logger.info("Querying ChromaDB for relevant context...")
        relevant_docs = chroma_service.query(prompt, n_results=5)
        
        context_files = []
        if relevant_docs:
            for doc, meta in relevant_docs:
                context_files.append(f"--- File: {meta['source']} ---\n{doc}\n---")
        
        context_str = "\n".join(context_files)
        logger.info(f"Found {len(relevant_docs)} relevant documents.")

        # 2. Collecter l'arborescence des fichiers
        _, file_paths = ai_service.collect_project_files()
        file_tree = "\n".join(file_paths)
        
        # 3. Mettre à jour et appeler l'IA avec l'historique
        _prompt_history.append({"role": "user", "content": prompt})
        response = ai_service.generate_changes_with_context(
            prompt,
            context_str,
            file_tree,
            _prompt_history
        )
        _prompt_history.append({"role": "assistant", "content": response.explanation})
        
        logger.info(f"Actions générées: {len(response.actions)}")
        
        if not response.actions:
            return jsonify({
                'explanation': response.explanation,
                'diff': ''
            })
        
        # 4. Exécuter les actions (logique existante)
        action_errors = []
        npm_install_required = {'dev': False, 'backend_dev': False}
        dev_files_modified = False
        
        allowed_workspaces = {
            'dev': config.paths.dev_path,
            'backend_dev': config.paths.backend_dev_path
        }
        
        for action in response.actions:
            try:
                if isinstance(action, ShellCommandAction):
                    _execute_shell_action(action, config, action_errors)
                
                elif isinstance(action, FileAction):
                    result = _execute_file_action(
                        action,
                        allowed_workspaces,
                        config.paths.base_dir
                    )
                    
                    if result['workspace'] == 'dev' and result['filename'] == 'package.json':
                        npm_install_required['dev'] = True
                    elif result['workspace'] == 'backend_dev' and result['filename'] == 'package.json':
                        npm_install_required['backend_dev'] = True
                    
                    if result['workspace'] == 'dev':
                        dev_files_modified = True
            
            except Exception as e:
                error_msg = f"Erreur lors de l'action: {str(e)}"
                logger.error(error_msg)
                action_errors.append(error_msg)
        
        # 5. npm install et redémarrage des serveurs (logique existante)
        if npm_install_required['dev']:
            logger.info("package.json modifié (dev), exécution de npm install...")
            _npm_service.install(config.paths.dev_path)
        
        if npm_install_required['backend_dev']:
            logger.info("package.json modifié (backend), exécution de npm install...")
            _npm_service.install(config.paths.backend_dev_path)
            _process_service.stop_backend_server()
            time.sleep(1)
            _process_service.start_backend_server(config.paths.backend_dev_path, config.servers.backend_port)
        
        # Redémarrer le serveur dev si des fichiers ont été modifiés OU si npm install a été exécuté
        if dev_files_modified or npm_install_required['dev']:
            logger.info("Fichiers dev modifiés ou npm install exécuté, redémarrage du serveur...")
            _process_service.stop_dev_server()
            time.sleep(2)
            _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
        
        # 6. Diff (Tentative best-effort, sinon ignoré)
        try:
             # On tente quand même un diff pour l'affichage, si git est dispo
             diff_result = _git_service.diff(config.paths.dev_path)
        except Exception:
             diff_result = None
        
        # 7. Préparer la réponse
        explanation = response.explanation
        if action_errors:
            explanation += "\n\nDes erreurs sont survenues:\n" + "\n".join(action_errors)
        
        return jsonify({'explanation': explanation})
    
    except Exception as e:
        logger.exception("Erreur lors du traitement de la requête")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/approve_changes', methods=['POST'])
def approve_changes():
    """
    Approuve les changements: Copie simple de dev vers prod (SANS Git).
    """
    logger.info("Approbation des changements (Mode Copie Simple)...")
    
    config = get_config()
    dev_path = config.paths.dev_path
    prod_path = config.paths.prod_path
    
    _process_service.stop_dev_server()
    
    try:
        if not prod_path:
            raise Exception('PROD_PATH non défini.')

        # S'assurer que prod existe
        if not prod_path.exists():
            prod_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Création du dossier prod: {prod_path}")

        # Liste des dossiers/fichiers à ignorer lors de la copie/nettoyage
        # On ignore .git pour ne pas casser le repo s'il existe dans prod
        # On ignore node_modules pour éviter de copier des milliers de fichiers (on fera npm install si besoin)
        ignore_patterns = shutil.ignore_patterns('.git', 'node_modules', '.vite', '__pycache__', '.env', 'dist')
        
        # 1. Nettoyer prod (sauf .git et ce qu'on veut garder)
        logger.info("Nettoyage du dossier prod...")
        ignored_names = set(['.git', 'node_modules', '.vite', '__pycache__', '.env', 'dist'])
        
        for item in prod_path.iterdir():
            if item.name in ignored_names:
                continue
            
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                logger.warning(f"Impossible de supprimer {item}: {e}")

        # 2. Copier dev vers prod
        logger.info("Copie des fichiers de dev vers prod...")
        shutil.copytree(
            dev_path, 
            prod_path, 
            dirs_exist_ok=True, 
            ignore=ignore_patterns
        )
        
        logger.info("Copie terminée.")
        
        _process_service.start_dev_server(dev_path, config.servers.dev_port)
        return jsonify({'message': 'Changements approuvés et copiés vers prod.'})

    except Exception as e:
        logger.exception("Erreur lors de l'approbation (copie)")
        _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/push_changes', methods=['POST'])
def push_changes():
    """
    Déclenche un Git Push manuel depuis le dossier PROD.
    """
    logger.info("Push manuel demandé...")
    config = get_config()
    prod_path = config.paths.prod_path
    target_branch = config.project.branch_name # Généralement 'main'
    
    try:
        if not _git_service.is_git_repo(prod_path):
            return jsonify({'error': "Le dossier de production n'est pas un dépôt Git."}), 400
            
        # AUTO-CORRECTION : Vérifier la branche courante
        current_branch = _git_service.get_current_branch(prod_path)
        logger.info(f"Branche courante: {current_branch}, Cible: {target_branch}")

        if current_branch == 'master' and target_branch != 'master':
            logger.warning(f"Branche 'master' détectée. Renommage automatique vers '{target_branch}'...")
            from app.utils.shell import run_command
            run_command(f'git branch -M {target_branch}', cwd=prod_path)
            current_branch = target_branch

        logger.info("Exécution de git add .")
        add_res = _git_service.add_all(prod_path)
        if add_res.failed:
             return jsonify({'error': f"Erreur git add: {add_res.stderr}"}), 500
        
        logger.info("Exécution de git commit")
        # On allow_empty au cas où rien n'a changé mais l'utilisateur veut quand même push
        commit_res = _git_service.commit(prod_path, "Mise à jour via Gemini CLI (Push Manuel)", allow_empty=True)
        if commit_res.failed:
             return jsonify({'error': f"Erreur git commit: {commit_res.stderr}"}), 500
        
        # Check remote presence
        if not _git_service.get_remote_url(prod_path, 'origin'):
             return jsonify({'error': "Aucun remote 'origin' n'est configuré sur le dossier de production."}), 400

        logger.info(f"Exécution de git push origin {target_branch}")
        # On utilise set_upstream=True pour être sûr
        result = _git_service.push(prod_path, 'origin', target_branch, set_upstream=True)
        
        if result.failed:
             return jsonify({'error': f"Erreur lors du push:\n{result.stderr}"}), 500
             
        return jsonify({'message': 'Push réussi vers le dépôt distant.'})

    except Exception as e:
        logger.exception("Erreur lors du push manuel")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/rollback_changes', methods=['POST'])
def rollback_changes():
    """Annule les changements locaux dans dev (Hard Reset + Clean)."""
    config = get_config()
    try:
        logger.info("Rollback demandé...")
        _git_service.reset_hard(config.paths.dev_path)
        _git_service.clean(config.paths.dev_path)
        
        # On redémarre le serveur pour être sûr que tout est propre
        _process_service.stop_dev_server()
        time.sleep(1)
        _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
        
        return jsonify({'message': 'Changements annulés avec succès.'})
    except Exception as e:
        logger.exception("Erreur lors du rollback")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/undo_change', methods=['POST'])
def undo_change():
    """Annule la dernière modification de l'IA (Restore stash)."""
    config = get_config()
    try:
        logger.info("Undo demandé (Stash Pop)...")
        # 1. On nettoie l'état actuel (qui est "mauvais" selon l'utilisateur)
        _git_service.reset_hard(config.paths.dev_path)
        _git_service.clean(config.paths.dev_path)
        
        # 2. On restaure l'état sauvegardé
        res = _git_service.stash_pop(config.paths.dev_path)
        if res.failed:
             return jsonify({'error': f"Impossible d'annuler (stash pop failed): {res.stderr}"}), 500
        
        # Redémarrage serveur
        _process_service.stop_dev_server()
        time.sleep(1)
        _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
             
        return jsonify({'message': 'Dernière modification annulée.'})
    except Exception as e:
        logger.exception("Erreur lors du Undo")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/confirm_change', methods=['POST'])
def confirm_change():
    """Confirme la dernière modification de l'IA (Drop stash)."""
    config = get_config()
    try:
        logger.info("Confirmation des changements (Drop Stash)...")
        res = _git_service.stash_drop(config.paths.dev_path)
        # On ne bloque pas si le drop échoue (ça veut juste dire qu'il n'y avait rien à drop ou erreur mineure)
        if res.failed:
            logger.warning(f"Stash drop failed: {res.stderr}")
            
        return jsonify({'message': 'Changements confirmés.'})
    except Exception as e:
        logger.exception("Erreur lors du Confirm")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/setup_and_start', methods=['POST'])
def setup_and_start():
    """
    Initialise l'environnement (clone, installe les dépendances)
    et démarre les serveurs de développement.
    """
    try:
        logger.info("Configuration de l'environnement de travail...")
        _workspace_service.setup_all()
        
        config = get_config()
        
        logger.info("Démarrage des serveurs de développement...")
        _process_service.start_dev_server(
            config.paths.dev_path,
            config.servers.dev_port
        )
        _process_service.start_backend_server(
            config.paths.backend_dev_path,
            config.servers.backend_port
        )
        
        # Initialiser le service ChromaDB avec le nom du projet
        project_name = config.paths.dev_path.parent.name
        from app.services.chroma_service import init_chroma_service
        init_chroma_service(project_name)
        
        return jsonify({'message': 'Environnement démarré avec succès.'})
    
    except Exception as e:
        logger.exception("Erreur lors de l'initialisation de l'environnement")
        return jsonify({'message': str(e)}), 500


# ... (le reste des routes reste inchangé) ...

# --- Fonctions helper ---
def _execute_file_action(action: FileAction, allowed_workspaces: dict, base_dir: Path) -> dict:
    """Exécute une action sur un fichier."""
    workspace_base, absolute_path = validate_file_path(action.file_path, allowed_workspaces)
    workspace_name = 'dev' if workspace_base == allowed_workspaces['dev'] else 'backend_dev'
    
    if action.action in [ActionType.CREATE, ActionType.UPDATE]:
        content = action.get_content()
        if content is None:
            raise ValueError(f"Contenu manquant pour {action.action}")
        
        if absolute_path.suffix in ('.js', '.jsx', '.ts', '.tsx'):
            content = content.replace('\\', '/')
        
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(content, encoding='utf-8')
        logger.info(f"{action.action}: {action.file_path}")
    
    elif action.action == ActionType.DELETE:
        if absolute_path.exists():
            absolute_path.unlink()
            logger.info(f"DELETE: {action.file_path}")
    
    return {'workspace': workspace_name, 'filename': absolute_path.name}


def _execute_shell_action(action: ShellCommandAction, config, errors: list):
    """Exécute une commande shell."""
    from app.utils.shell import run_command
    
    command = action.command
    cwd_rel = action.cwd
    
    if cwd_rel and cwd_rel.startswith('dev/'):
        actual_cwd = config.paths.dev_path
    elif cwd_rel and cwd_rel.startswith('backend_dev/'):
        actual_cwd = config.paths.backend_dev_path
    else:
        actual_cwd = config.paths.base_dir
    
    logger.info(f"Commande shell: {command} (cwd={actual_cwd})")
    result = run_command(command, cwd=actual_cwd)
    
    if result.failed:
        error = f"Commande échouée ({result.returncode}): {command}\n{result.stderr}"
        errors.append(error)
        logger.error(error)
    else:
        logger.info(f"Commande réussie: {command}")