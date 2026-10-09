from datetime import datetime, timezone
from email.message import EmailMessage

from mail_informer.parsing import parse_raw_message

RECEIVED = datetime(2026, 10, 9, 8, 30, tzinfo=timezone.utc)


def build(body="Hello there", subject="Hi", message_id="<abc@example.org>", **headers) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Anna <anna@example.org>"
    msg["To"] = "me@example.org"
    msg["Subject"] = subject
    if message_id:
        msg["Message-ID"] = message_id
    for key, value in headers.items():
        msg[key.replace("_", "-")] = value
    msg.set_content(body)
    return msg


def parse(msg: EmailMessage, account: str = "privat"):
    return parse_raw_message(msg.as_bytes(), RECEIVED, account)


def test_plain_text_mail_fields():
    mail = parse(build())
    assert mail.body_text == "Hello there"
    assert mail.subject == "Hi"
    assert mail.from_addr == "Anna <anna@example.org>"
    assert mail.to_addrs == "me@example.org"
    assert mail.internal_date == RECEIVED
    assert mail.labels == ["INBOX"]


def test_html_only_mail_is_converted_to_text():
    msg = EmailMessage()
    msg["Message-ID"] = "<h@example.org>"
    msg.set_content("<p>Hello <b>world</b></p>", subtype="html")
    mail = parse(msg)
    assert "Hello" in mail.body_text and "world" in mail.body_text
    assert "<p>" not in mail.body_text


def test_plain_part_wins_over_html():
    msg = build("plain text")
    msg.add_alternative("<p>html text</p>", subtype="html")
    assert parse(msg).body_text == "plain text"


def test_attachment_is_ignored():
    msg = build("the body")
    msg.add_attachment(b"secret bytes", maintype="text", subtype="plain", filename="a.txt")
    assert parse(msg).body_text == "the body"


def test_mail_without_text_has_empty_body():
    msg = EmailMessage()
    msg["Message-ID"] = "<n@example.org>"
    msg.set_content(b"\x00\x01", maintype="application", subtype="octet-stream")
    assert parse(msg).body_text == ""


def test_encoded_subject_and_sender_are_decoded():
    raw = (
        b"From: =?utf-8?q?J=C3=BCrgen?= <j@example.org>\r\n"
        b"Subject: =?utf-8?q?Gr=C3=BC=C3=9Fe?=\r\n"
        b"Message-ID: <e@example.org>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\nhi"
    )
    mail = parse_raw_message(raw, RECEIVED, "privat")
    assert mail.subject == "Grüße"
    assert mail.from_addr.startswith("Jürgen")


def test_unknown_charset_does_not_fail():
    raw = (
        b"Message-ID: <c@example.org>\r\n"
        b"Content-Type: text/plain; charset=made-up-9\r\n\r\ncaf\xc3\xa9"
    )
    assert "caf" in parse_raw_message(raw, RECEIVED, "privat").body_text


def test_list_unsubscribe_sets_bulk_flag():
    assert parse(build(List_Unsubscribe="<mailto:u@example.org>")).is_bulk is True
    assert parse(build()).is_bulk is False


def test_key_comes_from_message_id_with_account_prefix():
    assert parse(build()).gmail_id == "privat:abc@example.org"


def test_same_message_id_in_two_accounts_gives_two_keys():
    msg = build()
    assert parse(msg, "privat").gmail_id != parse(msg, "firma").gmail_id


def test_missing_message_id_gives_a_stable_hash_key():
    msg = build(message_id=None, Date="Fri, 09 Oct 2026 08:00:00 +0000")
    first, second = parse(msg), parse(msg)
    assert first.gmail_id == second.gmail_id
    assert first.gmail_id.startswith("privat:")
    assert "@" not in first.gmail_id


def test_different_mails_without_message_id_get_different_keys():
    a = parse(build("one", message_id=None))
    b = parse(build("two", message_id=None))
    assert a.gmail_id != b.gmail_id


def test_thread_is_first_reference():
    mail = parse(build(References="<root@example.org> <mid@example.org>",
                       In_Reply_To="<mid@example.org>"))
    assert mail.thread_id == "privat:root@example.org"


def test_thread_falls_back_to_in_reply_to_then_own_key():
    assert parse(build(In_Reply_To="<mid@example.org>")).thread_id == "privat:mid@example.org"
    assert parse(build()).thread_id == "privat:abc@example.org"


def test_snippet_is_cut_and_whitespace_collapsed():
    mail = parse(build("word  \n\n  " * 100))
    assert len(mail.snippet) <= 200
    assert "  " not in mail.snippet and "\n" not in mail.snippet
