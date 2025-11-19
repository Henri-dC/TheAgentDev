"""
Package des routes Flask.
"""
from flask import Flask

from app.routes.api import api_bp, init_services as init_api_services
from app.routes.settings import settings_bp, init_services as init_settings_services
from app.routes.preview import preview_bp
from app.routes.project import project_bp, init_services as init_project_services


def register_blueprints(app: Flask):
    """
    Enregistre tous les blueprints dans l'application Flask.
    
    Args:
        app: Instance Flask
    """
    app.register_blueprint(project_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(preview_bp)


def inject_services(
    process_svc=None,
    git_svc=None,
    npm_svc=None,
    workspace_svc=None,
    gemini_svc=None,
    claude_svc=None,
    chroma_svc=None
):
    """
    Injecte les services dans les routes qui en ont besoin.
    """
    init_api_services(
        process_svc=process_svc,
        git_svc=git_svc,
        npm_svc=npm_svc,
        workspace_svc=workspace_svc,
        gemini_svc=gemini_svc,
        claude_svc=claude_svc
    )
    init_project_services(
        workspace_svc=workspace_svc, 
        process_svc=process_svc
    )
    init_settings_services(
        process_service=process_svc,
        workspace_service=workspace_svc
    )