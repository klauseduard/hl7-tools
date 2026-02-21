"""HL7 message parsing: normalization, segment splitting, field/component extraction."""

import re
from dataclasses import dataclass, field


@dataclass
class Component:
    index: int          # 1-based
    value: str
    subcomponents: list


@dataclass
class Repetition:
    index: int          # 1-based
    value: str
    components: list    # list of Component


@dataclass
class Field:
    field_num: int
    address: str        # "PID-3", "MSH-9", "PID[2]-3"
    value: str          # first repetition value
    raw_value: str      # full value including ~ repetitions
    components: list    # list of Component
    repetitions: list   # list of Repetition


@dataclass
class Segment:
    name: str
    rep_index: int      # 1 for first occurrence, 2 for second, etc.
    fields: list        # list of Field
    raw_line: str


@dataclass
class ParsedMessage:
    segments: list                        # list of Segment
    version: str = None                   # from MSH-12
    message_type: str = None              # from MSH-9
    declared_charset: str = None          # from MSH-18


def normalize_message(raw):
    """Normalize raw HL7 text into a list of segment strings.

    Handles MLLP framing, log artifacts, mixed line endings, and
    single-line segment boundary detection.
    """
    content = raw

    # Strip MLLP framing: VT (0x0b) at start, FS (0x1c) + optional CR at end
    content = re.sub(r'^\x0b', '', content)
    content = re.sub(r'\x1c[\r\n]*$', '', content)

    # Strip common log/dump artifacts
    content = re.sub(r'<VT>|<SB>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<FS>|<EB>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<CR>', '\r', content, flags=re.IGNORECASE)

    # Handle 0x0b and 0x1c mid-message
    content = content.replace('\x0b', '').replace('\x1c', '')

    content = content.strip()
    if not content:
        return []

    # Collapse \r\n -> \r
    content = content.replace('\r\n', '\r')

    # If message has \r, use that as segment delimiter
    if '\r' in content:
        fragments = content.split('\r')
        result_parts = []
        prev = None
        for i, current in enumerate(fragments):
            if prev is not None:
                if len(current) == 0:
                    result_parts.append(prev)
                    prev = ''
                    continue
                if current[0] == '|' or current.startswith('\n|') or \
                   (current[0] == '\n' and len(current) < 4):
                    result_parts.append(prev)
                    current = current.lstrip('\n') if current.startswith('\n') else current
                elif current.startswith('\n') and len(current) > 4 and current[4] != '|':
                    result_parts.append(prev)
                    current = '~' + current[1:]
                else:
                    result_parts.append(prev)
                    result_parts.append('\r')  # marker, will be joined then re-split
                    # Actually, let's follow the JS logic more closely:
                    # result += prev + '\r'; prev = current; continue
                    prev = current
                    continue
            prev = current
        if prev is not None:
            result_parts.append(prev)
        # Rejoin and split on \r to get final segments
        rejoined = '\r'.join(result_parts)
        return [s for s in rejoined.split('\r') if s.strip()]

    # No \r — try \n
    if '\n' in content:
        return [s for s in content.split('\n') if s.strip()]

    # Single line: look for segment boundaries
    seg_pattern = r'(?<=.)(?=(?:MSH|MSA|EVN|PID|PV1|PV2|NK1|ORC|OBR|OBX|DG1|IN1|AL1|GT1|NTE|ERR|QRD|QRF|MRG|SCH|TXA|DSP|ZDS|ZPD|Z[A-Z][A-Z0-9])\|)'
    if re.search(seg_pattern, content):
        return [s for s in re.split(seg_pattern, content) if s.strip()]

    # Truly a single segment
    return [content]


def split_components(value):
    """Split a field value into components on ^, and subcomponents on &."""
    if not value or '^' not in value:
        return []
    parts = value.split('^')
    return [Component(
        index=idx + 1,
        value=comp,
        subcomponents=comp.split('&') if '&' in comp else []
    ) for idx, comp in enumerate(parts)]


