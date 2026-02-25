"""Colored table output for parsed HL7 messages using ANSI escape codes."""

import re
import sys

from .definitions import (
    DATA_TYPES, get_seg_def, get_field_def, resolve_version, MSH18_TO_ENCODING,
)
from .diff import MessageDiff
from .profile import get_profile_segment, get_profile_field, get_profile_component

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
_INVERSE = '\033[7m'          # inverse video (for diff highlights)
_UNDERLINE = '\033[4m'        # underline


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


def _check_field_validation(p_fld, fld):
    """Check a field against profile validation rules.

    Returns (is_required_empty, is_value_mismatch).
    """
    required_empty = False
    value_mismatch = False
    if not p_fld:
        return required_empty, value_mismatch
    val = fld.value or "" if fld else ""
    if p_fld.get("required") and not val:
        required_empty = True
    if p_fld.get("valueMap") and val:
        test_val = fld.components[0].value if fld.components else val
        if test_val and test_val not in p_fld["valueMap"] and val not in p_fld["valueMap"]:
            value_mismatch = True
    return required_empty, value_mismatch


def _profile_validation_counts(parsed, profile):
    """Count profile validation issues: (required_empty, value_mismatch, missing_segs, unexpected_segs)."""
    if not profile or not profile.get("segments"):
        return 0, 0, [], []
    profile_seg_names = set(profile["segments"].keys())
    msg_seg_names = {s.name for s in parsed.segments}
    missing_segs = [s for s in profile_seg_names if s not in msg_seg_names]
    # Deduplicated unexpected segments (preserve message order)
    seen = set()
    unexpected_segs = []
    for seg in parsed.segments:
        if seg.name not in profile_seg_names and seg.name not in seen:
            seen.add(seg.name)
            unexpected_segs.append(seg.name)
    required_empty = 0
    value_mismatch = 0
    for seg_name, seg_def in profile["segments"].items():
        if seg_name not in msg_seg_names:
            continue
        if not seg_def.get("fields"):
            continue
        for seg in parsed.segments:
            if seg.name != seg_name:
                continue
            for field_num, p_fld in seg_def["fields"].items():
                fld = None
                for f in seg.fields:
                    if f.field_num == int(field_num):
                        fld = f
                        break
                req, mis = _check_field_validation(p_fld, fld)
                if req:
                    required_empty += 1
                if mis:
                    value_mismatch += 1
    return required_empty, value_mismatch, missing_segs, unexpected_segs


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

    # Profile validation summary
    if profile:
        req_empty, val_mis, miss_segs, unexp_segs = _profile_validation_counts(parsed, profile)
        vparts = []
        if req_empty:
            vparts.append(_c(_RED, f'{req_empty} required field{"s" if req_empty > 1 else ""} empty', use_color))
        if val_mis:
            vparts.append(_c(_ORANGE, f'{val_mis} value{"s" if val_mis > 1 else ""} not in map', use_color))
        if miss_segs:
            vparts.append(_c(_BLUE, f'Missing segments: {", ".join(miss_segs)}', use_color))
        if unexp_segs:
            vparts.append(_c(_YELLOW, f'Unexpected segments: {", ".join(unexp_segs)}', use_color))
        if vparts:
            lines.append(f'\u26a0 Profile validation: {" | ".join(vparts)}')

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
        unexpected_badge = ''
        if profile and profile.get('segments') and seg.name not in profile['segments']:
            unexpected_badge = f' {_c(_YELLOW, "[Unexpected]", use_color)}'
        profile_badge += unexpected_badge
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

            # Profile validation badges
            val_badge = ''
            if p_fld:
                req_empty, val_mis = _check_field_validation(p_fld, fld)
                if req_empty:
                    val_badge += ' ' + _c(_RED, '\u25cfrequired', use_color)
                if val_mis:
                    val_badge += ' ' + _c(_ORANGE, '\u25cfnot in map', use_color)

            # Format the row
            addr_col = _c(_BLUE, f'{fld.address:<10}', use_color)
            name_col = _c(_GREEN, f'{fname:<32}', use_color) if fname else f'{"":32}'
            dt_col = _c(_ORANGE, f'{dt}{dt_suffix:<5}', use_color) if dt else f'{"":5}'
            val_col = display_val + rep_badge + val_badge

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


