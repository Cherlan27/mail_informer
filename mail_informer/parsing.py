import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import html2text


@dataclass(frozen=True)
class Mail:
    gmail_id: str
    thread_id: str
    internal_date: datetime
    from_addr: str | None
    to_addrs: str | None
    subject: str | None
    labels: list[str] = field(default_factory=list)
    snippet: str | None = None
    body_text: str = ""


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
    if part.get("filename"):  # Anhang
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
    plain: list[str] = []
    html: list[str] = []
    _collect(payload, plain, html)
    text = "\n\n".join(p.strip() for p in plain if p.strip())
    if text:
        return text
    return "\n\n".join(t for t in (_html_to_text(h) for h in html) if t)


def parse_message(raw: dict) -> Mail:
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
    )
