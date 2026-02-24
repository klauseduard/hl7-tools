"""Tests for hl7view.definitions: resolve_version, get_seg_def, get_field_def, data consistency."""

from hl7view.definitions import resolve_version, get_seg_def, get_field_def


def test_resolve_version_25():
    assert resolve_version("2.5") == "2.5"
    assert resolve_version("2.5.1") == "2.5"


def test_resolve_version_23():
    assert resolve_version("2.3") == "2.3"
    assert resolve_version("2.3.1") == "2.3"
    assert resolve_version("2.4") == "2.3"


def test_resolve_version_default():
    assert resolve_version(None) == "2.5"
    assert resolve_version("") == "2.5"


def test_get_seg_def_known():
    seg = get_seg_def("MSH", "2.5")
    assert seg is not None
    assert seg["name"] == "Message Header"
    assert "fields" in seg


def test_get_seg_def_unknown():
    assert get_seg_def("ZZZ", "2.5") is None


def test_get_field_def():
    fld = get_field_def("PID", 5, "2.5")
    assert fld is not None
    assert fld["name"] == "Patient Name"
    assert fld["dt"] == "XPN"
