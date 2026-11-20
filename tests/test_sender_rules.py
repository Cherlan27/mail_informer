import pytest

from mail_informer.analysis.sender_rules import (
    RuleFileError, SenderRule, load_rules, match, parse_rules)


def rule(**kw):
    base = {"name": "r1", "domain": "example.com", "category": "newsletter", "importance": "ignore"}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}  # None removes a key


def parse(*rules):
    return parse_rules({"rule": list(rules)})


# --- 1.1 parse_rules -------------------------------------------------------------------

def test_valid_file_gives_rules():
    rules = parse(rule(), rule(name="r2", sender="Jobs@Example.org", domain=None, category="job",
                               importance="normal"))
    assert rules == [
        SenderRule("r1", "domain", "example.com", "newsletter", "ignore"),
        SenderRule("r2", "sender", "jobs@example.org", "job", "normal"),
    ]


def test_file_without_rules_gives_no_rules():
    assert parse_rules({}) == []


@pytest.mark.parametrize("importance", ["important", "urgent"])
def test_rule_raises_importance(importance):
    with pytest.raises(ValueError, match="r1"):
        parse(rule(importance=importance))


def test_unknown_importance_is_refused():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(importance="high"))


def test_unknown_category():
    with pytest.raises(ValueError, match="r1.*category"):
        parse(rule(category="spam"))


def test_address_and_domain_in_one_rule():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(sender="a@example.com"))


def test_neither_address_nor_domain():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(domain=None))


def test_duplicate_name():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(), rule(domain="other.com"))


def test_duplicate_domain():
    with pytest.raises(ValueError, match="r2"):
        parse(rule(), rule(name="r2", domain="EXAMPLE.com"))


def test_duplicate_address():
    with pytest.raises(ValueError, match="r2"):
        parse(rule(sender="a@example.com", domain=None),
              rule(name="r2", sender="A@example.com", domain=None))


def test_unknown_key_names_rule_and_key():
    with pytest.raises(ValueError, match="r1.*subject"):
        parse(rule(subject="Sale"))


def test_missing_name_is_refused():
    with pytest.raises(ValueError, match="name"):
        parse({k: v for k, v in rule().items() if k != "name"})


def test_missing_category_names_rule():
    with pytest.raises(ValueError, match="r1.*category"):
        parse({k: v for k, v in rule().items() if k != "category"})


def test_rule_that_is_not_a_table_is_refused():
    with pytest.raises(ValueError):
        parse_rules({"rule": ["x"]})


def test_unknown_top_level_key_is_refused():
    with pytest.raises(ValueError, match="rules"):
        parse_rules({"rules": []})


def test_address_without_at_sign_is_refused():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(sender="example.com", domain=None))


def test_domain_with_at_sign_is_refused():
    with pytest.raises(ValueError, match="r1"):
        parse(rule(domain="a@example.com"))


@pytest.mark.parametrize("sender", [
    "LinkedIn <jobs@linkedin.com>",
    "<jobs@linkedin.com>",
    " jobs@linkedin.com",
    "jobs@linkedin.com ",
    "jobs@linkedin.com, news@linkedin.com",
    "jobs(news)@linkedin.com",
])
def test_sender_that_is_not_a_plain_address_is_refused(sender):
    with pytest.raises(ValueError, match="r1.*'sender'"):
        parse(rule(sender=sender, domain=None))


def test_plain_address_is_still_accepted():
    assert parse(rule(sender="Jobs@LinkedIn.com", domain=None))[0].value == "jobs@linkedin.com"


@pytest.mark.parametrize("domain", [".example.com", "example.com.", " example.com", "example.com	"])
def test_domain_with_dot_or_whitespace_at_an_end_is_refused(domain):
    with pytest.raises(ValueError, match="r1.*'domain'"):
        parse(rule(domain=domain))


def test_error_label_uses_the_trimmed_name():
    with pytest.raises(ValueError) as e:
        parse(rule(name=" shop-ads ", domain=".example.com"))
    assert str(e.value).startswith("rule 'shop-ads':")


# --- 1.2 load_rules --------------------------------------------------------------------

def test_load_rules_reads_a_file(tmp_path):
    f = tmp_path / "rules.toml"
    f.write_text('[[rule]]\nname = "ads"\ndomain = "shop.example"\n'
                 'category = "advertising"\nimportance = "ignore"\n', encoding="utf-8")
    assert load_rules(f) == [SenderRule("ads", "domain", "shop.example", "advertising", "ignore")]


