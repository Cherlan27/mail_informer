from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mail_informer.notify import rules

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def mail(gmail_id, importance, minutes=0):
    return SimpleNamespace(
        gmail_id=gmail_id, importance=importance, analyzed_at=BASE + timedelta(minutes=minutes))


def test_text_loses_control_characters_and_is_cut():
    message = rules.mail_message(
        "work", "urgent", "Anna\x00 <a@example.org>\x07", "Zeile eins\nZeile zwei\x1b")
    assert message["sender"] == "Anna <a@example.org>"
    assert message["summary"] == "Zeile eins Zeile zwei"


def test_sender_is_cut_to_200_and_summary_to_500_characters():
    message = rules.mail_message("work", "urgent", "s" * 300, "z" * 900)
    assert len(message["sender"]) == 200
    assert len(message["summary"]) == 500


def test_mail_message_has_exactly_the_allowed_keys():
    message = rules.mail_message("security", "important", "Bank", "Kurz.")
    assert message == {
        "kind": "mail", "category": "security", "importance": "important",
        "sender": "Bank", "summary": "Kurz.",
    }


def test_digest_message_has_exactly_kind_and_count():
    assert rules.digest_message(15) == {"kind": "digest", "count": 15}


def test_free_places_are_the_limit_minus_sent_and_never_negative():
    assert rules.free_places(0) == 10
    assert rules.free_places(4) == 6
    assert rules.free_places(10) == 0
    assert rules.free_places(25) == 0


def test_urgent_first_then_newest_first():
    ordered = rules.order_mails([
        mail("old-important", "important", 1),
        mail("new-important", "important", 5),
        mail("old-urgent", "urgent", 2),
        mail("new-urgent", "urgent", 4),
    ])
    assert [m.gmail_id for m in ordered] == \
        ["new-urgent", "old-urgent", "new-important", "old-important"]


def test_split_gives_singles_up_to_the_room_and_the_rest():
    mails = [mail(str(i), "important", i) for i in range(25)]
    singles, rest = rules.split_by_room(mails, 10)
    assert len(singles) == 10 and len(rest) == 15
    assert [m.gmail_id for m in singles] == [str(i) for i in range(24, 14, -1)]


def test_split_with_no_room_puts_everything_in_the_rest():
    singles, rest = rules.split_by_room([mail("a", "urgent")], 0)
    assert singles == [] and [m.gmail_id for m in rest] == ["a"]
