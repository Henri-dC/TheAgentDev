# Documentation Technique de AgentDev

## 1. Vue d'ensemble

AgentDev est une application web conçue pour servir d'environnement de développement assisté par une intelligence artificielle (IA). Elle fournit une interface de type IDE où un utilisateur peut formuler des demandes de modification de code en langage naturel. L'IA interprète ces demandes, propose des changements de code, les applique à un environnement de développement local, et présente un aperçu en temps réel ainsi qu'un "diff" des modifications.

L'objectif est d'accélérer le développement en automatisant les tâches de codage répétitives ou complexes, tout en gardant le développeur humain dans la boucle pour l'approbation finale.

**Architecture générale :**
- **Backend :** Serveur Flask (Python) qui orchestre la logique métier.
- **Frontend :** Interface web simple (HTML, CSS, JavaScript) sans framework lourd.
- **Agent IA :** Services Python qui interagissent avec des modèles de langage (Gemini, Claude) pour la génération de code.
- **Environnement de développement :** Projets Node.js (React/Vue) clonés et gérés par l'application, s'exécutant dans des processus enfants.
- **Base de données vectorielle :** ChromaDB pour l'indexation et la recherche de contexte pertinent dans le code source du projet.

---

## 2. Structure du Projet

Le projet est organisé de manière modulaire pour séparer les responsabilités.

```
/
├── app/                  # Cœur de l'application Flask
│   ├── __init__.py       # Factory de l'application Flask
│   ├── models/           # Modèles de données (ex: Actions)
│   ├── routes/           # Blueprints Flask (API, UI)
│   ├── services/         # Logique métier (Git, NPM, IA, etc.)
│   └── utils/            # Fonctions utilitaires
│
├── config/               # Configuration de l'application
│   ├── settings.py       # Chargement et gestion de la configuration
│   └── logging.py        # Configuration du logging
│
├── templates/            # Templates HTML (Flask/Jinja2)
│   ├── index.html        # Page principale de l'IDE
│   ├── settings.html     # Page de configuration du projet
│   └── ...
│
├── static/               # Fichiers statiques (CSS, JS client)
│
├── app.py                # Point d'entrée principal de l'application
├── requirements.txt      # Dépendances Python
├── project_config.json   # Fichier de configuration du projet actif
└── TECHNICAL_DOCUMENTATION.md # Ce fichier
```

---

## 3. Composants Clés

### 3.1. Backend (Flask)

Le backend est construit avec Flask et utilise un modèle de "factory" (`create_app` dans `app/__init__.py`) pour l'initialisation.

- **Initialisation :** La fonction `create_app` configure le logging, charge la configuration, initialise tous les services (voir 3.2), injecte les dépendances dans les routes et enregistre les blueprints Flask.
- **Point d'entrée :** `app.py` est le point d'entrée qui exécute l'application Flask. Il désactive le `reloader` intégré de Flask car la gestion des processus enfants (serveurs de développement) est gérée manuellement par le `ProcessService`.

### 3.2. Services (Logique Métier)

La logique principale est encapsulée dans des services pour être réutilisable et testable.

- **`ProcessService` (`app/services/process_service.py`)**
  - **Rôle :** Gérer le cycle de vie des processus externes, principalement les serveurs de développement `npm run dev` (frontend) et `nodemon server.js` (backend).
  - **Fonctionnalités :** Démarrer, arrêter et surveiller les processus. Il utilise `subprocess.Popen` et gère les PID pour s'assurer que les processus sont correctement terminés. Il vérifie également si les ports sont accessibles pour confirmer que les serveurs ont bien démarré.

- **`WorkspaceService` (`app/services/workspace_service.py`)**
  - **Rôle :** Gérer la création et la configuration de l'environnement de développement local.
  - **Fonctionnalités :**
    - Crée les répertoires `dev`, `backend_dev`, et `prod`.
    - Crée un nouveau projet frontend (Vue/React) via `npm create` si le répertoire `dev` est vide.
    - Installe les dépendances `npm`.
    - Configure `vite.config.js` avec un proxy vers le serveur backend.
    - Initialise les dépôts Git.