def _parse_field(address, field_num, raw_value):
    """Parse a single field value into components and repetitions."""
    f = Field(
        field_num=field_num,
        address=address,
        value=raw_value,
        raw_value=raw_value,
        components=[],
        repetitions=[]
    )

    if not raw_value:
        return f

    # Handle field repetitions (~)
    if '~' in raw_value:
        reps = raw_value.split('~')
        f.value = reps[0]
        f.repetitions = [Repetition(
            index=idx + 1,
            value=rep,
            components=split_components(rep)
        ) for idx, rep in enumerate(reps)]
        f.components = f.repetitions[0].components
    else:
        f.components = split_components(raw_value)

    return f


def reparse_field(field, new_raw):
    """Update a Field's value/components/repetitions from a new raw_value."""
    field.raw_value = new_raw
    if not new_raw:
        field.value = ""
        field.components = []
        field.repetitions = []
        return

    if "~" in new_raw:
        reps = new_raw.split("~")
        field.value = reps[0]
        field.repetitions = [
            Repetition(index=idx + 1, value=rep, components=split_components(rep))
            for idx, rep in enumerate(reps)
        ]
        field.components = field.repetitions[0].components
    else:
        field.value = new_raw
        field.components = split_components(new_raw)
        field.repetitions = []


def rebuild_raw_line(seg_name, fields):
    """Rebuild a segment's raw_line from its field values."""
    if seg_name == "MSH":
        # MSH-1 = | (implicit), MSH-2 = encoding chars, MSH-3+ = rest
        parts = []
        for fld in fields:
            if fld.field_num == 1:
                continue  # separator, not serialized between pipes
            if fld.field_num == 2:
                parts.append(fld.raw_value)
            else:
                parts.append(fld.raw_value)
        return "MSH|" + "|".join(parts)
    else:
        vals = [fld.raw_value for fld in fields]
        return seg_name + "|" + "|".join(vals)


def parse_hl7(raw):
    """Parse raw HL7 text into a ParsedMessage, or None if empty."""
    segments_raw = normalize_message(raw)
    if not segments_raw:
        return None

    result = ParsedMessage(segments=[])
    segment_counts = {}

    for seg_line in segments_raw:
        fields = seg_line.split('|')
        seg_name = fields[0]
        if not seg_name or len(seg_name) < 2:
            continue

        segment_counts[seg_name] = segment_counts.get(seg_name, 0) + 1
        seg_rep_idx = segment_counts[seg_name]

        seg = Segment(
            name=seg_name,
            rep_index=seg_rep_idx,
            fields=[],
            raw_line=seg_line
        )

        if seg_name == 'MSH':
            # MSH-1: field separator (always |)
            seg.fields.append(Field(
                field_num=1, address='MSH-1',
                value='|', raw_value='|',
                components=[], repetitions=[]
            ))
            # MSH-2: encoding characters
            if len(fields) > 1:
                seg.fields.append(Field(
                    field_num=2, address='MSH-2',
                    value=fields[1], raw_value=fields[1],
                    components=[], repetitions=[]
                ))
            # MSH-3 onwards: fields[2] = MSH-3, etc.
            for j in range(2, len(fields)):
                field_num = j + 1
                addr = f'MSH-{field_num}'
                seg.fields.append(_parse_field(addr, field_num, fields[j]))
        else:
            # Normal segments: fields[1] = SEG-1, etc.
            addr_prefix = seg_name + (f'[{seg_rep_idx}]' if seg_rep_idx > 1 else '')
            for j in range(1, len(fields)):
                addr = f'{addr_prefix}-{j}'
                seg.fields.append(_parse_field(addr, j, fields[j]))

        # Extract metadata from MSH
        if seg_name == 'MSH':
            version_field = next((f for f in seg.fields if f.field_num == 12), None)
            if version_field:
                ver = version_field.value
                if ver and '^' in ver:
                    ver = ver.split('^')[0]
                result.version = ver

            msg_type_field = next((f for f in seg.fields if f.field_num == 9), None)
            if msg_type_field:
                result.message_type = msg_type_field.value

            charset_field = next((f for f in seg.fields if f.field_num == 18), None)
            if charset_field:
                charset = charset_field.value or ''
                if '~' in charset:
                    charset = charset.split('~')[0]
                result.declared_charset = charset

        result.segments.append(seg)

    return result
