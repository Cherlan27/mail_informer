import argparse
import logging
from datetime import datetime, timedelta, timezone

from . import db
from .analysis.analyzer import MAX_ATTEMPTS, run_analysis
from .analysis.evaluate import evaluate, format_report, load_labels
from .analysis.model import ModelUnavailable, OpenAICompatibleClient
from .analysis.prompts import PROMPT_VERSION
from .accounts import Account, load_accounts
from .auth import authorize
from .config import load_config
from .gmail import GmailClient
from .imap import ImapClient
from .notify import rules as notify_rules
from .notify.client import HaWebhookClient, NotifierUnavailable
from .notify.notifier import run_notification
from .sync import MailSource, run_sync

log = logging.getLogger("mail_informer")

# Cron runs every 5 minutes. After 15 minutes without a sync, the poller counts as stuck.
MAX_SYNC_AGE = timedelta(minutes=15)
# The analyzer runs every 5 minutes. After 30 minutes without a pass, it counts as stuck.
MAX_ANALYZER_AGE = timedelta(minutes=30)
# The notifier runs every 5 minutes. After 30 minutes without a pass, it counts as stuck.
MAX_NOTIFIER_AGE = timedelta(minutes=30)


def _open_source(account: Account) -> MailSource:
    """Opens the mailbox of an account."""
    if account.kind == "gmail":
        return GmailClient.from_token(account.token_path)
    return ImapClient.connect(account)


def _warn_if_gmail_state_has_no_account(conn, accounts: list[Account]) -> None:
    # The upgrade stores the old Gmail sync point under the name "gmail". A file that
    # names that account differently starts it again from now and skips the gap.
    if db.get_cursor(conn, "gmail") and all(a.name != "gmail" for a in accounts):
        log.warning("A sync point for the account 'gmail' exists, but the accounts file has "
                    "no account with that name. If you renamed it, mails that arrived since "
                    "the last run are skipped.")


def _sync_account(conn, account: Account) -> bool:
    """Syncs one account. Returns False if it failed. The error is logged."""
    source = None
    try:
        source = _open_source(account)
        run_sync(conn, account.name, source)
        return True
    except Exception:
        log.exception("%s: sync failed", account.name)
        return False
    finally:
        close = getattr(source, "close", None)
        if close:
            close()


def _run(cfg) -> int:
    """Runs one sync of every account, unless another run holds the lock.

    A failing account does not stop the others. Returns 1 if any account failed.
    """
    accounts = load_accounts(cfg.accounts_path)
    with db.connect(cfg.database_url) as conn:
        if not db.try_lock(conn):
            log.info("Another run is active, exiting")
            return 0
        try:
            db.migrate(conn)
            for account in accounts:
                db.register_account(conn, account.name)
            _warn_if_gmail_state_has_no_account(conn, accounts)
            results = [_sync_account(conn, account) for account in accounts]
        finally:
            db.unlock(conn)
    return 0 if all(results) else 1


def _health(cfg) -> int:
    """Returns 1 if any account has no successful sync for too long, else 0."""
    accounts = load_accounts(cfg.accounts_path)
    with db.connect(cfg.database_url) as conn:
        last = db.oldest_sync_at(conn, [a.name for a in accounts])
    if last is None or datetime.now(timezone.utc) - last > MAX_SYNC_AGE:
        log.error("Oldest successful sync of an account: %s", last)
        return 1
    return 0


def _open_model(cfg, name: str) -> OpenAICompatibleClient:
    """Builds the client for the configured model server."""
    return OpenAICompatibleClient(
        cfg.model_url, name,
        api_key=cfg.model_api_key, reasoning_effort=cfg.model_reasoning_effort)


def _analyze(cfg) -> int:
    """Runs one analyzer pass. Returns 1 if the model server is unavailable."""
    model = _open_model(cfg, cfg.analyzer_model)
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


def _notify(cfg) -> int:
    """Runs one notifier pass. Returns 1 if Home Assistant is unavailable."""
    notifier = HaWebhookClient(cfg.ha_webhook_url)
    with db.connect(cfg.database_url) as conn:
        db.migrate(conn)
        try:
            run_notification(conn, notifier)
        except NotifierUnavailable as e:
            log.error("Home Assistant unavailable: %s", e)
            return 1
    return 0


def _notifier_health(cfg) -> int:
    """Returns 1 if mails wait to be reported and no pass succeeded recently, else 0."""
    with db.connect(cfg.database_url) as conn:
        waiting = db.count_reportable(conn, notify_rules.MAX_AGE_HOURS)
        last = db.last_notifier_ok(conn)
    if waiting and (last is None or datetime.now(timezone.utc) - last > MAX_NOTIFIER_AGE):
        log.error("%d mails wait to be reported. Last successful pass: %s", waiting, last)
        return 1
    return 0


def _evaluate(cfg, labels_path: str, model_name: str | None) -> int:
    """Compares a model with hand-made labels and prints the report."""
    name = model_name or cfg.analyzer_model
    if not name:
        raise RuntimeError("Give --model or set ANALYZER_MODEL")
    model = _open_model(cfg, name)
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
    parser.add_argument("command", choices=["auth", "run", "health", "analyze", "analyzer-health", "evaluate", "notify", "notifier-health"])
    parser.add_argument("--labels", default="eval/labels.jsonl",
                        help="label file for the evaluate command")
    parser.add_argument("--model", help="model name for the evaluate command")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(
            require_database=args.command != "auth",
            require_model=args.command == "analyze",
            require_webhook=args.command == "notify",
            require_model_server=args.command in ("analyze", "evaluate"),
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
        if args.command == "notify":
            return _notify(cfg)
        if args.command == "notifier-health":
            return _notifier_health(cfg)
        if args.command == "evaluate":
            return _evaluate(cfg, args.labels, args.model)
        return _run(cfg)
    except Exception:
        log.exception("Run failed")
        return 1
