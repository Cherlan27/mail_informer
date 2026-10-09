import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.message import EmailMessage

import html2text


@dataclass(frozen=True)
class Mail:
    """A mail as stored in the database."""

    gmail_id: str
    thread_id: str
    internal_date: datetime
    from_addr: str | None
    to_addrs: str | None
    subject: str | None
    labels: list[str] = field(default_factory=list)
    snippet: str | None = None
    body_text: str = ""
    is_bulk: bool | None = None  # None means unknown


def _headers(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _charset(part: dict) -> str:
    content_type = _headers(part).get("content-type", "")
    match = re.search(r'charset="?([\w.\-]+)"?', content_type, re.IGNORECASE)
    return match.group(1) if match else "utf-8"


def _decode(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    try:
        return raw.decode(_charset(part), errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _collect(part: dict, plain: list[str], html: list[str]) -> None:
    mime = part.get("mimeType", "")
    if part.get("parts"):
        for child in part["parts"]:
            _collect(child, plain, html)
        return
    if part.get("filename"):  # attachment
        return
    if mime == "text/plain":
        plain.append(_decode(part))
    elif mime == "text/html":
        html.append(_decode(part))


def _html_to_text(markup: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_images = True
    converter.ignore_links = True
    converter.body_width = 0
    return converter.handle(markup).strip()


def extract_body_text(payload: dict) -> str:
    """Extracts the plain-text body from a Gmail message payload.

    Prefers ``text/plain`` parts. Falls back to ``text/html`` converted to text.
    Attachments are ignored.

    Args:
        payload: The ``payload`` part of a Gmail message.

    Returns:
        The body text, or an empty string if the mail has no text.
    """
    plain: list[str] = []
    html: list[str] = []
    _collect(payload, plain, html)
    text = "\n\n".join(p.strip() for p in plain if p.strip())
    if text:
        return text
    return "\n\n".join(t for t in (_html_to_text(h) for h in html) if t)


def parse_message(raw: dict) -> Mail:
    """Converts a raw Gmail message (``format=full``) into a ``Mail``."""
    payload = raw.get("payload", {})
    headers = _headers(payload)
    internal_date = datetime.fromtimestamp(int(raw["internalDate"]) / 1000, tz=timezone.utc)
    return Mail(
        gmail_id=raw["id"],
        thread_id=raw["threadId"],
        internal_date=internal_date,
        from_addr=headers.get("from"),
        to_addrs=headers.get("to"),
        subject=headers.get("subject"),
        labels=list(raw.get("labelIds", [])),
        snippet=raw.get("snippet"),
        body_text=extract_body_text(payload),
        is_bulk="list-unsubscribe" in headers,
    )


SNIPPET_CHARS = 200
_ANGLE_ID = re.compile(r"<([^<>\s]+)>")


def _part_text(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        # Unknown charset: keep the mail and replace what cannot be read.
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _raw_body_text(msg: EmailMessage) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in msg.walk():
        if (part.is_multipart() or part.get_content_disposition() == "attachment"
                or part.get_filename()):
            continue
        kind = part.get_content_type()
        if kind == "text/plain":
            plain.append(_part_text(part))
        elif kind == "text/html":
            html.append(_part_text(part))
    text = "\n\n".join(p.strip() for p in plain if p.strip())
    if text:
        return text
    return "\n\n".join(t for t in (_html_to_text(h) for h in html) if t)


def _header(msg: EmailMessage, name: str) -> str | None:
    value = msg[name]
    return None if value is None else str(value)


def _first_id(value: str | None) -> str | None:
    match = _ANGLE_ID.search(value or "")
    return match.group(1) if match else None


def parse_raw_message(raw: bytes, received: datetime, account: str) -> Mail:
    """Converts a raw RFC 822 mail (for example from IMAP) into a ``Mail``.

    The key is built from the ``Message-ID`` header and the account name, not from
    the IMAP UID, so a UID reset cannot store the same mail twice. A mail without
    that header gets a key from a hash of its main fields.

    Args:
        raw: The whole mail as bytes.
        received: The time the server received the mail. The ``Date`` header is not
            used because the sender controls it.
        account: The account name. It is the prefix of the key.

    Returns:
        The parsed mail.
    """
    msg = message_from_bytes(raw, policy=policy.default)
    body = _raw_body_text(msg)
    subject = _header(msg, "Subject")
    sender = _header(msg, "From")

    message_id = _first_id(_header(msg, "Message-ID"))
    if message_id is None:
        basis = "\n".join([sender or "", _header(msg, "Date") or "", subject or "",
                           body[:SNIPPET_CHARS]])
        message_id = hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()
    key = f"{account}:{message_id}"

    parent = _first_id(_header(msg, "References")) or _first_id(_header(msg, "In-Reply-To"))
    return Mail(
        gmail_id=key,
        thread_id=f"{account}:{parent}" if parent else key,
        internal_date=received,
        from_addr=sender,
        to_addrs=_header(msg, "To"),
        subject=subject,
        labels=["INBOX"],
        snippet=" ".join(body.split())[:SNIPPET_CHARS],
        body_text=body,
        is_bulk=msg["List-Unsubscribe"] is not None,
    )
