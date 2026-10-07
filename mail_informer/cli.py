import argparse
import logging
import sys

from . import db
from .auth import authorize
from .config import load_config
from .gmail import GmailClient
from .sync import run_sync

log = logging.getLogger("mail_informer")


def _run(cfg) -> int:
    with db.connect(cfg.database_url) as conn:
        if not db.try_lock(conn):
            log.info("Anderer Lauf aktiv, beende mich")
            return 0
        db.migrate(conn)
        run_sync(conn, GmailClient.from_token(cfg.token_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="mail_informer")
    parser.add_argument("command", choices=["auth", "run"])
    args = parser.parse_args(argv)
    cfg = load_config()
    try:
        if args.command == "auth":
            authorize(cfg.client_secret_path, cfg.token_path)
            log.info("Token gespeichert: %s", cfg.token_path)
            return 0
        return _run(cfg)
    except Exception:
        log.exception("Lauf fehlgeschlagen")
        return 1


if __name__ == "__main__":
    sys.exit(main())
