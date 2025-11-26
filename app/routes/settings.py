"""
Routes de gestion des paramètres.
"""
from flask import Blueprint, request, jsonify, render_template

from config.settings import get_config, reload_config
from config.logging import get_logger

logger = get_logger(__name__)

settings_bp = Blueprint('settings', __name__)

process_svc = None
workspace_svc = None

def init_services(process_service, workspace_service):
    """
    Initialise les services pour ce blueprint.
    """
    global process_svc, workspace_svc
    process_svc = process_service
    workspace_svc = workspace_service


@settings_bp.route('/settings')
def settings_page():
    """Affiche la page des paramètres."""
    return render_template('settings.html')


@settings_bp.route('/api/get_settings', methods=['GET'])
def get_settings():
    """
    Retourne la configuration actuelle du projet.
    
    Returns:
        JSON avec tous les paramètres du projet
    """
    try:
        config = get_config()
        project_config = config.project
        
        # Construire le dictionnaire de réponse
        settings = {
            'repository_url': project_config.repository_url,
            'dev_path': project_config.dev_path,
            'prod_path': project_config.prod_path,
            'backend_dev_path': project_config.backend_dev_path,
            'frontend_framework': project_config.frontend_framework,
            'branch_name': project_config.branch_name,
            'wordpress_api_enabled': project_config.wordpress_api_enabled,
            'enable_database': project_config.enable_database,
            'database_url': project_config.database_url,
        }
        
        # Ajouter les variables WordPress si présentes
        settings.update(project_config.wordpress_env)
        
        return jsonify(settings)
    
    except Exception as e:
        logger.exception("Erreur lors de la récupération des paramètres")
        return jsonify({
            'error': f"Impossible de charger les paramètres: {str(e)}"
        }), 500


@settings_bp.route('/api/save_settings', methods=['POST'])
def save_settings():
    """
    Sauvegarde les paramètres du projet et prépare le démarrage.
    """
    try:
        new_settings = request.json
        if not new_settings:
            return jsonify({'status': 'error', 'message': 'Aucune donnée fournie'}), 400
        
        logger.info(f"Paramètres reçus pour sauvegarde : {new_settings}")

        config = get_config()
        
        # Mettre à jour la configuration
        if 'frontend_framework' in new_settings:
            config.project.frontend_framework = new_settings['frontend_framework']
        if 'repository_url' in new_settings:
            config.project.repository_url = new_settings['repository_url']
        if 'wordpress_api_enabled' in new_settings:
            config.project.wordpress_api_enabled = new_settings['wordpress_api_enabled']
        if 'enable_database' in new_settings:
            config.project.enable_database = new_settings['enable_database']
        if 'database_url' in new_settings:
            config.project.database_url = new_settings['database_url']
        if 'branch_name' in new_settings:
            config.project.branch_name = new_settings['branch_name']
            
        wordpress_keys = [
            'WP_API_URL', 'WOO_API_URL', 'WOO_CONSUMER_KEY', 'WOO_CONSUMER_SECRET', 
            'WP_USERNAME', 'WP_PASSWORD', 'ADMIN_USERNAME', 'ADMIN_PASSWORD', 
            'JWT_SECRET', 'MAILJET_API_KEY', 'MAILJET_SECRET_KEY', 'MAIL_FROM', 
            'MAIL_TO_ADMIN', 'INSTAGRAM_ACCESS_TOKEN', 'RECAPTCHA_SECRET_KEY'
        ]
        wordpress_env = {key: new_settings.get(key, '') for key in wordpress_keys if key in new_settings}
        
        if wordpress_env:
            config.project.wordpress_env = wordpress_env
            if config.project.wordpress_api_enabled:
                _write_backend_env_file(config, wordpress_env)
        
        config.project.save_to_file(config.paths.config_path)
        reload_config()
        
        logger.info("Paramètres sauvegardés, prêt à démarrer le projet.")
        
        return jsonify({
            'status': 'ok',
            'message': 'Paramètres enregistrés. Prêt à démarrer le projet.',
            'next_action': 'start_project'
        })
    
    except Exception as e:
        logger.exception("Erreur lors de la sauvegarde des paramètres")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@settings_bp.route('/api/start_project', methods=['POST'])
def start_project():
    """
    Démarre l'environnement de développement après configuration.
    """
    try:
        app_config = get_config()
        
        # Arrêter les serveurs existants par sécurité
        process_svc.stop_all()
        
        # Configurer et démarrer les services
        workspace_svc.setup_all()
        process_svc.start_dev_server(
            app_config.paths.dev_path,
            app_config.servers.dev_port
        )
        process_svc.start_backend_server(
            app_config.paths.backend_dev_path,
            app_config.servers.backend_port
        )
        
        logger.info("Serveurs de développement démarrés avec succès.")
        
        return jsonify({
            'status': 'ok',
            'message': 'Projet démarré avec succès.',
            'redirect_url': '/main'
        })

    except Exception as e:
        logger.exception("Erreur lors du démarrage du projet")
        return jsonify({'status': 'error', 'message': str(e)}), 500



def _write_backend_env_file(config, wordpress_env: dict):
    """
    Écrit le fichier .env du backend avec les variables WordPress.
    
    Args:
        config: Instance AppConfig
        wordpress_env: Dictionnaire des variables WordPress
    """
    backend_env_path = config.paths.backend_dev_path / '.env'
    
    try:
        with open(backend_env_path, 'w', encoding='utf-8') as f:
            for key, value in wordpress_env.items():
                f.write(f"{key}={value}\n")
        
        logger.info(f"Fichier .env WordPress créé: {backend_env_path}")
    
    except Exception as e:
        logger.error(f"Impossible d'écrire le fichier .env: {e}")
        raise