- **`GitService` (`app/services/git_service.py`)**
  - **Rôle :** Abstraire les interactions avec Git.
  - **Fonctionnalités :** Encapsule les commandes `git` (`clone`, `init`, `add`, `commit`, `push`, `diff`, `stash`, `reset`, etc.) via des appels à `subprocess`.

- **`NpmService` (`app/services/npm_service.py`)**
  - **Rôle :** Abstraire les interactions avec `npm`.
  - **Fonctionnalités :** Encapsule les commandes `npm` (`install`, `create vue@latest`, `create vite@latest -- --template react`).

- **Services IA (`gemini_service.py`, `claude_service.py`)**
  - **Rôle :** Communiquer avec les LLMs pour générer du code.
  - **Fonctionnalités :**
    - Formate le prompt de l'utilisateur en y ajoutant du contexte (résultats de ChromaDB, arborescence des fichiers, historique de la conversation).
    - Appelle l'API du LLM.
    - Parse la réponse de l'IA (qui est attendue dans un format structuré, ex: JSON ou Markdown avec des blocs de code) pour extraire des actions concrètes (`FileAction`, `ShellCommandAction`).

- **`ChromaService` (`app/services/chroma_service.py`)**
  - **Rôle :** Gérer l'indexation du code source et la recherche sémantique.
  - **Fonctionnalités :**
    - Scanne les fichiers du projet.
    - Divise le contenu des fichiers en fragments (chunks).
    - Crée des "embeddings" (vecteurs numériques) pour chaque fragment.
    - Stocke ces vecteurs dans une collection ChromaDB.
    - Fournit une méthode `query` pour retrouver les fragments de code les plus pertinents sémantiquement par rapport à un prompt utilisateur.

### 3.3. Routes (API et UI)

Les routes sont organisées en Blueprints Flask.

- **`project_bp` (`app/routes/project.py`)**
  - Gère la création et la sélection des projets.
  - Met à jour le fichier `project_config.json` pour pointer vers les bons répertoires.

- **`settings_bp` (`app/routes/settings.py`)**
  - Affiche la page des paramètres (`settings.html`).
  - `/api/save_settings` : Sauvegarde les choix de l'utilisateur (framework, repo URL, etc.) dans la configuration.
  - `/api/start_project` : Déclenche le `WorkspaceService` et le `ProcessService` pour initialiser l'environnement et démarrer les serveurs. Renvoie l'URL de redirection vers l'IDE.

- **`api_bp` (`app/routes/api.py`)**
  - C'est le cœur de l'IDE.
  - `/main` : Affiche la page principale `index.html`.
  - `/api/propose_changes` :
    1. Reçoit le prompt de l'utilisateur.
    2. Fait un `git stash` pour sauvegarder l'état actuel.
    3. Interroge `ChromaService` pour obtenir du contexte.
    4. Appelle le service d'IA (Gemini/Claude) avec le prompt enrichi.
    5. Exécute les actions (`FileAction`, `ShellCommandAction`) retournées par l'IA.
    6. Fait un `git diff` pour calculer les changements.
    7. Renvoie l'explication de l'IA et le diff au frontend.
  - `/api/confirm_change` : Supprime le stash (`git stash drop`).
  - `/api/undo_change` : Annule les changements en appliquant le stash (`git stash pop`).
  - `/api/approve_changes` : Copie les fichiers modifiés du répertoire `dev` vers le répertoire `prod` et effectue un `git push` depuis `prod`.

- **`preview_bp` (`app/routes/preview.py`)**
  - Sert le contenu du site en développement dans une iframe. Il agit comme un proxy vers le serveur `npm run dev`.

### 3.4. Frontend

Le frontend est volontairement simple.

