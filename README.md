# Simple Recipes

Web application for managing and sharing cooking recipes. Backend **FastAPI** (Python 3.12), frontend **HTMX** + **Pico.css**, storage **SQLite + Markdown**.

## Quick start (Docker)

```bash
# 1. Create the .env file (SECRET_KEY auto-generated)
make env

# 2. Build the image
make build

# 3. Start the service
make up
```

Open → **http://localhost:8080** (port configurable in `.env`).

## Configuration

Edit the `.env` file:

| Variable     | Default  | Description                              |
|--------------|----------|------------------------------------------|
| `PORT`       | `8080`   | Port exposed on the host                 |
| `SECRET_KEY` | *(auto)* | JWT secret key — **do not share**        |

### Changing the data directory

By default, recipes are stored in `./data/`. To use a different path (NAS, external drive…), edit `docker-compose.yml`:

```yaml
volumes:
  - /my/absolute/path:/app/data
```

## Storage structure

```
data/
├── db/
│   └── recipes.db          # SQLite database (metadata, users, tags)
└── recipes/
    └── {recipe-slug}/
        ├── recipe.md       # Markdown content
        └── images/
            ├── cover.jpg
            └── ...
```

## Local development (without Docker)

Requires Python 3.12+ and `make`:

```bash
make dev
```

Downloads HTMX/Pico.css, installs dependencies, and starts the server in reload mode on port 8000.

## Make commands

| Command         | Description                           |
|-----------------|---------------------------------------|
| `make build`    | Build the Docker image                |
| `make up`       | Start in the background               |
| `make down`     | Stop the service                      |
| `make logs`     | Follow container logs                 |
| `make shell`    | Open a shell in the container         |
| `make clean`    | Remove containers + image             |
| `make restart`  | Restart the service                   |
| `make dev`      | Local development without Docker      |
| `make test`     | Run unit tests                        |

## Unit tests

Tests cover Pydantic validators, storage functions (slug, URLs), and authentication (hashing + JWT).

### With Make (recommended)

```bash
make test
```

### Manually

```bash
cd backend
pip install -r requirements.txt pytest

PYTHONPATH=. \
DATA_DIR=/tmp/simple-recipes-test \
SECRET_KEY=test-secret-key-local \
COOKIE_SECURE=false \
pytest tests/ -v
```

> **Important:** run `pytest` from `backend/` (not from the root) to prevent pydantic-settings from loading the root `.env`, which contains variables not recognised by `Settings`.

### Useful pytest commands

| Command | Description |
|---|---|
| `pytest tests/ -v` | All tests, verbose |
| `pytest tests/test_schemas.py` | Single file |
| `pytest tests/ -k "Slug"` | Filter by test name |
| `pytest tests/ -x` | Stop at first failure |

## API

Interactive documentation is available at `/api/docs` (Swagger UI) once the service is running.