def test_file_missing(tmp_path):
    with pytest.raises(ValueError, match="rules.toml"):
        load_rules(tmp_path / "rules.toml")


def test_invalid_toml(tmp_path):
    f = tmp_path / "rules.toml"
    f.write_text("[[rule\nname =", encoding="utf-8")
    with pytest.raises(ValueError, match="rules.toml"):
        load_rules(f)


# --- 1.3 match -------------------------------------------------------------------------

ADDRESS = SenderRule("jobs", "sender", "jobs@example.com", "job", "ignore")
DOMAIN = SenderRule("example", "domain", "example.com", "newsletter", "ignore")


def test_exact_address():
    assert match([ADDRESS], '"Example Jobs" <Jobs@Example.com>') is ADDRESS


def test_other_address_does_not_match_an_address_rule():
    assert match([ADDRESS], "news@example.com") is None


def test_domain():
    assert match([DOMAIN], "news@example.com") is DOMAIN


def test_subdomain_does_not_match():
    assert match([DOMAIN], "news@mail.example.com") is None


def test_address_rule_wins():
    assert match([DOMAIN, ADDRESS], "jobs@example.com") is ADDRESS


@pytest.mark.parametrize("from_addr", [None, "", "no address here"])
def test_no_sender_address(from_addr):
    assert match([DOMAIN, ADDRESS], from_addr) is None


# --- 3 stricter values ------------------------------------------------------------------

@pytest.mark.parametrize("domain", [
    ".example.com", "example.com.", "exa mple.com", "example..com", "-example.com",
    "example-.com", "example", "http://example.com", "example.com/x", "a_b.example.com",
    "a" * 64 + ".com",
])
def test_domain_that_is_not_a_host_name_is_refused(domain):
    with pytest.raises(ValueError, match="r1.*'domain'"):
        parse(rule(domain=domain))


def test_valid_domain_is_stored_in_lower_case():
    assert parse(rule(domain="Mail.Example-Shop.co.uk"))[0].value == "mail.example-shop.co.uk"


def test_domain_label_of_63_characters_is_accepted():
    assert parse(rule(domain="a" * 63 + ".com"))[0].value == "a" * 63 + ".com"


@pytest.mark.parametrize("sender", [
    "a b@x.com", "a@.com", "a@x..com", "a@x", "@x.com", "a@b@x.com", "a@-x.com",
])
def test_sender_with_an_invalid_address_part_is_refused(sender):
    with pytest.raises(ValueError, match="r1.*'sender'"):
        parse(rule(sender=sender, domain=None))


@pytest.mark.parametrize("field, value", [
    ("sender", " a@example.com"),
    ("sender", "a@example.com\t"),
    ("domain", " example.com"),
    ("domain", "example.com "),
    ("category", "newsletter "),
    ("category", " newsletter"),
    ("importance", "ignore "),
    ("importance", " ignore"),
])
def test_value_with_surrounding_whitespace_is_refused(field, value):
    kw = {field: value}
    if field == "sender":
        kw["domain"] = None
    with pytest.raises(ValueError, match=f"r1.*'{field}'"):
        parse(rule(**kw))


@pytest.mark.parametrize("first, second", [("Ads", "ads"), ("ads", "Ads")])
def test_names_that_differ_only_in_case_are_duplicates(first, second):
    with pytest.raises(ValueError, match=f"'{second}'.*used twice"):
        parse(rule(name=first), rule(name=second, domain="other.com"))


def test_stored_name_keeps_its_case():
    assert parse(rule(name=" Shop-Ads "))[0].name == "Shop-Ads"


# --- 4 error type and unknown keys -------------------------------------------------------

def test_rule_errors_are_rule_file_errors():
    with pytest.raises(RuleFileError):
        parse(rule(category="spam"))


def test_load_errors_are_rule_file_errors(tmp_path):
    with pytest.raises(RuleFileError):
        load_rules(tmp_path / "missing.toml")
    f = tmp_path / "rules.toml"
    f.write_text("[[rule\nname =", encoding="utf-8")
    with pytest.raises(RuleFileError):
        load_rules(f)


def test_several_unknown_keys_are_named_in_sorted_order():
    with pytest.raises(RuleFileError) as e:
        parse(rule(zeta=1, mu=2, alpha=3, kappa=4, beta=5))
    assert "['alpha', 'beta', 'kappa', 'mu', 'zeta']" in str(e.value)