- **`project_selection.html` :** Permet de choisir un projet existant ou d'en créer un nouveau.
- **`settings.html` :** Formulaire pour configurer le projet. Le JavaScript sur cette page envoie les paramètres à `/api/save_settings`, puis appelle `/api/start_project` et redirige l'utilisateur vers `/main`.
- **`index.html` :** L'interface principale.
  - **Sidebar :** Contient le champ de prompt, les boutons d'action (Proposer, Approuver, Annuler), et la zone de réponse de l'IA.
  - **Main Content :** Affiche une `iframe` qui pointe vers `/preview`, montrant l'aperçu en direct du site en développement.
  - **JavaScript :**
    - Gère les appels `fetch` vers les différentes routes de `api_bp`.
    - Affiche les réponses de l'IA, le statut de chargement, et les diffs.
    - Gère la logique des boutons (confirmer/annuler les changements).
    - Implémente le drag-and-drop de composants, qui génère un prompt spécifique pour l'IA.

---

## 4. Workflows Principaux

### 4.1. Démarrage d'un projet

1.  **Utilisateur** arrive sur `/`.
2.  **`project.py`** affiche `project_selection.html`.
3.  **Utilisateur** sélectionne ou crée un projet.
4.  **`project.py`** met à jour `project_config.json` et redirige vers `/settings`.
5.  **`settings.py`** affiche `settings.html`.
6.  **Utilisateur** remplit le formulaire et clique sur "Enregistrer et Lancer".
7.  **JavaScript (`settings.html`)** envoie les données à `/api/save_settings`.
8.  **JavaScript** appelle ensuite `/api/start_project`.
9.  **`settings.py` (`start_project`)** :
    - Appelle `workspace_service.setup_all()` pour créer le projet, installer les `node_modules`, etc.
    - Appelle `process_service.start_dev_server()` et `start_backend_server()`.
    - Renvoie une réponse JSON `{ "redirect_url": "/main" }`.
10. **JavaScript** redirige le navigateur vers `/main`.

### 4.2. Cycle de modification par l'IA

1.  **Utilisateur** écrit une demande (ex: "Ajoute un bouton bleu dans le header") et clique sur "Proposer".
2.  **JavaScript (`index.html`)** envoie le prompt à `/api/propose_changes`.
3.  **`api.py` (`propose_changes`)** :
    - `git stash` dans le répertoire `/dev`.
    - `chroma_service.query(prompt)` -> obtient des extraits de code pertinents.
    - Appelle `gemini_service.generate_changes_with_context(prompt, context, ...)`
4.  **`gemini_service`** :
    - Construit un prompt système détaillé.
    - Appelle l'API de Gemini.
    - Parse la réponse et la transforme en une liste d'objets `FileAction` ou `ShellCommandAction`.
5.  **`api.py`** (suite) :
    - Itère sur les actions et les exécute (écrit/supprime des fichiers, lance des commandes).
    - Si `package.json` a été modifié, lance `npm install`.
    - Si des fichiers ont été modifiés, redémarre le serveur de développement via `process_service`.
    - `git diff` pour obtenir les changements.
    - Renvoie une réponse JSON `{ "explanation": "...", "diff": "..." }`.
6.  **JavaScript** affiche l'explication et le diff à l'utilisateur, et affiche les boutons "Confirmer" / "Annuler".
7.  **`iframe`** se recharge automatiquement pour montrer les changements visuels.
8.  **Utilisateur** clique sur "Confirmer".
9.  **JavaScript** appelle `/api/confirm_change`.
10. **`api.py`** exécute `git stash drop`. Les changements sont maintenant permanents dans la branche de développement.

---
## 5. Configuration

- **`project_config.json` :** Contient les chemins vers les répertoires `dev`, `prod`, `backend_dev`, le framework à utiliser, l'URL du dépôt Git, et les clés d'API pour les services externes (ex: WordPress). Ce fichier est modifié dynamiquement par l'application lors de la sélection/création de projet et de la sauvegarde des paramètres.
- **`config/settings.py` :** Un système de configuration en Python qui charge `project_config.json` et fournit un accès typé et validé aux paramètres via une instance d'objet `AppConfig`.
