"""Tests for hl7view.anonymize: anonymize_message, transliterate, PHI replacement."""

import copy

import pytest

from hl7view.anonymize import anonymize_message, transliterate
from hl7view.parser import parse_hl7


def _field(seg, num):
    return next(f for f in seg.fields if f.field_num == num)


def _seg(parsed, name):
    return next(s for s in parsed.segments if s.name == name)


def _pid(parsed):
    return _seg(parsed, "PID")


def test_anonymize_changes_patient_name(adt_parsed):
    original_name = _field(_pid(adt_parsed), 5).value
    anon = anonymize_message(adt_parsed)
    assert _field(_pid(anon), 5).value != original_name


def test_anonymize_changes_patient_id(adt_parsed):
    original_id = _field(_pid(adt_parsed), 3).value
    anon = anonymize_message(adt_parsed)
    assert _field(_pid(anon), 3).value != original_id


def test_anonymize_changes_dob(adt_parsed):
    original_dob = _field(_pid(adt_parsed), 7).value
    anon = anonymize_message(adt_parsed)
    new_dob = _field(_pid(anon), 7).value
    assert new_dob != original_dob
    # Still looks like a date: at least 8 chars, starts with digits
    assert len(new_dob) >= 8
    assert new_dob[:4].isdigit()


def test_anonymize_changes_phone(adt_parsed):
    original_phone = _field(_pid(adt_parsed), 13).raw_value
    anon = anonymize_message(adt_parsed)
    assert _field(_pid(anon), 13).raw_value != original_phone


def test_anonymize_preserves_structure(adt_parsed):
    anon = anonymize_message(adt_parsed)
    assert len(anon.segments) == len(adt_parsed.segments)
    assert [s.name for s in anon.segments] == [s.name for s in adt_parsed.segments]
    for orig_seg, anon_seg in zip(adt_parsed.segments, anon.segments):
        assert len(anon_seg.fields) == len(orig_seg.fields)


def test_anonymize_non_ascii_pool(adt_parsed):
    anon = anonymize_message(adt_parsed, use_non_ascii=True)
    name = _field(_pid(anon), 5).value
    # Estonian names contain non-ASCII characters
    has_non_ascii = any(ord(ch) > 127 for ch in name)
    assert has_non_ascii


def test_anonymize_does_not_mutate_original(adt_parsed):
    original_name = _field(_pid(adt_parsed), 5).value
    original_id = _field(_pid(adt_parsed), 3).value
    anonymize_message(adt_parsed)
    assert _field(_pid(adt_parsed), 5).value == original_name
    assert _field(_pid(adt_parsed), 3).value == original_id


def test_transliterate():
    assert transliterate("\u00d5ispuu") == "Oispuu"     # Õ -> O
    assert transliterate("K\u00fclli") == "Kulli"       # ü -> u
    assert transliterate("\u017danna") == "Zanna"       # Ž -> Z
    assert transliterate("Hello") == "Hello"            # pure ASCII passthrough


# ---------------------------------------------------------------------------
# NK1 tests (using ADT sample which has NK1 segment)
# ---------------------------------------------------------------------------

def test_anonymize_nk1_name(adt_parsed):
    original = _field(_seg(adt_parsed, "NK1"), 2).value
    anon = anonymize_message(adt_parsed)
    assert _field(_seg(anon, "NK1"), 2).value != original


def test_anonymize_nk1_address(adt_parsed):
    original = _field(_seg(adt_parsed, "NK1"), 4).raw_value
    anon = anonymize_message(adt_parsed)
    assert _field(_seg(anon, "NK1"), 4).raw_value != original


def test_anonymize_nk1_phone(adt_parsed):
    original = _field(_seg(adt_parsed, "NK1"), 5).raw_value
    anon = anonymize_message(adt_parsed)
    assert _field(_seg(anon, "NK1"), 5).raw_value != original


# ---------------------------------------------------------------------------
# PID extended fields (6, 18, 21, 23) — inline fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def pid_extended_parsed():
    msg = (
        "MSH|^~\\&|SYS|HOSP|RCV|HOSP|20260101120000||ADT^A01|1|P|2.5\r"
        "PID|1||123^^^HOSP^PI||Doe^Jane|Maiden^Anna|19800101|F"
        "|||123 Oak^^Town^ST^12345^US||555-1234||||S|ACCT001"
        "|||MOM001||Birth City"
    )
    return parse_hl7(msg)


def test_anonymize_pid_mothers_maiden_name(pid_extended_parsed):
    original = _field(_pid(pid_extended_parsed), 6).raw_value
    assert "Maiden" in original
    anon = anonymize_message(pid_extended_parsed)
    assert _field(_pid(anon), 6).raw_value != original


def test_anonymize_pid_account_number(pid_extended_parsed):
    original = _field(_pid(pid_extended_parsed), 18).raw_value
    assert original == "ACCT001"
    anon = anonymize_message(pid_extended_parsed)
    assert _field(_pid(anon), 18).raw_value != original


