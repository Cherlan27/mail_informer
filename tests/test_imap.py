import imaplib
import re
import ssl
from datetime import datetime, timezone

import pytest

from mail_informer import imap
from mail_informer.accounts import Account
from mail_informer.imap import ImapClient, ImapError

SINCE = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)


def raw_mail(n: int) -> bytes:
    return (f"From: a@example.org\r\nSubject: Mail {n}\r\nMessage-ID: <m{n}@example.org>\r\n"
            f"Content-Type: text/plain\r\n\r\nBody {n}").encode()


class FakeImap:
    """Answers like an IMAP server for the few commands the client uses."""

    def __init__(self, uids=(), validity=3, uid_in_trailer=False):
        self.uids = sorted(uids)
        self.validity = validity
        self.uid_in_trailer = uid_in_trailer
        self.log: list[tuple] = []

    def status(self, mailbox, what):
        self.log.append(("status", mailbox, what))
        nxt = (self.uids[-1] + 1) if self.uids else 1
        return "OK", [f'"INBOX" (UIDVALIDITY {self.validity} UIDNEXT {nxt})'.encode()]

    def select(self, mailbox="INBOX", readonly=False):
        self.log.append(("select", mailbox, readonly))
        return "OK", [str(len(self.uids)).encode()]

    def uid(self, command, *args):
        self.log.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(str(u).encode() for u in self._search(args))]
        assert command == "FETCH"
        wanted = [int(x) for x in args[0].split(",")]
        data = []
        for u in wanted:
            stamp = b'INTERNALDATE "09-Oct-2026 08:30:00 +0000"'
            if self.uid_in_trailer:
                data.append((b"1 (BODY[] {10}", raw_mail(u)))
                data.append(f" UID {u} ".encode() + stamp + b")")
            else:
                data.append((f"1 (UID {u} ".encode() + stamp + b" BODY[] {10}", raw_mail(u)))
                data.append(b")")
        return "OK", data

    def _search(self, args):
        if args[0] == "UID":  # "n:*": the newest mail is always included
            low = int(args[1].split(":")[0])
            found = [u for u in self.uids if u >= low]
            return found or self.uids[-1:]
        assert args[0] == "SINCE"
        return self.uids

    def logout(self):
        self.log.append(("logout",))


def client(fake):
    return ImapClient("privat", fake)


def collect(c, cursor, fallback=SINCE):
    return list(c.fetch_since(cursor, fallback, lambda ids: set()))


def keys(batches):
    return [m.gmail_id for mails, _ in batches for m in mails]


def test_start_cursor_is_validity_and_last_uid():
    assert client(FakeImap([4, 9], validity=7)).start_cursor() == "7:9"


def test_start_cursor_of_an_empty_mailbox():
    assert client(FakeImap([], validity=7)).start_cursor() == "7:0"


def test_fetch_returns_only_uids_above_the_cursor_with_the_highest_as_cursor():
    batches = collect(client(FakeImap([4, 5, 6, 7])), "3:5")
    assert keys(batches) == ["privat:m6@example.org", "privat:m7@example.org"]
    assert batches[-1][1] == "3:7"


def test_newest_old_mail_returned_by_n_star_is_dropped():
    assert collect(client(FakeImap([4, 5])), "3:5") == []


def test_mailbox_is_selected_read_only_and_fetched_with_peek():
    fake = FakeImap([6])
    collect(client(fake), "3:5")
    assert ("select", "INBOX", True) in fake.log
    fetches = [e for e in fake.log if e[:2] == ("uid", "FETCH")]
    assert fetches
    for entry in fetches:
        assert "BODY.PEEK[]" in entry[3]
        assert "BODY[]" not in entry[3].replace("BODY.PEEK[]", "")


def test_nothing_is_changed_on_the_server():
    fake = FakeImap([6, 7])
    collect(client(fake), "3:5")
    commands = {e[1] for e in fake.log if e[0] == "uid"}
    assert commands <= {"SEARCH", "FETCH"}  # no STORE, COPY, or EXPUNGE


def test_uid_in_the_trailer_of_the_answer_is_found():
    batches = collect(client(FakeImap([6], uid_in_trailer=True)), "3:5")
    assert keys(batches) == ["privat:m6@example.org"]
    assert batches[-1][1] == "3:6"


