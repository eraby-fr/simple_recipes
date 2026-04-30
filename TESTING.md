# Tests — Simple Recipes

Ce projet dispose de deux niveaux de tests indépendants.

---

## Vue d'ensemble

| Niveau | Outil | Portée | Où s'exécute |
|--------|-------|--------|--------------|
| **Tests unitaires** | pytest | Schémas, slugify, auth JWT | local · CI (tout push / PR) |
| **Tests de campagne** | pytest + Playwright | Parcours utilisateur complet (E2E) | local uniquement |

---

## 1. Tests unitaires

### Ce qu'ils couvrent

| Fichier | Classes testées |
|---------|----------------|
| `backend/tests/test_schemas.py` | `UserCreate`, `RecipeCreate`, `RecipeUpdate` (validation Pydantic) |
| `backend/tests/test_storage.py` | `slugify`, `validate_slug`, `fix_image_urls` |
| `backend/tests/test_auth.py` | `hash_password`, `verify_password`, `create_access_token`, `decode_token` |

### Prérequis

- Python 3.12+
- Les dépendances du backend (`backend/requirements.txt`)

Aucune base de données ni Docker requis : les tests utilisent un répertoire temporaire (`/tmp/simple_recipes_test_*`) créé automatiquement par `backend/tests/conftest.py`.

### Lancer localement

```bash
# Via Make (recommandé)
make test

# Ou manuellement
cd backend
pip install -r requirements.txt pytest -q
PYTHONPATH=. DATA_DIR=/tmp/simple-recipes-test \
  SECRET_KEY=test-secret-key-local COOKIE_SECURE=false \
  pytest tests/ -v
```

### Variables d'environnement injectées

| Variable | Valeur pour les tests | Rôle |
|----------|-----------------------|------|
| `PYTHONPATH` | `.` (depuis `backend/`) | Permet l'import de `app.*` |
| `DATA_DIR` | `/tmp/simple-recipes-test` | Répertoire de données isolé |
| `SECRET_KEY` | `test-secret-key-local` | Clé JWT de test |
| `COOKIE_SECURE` | `false` | Désactive `Secure` sur les cookies (HTTP local) |

### Intégration continue (GitHub Actions)

Le workflow `.github/workflows/unit-tests.yml` s'exécute **à chaque push et pull request** sur toutes les branches.

```
push / pull_request (toutes branches)
    └─ ubuntu-latest
        ├─ actions/checkout@v4
        ├─ actions/setup-python@v5  (Python 3.12, cache pip)
        ├─ pip install -r requirements.txt pytest
        └─ pytest tests/ -v
```

Le cache pip est indexé sur `backend/requirements.txt` : il est invalidé uniquement si les dépendances changent.

---

## 2. Tests de campagne (E2E Playwright)

### Ce qu'ils couvrent

27 scénarios bout-en-bout simulant deux utilisateurs (`testcook1` / `testcook2`) dans un navigateur Chromium réel :

- Inscription et connexion
- Création de 10 recettes (7 + 3)
- Liste, recherche plein-texte, filtre par tag
- Consultation du détail, modification
- Contrôle d'accès (403 pour non-auteur)
- Upload et suppression d'image
- Suppression de recettes
- Déconnexion et vérification de l'état non-authentifié

### Prérequis

- Docker (pour démarrer l'application de test)
- Python 3.12+ avec les dépendances de test

```bash
pip install pytest pytest-playwright playwright
playwright install chromium
```

### Lancer localement

```bash
cd /chemin/vers/simple_recipes
pytest tests/test_campaign.py -v --browser chromium -p no:randomly
```

Le fixture de session (`tests/conftest.py`) gère automatiquement le cycle de vie Docker :

1. `docker build` de l'image `simple-recipes:test`
2. Création d'un volume Docker nommé `simple-recipes-test-data` (nettoyé à chaque run)
3. Démarrage du conteneur sur le port **8181**
4. Attente de disponibilité (max 45 s)
5. Exécution des tests
6. Arrêt du conteneur et suppression du volume

### Conteneur de test

| Paramètre | Valeur |
|-----------|--------|
| Port | `8181` |
| Volume | `simple-recipes-test-data:/app/data` |
| `SECRET_KEY` | `ci-test-secret-key-1234567890abcdef` |
| `COOKIE_SECURE` | `false` |

> **Note** : les tests de campagne ne s'exécutent pas en CI (pas de workflow dédié). Ils nécessitent Docker et un affichage ou un mode headless. Ajouter un workflow GitHub Actions avec service Docker ou `act` est possible si nécessaire.

---

## 3. Livraison — Image Docker de release

Le workflow `.github/workflows/docker-release.yml` publie automatiquement une image sur **GitHub Container Registry** (`ghcr.io`) lors d'un push sur une branche `release/*`.

### Déclenchement

```bash
git checkout -b release/1.2.3
git push origin release/1.2.3
```

### Ce que produit le workflow

```
push → release/1.2.3
    └─ ubuntu-latest
        ├─ Connexion à ghcr.io (GITHUB_TOKEN — aucun secret à configurer)
        ├─ docker buildx build
        └─ push
            ├─ ghcr.io/<org>/<repo>:1.2.3
            └─ ghcr.io/<org>/<repo>:latest
```

Le cache BuildKit (`type=gha`) est activé pour accélérer les rebuilds.

### Consommer l'image

```bash
docker pull ghcr.io/<org>/simple-recipes:1.2.3
```

L'image est listée dans l'onglet **Packages** du dépôt GitHub.

### Pré-requis (dépôt privé uniquement)

**Settings → Actions → General → Workflow permissions** → cocher **Read and write permissions**.

---

## Référence rapide

```bash
make test          # Tests unitaires (sans Docker)
make dev           # Serveur de développement local
make up            # Démarrage via Docker Compose (production-like)

# Tests E2E (Docker requis)
pytest tests/test_campaign.py -v --browser chromium -p no:randomly
```
