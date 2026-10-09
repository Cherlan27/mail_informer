"""Read-only access to an IMAP mailbox. No database code."""

import imaplib
import logging
import re
import ssl
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

from .accounts import Account
from .parsing import Mail, parse_raw_message

log = logging.getLogger(__name__)

FOLDER = "INBOX"
BATCH_SIZE = 20  # large mails: fewer at once keeps memory small
TIMEOUT_SECONDS = 30  # a hanging server must not hold the poller lock for ever
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_UID = re.compile(rb"\bUID (\d+)")
_INTERNALDATE = re.compile(
    rb'INTERNALDATE "\s*(\d{1,2})-(\w{3})-(\d{4}) (\d\d):(\d\d):(\d\d) ([+-]\d{4})"')


class ImapError(Exception):
    """The mailbox could not be reached or refused the login. Never holds a password."""


def imap_date(day: datetime) -> str:
    """Formats a date for ``SEARCH SINCE`` (``07-Oct-2026``), independent of the locale."""
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def _server_time(text: bytes) -> datetime:
    match = _INTERNALDATE.search(text)
    if not match:
        return datetime.now(timezone.utc)
    day, month, year, hour, minute, second, zone = match.groups()
    sign = -1 if zone[:1] == b"-" else 1
    offset = timedelta(hours=int(zone[1:3]), minutes=int(zone[3:5])) * sign
    return datetime(int(year), _MONTHS.index(month.decode()) + 1, int(day),
                    int(hour), int(minute), int(second), tzinfo=timezone(offset))


class ImapClient:
    """Reads new mails from the INBOX of one account. Changes nothing on the server."""

    def __init__(self, account: str, connection):
        self._account = account
        self._conn = connection

    @classmethod
    def connect(cls, account: Account) -> "ImapClient":
        """Opens a TLS connection with certificate check and logs in.

        Raises:
            ImapError: If the server is not reachable, the certificate is not valid,
                or the login is refused. The message names the account only.
        """
        context = ssl.create_default_context()
        try:
            conn = imaplib.IMAP4_SSL(account.host, account.port, ssl_context=context,
                                     timeout=TIMEOUT_SECONDS)
            conn.login(account.user, account.password)
        except imaplib.IMAP4.error:
            # The server text can echo input, so it is not repeated.
            raise ImapError(f"{account.name}: login refused") from None
        except OSError as e:  # includes SSL and certificate errors
            raise ImapError(f"{account.name}: cannot connect ({type(e).__name__})") from None
        return cls(account.name, conn)

    def close(self) -> None:
        """Ends the session. Errors are ignored: the run is over anyway."""
        try:
            self._conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    def _status(self) -> tuple[int, int]:
        _, data = self._conn.status(FOLDER, "(UIDVALIDITY UIDNEXT)")
        text = b" ".join(d for d in data if isinstance(d, bytes))
        validity = re.search(rb"UIDVALIDITY (\d+)", text)
        next_uid = re.search(rb"UIDNEXT (\d+)", text)
        if not validity or not next_uid:
            raise ImapError(f"{self._account}: server did not report UIDVALIDITY and UIDNEXT")
        return int(validity.group(1)), int(next_uid.group(1))

    def start_cursor(self) -> str:
        """Returns the cursor for "from now": the UID validity and the newest UID."""
        validity, next_uid = self._status()
        return f"{validity}:{next_uid - 1}"

    def _search(self, *criteria: str) -> list[int]:
        _, data = self._conn.uid("SEARCH", *criteria)
        return sorted(int(n) for n in (data[0] or b"").split())

    def _fetch(self, uids: list[int]) -> list[tuple[int, bytes, datetime]]:
        _, data = self._conn.uid("FETCH", ",".join(map(str, uids)),
                                 "(UID BODY.PEEK[] INTERNALDATE)")
        found = []
        for index, item in enumerate(data):
            if not isinstance(item, tuple):
                continue
            # Servers differ in where they put the UID: before or after the mail.
            trailer = data[index + 1] if index + 1 < len(data) else b""
            meta = item[0] + (trailer if isinstance(trailer, bytes) else b"")
            uid = _UID.search(meta)
            if uid:
                found.append((int(uid.group(1)), item[1], _server_time(meta)))
        return found

    def fetch_since(
        self,
        cursor: str,
        fallback_since: datetime,
        is_known: Callable[[list[str]], set[str]],
    ) -> Iterator[tuple[list[Mail], str | None]]:
        """Yields mails with a UID above the cursor, 20 at a time.

        Each batch carries the cursor to store after it. If the UID validity changed,
        the old UIDs mean nothing, so the mails since ``fallback_since`` are loaded
        again. The database drops the ones it already has.

        Args:
            cursor: ``"<uidvalidity>:<last uid>"``.
            fallback_since: Where to restart after a changed UID validity.
            is_known: Not used. A mail key is known only after parsing the mail.
        """
        validity, next_uid = self._status()
        stored_validity, _, stored_last = cursor.partition(":")
        same_numbers = stored_validity == str(validity) and stored_last.isdigit()

        # Read-only: the server cannot set flags even by mistake.
        self._conn.select(FOLDER, readonly=True)
        if same_numbers:
            last = int(stored_last)
            # "n:*" always includes the newest mail, even if its UID is below n.
            uids = [u for u in self._search("UID", f"{last + 1}:*") if u > last]
        else:
            log.warning("%s: UID validity changed, loading mails since %s",
                        self._account, imap_date(fallback_since))
            uids = self._search("SINCE", imap_date(fallback_since))

        for start in range(0, len(uids), BATCH_SIZE):
            chunk = uids[start:start + BATCH_SIZE]
            mails = [parse_raw_message(raw, received, self._account)
                     for _, raw, received in sorted(self._fetch(chunk))]
            # UIDs go up, so a failure later leaves the cursor behind the first failed batch.
            yield mails, f"{validity}:{chunk[-1]}"
        if not uids and not same_numbers:
            yield [], f"{validity}:{next_uid - 1}"
