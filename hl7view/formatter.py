"""Colored table output for parsed HL7 messages using ANSI escape codes."""

import re
import sys

from .definitions import (
    DATA_TYPES, get_seg_def, get_field_def, resolve_version, MSH18_TO_ENCODING,
)
from .profile import get_profile_segment, get_profile_field

# ========== ANSI COLOR CODES ==========
# Catppuccin-inspired palette matching the web viewer

_RESET = '\033[0m'
_BOLD = '\033[1m'
_DIM = '\033[2m'
_ROSE = '\033[38;5;211m'      # segment names
_GREEN = '\033[38;5;150m'     # field names
_ORANGE = '\033[38;5;216m'    # data types
_BLUE = '\033[38;5;111m'      # addresses
_SAPPHIRE = '\033[38;5;117m'  # component addresses
_YELLOW = '\033[38;5;222m'    # warnings, rep badges
_RED = '\033[38;5;210m'       # errors
_GRAY = '\033[38;5;245m'      # dim/empty
_TEAL = '\033[38;5;116m'      # encoding info
_WHITE = '\033[38;5;252m'     # normal text


def _c(code, text, use_color):
    """Wrap text in ANSI color if use_color is True."""
    if not use_color:
        return text
    return f'{code}{text}{_RESET}'


def _resolve_obx5_type(seg_fields):
    """Get the OBX-5 data type from OBX-2 value."""
    for f in seg_fields:
        if f.field_num == 2 and f.value:
            return f.value
    return None


def format_encoding_header(enc_info, declared_charset, use_color):
    """Format one-line encoding info header."""
    parts = []

    if enc_info:
        detected = enc_info.get('encoding', 'unknown')
        bom = ' BOM' if enc_info.get('has_bom') else ''
        parts.append(f"Detected: {_c(_TEAL, detected + bom, use_color)}")

    if declared_charset:
        mapped = MSH18_TO_ENCODING.get(declared_charset, declared_charset)
        parts.append(f"MSH-18: {_c(_TEAL, declared_charset, use_color)} ({mapped})")

        # Check for mismatch
        if enc_info:
            detected = enc_info.get('encoding', '')
            if detected and mapped and detected != mapped and detected != 'ASCII':
                parts.append(_c(_YELLOW, f'[mismatch: detected {detected} vs declared {mapped}]', use_color))

    if parts:
        return ' | '.join(parts)
    return None


