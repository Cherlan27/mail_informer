import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str
    client_secret_path: str
    token_path: str


def load_config() -> Config:
    return Config(
        database_url=os.environ.get("DATABASE_URL", ""),
        client_secret_path=os.environ.get("CLIENT_SECRET_PATH", "secrets/client_secret.json"),
        token_path=os.environ.get("TOKEN_PATH", "secrets/token.json"),
    )
