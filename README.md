# Simple Recipes

Application web de gestion et partage de recettes de cuisine. Backend **FastAPI** (Python 3.12), frontend **HTMX** + **Pico.css**, stockage **SQLite + Markdown**.

## Démarrage rapide (Docker)

```bash
# 1. Créer le .env (SECRET_KEY générée automatiquement)
make env

# 2. Construire l'image
make build

# 3. Démarrer le service
make up
```

Ouvrir → **http://localhost:8080** (port modifiable dans `.env`).

## Configuration

Modifier le fichier `.env` :

| Variable     | Défaut   | Description                             |
|--------------|----------|-----------------------------------------|
| `PORT`       | `8080`   | Port exposé sur l'hôte                  |
| `SECRET_KEY` | *(auto)* | Clé secrète JWT — **ne pas partager**   |

### Changer le dossier de données

Par défaut, les recettes sont stockées dans `./data/`. Pour utiliser un autre chemin (NAS, disque externe…), modifier le fichier `docker-compose.yml` :

```yaml
volumes:
  - /mon/chemin/absolu:/app/data
```

## Structure du stockage

```
data/
├── db/
│   └── recipes.db          # Base SQLite (métadonnées, utilisateurs, tags)
└── recipes/
    └── {slug-recette}/
        ├── recipe.md       # Contenu Markdown
        └── images/
            ├── cover.jpg
            └── ...
```

## Développement local (sans Docker)

Nécessite Python 3.12+ et `make` :

```bash
make dev
```

Télécharge HTMX/Pico.css, installe les dépendances et lance le serveur en mode reload sur le port 8000.

## Commandes Make

| Commande        | Description                          |
|-----------------|--------------------------------------|
| `make build`    | Construire l'image Docker            |
| `make up`       | Démarrer en arrière-plan             |
| `make down`     | Arrêter le service                   |
| `make logs`     | Suivre les logs                      |
| `make shell`    | Shell dans le conteneur              |
| `make clean`    | Supprimer conteneurs + image         |
| `make restart`  | Redémarrer le service                |
| `make dev`      | Développement local sans Docker      |
| `make test`     | Lancer les tests unitaires           |

## Tests unitaires

Les tests couvrent les validateurs Pydantic, les fonctions de stockage (slug, URLs) et l'authentification (hachage + JWT).

### Avec Make (recommandé)

```bash
make test
```

### Manuellement

```bash
cd backend
pip install -r requirements.txt pytest

PYTHONPATH=. \
DATA_DIR=/tmp/simple-recipes-test \
SECRET_KEY=test-secret-key-local \
COOKIE_SECURE=false \
pytest tests/ -v
```

> **Important :** lancer `pytest` depuis `backend/` (et non depuis la racine) pour éviter que pydantic-settings charge le `.env` racine, qui contient des variables non reconnues par `Settings`.

### Commandes pytest utiles

| Commande | Description |
|---|---|
| `pytest tests/ -v` | Tous les tests, verbose |
| `pytest tests/test_schemas.py` | Un seul fichier |
| `pytest tests/ -k "Slug"` | Filtrer par nom de test |
| `pytest tests/ -x` | Arrêter au premier échec |

## API

La documentation interactive est disponible à `/api/docs` (Swagger UI) une fois le service lancé.
