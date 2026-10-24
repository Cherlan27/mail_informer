import ipaddress
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

DEFAULT_MODEL_URL = "http://host.docker.internal:11434/v1"

LOCAL_HOSTS = ("localhost", "host.docker.internal")


def is_local_model_url(url: str) -> bool:
    """Tells if a model server address is on this machine or in a private network.

    The decision uses the address text only. It makes no DNS lookup, because the
    answer of a lookup can change between the check and the request.

    Args:
        url: Base address of the model server.

    Returns:
        True for ``localhost``, ``host.docker.internal``, and IP addresses that are
        loopback, private, or link-local. False for every other host name or address.
    """
    host = urlparse(url).hostname or ""
    if host in LOCAL_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


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
            old ``OLLAMA_URL`` is set without ``MODEL_URL``, when a remote address is
            used without ``ALLOW_REMOTE_MODEL=true``, or when a remote address is not
            ``https://``.

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
    if require_model_server and not is_local_model_url(model_url):
        # The messages do not repeat the address: it may hold a user name and password.
        if not allow_remote_model:
            raise RuntimeError(
                "MODEL_URL is not a local address. Mail text would leave this network. "
                "Set ALLOW_REMOTE_MODEL=true to allow it")
        if not model_url.startswith("https://"):
            raise RuntimeError("A remote MODEL_URL must start with https://")
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
