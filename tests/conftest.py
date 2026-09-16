"""
Fixtures de session : Docker lifecycle + deux contextes navigateur persistants.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest
import requests

CONTAINER_NAME = "simple-recipes-test"
VOLUME_NAME  = "simple-recipes-test-data"
TEST_PORT    = 8181
_SECRET_KEY  = "ci-test-secret-key-1234567890abcdef"
BASE_URL     = f"http://localhost:{TEST_PORT}"


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ── Docker lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def docker_container():
    """Construit l'image, démarre le conteneur, attend la disponibilité, nettoie."""
    root = _project_root()

    # 1. Build
    print(f"\n[SETUP] docker build -t simple-recipes:test  (cwd={root})")
    subprocess.run(
        ["docker", "build", "-t", "simple-recipes:test", "."],
        cwd=root,
        check=True,
    )

    # 2. Supprimer tout conteneur résiduel
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    # 3. (Re)créer un volume Docker nommé propre
    #    Le volume est géré par Docker, donc docker volume rm fonctionne
    #    même si les fichiers appartiennent à uid 1001 (appuser).
    subprocess.run(["docker", "volume", "rm", "-f", VOLUME_NAME], capture_output=True)
    subprocess.run(["docker", "volume", "create", VOLUME_NAME], check=True, capture_output=True)

    # 4. Démarrer le conteneur
    print(f"[SETUP] docker run  {CONTAINER_NAME}  port {TEST_PORT}...")
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-p", f"{TEST_PORT}:8000",
            "-v", f"{VOLUME_NAME}:/app/data",
            "-e", f"SECRET_KEY={_SECRET_KEY}",
            "-e", "COOKIE_SECURE=false",
            "simple-recipes:test",
        ],
        check=True,
    )

    # 5. Attendre la disponibilité (max 45 s)
    print(f"[SETUP] En attente de {BASE_URL} ...")
    deadline = time.time() + 45
    ready = False
    while time.time() < deadline:
        try:
            if requests.get(f"{BASE_URL}/healthz", timeout=2).status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        logs = subprocess.run(
            ["docker", "logs", CONTAINER_NAME],
            capture_output=True,
            text=True,
        )
        print("DOCKER LOGS:\n", logs.stdout, logs.stderr)
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)
        pytest.fail(f"L'application n'a pas démarré à {BASE_URL} dans les 45 secondes.")

    print(f"[SETUP] Prêt → {BASE_URL}\n")
    yield BASE_URL

    # ── Nettoyage ──
    print("\n[TEARDOWN] Arrêt du conteneur ...")
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rm",  CONTAINER_NAME], capture_output=True)
    print(f"[TEARDOWN] Suppression du volume {VOLUME_NAME} ...")
    subprocess.run(["docker", "volume", "rm", "-f", VOLUME_NAME], capture_output=True)
    print("[TEARDOWN] Terminé.")


@pytest.fixture(scope="session")
def base_url(docker_container: str) -> str:
    return docker_container


# ── Contextes navigateur (un par utilisateur) ─────────────────────────────────

@pytest.fixture(scope="session")
def ctx1(browser, base_url):
    ctx = browser.new_context(base_url=base_url, ignore_https_errors=True)
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def ctx2(browser, base_url):
    ctx = browser.new_context(base_url=base_url, ignore_https_errors=True)
    yield ctx
    ctx.close()


@pytest.fixture(scope="session")
def page1(ctx1):
    """Page persistante pour testcook1 (conserve les cookies de session)."""
    p = ctx1.new_page()
    yield p
    p.close()


@pytest.fixture(scope="session")
def page2(ctx2):
    """Page persistante pour testcook2 (conserve les cookies de session)."""
    p = ctx2.new_page()
    yield p
    p.close()
