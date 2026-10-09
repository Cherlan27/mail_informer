"""One analyzer pass: rate unanalyzed mails with the model and store the results."""

import logging

import psycopg

from .. import db
from . import prompts, rules
from .model import ModelClient
from .rules import InvalidAnswer

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
PASS_LIMIT = 50
SUMMARY_LEVELS = ("important", "urgent")


def classify(model: ModelClient, mail: db.PendingMail) -> rules.Classification:
    """Asks the model to rate one mail. The bulk guard is not applied here.

    Raises:
        InvalidAnswer: If the model answers outside the schema.
        ModelUnavailable: If the model server cannot be reached.
    """
    answer = model.chat_json(
        prompts.classify_messages(
            rules.build_classify_input(mail.from_addr, mail.subject, mail.body_text)),
        prompts.CLASSIFY_SCHEMA,
    )
    return rules.parse_classification(answer)


def _analyze(model: ModelClient, mail: db.PendingMail) -> tuple[rules.Classification, str, str]:
    """Asks the model about one mail.

    Returns:
        The classification, the importance after the bulk guard, and the summary
        (empty if the mail is not important).

    Raises:
        InvalidAnswer: If the model answers outside the schema.
        ModelUnavailable: If the model server cannot be reached.
    """
    classification = classify(model, mail)
    importance = rules.apply_bulk_guard(classification.importance, mail.is_bulk)
    summary = ""
    if importance in SUMMARY_LEVELS:
        answer = model.chat_json(
            prompts.summarize_messages(
                rules.build_summarize_input(mail.from_addr, mail.subject, mail.body_text)),
            prompts.SUMMARIZE_SCHEMA,
        )
        summary = rules.parse_summary(answer)
    return classification, importance, summary


def run_analysis(
    conn: psycopg.Connection,
    model: ModelClient,
    model_name: str,
    max_attempts: int = MAX_ATTEMPTS,
    limit: int = PASS_LIMIT,
) -> int:
    """Runs one analyzer pass.

    Each mail is stored in its own transaction, so a crash loses at most the mail
    that is being analyzed. Only one pass can run at a time.

    Args:
        conn: Database connection.
        model: The model to ask.
        model_name: Name stored with each result.
        max_attempts: How many invalid answers a mail may get before it is marked failed.
        limit: Maximum number of mails in this pass.

    Returns:
        The number of mails that got a finished result. 0 if another pass is active.

    Raises:
        ModelUnavailable: If the model server cannot be reached. Mails finished before
            that stay stored. No attempt is counted for the current mail.
    """
    if not db.try_analyzer_lock(conn):
        log.info("Another analyzer pass is active, exiting")
        return 0
    try:
        done = 0
        for mail in db.pick_unanalyzed(conn, prompts.PROMPT_VERSION, max_attempts, limit):
            try:
                classification, importance, summary = _analyze(model, mail)
            except InvalidAnswer as e:
                status = db.record_failed_attempt(
                    conn, mail.gmail_id, prompts.PROMPT_VERSION, model_name, max_attempts)
                log.warning("Invalid model answer for %s (%s): %s", mail.gmail_id, status, e)
                continue
            db.save_result(
                conn, mail.gmail_id, prompts.PROMPT_VERSION, model_name,
                classification.category, importance, summary, classification.reason,
            )
            done += 1
        db.touch_analyzer_ok(conn)
        log.info("%d mails analyzed", done)
        return done
    finally:
        db.analyzer_unlock(conn)
