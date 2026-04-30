import os
import tempfile

# Définir les variables d'environnement avant tout import de l'application
# pour que pydantic-settings les utilise à la place du .env
_tmpdir = tempfile.mkdtemp(prefix="simple_recipes_test_")
os.environ.setdefault("DATA_DIR", _tmpdir)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-abcdef1234567890")
os.environ.setdefault("COOKIE_SECURE", "false")
