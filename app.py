"""
Point d'entrée principal de l'application.
"""
import signal
import sys
import atexit
from app import create_app
from config.logging import get_logger
from app.services.process_service import process_service

logger = get_logger(__name__)

# Fonction de nettoyage unifiée
def cleanup():
    logger.info("Arrêt de l'application et nettoyage des processus...")
    process_service.stop_all()

# Enregistrer cleanup pour qu'il s'exécute à la sortie normale
atexit.register(cleanup)

# Gérer les signaux d'arrêt
def signal_handler(sig, frame):
    logger.info(f"Signal {sig} reçu.")
    # cleanup() sera appelé par atexit lors du sys.exit, 
    # mais on peut forcer l'arrêt ici si besoin pour être sûr.
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == '__main__':
    try:
        # Créer l'application Flask via la factory
        app = create_app()
        
        # Lancer le serveur Flask
        logger.info("Démarrage du serveur Flask sur http://0.0.0.0:5000")
        
        # use_reloader=False car nous gérons les processus enfants manuellement
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False
        )
    
    except Exception as e:
        logger.critical(f"Le serveur n'a pas pu démarrer: {e}", exc_info=True)