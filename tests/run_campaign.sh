#!/usr/bin/env bash
# =============================================================================
# run_campaign.sh — Lance la campagne de test complète Simple Recipes
#
# Usage :
#   ./tests/run_campaign.sh [--headed] [--no-rebuild]
#
# Options :
#   --headed      Afficher le navigateur (utile pour le débogage)
#   --no-rebuild  Sauter l'étape docker build (utiliser l'image existante)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HEADED=""
SKIP_BUILD=0

for arg in "$@"; do
  case $arg in
    --headed)     HEADED="--headed" ;;
    --no-rebuild) SKIP_BUILD=1 ;;
  esac
done

echo "========================================"
echo "  Simple Recipes — Campagne de test"
echo "========================================"
echo "Projet : $PROJECT_ROOT"
echo ""

# ── 1. Dépendances Python ─────────────────────────────────────────────────────
echo "[1/4] Installation des dépendances de test ..."
pip install -q -r "$SCRIPT_DIR/requirements-test.txt" \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org

# ── 2. Navigateurs Playwright ────────────────────────────────────────────────
echo "[2/4] Installation de Chromium (Playwright) ..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

# ── 3. Build Docker (sauf --no-rebuild) ──────────────────────────────────────
if [ "$SKIP_BUILD" -eq 0 ]; then
  echo "[3/4] Construction de l'image Docker simple-recipes:test ..."
  docker build -t simple-recipes:test "$PROJECT_ROOT"
else
  echo "[3/4] Build ignoré (--no-rebuild)."
fi

# ── 4. Exécution des tests ────────────────────────────────────────────────────
echo "[4/4] Lancement de pytest ..."
echo ""
pytest "$SCRIPT_DIR/test_campaign.py" \
  -v \
  -s \
  --browser chromium \
  $HEADED \
  --tb=short \
  --timeout=60 \
  -p no:randomly \
  "$@" \
  || true   # ne pas masquer les résultats même en cas d'échec partiel

echo ""
echo "========================================"
echo "  Campagne terminée."
echo "  Les données de test ont été nettoyées"
echo "  par le fixture docker_container."
echo "========================================"