def test_anonymize_pid_mothers_id(pid_extended_parsed):
    original = _field(_pid(pid_extended_parsed), 21).raw_value
    assert original == "MOM001"
    anon = anonymize_message(pid_extended_parsed)
    assert _field(_pid(anon), 21).raw_value != original


def test_anonymize_pid_birth_place(pid_extended_parsed):
    original = _field(_pid(pid_extended_parsed), 23).raw_value
    assert original == "Birth City"
    anon = anonymize_message(pid_extended_parsed)
    assert _field(_pid(anon), 23).raw_value != original


# ---------------------------------------------------------------------------
# GT1 tests — inline fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def gt1_parsed():
    msg = (
        "MSH|^~\\&|SYS|HOSP|RCV|HOSP|20260101120000||ADT^A01|1|P|2.5\r"
        "PID|1||123^^^HOSP^PI||Doe^Jane||19800101|F\r"
        "GT1|1||Smith^Robert^M||456 Elm^^City^ST^67890^US"
        "|555-2345|555-3456|19750315|||123-45-6789"
    )
    return parse_hl7(msg)


def test_anonymize_gt1_name(gt1_parsed):
    original = _field(_seg(gt1_parsed, "GT1"), 3).value
    anon = anonymize_message(gt1_parsed)
    assert _field(_seg(anon, "GT1"), 3).value != original


def test_anonymize_gt1_address(gt1_parsed):
    original = _field(_seg(gt1_parsed, "GT1"), 5).raw_value
    anon = anonymize_message(gt1_parsed)
    assert _field(_seg(anon, "GT1"), 5).raw_value != original


def test_anonymize_gt1_phone_home(gt1_parsed):
    original = _field(_seg(gt1_parsed, "GT1"), 6).raw_value
    anon = anonymize_message(gt1_parsed)
    assert _field(_seg(anon, "GT1"), 6).raw_value != original


def test_anonymize_gt1_phone_business(gt1_parsed):
    original = _field(_seg(gt1_parsed, "GT1"), 7).raw_value
    anon = anonymize_message(gt1_parsed)
    assert _field(_seg(anon, "GT1"), 7).raw_value != original


def test_anonymize_gt1_dob(gt1_parsed):
    original = _field(_seg(gt1_parsed, "GT1"), 8).raw_value
    anon = anonymize_message(gt1_parsed)
    new_dob = _field(_seg(anon, "GT1"), 8).raw_value
    assert new_dob != original
    assert new_dob[:4].isdigit()


# ---------------------------------------------------------------------------
# IN1 tests — inline fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def in1_parsed():
    msg = (
        "MSH|^~\\&|SYS|HOSP|RCV|HOSP|20260101120000||ADT^A01|1|P|2.5\r"
        "PID|1||123^^^HOSP^PI||Doe^Jane||19800101|F\r"
        "IN1|1|BCBS|INS001|Blue Cross||||||||||"
        "||Jones^Mary||19850520|789 Pine^^Town^ST^11111^US"
    )
    return parse_hl7(msg)


def test_anonymize_in1_name(in1_parsed):
    original = _field(_seg(in1_parsed, "IN1"), 16).value
    anon = anonymize_message(in1_parsed)
    assert _field(_seg(anon, "IN1"), 16).value != original


def test_anonymize_in1_dob(in1_parsed):
    original = _field(_seg(in1_parsed, "IN1"), 18).raw_value
    anon = anonymize_message(in1_parsed)
    assert _field(_seg(anon, "IN1"), 18).raw_value != original


def test_anonymize_in1_address(in1_parsed):
    original = _field(_seg(in1_parsed, "IN1"), 19).raw_value
    anon = anonymize_message(in1_parsed)
    assert _field(_seg(anon, "IN1"), 19).raw_value != original


# ---------------------------------------------------------------------------
# MRG tests — inline fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mrg_parsed():
    msg = (
        "MSH|^~\\&|SYS|HOSP|RCV|HOSP|20260101120000||ADT^A34|1|P|2.5\r"
        "PID|1||NEW123^^^HOSP^PI||Doe^Jane||19800101|F\r"
        "MRG|OLD123^^^HOSP^PI|OLD456|||OLD789|OLD999|Prior^Name^M"
    )
    return parse_hl7(msg)


def test_anonymize_mrg_prior_ids(mrg_parsed):
    original_1 = _field(_seg(mrg_parsed, "MRG"), 1).raw_value
    anon = anonymize_message(mrg_parsed)
    assert _field(_seg(anon, "MRG"), 1).raw_value != original_1


def test_anonymize_mrg_prior_name(mrg_parsed):
    original = _field(_seg(mrg_parsed, "MRG"), 7).value
    anon = anonymize_message(mrg_parsed)
    assert _field(_seg(anon, "MRG"), 7).value != original
