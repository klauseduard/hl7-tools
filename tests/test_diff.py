"""Tests for hl7view.diff — field-level message comparison."""

import copy

import pytest

from hl7view.parser import parse_hl7, reparse_field, rebuild_raw_line
from hl7view.diff import diff_messages, FieldDiff, SegmentDiff, MessageDiff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _modify_field(parsed, seg_name, field_num, new_value, rep_index=1):
    """Modify a field in a parsed message (returns a deep copy)."""
    msg = copy.deepcopy(parsed)
    for seg in msg.segments:
        if seg.name == seg_name and seg.rep_index == rep_index:
            for fld in seg.fields:
                if fld.field_num == field_num:
                    reparse_field(fld, new_value)
                    seg.raw_line = rebuild_raw_line(seg.name, seg.fields)
                    return msg
    raise ValueError(f"Field {seg_name}-{field_num} not found")


def _remove_segment(parsed, seg_name, rep_index=1):
    """Remove a segment from a parsed message (returns a deep copy)."""
    msg = copy.deepcopy(parsed)
    msg.segments = [s for s in msg.segments
                    if not (s.name == seg_name and s.rep_index == rep_index)]
    return msg


def _diff_statuses(diff_result):
    """Extract flat list of (address, status) from a MessageDiff."""
    result = []
    for sd in diff_result.segment_diffs:
        for fd in sd.field_diffs:
            result.append((fd.address, fd.status))
    return result


def _changed_fields(diff_result):
    """Extract field diffs that are not identical."""
    return [fd for sd in diff_result.segment_diffs
            for fd in sd.field_diffs if fd.status != 'identical']


# ---------------------------------------------------------------------------
# Tests: identical messages
# ---------------------------------------------------------------------------

class TestIdenticalMessages:

    def test_identical_adt(self, adt_parsed):
        result = diff_messages(adt_parsed, copy.deepcopy(adt_parsed))
        assert result.summary['modified'] == 0
        assert result.summary['a_only'] == 0
        assert result.summary['b_only'] == 0
        assert result.summary['identical'] == result.summary['total_fields']

    def test_identical_oru(self, oru_parsed):
        result = diff_messages(oru_parsed, copy.deepcopy(oru_parsed))
        assert result.summary['modified'] == 0
        assert result.summary['a_only'] == 0
        assert result.summary['b_only'] == 0

    def test_all_segment_diffs_identical(self, adt_parsed):
        result = diff_messages(adt_parsed, copy.deepcopy(adt_parsed))
        for sd in result.segment_diffs:
            assert sd.status == 'identical'

    def test_metadata_preserved(self, adt_parsed):
        result = diff_messages(adt_parsed, copy.deepcopy(adt_parsed))
        assert result.version_a == '2.5'
        assert result.version_b == '2.5'
        assert result.type_a == 'ADT^A01'
        assert result.type_b == 'ADT^A01'


# ---------------------------------------------------------------------------
# Tests: single field modified
# ---------------------------------------------------------------------------

class TestSingleFieldModified:

    def test_modify_pid_name(self, adt_parsed):
        msg_b = _modify_field(adt_parsed, 'PID', 5, 'DOE^JOHN')
        result = diff_messages(adt_parsed, msg_b)
        assert result.summary['modified'] == 1
        changed = _changed_fields(result)
        assert len(changed) == 1
        assert changed[0].address == 'PID-5'
        assert changed[0].status == 'modified'
        assert 'Tamm' in changed[0].value_a
        assert changed[0].value_b == 'DOE^JOHN'

    def test_modify_msh_control_id(self, adt_parsed):
        msg_b = _modify_field(adt_parsed, 'MSH', 10, 'MSG99999')
        result = diff_messages(adt_parsed, msg_b)
        changed = _changed_fields(result)
        modified = [f for f in changed if f.status == 'modified']
        assert len(modified) == 1
        assert modified[0].address == 'MSH-10'

    def test_modify_preserves_other_fields(self, adt_parsed):
        msg_b = _modify_field(adt_parsed, 'PID', 5, 'DOE^JOHN')
        result = diff_messages(adt_parsed, msg_b)
        # All other fields should be identical
        assert result.summary['identical'] == result.summary['total_fields'] - 1


# ---------------------------------------------------------------------------
# Tests: added/removed segments
# ---------------------------------------------------------------------------

class TestSegmentAddRemove:

    def test_segment_only_in_a(self, adt_parsed):
        msg_b = _remove_segment(adt_parsed, 'NK1')
        result = diff_messages(adt_parsed, msg_b)
        nk1_diffs = [sd for sd in result.segment_diffs if sd.name == 'NK1']
        assert len(nk1_diffs) == 1
        assert nk1_diffs[0].status == 'a_only'
        assert all(fd.status == 'a_only' for fd in nk1_diffs[0].field_diffs)

    def test_segment_only_in_b(self, adt_parsed):
        msg_a = _remove_segment(adt_parsed, 'NK1')
        result = diff_messages(msg_a, adt_parsed)
        nk1_diffs = [sd for sd in result.segment_diffs if sd.name == 'NK1']
        assert len(nk1_diffs) == 1
        assert nk1_diffs[0].status == 'b_only'
        assert all(fd.status == 'b_only' for fd in nk1_diffs[0].field_diffs)

    def test_a_only_counts(self, adt_parsed):
        msg_b = _remove_segment(adt_parsed, 'NK1')
        result = diff_messages(adt_parsed, msg_b)
        # NK1 has fields — they should all be a_only
        nk1_seg = [s for s in adt_parsed.segments if s.name == 'NK1'][0]
        assert result.summary['a_only'] == len(nk1_seg.fields)

    def test_removed_evn_segment(self, adt_parsed):
        msg_b = _remove_segment(adt_parsed, 'EVN')
        result = diff_messages(adt_parsed, msg_b)
        evn_diffs = [sd for sd in result.segment_diffs if sd.name == 'EVN']
        assert evn_diffs[0].status == 'a_only'


