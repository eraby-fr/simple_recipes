# Tests — Simple Recipes

This project has two independent test levels.

---

## Overview

| Level | Tool | Scope | Where it runs |
|-------|------|-------|---------------|
| **Unit tests** | pytest | Schemas, slugify, JWT auth | local · CI (every push / PR) |
| **Campaign tests** | pytest + Playwright | Full end-to-end user flows | local only |

---

## 1. Unit tests

### What they cover

| File | Tested classes |
|------|----------------|
| `backend/tests/test_schemas.py` | `UserCreate`, `RecipeCreate`, `RecipeUpdate` (Pydantic validation) |
| `backend/tests/test_storage.py` | `slugify`, `validate_slug`, `fix_image_urls` |
| `backend/tests/test_auth.py` | `hash_password`, `verify_password`, `create_access_token`, `decode_token` |

### Prerequisites

- Python 3.12+
- Backend dependencies (`backend/requirements.txt`)

No database or Docker required: tests use a temporary directory (`/tmp/simple_recipes_test_*`) created automatically by `backend/tests/conftest.py`.

### Running locally

```bash
# Via Make (recommended)
make test

# Or manually
cd backend
pip install -r requirements.txt pytest -q
PYTHONPATH=. DATA_DIR=/tmp/simple-recipes-test \
  SECRET_KEY=test-secret-key-local COOKIE_SECURE=false \
  pytest tests/ -v
```

### Injected environment variables

| Variable | Value for tests | Role |
|----------|-----------------|------|
| `PYTHONPATH` | `.` (from `backend/`) | Enables `app.*` imports |
| `DATA_DIR` | `/tmp/simple-recipes-test` | Isolated data directory |
| `SECRET_KEY` | `test-secret-key-local` | Test JWT key |
| `COOKIE_SECURE` | `false` | Disables `Secure` flag on cookies (local HTTP) |

### Continuous integration (GitHub Actions)

The workflow `.github/workflows/unit-tests.yml` runs **on every push and pull request** across all branches.

```
push / pull_request (all branches)
    └─ ubuntu-latest
        ├─ actions/checkout@v4
        ├─ actions/setup-python@v5  (Python 3.12, pip cache)
        ├─ pip install -r requirements.txt pytest
        └─ pytest tests/ -v
```

The pip cache is keyed on `backend/requirements.txt` and is only invalidated when dependencies change.

---

## 2. Campaign tests (E2E Playwright)

### What they cover

27 end-to-end scenarios simulating two users (`testcook1` / `testcook2`) in a real Chromium browser:

- Registration and login
- Creating 10 recipes (7 + 3)
- Listing, full-text search, tag filtering
- Viewing detail, editing
- Access control (403 for non-author)
- Image upload and deletion
- Recipe deletion
- Logout and verification of unauthenticated state

### Prerequisites

- Docker (to start the test application)
- Python 3.12+ with test dependencies

```bash
pip install pytest pytest-playwright playwright
playwright install chromium
```

### Running locally

```bash
cd /path/to/simple_recipes
pytest tests/test_campaign.py -v --browser chromium -p no:randomly
```

The session fixture (`tests/conftest.py`) automatically manages the Docker lifecycle:

1. `docker build` of the `simple-recipes:test` image
2. Create a named Docker volume `simple-recipes-test-data` (cleaned on each run)
3. Start the container on port **8181**
4. Wait for availability (max 45 s)
5. Run the tests
6. Stop the container and remove the volume

### Test container

| Parameter | Value |
|-----------|-------|
| Port | `8181` |
| Volume | `simple-recipes-test-data:/app/data` |
| `SECRET_KEY` | `ci-test-secret-key-1234567890abcdef` |
| `COOKIE_SECURE` | `false` |

> **Note**: campaign tests do not run in CI (no dedicated workflow). They require Docker and a display or headless mode. Adding a GitHub Actions workflow with a Docker service or `act` is possible if needed.

---

## 3. Release — Docker image

The workflow `.github/workflows/docker-release.yml` automatically publishes an image to **GitHub Container Registry** (`ghcr.io`) on a push to a `release/*` branch.

### Trigger

```bash
git checkout -b release/1.2.3
git push origin release/1.2.3
```

### What the workflow produces

```
push → release/1.2.3
    └─ ubuntu-latest
        ├─ Login to ghcr.io (GITHUB_TOKEN — no secret to configure)
        ├─ docker buildx build
        └─ push
            ├─ ghcr.io/<org>/<repo>:1.2.3
            └─ ghcr.io/<org>/<repo>:latest
```

BuildKit cache (`type=gha`) is enabled to speed up rebuilds.

### Pulling the image

```bash
docker pull ghcr.io/<org>/simple-recipes:1.2.3
```

The image is listed in the **Packages** tab of the GitHub repository.

### Prerequisites (private repository only)

**Settings → Actions → General → Workflow permissions** → check **Read and write permissions**.

---

## Quick reference

```bash
make test          # Unit tests (no Docker)
make dev           # Local development server
make up            # Start via Docker Compose (production-like)

# E2E tests (Docker required)
pytest tests/test_campaign.py -v --browser chromium -p no:randomly
```
