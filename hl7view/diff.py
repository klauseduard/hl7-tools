"""HL7 message comparison: field-level diff between two parsed messages."""

from dataclasses import dataclass, field


@dataclass
class FieldDiff:
    """Difference record for a single field."""
    address: str
    field_num: int
    status: str          # 'identical', 'modified', 'a_only', 'b_only'
    value_a: str         # raw_value from message A (or None)
    value_b: str         # raw_value from message B (or None)
    field_a: object = None  # Field dataclass from A (or None)
    field_b: object = None  # Field dataclass from B (or None)


@dataclass
class SegmentDiff:
    """Difference record for a segment (by name + rep_index)."""
    name: str
    rep_index: int
    status: str          # 'identical', 'modified', 'a_only', 'b_only'
    field_diffs: list    # list of FieldDiff


@dataclass
class MessageDiff:
    """Top-level diff result between two messages."""
    segment_diffs: list  # list of SegmentDiff
    summary: dict        # {'total_fields', 'identical', 'modified', 'a_only', 'b_only'}
    version_a: str
    version_b: str
    type_a: str
    type_b: str


def _seg_key(seg):
    """Return (name, rep_index) tuple for segment indexing."""
    return (seg.name, seg.rep_index)


def _build_field_map(seg):
    """Build {field_num: field} dict for a segment."""
    return {f.field_num: f for f in seg.fields}


def diff_messages(parsed_a, parsed_b):
    """Compare two ParsedMessage objects field-by-field.

    Returns a MessageDiff with per-segment, per-field comparison results.
    """
    # Index segments by (name, rep_index), preserving order
    seg_map_a = {}
    seg_order_a = []
    for seg in parsed_a.segments:
        key = _seg_key(seg)
        seg_map_a[key] = seg
        seg_order_a.append(key)

    seg_map_b = {}
    seg_order_b = []
    for seg in parsed_b.segments:
        key = _seg_key(seg)
        seg_map_b[key] = seg
        seg_order_b.append(key)

    # Union of segment keys, preserving order (A first, then B-only)
    all_keys = list(seg_order_a)
    seen = set(all_keys)
    for key in seg_order_b:
        if key not in seen:
            all_keys.append(key)
            seen.add(key)

    segment_diffs = []
    counts = {'total_fields': 0, 'identical': 0, 'modified': 0, 'a_only': 0, 'b_only': 0}

    for key in all_keys:
        seg_name, rep_idx = key
        seg_a = seg_map_a.get(key)
        seg_b = seg_map_b.get(key)

        if seg_a and not seg_b:
            # Segment only in A
            field_diffs = []
            for fld in seg_a.fields:
                addr = _make_address(seg_name, rep_idx, fld.field_num)
                fd = FieldDiff(
                    address=addr, field_num=fld.field_num,
                    status='a_only',
                    value_a=fld.raw_value, value_b=None,
                    field_a=fld, field_b=None,
                )
                field_diffs.append(fd)
                counts['a_only'] += 1
                counts['total_fields'] += 1
            segment_diffs.append(SegmentDiff(
                name=seg_name, rep_index=rep_idx,
                status='a_only', field_diffs=field_diffs,
            ))

        elif seg_b and not seg_a:
            # Segment only in B
            field_diffs = []
            for fld in seg_b.fields:
                addr = _make_address(seg_name, rep_idx, fld.field_num)
                fd = FieldDiff(
                    address=addr, field_num=fld.field_num,
                    status='b_only',
                    value_a=None, value_b=fld.raw_value,
                    field_a=None, field_b=fld,
                )
                field_diffs.append(fd)
                counts['b_only'] += 1
                counts['total_fields'] += 1
            segment_diffs.append(SegmentDiff(
                name=seg_name, rep_index=rep_idx,
                status='b_only', field_diffs=field_diffs,
            ))

        else:
            # Segment in both — compare fields
            fields_a = _build_field_map(seg_a)
            fields_b = _build_field_map(seg_b)
            all_fnums = sorted(set(fields_a.keys()) | set(fields_b.keys()))

            field_diffs = []
            seg_status = 'identical'

            for fnum in all_fnums:
                fa = fields_a.get(fnum)
                fb = fields_b.get(fnum)
                addr = _make_address(seg_name, rep_idx, fnum)

                if fa and not fb:
                    fd = FieldDiff(
                        address=addr, field_num=fnum,
                        status='a_only',
                        value_a=fa.raw_value, value_b=None,
                        field_a=fa, field_b=None,
                    )
                    seg_status = 'modified'
                    counts['a_only'] += 1
                elif fb and not fa:
                    fd = FieldDiff(
                        address=addr, field_num=fnum,
                        status='b_only',
                        value_a=None, value_b=fb.raw_value,
                        field_a=None, field_b=fb,
                    )
                    seg_status = 'modified'
                    counts['b_only'] += 1
                elif fa.raw_value == fb.raw_value:
                    fd = FieldDiff(
                        address=addr, field_num=fnum,
                        status='identical',
                        value_a=fa.raw_value, value_b=fb.raw_value,
                        field_a=fa, field_b=fb,
                    )
                    counts['identical'] += 1
                else:
                    fd = FieldDiff(
                        address=addr, field_num=fnum,
                        status='modified',
                        value_a=fa.raw_value, value_b=fb.raw_value,
                        field_a=fa, field_b=fb,
                    )
                    seg_status = 'modified'
                    counts['modified'] += 1

                counts['total_fields'] += 1
                field_diffs.append(fd)

            segment_diffs.append(SegmentDiff(
                name=seg_name, rep_index=rep_idx,
                status=seg_status, field_diffs=field_diffs,
            ))

    return MessageDiff(
        segment_diffs=segment_diffs,
        summary=counts,
        version_a=parsed_a.version,
        version_b=parsed_b.version,
        type_a=parsed_a.message_type,
        type_b=parsed_b.message_type,
    )


def _make_address(seg_name, rep_index, field_num):
    """Build field address string like 'PID-3' or 'OBX[2]-5'."""
    if rep_index > 1:
        return f'{seg_name}[{rep_index}]-{field_num}'
    return f'{seg_name}-{field_num}'
