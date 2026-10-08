import argparse
import logging
from datetime import datetime, timedelta, timezone

from . import db
from .auth import authorize
from .config import load_config
from .gmail import GmailClient
from .sync import run_sync

log = logging.getLogger("mail_informer")

# Cron runs every 30 minutes. After 90 minutes without a sync, the poller counts as stuck.
MAX_SYNC_AGE = timedelta(minutes=90)


def _run(cfg) -> int:
    """Runs one sync, unless another run holds the lock."""
    """Runs one sync, unless another run holds the lock."""
    with db.connect(cfg.database_url) as conn:
        if not db.try_lock(conn):
            log.info("Another run is active, exiting")
            return 0
        try:
            db.migrate(conn)
            run_sync(conn, GmailClient.from_token(cfg.token_path))
        finally:
            db.unlock(conn)
    return 0


def _health(cfg) -> int:
    """Returns 1 if the last successful sync is too old, else 0."""
    """Returns 1 if the last successful sync is too old, else 0."""
    with db.connect(cfg.database_url) as conn:
        last = db.last_sync_at(conn)
    if last is None or datetime.now(timezone.utc) - last > MAX_SYNC_AGE:
        log.error("Last successful sync: %s", last)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Runs the command line interface.

    Args:
        argv: Command line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code: 0 on success, 1 on failure.
    """
    """Runs the command line interface.

    Args:
        argv: Command line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code: 0 on success, 1 on failure.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="mail_informer")
    parser.add_argument("command", choices=["auth", "run", "health"])
    args = parser.parse_args(argv)
    try:
        cfg = load_config(require_database=args.command != "auth")
        if args.command == "auth":
            authorize(cfg.client_secret_path, cfg.token_path)
            log.info("Token saved: %s", cfg.token_path)
            return 0
        if args.command == "health":
            return _health(cfg)
        return _run(cfg)
    except Exception:
        log.exception("Run failed")
        return 1
