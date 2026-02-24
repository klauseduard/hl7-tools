# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HL7 v2.x message toolkit: web viewer, terminal TUI, Python parsing library, and MCP server for AI agents.

## Tools

### Interactive HL7 Viewer (`hl7-viewer.html`)

Single self-contained HTML/CSS/JS file. Open directly in Firefox (`file://` works, no server needed).

**Features:**
- Three-panel layout: Input (paste/drag-drop/Open button) | Parsed table | Field detail
- Embedded HL7 v2.3 and v2.5 segment/field definitions (~23 segments each) with data type component breakdowns (~30 composite types)
- Auto-detects HL7 version from MSH-12 (v2.3.1 maps to v2.3 definitions)
- Correct MSH field numbering: MSH-1 = `|` (field separator), MSH-2 = encoding characters
- Component (`^`) and subcomponent (`&`) splitting, field repetition (`~`) handling
- Loadable integration profile JSON files via `<input type="file">` for custom field names, descriptions, notes, value maps
- Live search/filter, collapsible segment groups, keyboard navigation, click-to-highlight raw view correspondence
- Dark theme with color coding: segments (rose), field names (green), data types (orange), addresses (blue)
- Encoding/charset awareness: byte-level detection (UTF-8/Latin-1/ASCII via BOM + heuristic), MSH-18 parsing, mismatch warnings in encoding info bar
- File Open button reads files as ArrayBuffer with automatic encoding detection (not just UTF-8)
- localStorage integration: external components can inject messages via `hl7viewer.pending` key (raw text or base64 bytes + optional profile)

**Integration Profiles** (`profiles/` directory):
- JSON files that overlay custom field names, descriptions, notes, and value maps onto the parsed view
- Profile fields support `required: true` (enforced by `hl7_validate`) and `valueMap` validation
- `profiles/sample-profile.json` — documented example showing all supported schema options
- Profiles are loaded via the toolbar file picker; work from `file://` protocol

### MCP Server (`hl7view/mcp_server.py`)

Exposes HL7 parsing capabilities to LLM agents via the Model Context Protocol (MCP).

**Setup:**
```bash
python3 -m venv venv
venv/bin/pip install -r requirements-mcp.txt
```

**Run:** Registered in `~/.claude.json` under `mcpServers.hl7` — starts automatically with Claude Code.

**Tools (7):**
- `hl7_parse` — Parse raw HL7 into structured JSON with definitions and profile overlays
- `hl7_get_field` — Extract a specific field by address (e.g. "PID-5", "MSH-9.1")
- `hl7_validate` — Check message for structural issues (missing required fields, length violations, unknown segments); with a profile: enforces `required` fields and `valueMap` value checks
- `hl7_anonymize` — Strip PHI from PID/NK1 segments
- `hl7_transform` — Modify field values by address (e.g. `{"PID-5": "DOE^JOHN"}`)
- `hl7_send` — Send message via MLLP with optional TLS/mTLS
- `hl7_explain` — Look up HL7 definitions (segments, fields, data types) without a message

**Resources (3):**
- `hl7://samples/{name}` — Sample HL7 messages from `samples/` directory
- `hl7://profiles/{name}` — Integration profiles from `profiles/` directory
- `hl7://definitions/{version}` — HL7 v2.3/v2.5 definition summaries

## HL7 Parsing Notes

- MSH-1 is the field separator `|` (implicit, not in pipe-split output). MSH-2 is encoding characters. MSH-3 onwards = `fields[2], fields[3], ...` with field number = array index + 1
- All other segments: `fields[1]` = SEG-1, `fields[2]` = SEG-2, etc.
- Repeated segments use bracket notation: `PID[2]-3`
- `replaceIllegalNewLines` / `normalizeMessage` handles HL7 messages where `\r` segment delimiters have been mixed with `\n` characters

## Sample Messages

`samples/` directory — included in repo:
- `adt-a01-admit-v25.hl7` — ADT^A01 admission (v2.5), 5 segments: MSH, EVN, PID, NK1, PV1
- `orm-o01-order-v23.hl7` — ORM^O01 radiology order (v2.3.1), 6 segments including ZDS custom segment, non-ASCII Estonian names, ISO-8859-1 charset
- `oru-r01-lab-v25.hl7` — ORU^R01 lab results (v2.5), 11 segments with 5 OBX (numeric, coded, string, formatted text with escape sequences, repeating values), NTE
