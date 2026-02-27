#!/usr/bin/env python3
"""Generate JS definitions in hl7-viewer.html from Python source of truth.

Usage:
    venv/bin/python tools/gen_js_defs.py

Reads HL7 definitions from hl7view.definitions and writes them as JS into
hl7-viewer.html between @@GENERATED_DEFS_START@@ / @@GENERATED_DEFS_END@@
marker comments.
"""

import json
import os
import sys

# Add project root to path so we can import hl7view
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from hl7view.definitions import DATA_TYPES, HL7_V23, HL7_V25, HL7_V28, MSH18_TO_ENCODING

START_MARKER = "// @@GENERATED_DEFS_START@@"
END_MARKER = "// @@GENERATED_DEFS_END@@"

HTML_FILE = os.path.join(PROJECT_ROOT, "hl7-viewer.html")


def _js_str(s):
    """Quote a string for JS, using double quotes only when needed."""
    # Use json.dumps for correct escaping (handles quotes, backslashes, etc.)
    return json.dumps(s)


def _format_data_types(data_types):
    """Format DATA_TYPES as compact JS matching hand-written style."""
    lines = ["const DATA_TYPES = {"]
    for dt_name, dt_def in data_types.items():
        if dt_def.get("primitive"):
            lines.append(f'{dt_name}:{{name:{_js_str(dt_def["name"])},primitive:true}},')
        else:
            comps = ",".join(
                f'{{name:{_js_str(c["name"])},dt:{_js_str(c["dt"])}}}'
                for c in dt_def["components"]
            )
            lines.append(f'{dt_name}:{{name:{_js_str(dt_def["name"])},components:[')
            lines.append(f"{comps}]}},")
    lines.append("};")
    return "\n".join(lines)


def _format_field(fnum, fdef):
    """Format a single field definition as JS."""
    rep = "true" if fdef["rep"] else "false"
    return (
        f'{fnum}:{{name:{_js_str(fdef["name"])},'
        f'dt:{_js_str(fdef["dt"])},'
        f'opt:{_js_str(fdef["opt"])},'
        f'rep:{rep},'
        f'len:{fdef["len"]}}}'
    )


def _format_segment_defs(var_name, seg_defs):
    """Format a full version's segment definitions as a JS const."""
    lines = [f"const {var_name} = {{"]
    for seg_name, seg_def in seg_defs.items():
        lines.append(f'{seg_name}:{{name:{_js_str(seg_def["name"])},fields:{{')
        field_lines = []
        for fnum in sorted(seg_def["fields"].keys()):
            field_lines.append(_format_field(fnum, seg_def["fields"][fnum]))
        lines.append(",\n".join(field_lines))
        lines.append("}},")
    lines.append("};")
    return "\n".join(lines)


def _format_msh18(msh18):
    """Format MSH18_TO_ENCODING as compact JS."""
    entries = ",".join(f"{_js_str(k)}:{_js_str(v)}" for k, v in msh18.items())
    return f"const MSH18_TO_ENCODING = {{{entries}}};"


def generate_js_block():
    """Generate the complete JS definitions block."""
    parts = [
        "// ========== DATA TYPE DEFINITIONS ==========",
        _format_data_types(DATA_TYPES),
        "",
        "// ========== HL7 v2.3 SEGMENT DEFINITIONS ==========",
        _format_segment_defs("HL7_V23", HL7_V23),
        "",
        "// ========== HL7 v2.5 SEGMENT DEFINITIONS ==========",
        _format_segment_defs("HL7_V25", HL7_V25),
        "",
        "// ========== HL7 v2.8 SEGMENT DEFINITIONS ==========",
        _format_segment_defs("HL7_V28", HL7_V28),
        "",
        'const HL7_DEFS = {"2.3": HL7_V23, "2.5": HL7_V25, "2.8": HL7_V28};',
        "",
        "// ========== MSH-18 CHARACTER SET MAPPING ==========",
        _format_msh18(MSH18_TO_ENCODING),
    ]
    return "\n".join(parts)


def update_html(html_path=None):
    """Replace definitions block in hl7-viewer.html between markers."""
    path = html_path or HTML_FILE
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    start_idx = content.find(START_MARKER)
    end_idx = content.find(END_MARKER)

    if start_idx == -1 or end_idx == -1:
        print(f"ERROR: Marker comments not found in {path}", file=sys.stderr)
        print(f"  Expected: {START_MARKER}", file=sys.stderr)
        print(f"  Expected: {END_MARKER}", file=sys.stderr)
        sys.exit(1)

    # Find the end of the END_MARKER line
    end_line_end = content.index("\n", end_idx)

    js_block = generate_js_block()

    new_content = (
        content[: start_idx + len(START_MARKER)]
        + "\n"
        + js_block
        + "\n"
        + content[end_idx:]
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    # Print summary
    v23_segs = len(HL7_V23)
    v25_segs = len(HL7_V25)
    v28_segs = len(HL7_V28)
    dt_count = len(DATA_TYPES)
    print(f"Generated JS definitions in {os.path.basename(path)}:")
    print(f"  DATA_TYPES: {dt_count} types")
    print(f"  HL7_V23: {v23_segs} segments")
    print(f"  HL7_V25: {v25_segs} segments")
    print(f"  HL7_V28: {v28_segs} segments")
    print(f"  MSH18_TO_ENCODING: {len(MSH18_TO_ENCODING)} mappings")


if __name__ == "__main__":
    update_html()
