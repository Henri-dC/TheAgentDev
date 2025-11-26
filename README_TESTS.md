# Guide de résolution des problèmes d'import pytest

## Problème : Erreur d'import pytest dans l'IDE

Si vous avez installé pytest mais que l'IDE affiche toujours une erreur d'import, voici les solutions :

### Solution 1 : Vérifier que pytest est installé dans l'environnement virtuel

```powershell
# Activer l'environnement virtuel
cd "C:\Users\PC\VSC Dosss\Agent dev\IA"
.\IA\Scripts\Activate.ps1

# Vérifier l'installation
pip list | Select-String pytest

# Si pytest n'est pas installé, l'installer
pip install pytest pytest-mock pytest-cov
```

### Solution 2 : Configurer l'IDE pour utiliser le bon interpréteur

1. **Dans VS Code/Cursor** :

   - Appuyez sur `Ctrl+Shift+P` (ou `Cmd+Shift+P` sur Mac)
   - Tapez "Python: Select Interpreter"
   - Choisissez l'interpréteur : `IA\IA\Scripts\python.exe`

2. **Ou utilisez le fichier `.vscode/settings.json`** qui a été créé automatiquement

### Solution 3 : Redémarrer l'IDE

Après avoir changé l'interpréteur, redémarrez complètement VS Code/Cursor.

### Solution 4 : Vérifier manuellement

```powershell
# Tester pytest directement
cd "C:\Users\PC\VSC Dosss\Agent dev\IA"
.\IA\Scripts\python.exe -m pytest --version
```

Si cette commande fonctionne, pytest est bien installé et le problème vient de la configuration de l'IDE.

### Solution 5 : Réinstaller pytest dans l'environnement virtuel

```powershell
cd "C:\Users\PC\VSC Dosss\Agent dev\IA"
.\IA\Scripts\pip.exe install --upgrade pytest pytest-mock pytest-cov
```

## Exécuter les tests

Une fois le problème résolu, vous pouvez exécuter les tests avec :

```powershell
# Depuis le dossier IA
cd "C:\Users\PC\VSC Dosss\Agent dev\IA"
.\IA\Scripts\python.exe -m pytest

# Ou si l'environnement virtuel est activé
pytest
```

## Vérification rapide

Pour vérifier que tout fonctionne :

```powershell
cd "C:\Users\PC\VSC Dosss\Agent dev\IA"
.\IA\Scripts\python.exe -c "import pytest; print(pytest.__version__)"
```

Cette commande devrait afficher la version de pytest sans erreur.
