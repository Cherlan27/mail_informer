import argparse
import logging
from datetime import datetime, timedelta, timezone

from . import db
from .analysis.analyzer import MAX_ATTEMPTS, run_analysis
from .analysis.evaluate import evaluate, format_report, load_labels
from .analysis.model import ModelUnavailable, OllamaClient
from .analysis.prompts import PROMPT_VERSION
from .auth import authorize
from .config import load_config
from .gmail import GmailClient
from .sync import run_sync

log = logging.getLogger("mail_informer")

# Cron runs every 30 minutes. After 90 minutes without a sync, the poller counts as stuck.
MAX_SYNC_AGE = timedelta(minutes=90)
# The analyzer runs every 5 minutes. After 30 minutes without a pass, it counts as stuck.
MAX_ANALYZER_AGE = timedelta(minutes=30)


def _run(cfg) -> int:
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
    with db.connect(cfg.database_url) as conn:
        last = db.last_sync_at(conn)
    if last is None or datetime.now(timezone.utc) - last > MAX_SYNC_AGE:
        log.error("Last successful sync: %s", last)
        return 1
    return 0


def _analyze(cfg) -> int:
    """Runs one analyzer pass. Returns 1 if the model server is unavailable."""
    model = OllamaClient(cfg.ollama_url, cfg.analyzer_model)
    with db.connect(cfg.database_url) as conn:
        db.migrate(conn)
        try:
            run_analysis(conn, model, cfg.analyzer_model)
        except ModelUnavailable as e:
            log.error("Model server unavailable: %s", e)
            return 1
    return 0


def _analyzer_health(cfg) -> int:
    """Returns 1 if mails wait for analysis and no pass succeeded recently, else 0."""
    with db.connect(cfg.database_url) as conn:
        waiting = db.count_unanalyzed(conn, PROMPT_VERSION, MAX_ATTEMPTS)
        last = db.last_analyzer_ok(conn)
    if waiting and (last is None or datetime.now(timezone.utc) - last > MAX_ANALYZER_AGE):
        log.error("%d mails wait for analysis. Last successful pass: %s", waiting, last)
        return 1
    return 0


def _evaluate(cfg, labels_path: str, model_name: str | None) -> int:
    """Compares a model with hand-made labels and prints the report."""
    name = model_name or cfg.analyzer_model
    if not name:
        raise RuntimeError("Give --model or set ANALYZER_MODEL")
    model = OllamaClient(cfg.ollama_url, name)
    labels = load_labels(labels_path)
    with db.connect(cfg.database_url) as conn:
        print(format_report(evaluate(conn, model, labels), name))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Runs the command line interface.

    Args:
        argv: Command line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code: 0 on success, 1 on failure.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="mail_informer")
    parser.add_argument("command", choices=["auth", "run", "health", "analyze", "analyzer-health", "evaluate"])
    parser.add_argument("--labels", default="eval/labels.jsonl",
                        help="label file for the evaluate command")
    parser.add_argument("--model", help="model name for the evaluate command")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(
            require_database=args.command != "auth",
            require_model=args.command == "analyze",
        )
        if args.command == "auth":
            authorize(cfg.client_secret_path, cfg.token_path)
            log.info("Token saved: %s", cfg.token_path)
            return 0
        if args.command == "health":
            return _health(cfg)
        if args.command == "analyze":
            return _analyze(cfg)
        if args.command == "analyzer-health":
            return _analyzer_health(cfg)
        if args.command == "evaluate":
            return _evaluate(cfg, args.labels, args.model)
        return _run(cfg)
    except Exception:
        log.exception("Run failed")
        return 1
