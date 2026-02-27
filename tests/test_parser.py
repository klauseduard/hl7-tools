"""Tests for hl7view.parser: parse_hl7, MSH numbering, components, repetitions, reparse/rebuild."""

from hl7view.parser import parse_hl7, reparse_field, rebuild_raw_line


def _field(seg, num):
    """Get field by field_num from a segment."""
    return next(f for f in seg.fields if f.field_num == num)


# --- Structure ---

def test_parse_adt_structure(adt_parsed):
    assert len(adt_parsed.segments) == 5
    assert [s.name for s in adt_parsed.segments] == ["MSH", "EVN", "PID", "NK1", "PV1"]
    assert adt_parsed.version == "2.5"
    assert adt_parsed.message_type == "ADT^A01"


def test_parse_orm_structure(orm_parsed):
    assert len(orm_parsed.segments) == 6
    names = [s.name for s in orm_parsed.segments]
    assert "ZDS" in names
    assert orm_parsed.version == "2.3.1"
    assert orm_parsed.message_type == "ORM^O01"


def test_parse_oru_structure(oru_parsed):
    # MSH, PID, PV1, ORC, OBR, OBX×5, NTE = 11
    assert len(oru_parsed.segments) == 11
    obx_segs = [s for s in oru_parsed.segments if s.name == "OBX"]
    assert len(obx_segs) == 5
    assert oru_parsed.message_type == "ORU^R01"


def test_v28_sample_parses(oru_v28_parsed):
    assert oru_v28_parsed.version == "2.8"
    assert oru_v28_parsed.message_type == "ORU^R01^ORU_R01"
    seg_names = [s.name for s in oru_v28_parsed.segments]
    assert "SFT" in seg_names
    assert "SPM" in seg_names
    assert "OBX" in seg_names
    assert len(oru_v28_parsed.segments) == 13


# --- MSH field numbering ---

def test_msh_field_numbering(adt_parsed):
    msh = adt_parsed.segments[0]
    assert msh.name == "MSH"
    assert _field(msh, 1).value == "|"
    assert _field(msh, 2).value == "^~\\&"
    msh9 = _field(msh, 9)
    assert msh9.value == "ADT^A01"


# --- PID field values ---

def test_pid_field_values(adt_parsed):
    pid = next(s for s in adt_parsed.segments if s.name == "PID")
    assert "PAT78432" in _field(pid, 3).value
    assert "Tamm" in _field(pid, 5).value


# --- Components ---

def test_component_splitting(adt_parsed):
    pid = next(s for s in adt_parsed.segments if s.name == "PID")
    pid5 = _field(pid, 5)
    assert len(pid5.components) >= 3
    assert pid5.components[0].value == "Tamm"       # family name
    assert pid5.components[1].value == "Kristjan"    # given name
    assert pid5.components[2].value == "Aleksander"  # middle name


def test_subcomponent_splitting():
    """Synthetic field with & subcomponents."""
    raw = "MSH|^~\\&|A|B|C|D|20260101||ADT^A01|1|P|2.5\rPID|1||123^^^AUTH&1.2.3&ISO^PI"
    parsed = parse_hl7(raw)
    pid = next(s for s in parsed.segments if s.name == "PID")
    pid3 = _field(pid, 3)
    # Component 4 is "AUTH&1.2.3&ISO" — should have subcomponents
    comp4 = pid3.components[3]
    assert len(comp4.subcomponents) == 3
    assert comp4.subcomponents[0] == "AUTH"
    assert comp4.subcomponents[1] == "1.2.3"
    assert comp4.subcomponents[2] == "ISO"


# --- Repetitions ---

def test_repetition_splitting(adt_parsed):
    pid = next(s for s in adt_parsed.segments if s.name == "PID")
    pid13 = _field(pid, 13)
    assert len(pid13.repetitions) == 2
    assert "+37255500123" in pid13.repetitions[0].value
    assert "+37255500456" in pid13.repetitions[1].value


# --- Declared charset ---

def test_declared_charset(adt_parsed, orm_parsed):
    assert adt_parsed.declared_charset == "UNICODE UTF-8"
    assert orm_parsed.declared_charset == "8859/1"


# --- Repeated segments ---

def test_repeated_segments(oru_parsed):
    obx_segs = [s for s in oru_parsed.segments if s.name == "OBX"]
    assert len(obx_segs) == 5
    assert [s.rep_index for s in obx_segs] == [1, 2, 3, 4, 5]


# --- Edge cases ---

def test_parse_empty_returns_none():
    assert parse_hl7("") is None


def test_parse_garbage_returns_minimal():
    """Non-HL7 input produces a message with no usable fields (no MSH, no version)."""
    result = parse_hl7("not hl7 at all")
    # Parser doesn't reject — but no MSH means no version/message_type
    assert result is not None
    assert result.version is None
    assert result.message_type is None


# --- Reparse / rebuild ---

def test_reparse_field(adt_parsed):
    pid = next(s for s in adt_parsed.segments if s.name == "PID")
    pid5 = _field(pid, 5)
    reparse_field(pid5, "NEW^VALUE^MID")
    assert pid5.value == "NEW^VALUE^MID"
    assert pid5.raw_value == "NEW^VALUE^MID"
    assert pid5.components[0].value == "NEW"
    assert pid5.components[1].value == "VALUE"
    assert pid5.components[2].value == "MID"


def test_rebuild_raw_line(adt_parsed):
    pid = next(s for s in adt_parsed.segments if s.name == "PID")
    pid5 = _field(pid, 5)
    reparse_field(pid5, "DOE^JANE")
    rebuilt = rebuild_raw_line("PID", pid.fields)
    assert rebuilt.startswith("PID|")
    assert "DOE^JANE" in rebuilt


# --- Normalization ---

def test_normalize_mixed_line_endings():
    """Message with \r\n line endings parses correctly."""
    raw = "MSH|^~\\&|A|B|C|D|20260101||ADT^A01|1|P|2.5\r\nEVN|A01|20260101\r\nPID|1||123"
    parsed = parse_hl7(raw)
    assert parsed is not None
    names = [s.name for s in parsed.segments]
    assert "MSH" in names
    assert "EVN" in names
    assert "PID" in names
