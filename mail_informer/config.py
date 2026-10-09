import os
from dataclasses import dataclass

DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"


@dataclass(frozen=True)
class Config:
    """Runtime settings, read from environment variables."""

    database_url: str
    client_secret_path: str
    token_path: str
    ollama_url: str
    analyzer_model: str
    ha_webhook_url: str


def load_config(
    require_database: bool = True, require_model: bool = False, require_webhook: bool = False
) -> Config:
    """Reads the settings from environment variables.

    Args:
        require_database: If True, fail when ``DATABASE_URL`` is missing.
        require_model: If True, fail when ``ANALYZER_MODEL`` is missing.
        require_webhook: If True, fail when ``HA_WEBHOOK_URL`` is missing or not an HTTP address.

    Returns:
        The loaded settings.

    Raises:
        RuntimeError: If a required value is not set.
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if require_database and not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    analyzer_model = os.environ.get("ANALYZER_MODEL", "")
    if require_model and not analyzer_model:
        raise RuntimeError("ANALYZER_MODEL is not set")
    ha_webhook_url = os.environ.get("HA_WEBHOOK_URL", "")
    if require_webhook:
        if not ha_webhook_url:
            raise RuntimeError("HA_WEBHOOK_URL is not set")
        # The address holds a secret id, so the message must not repeat it.
        if not ha_webhook_url.startswith(("http://", "https://")):
            raise RuntimeError("HA_WEBHOOK_URL must start with http:// or https://")
    return Config(
        database_url=database_url,
        client_secret_path=os.environ.get("CLIENT_SECRET_PATH", "secrets/client_secret.json"),
        token_path=os.environ.get("TOKEN_PATH", "secrets/token.json"),
        ollama_url=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        analyzer_model=analyzer_model,
        ha_webhook_url=ha_webhook_url,
    )
