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


def test_new_segments_v25():
    """All 11 new segments exist in v2.5 with correct field counts."""
    expected = {
        "RXA": 26, "RXE": 44, "RXO": 28, "RXR": 6,
        "FT1": 31, "PR1": 20, "PD1": 21, "IN2": 72,
        "ROL": 12, "DB1": 8, "ACC": 11,
    }
    for seg_name, field_count in expected.items():
        seg = get_seg_def(seg_name, "2.5")
        assert seg is not None, f"{seg_name} missing from v2.5"
        assert len(seg["fields"]) == field_count, (
            f"{seg_name} expected {field_count} fields, got {len(seg['fields'])}")


def test_new_segments_v28():
    """All 11 new segments also exist in v2.8 (inherited via deepcopy)."""
    for seg_name in ["RXA", "RXE", "RXO", "RXR", "FT1", "PR1",
                     "PD1", "IN2", "ROL", "DB1", "ACC"]:
        seg = get_seg_def(seg_name, "2.8")
        assert seg is not None, f"{seg_name} missing from v2.8"


def test_new_segments_ce_to_cwe_v28():
    """CE fields in new segments become CWE in v2.8."""
    # RXA-5 is CE in v2.5, CWE in v2.8
    assert get_field_def("RXA", 5, "2.5")["dt"] == "CE"
    assert get_field_def("RXA", 5, "2.8")["dt"] == "CWE"
    # FT1-7 is CE in v2.5, CWE in v2.8
    assert get_field_def("FT1", 7, "2.5")["dt"] == "CE"
    assert get_field_def("FT1", 7, "2.8")["dt"] == "CWE"
    # PR1-3 is CE in v2.5, CWE in v2.8
    assert get_field_def("PR1", 3, "2.5")["dt"] == "CE"
    assert get_field_def("PR1", 3, "2.8")["dt"] == "CWE"


def test_new_data_types():
    """New data types JCC, LA1, LA2, RMC, PTA, DDI are defined."""
    from hl7view.definitions import DATA_TYPES
    for dt_name in ["JCC", "LA1", "LA2", "RMC", "PTA", "DDI"]:
        assert dt_name in DATA_TYPES, f"{dt_name} missing from DATA_TYPES"
        assert "components" in DATA_TYPES[dt_name], f"{dt_name} has no components"


def test_v28_does_not_mutate_v25():
    """Deepcopy isolation: v2.8 changes must not affect v2.5."""
    assert "OBX" in HL7_V25
    assert 20 not in HL7_V25["OBX"]["fields"]
    assert 22 not in HL7_V25["MSH"]["fields"]
    assert HL7_V25["OBX"]["fields"][3]["dt"] == "CE"
    assert HL7_V25["OBR"]["fields"][4]["dt"] == "CE"


# --- JS codegen sync ---

def test_js_defs_in_sync():
    """hl7-viewer.html JS definitions match Python source of truth."""
    import os
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(project_root, "tools"))
    from gen_js_defs import generate_js_block, START_MARKER, END_MARKER

    expected = generate_js_block()

    html_path = os.path.join(project_root, "hl7-viewer.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)
    assert start_idx != -1, f"Marker {START_MARKER} not found in hl7-viewer.html"
    assert end_idx != -1, f"Marker {END_MARKER} not found in hl7-viewer.html"

    # Extract content between markers (after START_MARKER newline, before END_MARKER)
    actual = content[start_idx + len(START_MARKER) + 1 : end_idx].rstrip("\n")

    assert actual == expected, (
        "JS definitions in hl7-viewer.html are out of sync with Python. "
        "Run: venv/bin/python tools/gen_js_defs.py"
    )