# ---------------------------------------------------------------------------
# Tests: different OBX counts (ORU has 5 OBX segments)
# ---------------------------------------------------------------------------

class TestDifferentOBXCounts:

    def test_oru_fewer_obx_in_b(self, oru_parsed):
        """Remove OBX[5] from B — should show as a_only."""
        msg_b = _remove_segment(oru_parsed, 'OBX', rep_index=5)
        result = diff_messages(oru_parsed, msg_b)
        obx5_diffs = [sd for sd in result.segment_diffs
                      if sd.name == 'OBX' and sd.rep_index == 5]
        assert len(obx5_diffs) == 1
        assert obx5_diffs[0].status == 'a_only'

    def test_oru_extra_obx_in_b(self, oru_parsed):
        """Remove OBX[5] from A — should show as b_only."""
        msg_a = _remove_segment(oru_parsed, 'OBX', rep_index=5)
        result = diff_messages(msg_a, oru_parsed)
        obx5_diffs = [sd for sd in result.segment_diffs
                      if sd.name == 'OBX' and sd.rep_index == 5]
        assert len(obx5_diffs) == 1
        assert obx5_diffs[0].status == 'b_only'

    def test_modified_obx_value(self, oru_parsed):
        """Modify OBX[1]-5 (glucose value) and check diff."""
        msg_b = _modify_field(oru_parsed, 'OBX', 5, '6.2', rep_index=1)
        result = diff_messages(oru_parsed, msg_b)
        changed = _changed_fields(result)
        obx1_5 = [f for f in changed if f.address == 'OBX-5']
        assert len(obx1_5) == 1
        assert obx1_5[0].value_a == '5.4'
        assert obx1_5[0].value_b == '6.2'


# ---------------------------------------------------------------------------
# Tests: empty vs populated fields
# ---------------------------------------------------------------------------

class TestEmptyVsPopulated:

    def test_field_cleared(self, adt_parsed):
        """Clear PID-8 (sex) in B — should show as modified."""
        msg_b = _modify_field(adt_parsed, 'PID', 8, '')
        result = diff_messages(adt_parsed, msg_b)
        changed = _changed_fields(result)
        pid8 = [f for f in changed if f.address == 'PID-8']
        assert len(pid8) == 1
        assert pid8[0].status == 'modified'
        assert pid8[0].value_a == 'M'
        assert pid8[0].value_b == ''

    def test_field_populated(self, adt_parsed):
        """Set PID-8 to 'F' in B from 'M' — modified."""
        msg_b = _modify_field(adt_parsed, 'PID', 8, 'F')
        result = diff_messages(adt_parsed, msg_b)
        changed = _changed_fields(result)
        pid8 = [f for f in changed if f.address == 'PID-8']
        assert len(pid8) == 1
        assert pid8[0].value_a == 'M'
        assert pid8[0].value_b == 'F'


# ---------------------------------------------------------------------------
# Tests: cross-message comparison (ADT vs ORU)
# ---------------------------------------------------------------------------

class TestCrossMessage:

    def test_different_message_types(self, adt_parsed, oru_parsed):
        result = diff_messages(adt_parsed, oru_parsed)
        assert result.type_a == 'ADT^A01'
        assert result.type_b == 'ORU^R01'
        # Should have both a_only and b_only segments
        assert result.summary['a_only'] > 0
        assert result.summary['b_only'] > 0
        # MSH exists in both — some fields should be modified
        assert result.summary['modified'] > 0

    def test_segment_order_preserved(self, adt_parsed, oru_parsed):
        """A-side segments come first in diff order."""
        result = diff_messages(adt_parsed, oru_parsed)
        seg_names = [sd.name for sd in result.segment_diffs]
        # MSH, EVN, PID, NK1, PV1 from A should appear before ORC, OBR, OBX, NTE from B
        msh_idx = seg_names.index('MSH')
        assert msh_idx == 0  # MSH is first in both

    def test_shared_segments_compared(self, adt_parsed, oru_parsed):
        """PID appears in both — should be compared field by field."""
        result = diff_messages(adt_parsed, oru_parsed)
        pid_diffs = [sd for sd in result.segment_diffs if sd.name == 'PID']
        assert len(pid_diffs) == 1
        assert pid_diffs[0].status == 'modified'  # PID has differences


# ---------------------------------------------------------------------------
# Tests: MessageDiff structure
# ---------------------------------------------------------------------------

class TestDiffStructure:

    def test_summary_counts_consistent(self, adt_parsed):
        msg_b = _modify_field(adt_parsed, 'PID', 5, 'DOE^JOHN')
        result = diff_messages(adt_parsed, msg_b)
        s = result.summary
        assert s['total_fields'] == s['identical'] + s['modified'] + s['a_only'] + s['b_only']

    def test_field_diff_has_both_fields(self, adt_parsed):
        msg_b = _modify_field(adt_parsed, 'PID', 5, 'DOE^JOHN')
        result = diff_messages(adt_parsed, msg_b)
        for sd in result.segment_diffs:
            for fd in sd.field_diffs:
                if fd.status == 'identical' or fd.status == 'modified':
                    assert fd.field_a is not None
                    assert fd.field_b is not None
                elif fd.status == 'a_only':
                    assert fd.field_a is not None
                    assert fd.field_b is None
                elif fd.status == 'b_only':
                    assert fd.field_a is None
                    assert fd.field_b is not None
