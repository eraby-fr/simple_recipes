from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_SECRET = "change-me-in-production-please"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    data_dir: Path = Path("/app/data")
    secret_key: str = _DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    cookie_secure: bool = True


settings = Settings()

if settings.secret_key == _DEFAULT_SECRET:
    import warnings
    warnings.warn(
        "SECURITY: SECRET_KEY n'a pas été modifié. "
        "Définissez SECRET_KEY dans votre .env avant tout déploiement.",
        stacklevel=1,
    )

RECIPES_DIR: Path = settings.data_dir / "recipes"
DB_PATH: Path = settings.data_dir / "db" / "recipes.db"
