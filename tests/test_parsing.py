import base64

from mail_informer.parsing import extract_body_text, parse_message


def b64(text: str, charset: str = "utf-8") -> str:
    return base64.urlsafe_b64encode(text.encode(charset)).decode()


def part(mime, text=None, filename="", charset="utf-8", parts=None):
    p = {"mimeType": mime, "filename": filename, "body": {}}
    if text is not None:
        p["body"] = {"data": b64(text, charset)}
        p["headers"] = [{"name": "Content-Type", "value": f'{mime}; charset="{charset}"'}]
    if parts:
        p["parts"] = parts
    return p


def test_plain():
    assert extract_body_text(part("text/plain", "Hallo Welt")) == "Hallo Welt"


def test_alternative_prefers_plain():
    payload = part("multipart/alternative", parts=[
        part("text/plain", "Klartext"),
        part("text/html", "<p>Ganz <b>anders</b></p>"),
    ])
    assert extract_body_text(payload) == "Klartext"


def test_html_only_converted_to_text():
    text = extract_body_text(part("text/html", "<p>Hallo <b>Welt</b></p>"))
    assert "Hallo" in text and "Welt" in text and "<" not in text


def test_no_text():
    payload = part("multipart/mixed", parts=[part("application/pdf", filename="a.pdf")])
    assert extract_body_text(payload) == ""


def test_attachment_ignored():
    payload = part("multipart/mixed", parts=[
        part("text/plain", "Text"),
        part("text/plain", "Anhang-Inhalt", filename="notes.txt"),
    ])
    assert extract_body_text(payload) == "Text"


def test_charset_latin1():
    assert extract_body_text(part("text/plain", "Grüße", charset="iso-8859-1")) == "Grüße"


def test_parse_message_fields():
    raw = {
        "id": "m1", "threadId": "t1", "internalDate": "1700000000000",
        "labelIds": ["INBOX", "UNREAD"], "snippet": "Hi",
        "payload": {
            **part("text/plain", "Body"),
            "headers": [
                {"name": "From", "value": "a@example.com"},
                {"name": "To", "value": "b@example.com"},
                {"name": "Subject", "value": "Betreff"},
            ],
        },
    }
    mail = parse_message(raw)
    assert (mail.gmail_id, mail.thread_id) == ("m1", "t1")
    assert mail.from_addr == "a@example.com" and mail.subject == "Betreff"
    assert mail.labels == ["INBOX", "UNREAD"] and mail.body_text == "Body"
    assert mail.internal_date.year == 2023
