"""Tests for hl7view.profile: load_profile, get_profile_*, validation counts."""

from hl7view.profile import (
    load_profile,
    get_profile_segment,
    get_profile_field,
    get_profile_component,
)
from hl7view.formatter import _profile_validation_counts


def test_load_profile(sample_profile):
    assert sample_profile["name"] == "Carestream v2.3 ORM/ORU"
    assert "segments" in sample_profile


def test_get_profile_segment(sample_profile):
    msh = get_profile_segment(sample_profile, "MSH")
    assert msh is not None
    assert "fields" in msh
    assert get_profile_segment(sample_profile, "NONEXIST") is None


def test_get_profile_field(sample_profile):
    fld = get_profile_field(sample_profile, "MSH", 3)
    assert fld is not None
    assert fld["customName"] == "Sending Application (RadIS)"
    assert get_profile_field(sample_profile, "MSH", 999) is None


def test_get_profile_component(sample_profile):
    # PID field 3 has components defined (1, 4, 5)
    comp = get_profile_component(sample_profile, "PID", 3, 1)
    assert comp is not None
    assert "description" in comp
    assert get_profile_component(sample_profile, "PID", 3, 999) is None


def test_profile_none_safe():
    assert get_profile_segment(None, "MSH") is None
    assert get_profile_field(None, "MSH", 3) is None
    assert get_profile_component(None, "MSH", 3, 1) is None


def test_validation_counts_no_profile(adt_parsed):
    req, mis, missing, unexpected = _profile_validation_counts(adt_parsed, None)
    assert req == 0
    assert mis == 0
    assert missing == []
    assert unexpected == []


def test_validation_counts_missing_segs(adt_parsed, sample_profile):
    """ADT message lacks OBR, OBX, ZDS — profile expects them."""
    _, _, missing_segs, _ = _profile_validation_counts(adt_parsed, sample_profile)
    for seg in ["OBR", "OBX", "ZDS"]:
        assert seg in missing_segs


def test_validation_counts_unexpected_segs(adt_parsed, sample_profile):
    """ADT has EVN, NK1, PV1 which the sample profile doesn't define."""
    _, _, _, unexpected_segs = _profile_validation_counts(adt_parsed, sample_profile)
    for seg in ["EVN", "NK1", "PV1"]:
        assert seg in unexpected_segs
