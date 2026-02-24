"""Tests for hl7view.anonymize: anonymize_message, transliterate, PHI replacement."""

import copy

from hl7view.anonymize import anonymize_message, transliterate


def _field(seg, num):
    return next(f for f in seg.fields if f.field_num == num)


def _pid(parsed):
    return next(s for s in parsed.segments if s.name == "PID")


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
