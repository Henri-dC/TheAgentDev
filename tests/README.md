# Tests Unitaires

Ce dossier contient les tests unitaires pour l'application AgentDev.

## Structure

```
tests/
├── __init__.py
├── conftest.py          # Fixtures communes
├── app/
│   └── services/
│       ├── test_chroma_service.py
│       ├── test_claude_service.py
│       ├── test_gemini_service.py
│       ├── test_git_service.py
│       ├── test_npm_service.py
│       ├── test_process_service.py
│       └── test_workspace_service.py
└── README.md
```

## Installation

Installer les dépendances de test :

```bash
pip install -r requirements.txt
```

## Exécution des tests

### Tous les tests

```bash
pytest
```

### Tests d'un service spécifique

```bash
pytest tests/app/services/test_git_service.py
```

### Tests avec couverture de code

```bash
pytest --cov=app --cov-report=html
```

### Tests en mode verbeux

```bash
pytest -v
```

### Tests avec affichage des print

```bash
pytest -s
```

## Fixtures disponibles

Les fixtures suivantes sont disponibles dans `conftest.py` :

- `temp_dir`: Crée un répertoire temporaire pour les tests
- `mock_config`: Configuration mock pour les tests
- `mock_gemini_config`: Configuration Gemini mock activée
- `mock_claude_config`: Configuration Claude mock activée
- `mock_command_result`: Factory pour créer des CommandResult mock

## Notes

- Les tests utilisent des mocks pour éviter les dépendances externes (API, fichiers système, etc.)
- Les tests sont isolés et ne modifient pas l'environnement réel
- Les répertoires temporaires sont automatiquement nettoyés après chaque test