def format_message(parsed, version=None, verbose=False, show_empty=False, no_color=False, profile=None):
    """Format a parsed HL7 message as a colored table string."""
    use_color = not no_color and sys.stdout.isatty()

    if version is None:
        version = resolve_version(parsed.version)

    lines = []

    # Header line
    msg_type = parsed.message_type or '???'
    ver_display = f'v{parsed.version}' if parsed.version else 'v?'
    seg_count = len(parsed.segments)
    header = f'{_c(_BOLD, msg_type, use_color)} {ver_display} | {seg_count} segments'
    if profile:
        header += f' | {_c(_TEAL, "Profile: " + profile["name"], use_color)}'
    lines.append(header)

    # Full-width rule
    rule_char = '\u2550'  # ═
    lines.append(rule_char * 72)

    for seg in parsed.segments:
        seg_def = get_seg_def(seg.name, version)
        seg_desc = seg_def['name'] if seg_def else ''
        p_seg = get_profile_segment(profile, seg.name)
        if not seg_desc and p_seg:
            seg_desc = p_seg.get('description', '')
        rep_label = f'[{seg.rep_index}]' if seg.rep_index > 1 else ''

        # Segment header line
        seg_label = f'{seg.name}{rep_label}'
        profile_badge = f' {_c(_TEAL, "[Profile]", use_color)}' if p_seg else ''
        if seg_desc:
            seg_header = f'\u2500\u2500 {_c(_ROSE + _BOLD, seg_label, use_color)}  {_c(_ROSE, seg_desc, use_color)}{profile_badge} '
        else:
            seg_header = f'\u2500\u2500 {_c(_ROSE + _BOLD, seg_label, use_color)}{profile_badge} '
        # Pad with ─
        visible_len = len(f'── {seg_label}  {seg_desc} ') if seg_desc else len(f'── {seg_label} ')
        seg_header += '\u2500' * max(0, 72 - visible_len)
        lines.append(seg_header)

        # Resolve OBX-5 type if this is an OBX segment
        obx5_type = None
        if seg.name == 'OBX':
            obx5_type = _resolve_obx5_type(seg.fields)

        for fld in seg.fields:
            fld_def = get_field_def(seg.name, fld.field_num, version)

            # Determine effective data type
            dt = ''
            dt_suffix = ''
            if fld_def:
                dt = fld_def['dt']
                if dt == '*' and seg.name == 'OBX' and fld.field_num == 5:
                    if obx5_type:
                        dt = obx5_type
                        dt_suffix = '\u21902'  # ←2
                    else:
                        dt = '*'

            # Skip empty fields unless requested
            if not fld.value and not fld.raw_value and not show_empty:
                continue

            # Format field name — profile customName overrides standard
            p_fld = get_profile_field(profile, seg.name, fld.field_num)
            fname = fld_def['name'] if fld_def else ''
            if p_fld and p_fld.get('customName'):
                fname = p_fld['customName']

            # Value display — apply valueMap if available
            display_val = fld.value if fld.value else ''
            if p_fld and p_fld.get('valueMap') and fld.value:
                mapped = p_fld['valueMap'].get(fld.value)
                if mapped:
                    display_val = f'{fld.value} {_c(_TEAL, f"({mapped})", use_color)}'
            if not display_val and not fld.raw_value:
                display_val = _c(_GRAY, '(empty)', use_color)

            # Repetition badge
            rep_badge = ''
            if fld.repetitions and len(fld.repetitions) > 1:
                rep_badge = _c(_YELLOW, f' [{len(fld.repetitions)}x]', use_color)

            # Format the row
            addr_col = _c(_BLUE, f'{fld.address:<10}', use_color)
            name_col = _c(_GREEN, f'{fname:<32}', use_color) if fname else f'{"":32}'
            dt_col = _c(_ORANGE, f'{dt}{dt_suffix:<5}', use_color) if dt else f'{"":5}'
            val_col = display_val + rep_badge

            lines.append(f'{addr_col} {name_col} {dt_col} {val_col}')

            # Verbose: show component sub-rows
            if verbose and fld.components:
                dt_info = DATA_TYPES.get(dt, {})
                comp_defs = dt_info.get('components', [])
                for comp in fld.components:
                    if not comp.value and not show_empty:
                        continue
                    comp_name = ''
                    comp_dt = ''
                    if comp.index <= len(comp_defs):
                        comp_name = comp_defs[comp.index - 1].get('name', '')
                        comp_dt = comp_defs[comp.index - 1].get('dt', '')
                    comp_addr = f'{fld.address}.{comp.index}'
                    comp_val = comp.value if comp.value else _c(_GRAY, '(empty)', use_color)

                    c_addr = _c(_SAPPHIRE, f'  {comp_addr:<10}', use_color)
                    c_name = _c(_GREEN, f'{comp_name:<30}', use_color) if comp_name else f'{"":30}'
                    c_dt = _c(_ORANGE, f'{comp_dt:<5}', use_color) if comp_dt else f'{"":5}'
                    lines.append(f'{c_addr}   {c_name} {c_dt} {comp_val}')

                    # Subcomponent rows
                    if verbose and comp.subcomponents and len(comp.subcomponents) > 1:
                        for si, subval in enumerate(comp.subcomponents, 1):
                            if not subval and not show_empty:
                                continue
                            sub_addr = f'{fld.address}.{comp.index}.{si}'
                            s_addr = _c(_GRAY, f'    {sub_addr:<10}', use_color)
                            s_val = subval if subval else _c(_GRAY, '(empty)', use_color)
                            lines.append(f'{s_addr}     {"":30} {"":5} {s_val}')

            # Verbose: show additional repetitions
            if verbose and fld.repetitions and len(fld.repetitions) > 1:
                for rep in fld.repetitions[1:]:
                    rep_label_str = f'{fld.address}~{rep.index}'
                    r_addr = _c(_YELLOW, f'  {rep_label_str:<10}', use_color)
                    r_val = rep.value if rep.value else _c(_GRAY, '(empty)', use_color)
                    lines.append(f'{r_addr}   {"":30} {"":5} {r_val}')

                    if rep.components:
                        dt_info = DATA_TYPES.get(dt, {})
                        comp_defs = dt_info.get('components', [])
                        for comp in rep.components:
                            if not comp.value and not show_empty:
                                continue
                            comp_name = ''
                            comp_dt = ''
                            if comp.index <= len(comp_defs):
                                comp_name = comp_defs[comp.index - 1].get('name', '')
                                comp_dt = comp_defs[comp.index - 1].get('dt', '')
                            comp_addr = f'{fld.address}~{rep.index}.{comp.index}'
                            comp_val = comp.value if comp.value else _c(_GRAY, '(empty)', use_color)
                            c_addr = _c(_SAPPHIRE, f'    {comp_addr:<10}', use_color)
                            c_name = _c(_GREEN, f'{comp_name:<28}', use_color) if comp_name else f'{"":28}'
                            c_dt = _c(_ORANGE, f'{comp_dt:<5}', use_color) if comp_dt else f'{"":5}'
                            lines.append(f'{c_addr}     {c_name} {c_dt} {comp_val}')

    lines.append('')
    return '\n'.join(lines)


def format_field_value(parsed, field_spec, version=None):
    """Extract and return a single field value by address (e.g. 'PID-5').

    Returns the value string, or None if not found.
    """
    if version is None:
        version = resolve_version(parsed.version)

    # Parse field_spec: SEG-N or SEG[rep]-N
    match = re.match(r'^([A-Z][A-Z0-9]{1,2})(?:\[(\d+)\])?-(\d+)$', field_spec)
    if not match:
        return None

    seg_name = match.group(1)
    rep_idx = int(match.group(2)) if match.group(2) else None
    field_num = int(match.group(3))

    for seg in parsed.segments:
        if seg.name != seg_name:
            continue
        if rep_idx is not None and seg.rep_index != rep_idx:
            continue
        for fld in seg.fields:
            if fld.field_num == field_num:
                return fld.raw_value
    return None


def format_raw(parsed):
    """Return raw segment lines (post-normalization), one per line."""
    return '\n'.join(seg.raw_line for seg in parsed.segments) + '\n'
