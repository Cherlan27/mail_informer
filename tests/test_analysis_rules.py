import pytest

from mail_informer.analysis import rules
from mail_informer.analysis.rules import InvalidAnswer


# --- 4.1 enums and answer validation -------------------------------------------------

def test_allowed_values():
    assert set(rules.CATEGORIES) == {
        "security", "personal", "work", "authority", "appointment", "invoice",
        "delivery", "job", "newsletter", "advertising", "other",
    }
    assert rules.IMPORTANCE == ("ignore", "normal", "important", "urgent")


def test_valid_classification():
    result = rules.parse_classification(
        {"category": "security", "importance": "urgent", "reason": "Login from a new device"}
    )
    assert (result.category, result.importance) == ("security", "urgent")
    assert result.reason == "Login from a new device"


@pytest.mark.parametrize("answer", [
    {"category": "spam", "importance": "normal", "reason": "x"},      # unknown category
    {"category": "other", "importance": "critical", "reason": "x"},   # unknown importance
    {"category": "other", "importance": "normal"},                    # reason missing
    {"importance": "normal", "reason": "x"},                          # category missing
    {"category": 3, "importance": "normal", "reason": "x"},           # wrong type
    {"category": "other", "importance": None, "reason": "x"},         # wrong type
    {"category": "Other", "importance": "normal", "reason": "x"},     # case matters
    ["category", "importance"],                                       # not an object
    "urgent",                                                         # not an object
])
def test_invalid_classification_is_rejected(answer):
    with pytest.raises(InvalidAnswer):
        rules.parse_classification(answer)


def test_valid_summary():
    assert rules.parse_summary({"summary": "Die Bank meldet eine neue Anmeldung."}) == \
        "Die Bank meldet eine neue Anmeldung."


@pytest.mark.parametrize("answer", [{}, {"summary": 5}, {"summary": None}, [], "text"])
def test_invalid_summary_is_rejected(answer):
    with pytest.raises(InvalidAnswer):
        rules.parse_summary(answer)


# --- 4.3 bulk guard ------------------------------------------------------------------

def test_bulk_urgent_becomes_important():
    assert rules.apply_bulk_guard("urgent", is_bulk=True) == "important"


def test_unknown_bulk_is_treated_as_bulk():
    assert rules.apply_bulk_guard("urgent", is_bulk=None) == "important"


def test_known_non_bulk_urgent_stays_urgent():
    assert rules.apply_bulk_guard("urgent", is_bulk=False) == "urgent"


@pytest.mark.parametrize("level", ["ignore", "normal", "important"])
@pytest.mark.parametrize("is_bulk", [True, False, None])
def test_other_levels_are_never_changed(level, is_bulk):
    assert rules.apply_bulk_guard(level, is_bulk=is_bulk) == level


# --- 4.5 text cleaning and truncation ------------------------------------------------

def test_clean_text_cuts_to_max_length():
    assert rules.clean_text("a" * 50, max_len=10) == "a" * 10


def test_clean_text_removes_control_characters_but_keeps_text():
    assert rules.clean_text("Hallo\x00 \x07Welt\x1b[31m!") == "Hallo Welt[31m!"


def test_clean_text_keeps_newline_as_space_and_trims():
    assert rules.clean_text("  line one\nline two \t ") == "line one line two"


def test_summary_and_reason_are_cut_when_parsed():
    result = rules.parse_classification(
        {"category": "other", "importance": "normal", "reason": "r" * 1000}
    )
    assert len(result.reason) == rules.REASON_MAX_CHARS
    assert len(rules.parse_summary({"summary": "s" * 5000})) == rules.SUMMARY_MAX_CHARS


# --- 4.7 input builders --------------------------------------------------------------

def test_classify_input_uses_sender_subject_and_start_of_body():
    data = rules.build_classify_input("a@example.org", "Betreff", "x" * 10_000)
    assert data["sender"] == "a@example.org"
    assert data["subject"] == "Betreff"
    assert data["body"] == "x" * rules.CLASSIFY_BODY_CHARS


def test_short_body_is_not_changed():
    assert rules.build_classify_input("a", "b", "kurz")["body"] == "kurz"


def test_summarize_input_is_longer_but_still_limited():
    data = rules.build_summarize_input("a", "b", "y" * 50_000)
    assert len(data["body"]) == rules.SUMMARIZE_BODY_CHARS
    assert rules.SUMMARIZE_BODY_CHARS > rules.CLASSIFY_BODY_CHARS


def test_missing_sender_or_subject_become_empty_text():
    data = rules.build_classify_input(None, None, "")
    assert (data["sender"], data["subject"], data["body"]) == ("", "", "")
