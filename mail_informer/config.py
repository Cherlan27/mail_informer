import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime settings, read from environment variables."""

    database_url: str
    client_secret_path: str
    token_path: str


def load_config(require_database: bool = True) -> Config:
    """Reads the settings from environment variables.

    Args:
        require_database: If True, fail when ``DATABASE_URL`` is missing.

    Returns:
        The loaded settings.

    Raises:
        RuntimeError: If the database URL is required but not set.
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if require_database and not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return Config(
        database_url=database_url,
        client_secret_path=os.environ.get("CLIENT_SECRET_PATH", "secrets/client_secret.json"),
        token_path=os.environ.get("TOKEN_PATH", "secrets/token.json"),
    )