def _char_diff_highlight(val_a, val_b, max_val, use_color):
    """Return (disp_a, disp_b) with ANSI inverse highlighting on changed chars.

    Uses smart truncation to ensure the differing region is visible."""
    if not use_color:
        # No color: just truncate normally
        da = (val_a[:max_val] + '\u2026') if len(val_a) > max_val + 1 else val_a
        db = (val_b[:max_val] + '\u2026') if len(val_b) > max_val + 1 else val_b
        return da, db

    # Find common prefix/suffix
    p = 0
    min_len = min(len(val_a), len(val_b))
    while p < min_len and val_a[p] == val_b[p]:
        p += 1
    sa, sb = len(val_a), len(val_b)
    while sa > p and sb > p and val_a[sa - 1] == val_b[sb - 1]:
        sa -= 1
        sb -= 1

    mid_a = val_a[p:sa]
    mid_b = val_b[p:sb]
    prefix = val_a[:p]
    suf_a = val_a[sa:]
    suf_b = val_b[sb:]

    hl = _INVERSE + _ORANGE

    def _render_side(prefix, mid, suffix, max_val):
        total = len(prefix) + len(mid) + len(suffix)
        if total <= max_val + 1:
            # Fits: highlight the middle
            if mid:
                return prefix + hl + mid + _RESET + suffix
            else:
                return prefix + suffix
        # Smart truncation: ensure diff region is visible
        mid_len = max(len(mid), 1)
        budget = max_val - mid_len
        if budget < 4:
            return hl + mid[:max_val] + _RESET + '\u2026'
        before = min(budget // 2, len(prefix))
        after = min(budget - before, len(suffix))
        r = ''
        if before < len(prefix):
            r += '\u2026'
        r += prefix[len(prefix) - before:] if before else ''
        if mid:
            mid_budget = max_val - before - after
            if len(mid) > mid_budget:
                r += hl + mid[:mid_budget] + _RESET + '\u2026'
            else:
                r += hl + mid + _RESET
        r += suffix[:after] if after else ''
        if after < len(suffix):
            r += '\u2026'
        return r

    return _render_side(prefix, mid_a, suf_a, max_val), _render_side(prefix, mid_b, suf_b, max_val)


def format_diff(diff_result, no_color=False, show_identical=False):
    """Format a MessageDiff as a colored terminal table showing differences."""
    use_color = not no_color and sys.stdout.isatty()

    lines = []

    # Header
    type_a = diff_result.type_a or '???'
    type_b = diff_result.type_b or '???'
    ver_a = f'v{diff_result.version_a}' if diff_result.version_a else 'v?'
    ver_b = f'v{diff_result.version_b}' if diff_result.version_b else 'v?'
    lines.append(
        f'{_c(_BOLD, "Compare:", use_color)} '
        f'{_c(_ROSE, type_a, use_color)} {ver_a}  vs  '
        f'{_c(_ROSE, type_b, use_color)} {ver_b}'
    )

    # Summary
    s = diff_result.summary
    diff_count = s['modified'] + s['a_only'] + s['b_only']
    seg_count = sum(1 for sd in diff_result.segment_diffs if sd.status != 'identical')
    parts = []
    if s['modified']:
        parts.append(_c(_ORANGE, f"{s['modified']} modified", use_color))
    if s['a_only']:
        parts.append(_c(_RED, f"{s['a_only']} A-only", use_color))
    if s['b_only']:
        parts.append(_c(_GREEN, f"{s['b_only']} B-only", use_color))
    summary_text = ', '.join(parts) if parts else 'no differences'
    lines.append(f'{diff_count} difference{"s" if diff_count != 1 else ""} across {seg_count} segment{"s" if seg_count != 1 else ""}: {summary_text}')

    # Rule
    rule_char = '\u2550'
    lines.append(rule_char * 90)

    # Column headers
    hdr = (
        f'{_c(_DIM, f"{"Address":<12} {"Field Name":<28} {"Message A":<20} {"Message B":<20} Status", use_color)}'
    )
    lines.append(hdr)
    lines.append('\u2500' * 90)

    version_a = resolve_version(diff_result.version_a)
    version_b = resolve_version(diff_result.version_b)

    for seg_diff in diff_result.segment_diffs:
        # Skip fully identical segments unless show_identical
        if not show_identical and seg_diff.status == 'identical':
            continue

        # Check if there are any non-identical fields to show
        has_diffs = any(fd.status != 'identical' for fd in seg_diff.field_diffs)
        if not show_identical and not has_diffs:
            continue

        # Segment header
        version = version_a if seg_diff.status != 'b_only' else version_b
        seg_def = get_seg_def(seg_diff.name, version)
        seg_desc = seg_def['name'] if seg_def else ''
        rep_label = f'[{seg_diff.rep_index}]' if seg_diff.rep_index > 1 else ''
        seg_label = f'{seg_diff.name}{rep_label}'

        status_badge = ''
        if seg_diff.status == 'a_only':
            status_badge = _c(_RED, ' [A only]', use_color)
        elif seg_diff.status == 'b_only':
            status_badge = _c(_GREEN, ' [B only]', use_color)

        if seg_desc:
            seg_header = f'\u2500\u2500 {_c(_ROSE + _BOLD, seg_label, use_color)}  {_c(_ROSE, seg_desc, use_color)}{status_badge} '
        else:
            seg_header = f'\u2500\u2500 {_c(_ROSE + _BOLD, seg_label, use_color)}{status_badge} '
        visible_len = len(f'── {seg_label}  {seg_desc} ') if seg_desc else len(f'── {seg_label} ')
        seg_header += '\u2500' * max(0, 90 - visible_len)
        lines.append(seg_header)

        for fd in seg_diff.field_diffs:
            if not show_identical and fd.status == 'identical':
                continue

            fld_def = get_field_def(seg_diff.name, fd.field_num, version)
            fname = fld_def['name'] if fld_def else ''

            val_a = fd.value_a if fd.value_a is not None else ''
            val_b = fd.value_b if fd.value_b is not None else ''

            # Truncate long values for table display
            max_val = 18

            # Status label with color
            if fd.status == 'modified':
                status_str = _c(_ORANGE, 'modified', use_color)
                border = _c(_ORANGE, '\u2502 ', use_color)
                disp_a, disp_b = _char_diff_highlight(val_a, val_b, max_val, use_color)
            elif fd.status == 'a_only':
                status_str = _c(_RED, 'A only', use_color)
                border = _c(_RED, '\u2502 ', use_color)
                disp_a = (val_a[:max_val] + '\u2026') if len(val_a) > max_val + 1 else val_a
                disp_b = _c(_GRAY, '\u2014', use_color)
            elif fd.status == 'b_only':
                status_str = _c(_GREEN, 'B only', use_color)
                border = _c(_GREEN, '\u2502 ', use_color)
                disp_a = _c(_GRAY, '\u2014', use_color)
                disp_b = (val_b[:max_val] + '\u2026') if len(val_b) > max_val + 1 else val_b
            else:
                status_str = _c(_GRAY, 'identical', use_color)
                border = '  '
                disp_a = (val_a[:max_val] + '\u2026') if len(val_a) > max_val + 1 else val_a
                disp_b = (val_b[:max_val] + '\u2026') if len(val_b) > max_val + 1 else val_b

            addr_col = _c(_BLUE, f'{fd.address:<12}', use_color)
            name_col = _c(_GREEN, f'{fname:<28}', use_color) if fname else f'{"":28}'

            # Pad based on visible length (ANSI codes don't count)
            vis_a = len(re.sub(r'\033\[[^m]*m', '', disp_a))
            vis_b = len(re.sub(r'\033\[[^m]*m', '', disp_b))
            pad_a = disp_a + ' ' * max(0, 20 - vis_a)
            pad_b = disp_b + ' ' * max(0, 20 - vis_b)

            lines.append(f'{border}{addr_col}{name_col}{pad_a} {pad_b} {status_str}')

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
