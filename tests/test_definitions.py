"""Tests for hl7view.definitions: resolve_version, get_seg_def, get_field_def, data consistency."""

from hl7view.definitions import resolve_version, get_seg_def, get_field_def, HL7_V25, HL7_V28


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


# --- v2.8 definitions ---

def test_resolve_version_28():
    assert resolve_version("2.8") == "2.8"
    assert resolve_version("2.8.1") == "2.8"


def test_resolve_version_26_27_fallback():
    assert resolve_version("2.6") == "2.5"
    assert resolve_version("2.7") == "2.5"
    assert resolve_version("2.7.1") == "2.5"


def test_get_seg_def_v28():
    """OBX-20 exists in v2.8 with CWE type."""
    fld = get_field_def("OBX", 20, "2.8")
    assert fld is not None
    assert fld["name"] == "Observation Site"
    assert fld["dt"] == "CWE"


def test_get_seg_def_v28_new_segments():
    """SPM and SFT are available in v2.8."""
    spm = get_seg_def("SPM", "2.8")
    assert spm is not None
    assert spm["name"] == "Specimen"
    sft = get_seg_def("SFT", "2.8")
    assert sft is not None
    assert sft["name"] == "Software Segment"


def test_get_seg_def_v25_new_segments():
    """SPM and SFT are also available in v2.5 (added to base)."""
    spm = get_seg_def("SPM", "2.5")
    assert spm is not None
    sft = get_seg_def("SFT", "2.5")
    assert sft is not None
    tq1 = get_seg_def("TQ1", "2.5")
    assert tq1 is not None
    tq2 = get_seg_def("TQ2", "2.5")
    assert tq2 is not None


def test_v28_ce_to_cwe():
    """OBX-3 is CE in v2.5, CWE in v2.8."""
    fld_25 = get_field_def("OBX", 3, "2.5")
    assert fld_25["dt"] == "CE"
    fld_28 = get_field_def("OBX", 3, "2.8")
    assert fld_28["dt"] == "CWE"


def test_v28_msh_extensions():
    """MSH-22..25 exist in v2.8 but not in v2.5."""
    for fnum in (22, 23, 24, 25):
        assert get_field_def("MSH", fnum, "2.8") is not None
        assert get_field_def("MSH", fnum, "2.5") is None


def test_v28_obx_extensions():
    """OBX-20..25 exist in v2.8 but not in v2.5."""
    for fnum in (20, 21, 22, 23, 24, 25):
        assert get_field_def("OBX", fnum, "2.8") is not None
        assert get_field_def("OBX", fnum, "2.5") is None


def test_v28_does_not_mutate_v25():
    """Deepcopy isolation: v2.8 changes must not affect v2.5."""
    assert "OBX" in HL7_V25
    assert 20 not in HL7_V25["OBX"]["fields"]
    assert 22 not in HL7_V25["MSH"]["fields"]
    assert HL7_V25["OBX"]["fields"][3]["dt"] == "CE"
    assert HL7_V25["OBR"]["fields"][4]["dt"] == "CE"