def test_received_time_comes_from_the_server():
    mail = collect(client(FakeImap([6])), "3:5")[0][0][0]
    assert mail.internal_date == datetime(2026, 10, 9, 8, 30, tzinfo=timezone.utc)


def test_fetch_works_in_batches_of_twenty():
    batches = collect(client(FakeImap(range(1, 46))), "3:0")
    assert [len(m) for m, _ in batches] == [20, 20, 5]
    assert [c for _, c in batches] == ["3:20", "3:40", "3:45"]


def test_changed_validity_reloads_since_the_date_and_stores_the_new_validity():
    fake = FakeImap([1, 2, 3], validity=9)
    batches = collect(client(fake), "3:50")
    assert keys(batches) == [f"privat:m{n}@example.org" for n in (1, 2, 3)]
    assert batches[-1][1] == "9:3"
    search = [e for e in fake.log if e[:2] == ("uid", "SEARCH")][0]
    assert search[2:] == ("SINCE", "07-Oct-2026")


def test_since_date_uses_english_month_names_regardless_of_locale():
    assert imap.imap_date(datetime(2026, 3, 1, tzinfo=timezone.utc)) == "01-Mar-2026"
    assert imap.imap_date(datetime(2026, 12, 31, tzinfo=timezone.utc)) == "31-Dec-2026"


def test_changed_validity_without_mails_still_stores_the_new_cursor():
    batches = collect(client(FakeImap([], validity=9)), "3:50")
    assert batches == [([], "9:0")]


class Recorder:
    """Stands in for imaplib.IMAP4_SSL."""

    instances: list = []
    login_error: Exception | None = None

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.args = dict(host=host, port=port, ssl_context=ssl_context, timeout=timeout)
        self.logged_in = None
        Recorder.instances.append(self)

    def login(self, user, password):
        if Recorder.login_error:
            raise Recorder.login_error
        self.logged_in = (user, password)
        return "OK", [b"done"]


@pytest.fixture
def recorder(monkeypatch):
    Recorder.instances = []
    Recorder.login_error = None
    monkeypatch.setattr(imap.imaplib, "IMAP4_SSL", Recorder)
    return Recorder


ACCOUNT = Account("privat", "imap", host="imap.example.org", user="me@example.org",
                  password="s3cret-pw", port=993)


def test_connection_verifies_the_certificate_and_has_a_timeout(recorder):
    ImapClient.connect(ACCOUNT)
    args = recorder.instances[0].args
    assert args["host"] == "imap.example.org" and args["port"] == 993
    assert args["ssl_context"].verify_mode == ssl.CERT_REQUIRED
    assert args["ssl_context"].check_hostname is True
    assert args["timeout"] and args["timeout"] > 0
    assert recorder.instances[0].logged_in == ("me@example.org", "s3cret-pw")


def test_refused_login_raises_an_error_without_the_password(recorder):
    recorder.login_error = imaplib.IMAP4.error("[AUTHENTICATIONFAILED] nope")
    with pytest.raises(ImapError) as err:
        ImapClient.connect(ACCOUNT)
    assert "s3cret-pw" not in str(err.value)
    assert "privat" in str(err.value)


def test_network_errors_become_imap_errors(recorder):
    recorder.login_error = OSError("connection reset")
    with pytest.raises(ImapError):
        ImapClient.connect(ACCOUNT)


def test_certificate_error_becomes_an_imap_error_and_sends_no_login(monkeypatch):
    def refuse(*args, **kwargs):
        raise ssl.SSLCertVerificationError("bad certificate")

    monkeypatch.setattr(imap.imaplib, "IMAP4_SSL", refuse)
    with pytest.raises(ImapError, match="privat"):
        ImapClient.connect(ACCOUNT)


def test_close_logs_out():
    fake = FakeImap()
    client(fake).close()
    assert ("logout",) in fake.log


def test_status_parser_ignores_the_order_of_the_words():
    fake = FakeImap([1])
    fake.status = lambda m, w: ("OK", [b'"INBOX" (MESSAGES 1 UIDNEXT 2 UIDVALIDITY 5)'])
    cursor = client(fake).start_cursor()
    assert cursor == "5:1"
    assert re.fullmatch(r"\d+:\d+", cursor)
