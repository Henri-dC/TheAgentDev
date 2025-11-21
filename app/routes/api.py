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
        
        # Sauvegarder l'état actuel avant les changements de l'IA
        _git_service.stash(config.paths.dev_path)

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
        
        # 6. Générer le diff
        diff_result = _git_service.diff(config.paths.dev_path)
        
        # 7. Préparer la réponse
        explanation = response.explanation
        if action_errors:
            explanation += "\n\nDes erreurs sont survenues:\n" + "\n".join(action_errors)
        
        return jsonify({'explanation': explanation})
    
    except Exception as e:
        logger.exception("Erreur lors du traitement de la requête")
        return jsonify({'error': str(e)}), 500

# ... (le reste des routes reste inchangé) ...

@api_bp.route('/api/approve_changes', methods=['POST'])
def approve_changes():
    """
    Approuve les changements: copie dev → prod et push.
    """
    logger.info("Approbation des changements...")
    
    config = get_config()
    dev_path = config.paths.dev_path
    prod_path = config.paths.prod_path
    branch_name = config.project.branch_name
    repo_url = config.project.repository_url
    
    _process_service.stop_dev_server()
    
    try:
        if not _git_service.status(dev_path).stdout.strip():
            _process_service.start_dev_server(dev_path, config.servers.dev_port)
            return jsonify({'message': 'Aucun changement à approuver.'})
        
        changed_files = _git_service.get_changed_files(dev_path)
        if not prod_path:
            raise Exception('PROD_PATH non défini.')
        
        # --- Synchronisation PROD ---
        logger.info(f"Synchronisation de {prod_path} avec origin/{branch_name}...")
        
        # S'assurer que le remote est bon
        if repo_url:
            _git_service.set_remote_url(prod_path, 'origin', repo_url)

        # Fetch d'abord pour connaitre l'état du remote
        _git_service.fetch(prod_path)
        
        # Vérifier si la branche existe localement
        if not _git_service.branch_exists(prod_path, branch_name):
            logger.info(f"Branche {branch_name} introuvable localement dans prod. Tentative de création...")
            # Essayer de créer depuis origin/branch_name
            result = _git_service.checkout(prod_path, branch_name) # Git checkout gère souvent la création auto si remote existe
            if result.failed:
                # Si échec (ex: pas de remote correspondant), créer une branche orpheline ou depuis HEAD
                logger.warning(f"Checkout direct échoué. Création forcée de {branch_name}.")
                _git_service.create_branch(prod_path, branch_name)
                _git_service.checkout(prod_path, branch_name)
        else:
            _git_service.checkout(prod_path, branch_name)

        # Reset hard pour s'aligner sur le remote (s'il existe)
        try:
            _git_service.reset_hard(prod_path, f'origin/{branch_name}')
        except Exception:
            logger.warning(f"Impossible de reset sur origin/{branch_name} (peut-être nouveau repo).")
        
        # --- Application des changements ---
        for rel_path in changed_files:
            src_path = dev_path / rel_path
            dst_path = prod_path / rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
            elif dst_path.exists():
                dst_path.unlink()
        
        _git_service.add_all(prod_path)
        if _git_service.status(prod_path).stdout.strip():
            _git_service.commit(prod_path, "Approbation des changements de dev")
            _git_service.push(prod_path, 'origin', branch_name, set_upstream=True)

        # --- Synchronisation DEV ---
        logger.info(f"Synchronisation du répertoire dev ({dev_path}) avec origin/{branch_name}...")
        
        if repo_url:
            _git_service.set_remote_url(dev_path, 'origin', repo_url)
            
        _git_service.fetch(dev_path)
        
        # Basculer dev sur la bonne branche si nécessaire
        if not _git_service.branch_exists(dev_path, branch_name):
             _git_service.create_branch(dev_path, branch_name)
             
        current_branch = _git_service.get_current_branch(dev_path)
        if current_branch != branch_name:
             _git_service.checkout(dev_path, branch_name)

        _git_service.reset_hard(dev_path, f'origin/{branch_name}')
        
        _process_service.start_dev_server(dev_path, config.servers.dev_port, force_clean=True)
        
        return jsonify({'message': 'Changements approuvés et appliqués à prod.'})

    except GitError as e:
        logger.error(f"Erreur Git lors de l'approbation: {e.stderr}")
        _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
        # Renvoyer un message d'erreur détaillé au frontend
        error_details = f"Une erreur Git est survenue:\n{e.stderr}"
        return jsonify({'error': error_details}), 500
    
    except Exception as e:
        logger.exception("Erreur lors de l'approbation")
        _process_service.start_dev_server(config.paths.dev_path, config.servers.dev_port)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/rollback_changes', methods=['POST'])
def rollback_changes():
    """Annule les changements locaux dans dev."""
    try:
        config = get_config()
        dev_path = config.paths.dev_path
        logger.info("Rollback des changements dans dev...")
        _git_service.reset_hard(dev_path)
        _git_service.clean(dev_path, force=True, directories=True)
        _process_service.start_dev_server(dev_path, config.servers.dev_port, force_clean=True)
        return jsonify({'message': 'Dev réinitialisé avec succès.'})
    except Exception as e:
        logger.exception("Erreur lors du rollback")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/undo_change', methods=['POST'])
def undo_change():
    """Annule la dernière modification de l'IA en restaurant le stash."""
    try:
        config = get_config()
        dev_path = config.paths.dev_path
        logger.info("Annulation de la dernière modification de l'IA...")
        _git_service.stash_pop(dev_path)
        _process_service.stop_dev_server()
        time.sleep(2)
        _process_service.start_dev_server(dev_path, config.servers.dev_port)
        return jsonify({'message': 'Modification annulée avec succès.'})
    except Exception as e:
        logger.exception("Erreur lors de l'annulation de la modification")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/confirm_change', methods=['POST'])
def confirm_change():
    """Confirme la dernière modification de l'IA en supprimant le stash."""
    try:
        config = get_config()
        dev_path = config.paths.dev_path
        logger.info("Confirmation de la dernière modification de l'IA...")
        _git_service.stash_drop(dev_path)
        _process_service.stop_dev_server()
        time.sleep(2)
        _process_service.start_dev_server(dev_path, config.servers.dev_port)
        return jsonify({'message': 'Modification confirmée avec succès.'})
    except Exception as e:
        logger.exception("Erreur lors de la confirmation de la modification")
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