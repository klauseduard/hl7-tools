#!/usr/bin/env python3
"""HL7 v2.x MCP Server — exposes HL7 parsing tools to AI agents."""

import sys
import os
import json
import re
import logging
from pathlib import Path
from enum import Enum

import typer
from fastmcp import FastMCP

# Ensure hl7view package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hl7view.parser import parse_hl7, reparse_field, rebuild_raw_line
from hl7view.definitions import (
    get_seg_def, get_field_def, DATA_TYPES,
    resolve_version, HL7_V23, HL7_V25, HL7_DEFS,
)
from hl7view.anonymize import anonymize_message
from hl7view.mllp import mllp_send, reconstruct_message
from hl7view.profile import load_profile, get_profile_field, get_profile_segment
from hl7view.formatter import format_field_value

# ---------------------------------------------------------------------------
# Logging — stderr only (MCP best practice)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("hl7-mcp")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = PROJECT_DIR / "profiles"
SAMPLES_DIR = PROJECT_DIR / "samples"

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "hl7-tools",
    instructions=(
        "HL7 v2.x message parsing, validation, transformation, and transport tools. "
        "Use hl7_parse to parse raw HL7 messages. Use hl7_get_field for targeted field "
        "extraction. Use hl7_validate to check for structural issues. Use hl7_explain "
        "for HL7 definition lookups without a message."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_profile_by_name(name: str) -> dict | None:
    """Load a profile JSON by stem name from the profiles directory."""
    if not name:
        return None
    path = PROFILES_DIR / name
    if not path.suffix:
        path = path.with_suffix(".json")
    path = path.resolve()
    if not path.is_relative_to(PROFILES_DIR.resolve()):
        return None
    if not path.exists():
        return None
    return load_profile(str(path))


def _component_to_dict(comp):
    """Serialize a Component dataclass to dict."""
    d = {"index": comp.index, "value": comp.value}
    if comp.subcomponents:
        d["subcomponents"] = comp.subcomponents
    return d


def _field_to_dict(field, seg_name, version, profile=None, show_empty=False):
    """Serialize a Field to dict with definition metadata."""
    if not show_empty and not field.value and not field.raw_value:
        return None

    fld_def = get_field_def(seg_name, field.field_num, version)
    p_fld = get_profile_field(profile, seg_name, field.field_num) if profile else None

    d = {
        "address": field.address,
        "field_num": field.field_num,
        "value": field.value,
    }

    if field.raw_value != field.value:
        d["raw_value"] = field.raw_value

    # Definition metadata
    if fld_def:
        d["name"] = fld_def["name"]
        d["data_type"] = fld_def["dt"]
        if fld_def["opt"] == "R":
            d["required"] = True
        if fld_def["rep"]:
            d["repeating"] = True
        if fld_def["len"]:
            d["max_length"] = fld_def["len"]

    # Profile overlay
    if p_fld:
        if p_fld.get("customName"):
            d["profile_name"] = p_fld["customName"]
        if p_fld.get("description"):
            d["profile_description"] = p_fld["description"]
        if p_fld.get("notes"):
            d["profile_notes"] = p_fld["notes"]
        if p_fld.get("valueMap") and field.value:
            mapped = p_fld["valueMap"].get(field.value)
            if mapped:
                d["mapped_value"] = mapped

    # Components
    if field.components:
        dt = fld_def["dt"] if fld_def else None
        # Resolve OBX-5 dynamic type
        if dt == "*":
            dt = None
        dt_info = DATA_TYPES.get(dt, {}) if dt else {}
        comp_defs = dt_info.get("components", [])

        comps = []
        for comp in field.components:
            if not show_empty and not comp.value:
                continue
            cd = _component_to_dict(comp)
            if comp.index <= len(comp_defs):
                cd["name"] = comp_defs[comp.index - 1]["name"]
                cd["data_type"] = comp_defs[comp.index - 1]["dt"]
            comps.append(cd)
        if comps:
            d["components"] = comps

    # Repetitions
    if field.repetitions and len(field.repetitions) > 1:
        reps = []
        for rep in field.repetitions:
            rd = {"index": rep.index, "value": rep.value}
            if rep.components:
                rd["components"] = [_component_to_dict(c) for c in rep.components if show_empty or c.value]
            reps.append(rd)
        d["repetitions"] = reps

    return d


def _serialize_parsed(parsed, version=None, profile=None, show_empty=False):
    """Serialize a ParsedMessage to a JSON-friendly dict."""
    if version is None:
        version = resolve_version(parsed.version)

    result = {
        "message_type": parsed.message_type,
        "version": parsed.version,
        "resolved_version": version,
        "segment_count": len(parsed.segments),
        "segments": [],
    }

    if parsed.declared_charset:
        result["declared_charset"] = parsed.declared_charset

    if profile:
        result["profile"] = profile.get("name", "unknown")

    for seg in parsed.segments:
        seg_def = get_seg_def(seg.name, version)
        p_seg = get_profile_segment(profile, seg.name) if profile else None

        seg_dict = {
            "name": seg.name,
        }
        if seg_def:
            seg_dict["description"] = seg_def["name"]
        elif p_seg and p_seg.get("description"):
            seg_dict["description"] = p_seg["description"]

        if seg.rep_index > 1:
            seg_dict["repetition"] = seg.rep_index

        fields = []
        for fld in seg.fields:
            fd = _field_to_dict(fld, seg.name, version, profile, show_empty)
            if fd is not None:
                fields.append(fd)
        seg_dict["fields"] = fields
        result["segments"].append(seg_dict)

    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def hl7_parse(message: str, profile: str = "", show_empty: bool = False) -> str:
    """Parse a raw HL7 v2.x message into structured JSON.

    Args:
        message: Raw HL7 message text (segments separated by \\r, \\n, or \\r\\n).
        profile: Optional profile name (filename in profiles/ dir, e.g. "sample-profile").
        show_empty: If true, include empty fields in output (default: false, saves tokens).

    Returns:
        JSON with version, message_type, segments array with field definitions,
        component breakdowns, and profile overlays.
    """
    parsed = parse_hl7(message)
    if not parsed:
        return json.dumps({"error": "Could not parse message — no valid segments found"})

    prof = _load_profile_by_name(profile) if profile else None
    version = resolve_version(parsed.version)
    result = _serialize_parsed(parsed, version, prof, show_empty)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def hl7_get_field(message: str, address: str) -> str:
    """Extract a specific field from an HL7 message by address.

    Args:
        message: Raw HL7 message text.
        address: HL7 field address, e.g. "PID-5", "OBX[2]-5", "MSH-9.1" (dot for component).

    Returns:
        JSON with the field value, definition metadata, and component breakdown.
        Dot notation (e.g. "PID-5.1") returns just the component value.
    """
    parsed = parse_hl7(message)
    if not parsed:
        return json.dumps({"error": "Could not parse message"})

    version = resolve_version(parsed.version)

    # Check for component dot notation: PID-5.1
    comp_index = None
    base_address = address
    dot_match = re.match(r'^(.+)\.(\d+)$', address)
    if dot_match:
        base_address = dot_match.group(1)
        comp_index = int(dot_match.group(2))

    # Parse segment/field from base address
    addr_match = re.match(r'^([A-Z][A-Z0-9]{1,2})(?:\[(\d+)\])?-(\d+)$', base_address)
    if not addr_match:
        return json.dumps({"error": f"Invalid address format: {address}. Expected SEG-N, SEG[rep]-N, or SEG-N.comp"})

    seg_name = addr_match.group(1)
    rep_idx = int(addr_match.group(2)) if addr_match.group(2) else None
    field_num = int(addr_match.group(3))

    # Find the field
    for seg in parsed.segments:
        if seg.name != seg_name:
            continue
        if rep_idx is not None and seg.rep_index != rep_idx:
            continue
        for fld in seg.fields:
            if fld.field_num == field_num:
                if comp_index is not None:
                    # Return specific component
                    fld_def = get_field_def(seg_name, field_num, version)
                    dt = fld_def["dt"] if fld_def else None
                    dt_info = DATA_TYPES.get(dt, {}) if dt else {}
                    comp_defs = dt_info.get("components", [])

                    comp_value = None
                    comp_name = None
                    if fld.components and comp_index <= len(fld.components):
                        comp_value = fld.components[comp_index - 1].value
                    elif not fld.components and comp_index == 1:
                        comp_value = fld.value

                    if comp_index <= len(comp_defs):
                        comp_name = comp_defs[comp_index - 1]["name"]

                    result = {
                        "address": f"{base_address}.{comp_index}",
                        "value": comp_value,
                    }
                    if comp_name:
                        result["name"] = comp_name
                    return json.dumps(result, ensure_ascii=False)

                # Return full field
                fd = _field_to_dict(fld, seg_name, version, show_empty=True)
                return json.dumps(fd, ensure_ascii=False)

    return json.dumps({"error": f"Field {address} not found in message"})


@mcp.tool()
def hl7_validate(message: str, profile: str = "") -> str:
    """Check an HL7 message for structural issues.

    Args:
        message: Raw HL7 message text.
        profile: Optional profile name for profile-aware validation.

    Returns:
        JSON with a list of issues, each with severity (error/warning/info),
        field address, and description.
    """
    parsed = parse_hl7(message)
    if not parsed:
        return json.dumps({"issues": [{"severity": "error", "description": "Could not parse message — no valid segments found"}]})

    version = resolve_version(parsed.version)
    prof = _load_profile_by_name(profile) if profile else None
    issues = []

    # Check: MSH must be first segment
    if not parsed.segments or parsed.segments[0].name != "MSH":
        issues.append({"severity": "error", "description": "Message must start with MSH segment"})

    # Check required MSH fields
    for req_field, req_name in [(9, "Message Type"), (10, "Message Control ID"), (12, "Version ID")]:
        val = format_field_value(parsed, f"MSH-{req_field}", version)
        if not val:
            issues.append({"severity": "error", "field": f"MSH-{req_field}", "description": f"Required field {req_name} is empty"})

    # Check unknown segments
    for seg in parsed.segments:
        seg_def = get_seg_def(seg.name, version)
        if not seg_def and not seg.name.startswith("Z"):
            p_seg = get_profile_segment(prof, seg.name) if prof else None
            if not p_seg:
                issues.append({"severity": "warning", "field": seg.name, "description": f"Unknown segment (not in v{version} definitions)"})

    # Check field lengths
    for seg in parsed.segments:
        for fld in seg.fields:
            if not fld.raw_value:
                continue
            fld_def = get_field_def(seg.name, fld.field_num, version)
            if fld_def and fld_def["len"] and len(fld.raw_value) > fld_def["len"]:
                issues.append({
                    "severity": "warning",
                    "field": fld.address,
                    "description": f"Value length ({len(fld.raw_value)}) exceeds max ({fld_def['len']})",
                })

    # Check required fields (opt == "R") that are empty
    for seg in parsed.segments:
        seg_def = get_seg_def(seg.name, version)
        if not seg_def:
            continue
        for fnum, fdef in seg_def.get("fields", {}).items():
            if fdef["opt"] != "R":
                continue
            found = False
            for fld in seg.fields:
                if fld.field_num == fnum and fld.raw_value:
                    found = True
                    break
            if not found:
                addr = f"{seg.name}-{fnum}"
                if seg.rep_index > 1:
                    addr = f"{seg.name}[{seg.rep_index}]-{fnum}"
                issues.append({
                    "severity": "warning",
                    "field": addr,
                    "description": f"Required field {fdef['name']} is empty",
                })

    # Profile-aware validation
    if prof and prof.get("segments"):
        for seg_name_p, seg_prof in prof["segments"].items():
            if "fields" not in seg_prof:
                continue
            # Find matching segments in message
            matching_segs = [s for s in parsed.segments if s.name == seg_name_p]
            if not matching_segs:
                if seg_prof.get("custom"):
                    # Custom/Z-segments: only info-level
                    issues.append({
                        "severity": "info",
                        "field": seg_name_p,
                        "description": f"Profile defines custom segment {seg_name_p} but it is not in the message",
                    })
                else:
                    issues.append({
                        "severity": "info",
                        "field": seg_name_p,
                        "description": f"Profile expects segment {seg_name_p} but it is not in the message",
                    })
                continue

            # Check each field the profile defines
            for fnum_str, fprof in seg_prof["fields"].items():
                try:
                    fnum = int(fnum_str)
                except ValueError:
                    continue

                for seg in matching_segs:
                    addr = f"{seg.name}-{fnum}"
                    if seg.rep_index > 1:
                        addr = f"{seg.name}[{seg.rep_index}]-{fnum}"

                    # Find field value in this segment
                    fld_value = None
                    for fld in seg.fields:
                        if fld.field_num == fnum:
                            fld_value = fld.raw_value
                            break

                    display_name = fprof.get("customName", addr)

                    # Required field check
                    if fprof.get("required") and not fld_value:
                        issues.append({
                            "severity": "error",
                            "field": addr,
                            "description": f"Profile requires {display_name} but it is empty",
                        })

                    # Value map check — warn if value is not in the expected set
                    if fld_value and fprof.get("valueMap"):
                        # For composite fields, check the raw value and first component
                        check_values = [fld_value]
                        if "^" in fld_value:
                            check_values.append(fld_value.split("^")[0])
                        if not any(v in fprof["valueMap"] for v in check_values):
                            expected = ", ".join(fprof["valueMap"].keys())
                            issues.append({
                                "severity": "warning",
                                "field": addr,
                                "description": f"Value '{fld_value}' not in profile value map for {display_name}. Expected: {expected}",
                            })

    # Encoding mismatch check
    if parsed.declared_charset:
        from hl7view.definitions import MSH18_TO_ENCODING
        declared_enc = MSH18_TO_ENCODING.get(parsed.declared_charset, parsed.declared_charset)
        if declared_enc and declared_enc not in ("ASCII", ""):
            issues.append({
                "severity": "info",
                "field": "MSH-18",
                "description": f"Declared character set: {parsed.declared_charset} ({declared_enc})",
            })

    return json.dumps({"issue_count": len(issues), "issues": issues}, ensure_ascii=False)


@mcp.tool()
def hl7_anonymize(message: str, non_ascii_names: bool = False) -> str:
    """Strip PHI (Protected Health Information) from an HL7 message.

    Anonymizes PID and NK1 segments: patient name, ID, DOB, address, phone, SSN.
    Each call generates different random replacements.

    Args:
        message: Raw HL7 message text.
        non_ascii_names: If true, use Estonian name pool with special characters
                        (useful for testing charset handling). Default: ASCII names.

    Returns:
        The anonymized HL7 message as raw text.
    """
    parsed = parse_hl7(message)
    if not parsed:
        return "Error: Could not parse message"

    anon = anonymize_message(parsed, use_non_ascii=non_ascii_names)
    return reconstruct_message(anon)


@mcp.tool()
def hl7_transform(message: str, changes: dict[str, str]) -> str:
    """Modify field values in an HL7 message.

    Args:
        message: Raw HL7 message text.
        changes: Dict mapping field addresses to new values.
                 Example: {"PID-5": "DOE^JOHN", "MSH-9": "ADT^A08"}

    Returns:
        The modified HL7 message as raw text.
    """
    parsed = parse_hl7(message)
    if not parsed:
        return "Error: Could not parse message"

    errors = []
    for address, new_value in changes.items():
        # Parse address
        addr_match = re.match(r'^([A-Z][A-Z0-9]{1,2})(?:\[(\d+)\])?-(\d+)$', address)
        if not addr_match:
            errors.append(f"Invalid address: {address}")
            continue

        seg_name = addr_match.group(1)
        rep_idx = int(addr_match.group(2)) if addr_match.group(2) else None
        field_num = int(addr_match.group(3))

        found = False
        for seg in parsed.segments:
            if seg.name != seg_name:
                continue
            if rep_idx is not None and seg.rep_index != rep_idx:
                continue

            for fld in seg.fields:
                if fld.field_num == field_num:
                    reparse_field(fld, new_value)
                    found = True
                    break

            if found:
                seg.raw_line = rebuild_raw_line(seg.name, seg.fields)
                break

        if not found:
            errors.append(f"Field {address} not found")

    result = reconstruct_message(parsed)
    if errors:
        result = f"# Warnings: {'; '.join(errors)}\n{result}"
    return result


@mcp.tool()
def hl7_send(
    host: str,
    port: int,
    message: str,
    timeout: int = 10,
    tls: bool = False,
    tls_ca: str = "",
    tls_cert: str = "",
    tls_key: str = "",
    tls_insecure: bool = False,
) -> str:
    """Send an HL7 message via MLLP and return the response.

    Args:
        host: Target hostname or IP address.
        port: Target port number.
        message: Raw HL7 message text to send.
        timeout: Socket timeout in seconds (default: 10).
        tls: Enable TLS encryption.
        tls_ca: Path to CA certificate PEM file.
        tls_cert: Path to client certificate PEM file (for mTLS).
        tls_key: Path to client private key PEM file (for mTLS).
        tls_insecure: Skip server certificate verification (for testing).

    Returns:
        JSON with response_text, elapsed_ms, and ack_code (if ACK/NAK response).
    """
    # Normalize message for wire format
    parsed = parse_hl7(message)
    if not parsed:
        return json.dumps({"error": "Could not parse message"})

    wire_msg = reconstruct_message(parsed)

    tls_config = None
    if tls or tls_ca or tls_cert:
        tls_config = {}
        if tls_ca:
            tls_config["ca_cert"] = tls_ca
        if tls_cert:
            tls_config["client_cert"] = tls_cert
        if tls_key:
            tls_config["client_key"] = tls_key
        if tls_insecure:
            tls_config["insecure"] = True

    try:
        response_text, elapsed_ms = mllp_send(
            host, port, wire_msg, timeout=timeout, tls_config=tls_config,
        )
    except (ConnectionError, TimeoutError, OSError) as e:
        return json.dumps({"error": str(e), "error_type": type(e).__name__})

    result = {"elapsed_ms": elapsed_ms}

    if response_text:
        result["response_text"] = response_text
        # Try to parse the response to extract ACK code
        resp_parsed = parse_hl7(response_text)
        if resp_parsed:
            ack_code = format_field_value(resp_parsed, "MSA-1")
            if ack_code:
                result["ack_code"] = ack_code
            resp_msg_type = resp_parsed.message_type
            if resp_msg_type:
                result["response_type"] = resp_msg_type
    else:
        result["response_text"] = None

    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def hl7_explain(item: str, version: str = "2.5") -> str:
    """Look up HL7 definitions — segments, fields, or data types.

    No message needed — pure reference lookup.

    Args:
        item: What to look up. Can be:
              - Segment name: "PID", "OBX", "MSH"
              - Field address: "PID-5", "MSH-9", "OBR-4"
              - Data type: "XPN", "CX", "CE", "HD"
        version: HL7 version to use for definitions ("2.3" or "2.5", default "2.5").

    Returns:
        JSON with definition details: for segments all fields are listed,
        for fields the name/type/components, for data types the component breakdown.
    """
    resolved = resolve_version(version)
    item = item.strip()

    # Check if it's a data type
    if item.upper() in DATA_TYPES:
        dt = DATA_TYPES[item.upper()]
        result = {"type": "data_type", "code": item.upper(), "name": dt["name"]}
        if dt.get("primitive"):
            result["primitive"] = True
        if dt.get("components"):
            result["components"] = [
                {"index": i + 1, "name": c["name"], "data_type": c["dt"]}
                for i, c in enumerate(dt["components"])
            ]
        return json.dumps(result, ensure_ascii=False)

    # Check if it's a field address (SEG-N)
    field_match = re.match(r'^([A-Z][A-Z0-9]{1,2})-(\d+)$', item)
    if field_match:
        seg_name = field_match.group(1)
        field_num = int(field_match.group(2))
        fld_def = get_field_def(seg_name, field_num, resolved)
        if not fld_def:
            return json.dumps({"error": f"No definition for {item} in v{resolved}"})

        result = {
            "type": "field",
            "address": item,
            "name": fld_def["name"],
            "data_type": fld_def["dt"],
            "optionality": fld_def["opt"],
            "repeating": fld_def["rep"],
            "max_length": fld_def["len"],
            "version": resolved,
        }

        # Add component breakdown if composite type
        dt_info = DATA_TYPES.get(fld_def["dt"], {})
        if dt_info.get("components"):
            result["components"] = [
                {"index": i + 1, "name": c["name"], "data_type": c["dt"]}
                for i, c in enumerate(dt_info["components"])
            ]

        return json.dumps(result, ensure_ascii=False)

    # Check if it's a segment name
    seg_name = item.upper()
    seg_def = get_seg_def(seg_name, resolved)
    if seg_def:
        result = {
            "type": "segment",
            "name": seg_name,
            "description": seg_def["name"],
            "version": resolved,
            "fields": [],
        }
        for fnum in sorted(seg_def["fields"].keys()):
            fdef = seg_def["fields"][fnum]
            fd = {
                "field_num": fnum,
                "address": f"{seg_name}-{fnum}",
                "name": fdef["name"],
                "data_type": fdef["dt"],
                "optionality": fdef["opt"],
                "repeating": fdef["rep"],
                "max_length": fdef["len"],
            }
            result["fields"].append(fd)
        return json.dumps(result, ensure_ascii=False)

    return json.dumps({"error": f"Unknown item: {item}. Try a segment name (PID), field address (PID-5), or data type (XPN)."})


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("hl7://samples/{name}")
def get_sample(name: str) -> str:
    """Get a sample HL7 message by filename (e.g. 'adt-a01-admit-v25.hl7')."""
    path = (SAMPLES_DIR / name).resolve()
    if not path.is_relative_to(SAMPLES_DIR.resolve()):
        return "Access denied: path escapes samples directory"
    if not path.exists():
        available = [f.name for f in SAMPLES_DIR.glob("*.hl7")] if SAMPLES_DIR.exists() else []
        return f"Sample not found: {name}. Available: {', '.join(available)}"
    return path.read_text(encoding="utf-8", errors="replace")


@mcp.resource("hl7://profiles/{name}")
def get_profile_resource(name: str) -> str:
    """Get an integration profile by filename (e.g. 'sample-profile.json')."""
    path = PROFILES_DIR / name
    if not path.suffix:
        path = path.with_suffix(".json")
    path = path.resolve()
    if not path.is_relative_to(PROFILES_DIR.resolve()):
        return "Access denied: path escapes profiles directory"
    if not path.exists():
        available = [f.name for f in PROFILES_DIR.glob("*.json")] if PROFILES_DIR.exists() else []
        return f"Profile not found: {name}. Available: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


@mcp.resource("hl7://definitions/{version}")
def get_definitions(version: str) -> str:
    """Get HL7 definitions summary for a version (2.3 or 2.5).

    Returns a list of all segments with their field inventories.
    """
    resolved = resolve_version(version)
    defs = HL7_DEFS.get(resolved)
    if not defs:
        return json.dumps({"error": f"No definitions for version {version}"})

    result = {"version": resolved, "segments": []}
    for seg_name in sorted(defs.keys()):
        seg = defs[seg_name]
        seg_info = {
            "name": seg_name,
            "description": seg["name"],
            "field_count": len(seg["fields"]),
            "fields": [
                {"num": fnum, "name": seg["fields"][fnum]["name"], "dt": seg["fields"][fnum]["dt"]}
                for fnum in sorted(seg["fields"].keys())
            ],
        }
        result["segments"].append(seg_info)

    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

class Transport(str, Enum):
    stdio = "stdio"
    sse = "sse"

app = typer.Typer()


@app.command()
def main(
    transport: Transport = typer.Option(Transport.stdio, help="Transport to use"),
    host: str = typer.Option("127.0.0.1", help="Host to listen on (SSE only)"),
    port: int = typer.Option(8000, help="Port to listen on (SSE only)"),
):
    """Run the HL7 MCP server."""
    if transport == Transport.stdio:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    app()
