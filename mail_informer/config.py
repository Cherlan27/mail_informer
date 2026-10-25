import os
from dataclasses import dataclass, field

from .analysis import server_address

DEFAULT_MODEL_URL = "http://host.docker.internal:11434/v1"


@dataclass(frozen=True)
class Config:
    """Runtime settings, read from environment variables."""

    database_url: str
    client_secret_path: str
    token_path: str
    accounts_path: str
    model_url: str
    # repr=False: a logged config must not show the key.
    model_api_key: str = field(repr=False)
    model_reasoning_effort: str
    allow_remote_model: bool
    analyzer_model: str
    ha_webhook_url: str


def load_config(
    require_database: bool = True,
    require_model: bool = False,
    require_webhook: bool = False,
    require_model_server: bool = False,
) -> Config:
    """Reads the settings from environment variables.

    Args:
        require_database: If True, fail when ``DATABASE_URL`` is missing.
        require_model: If True, fail when ``ANALYZER_MODEL`` is missing.
        require_webhook: If True, fail when ``HA_WEBHOOK_URL`` is missing or not an HTTP address.
        require_model_server: If True, check the model server settings: fail when the
            old ``OLLAMA_URL`` is set without ``MODEL_URL``, or when mail text may not
            be sent to ``MODEL_URL`` (see ``analysis.server_address.check``).

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
    if require_model_server and os.environ.get("OLLAMA_URL") and not os.environ.get("MODEL_URL"):
        raise RuntimeError(
            "OLLAMA_URL is replaced by MODEL_URL. Set MODEL_URL to the same address "
            "with /v1 added, for example http://localhost:11434/v1")
    model_url = os.environ.get("MODEL_URL", DEFAULT_MODEL_URL)
    allow_remote_model = os.environ.get("ALLOW_REMOTE_MODEL", "") == "true"
    if require_model_server:
        try:
            server_address.check(model_url, allow_remote_model)
        except ValueError as e:
            raise RuntimeError(f"MODEL_URL is refused: {e}") from e
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
        accounts_path=os.environ.get("ACCOUNTS_PATH", "secrets/accounts.toml"),
        model_url=model_url,
        model_api_key=os.environ.get("MODEL_API_KEY", ""),
        model_reasoning_effort=os.environ.get("MODEL_REASONING_EFFORT", ""),
        allow_remote_model=allow_remote_model,
        analyzer_model=analyzer_model,
        ha_webhook_url=ha_webhook_url,
    )
