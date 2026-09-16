from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_SECRET = "change-me-in-production-please"
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    data_dir: Path = Path("/app/data")
    secret_key: str = _DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # 12 hours
    cookie_secure: bool = True

    # Comma-separated Host header allow-list. "*" disables the check, which is
    # only safe when a reverse proxy already validates the Host header.
    allowed_hosts: str = "*"

    # OpenAPI schema and Swagger/ReDoc UIs. They describe the whole API surface
    # to anonymous visitors, so they stay off unless explicitly enabled.
    enable_docs: bool = False

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()] or ["*"]


settings = Settings()

if settings.secret_key == _DEFAULT_SECRET:
    raise RuntimeError(
        "SECURITY: SECRET_KEY still holds its default value. Generate a random "
        "one (python -c 'import secrets; print(secrets.token_urlsafe(48))') and "
        "set it in your .env before starting the application."
    )

if len(settings.secret_key) < _MIN_SECRET_LENGTH:
    raise RuntimeError(
        f"SECURITY: SECRET_KEY is too short ({len(settings.secret_key)} characters). "
        f"It must be at least {_MIN_SECRET_LENGTH} characters long."
    )

RECIPES_DIR: Path = settings.data_dir / "recipes"
DB_PATH: Path = settings.data_dir / "db" / "recipes.db"
