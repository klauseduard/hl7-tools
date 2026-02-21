# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HL7 message parsing tools: a legacy CLI Java utility and an interactive browser-based viewer.

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

**Integration Profiles** (`profiles/` directory):
- JSON files that overlay custom field names, descriptions, notes, and value maps onto the parsed view
- `profiles/sample-profile.json` — documented example showing all supported schema options
- Profiles are loaded via the toolbar file picker; work from `file://` protocol

### Legacy CLI Tool (`HL7MessageViewer.java`) — not in repo

```bash
javac HL7MessageViewer.java
java -cp . HL7MessageViewer <file.hl7>
```

**Known issue:** MSH-1 (field separator `|`) is never output, and MSH-2 (encoding chars `^~\&`) is mislabeled as MSH-1. The interactive viewer fixes this.

### Shell Wrappers — not in repo

- `hl7_message_viewer` — processes one or more HL7 files passed as arguments
- `hl7_message_viewer_clipboard` — reads HL7 content from X clipboard (via `xclip -o`) and pipes to the viewer

### MCP Server (`hl7view/mcp_server.py`)

Exposes HL7 parsing capabilities to LLM agents via the Model Context Protocol (MCP).

**Setup:**
```bash
cd /home/klaus/bin/hl7tools
python3 -m venv venv
venv/bin/pip install -r requirements-mcp.txt
```

**Run:** Registered in `~/.claude.json` under `mcpServers.hl7` — starts automatically with Claude Code.

**Tools (7):**
- `hl7_parse` — Parse raw HL7 into structured JSON with definitions and profile overlays
- `hl7_get_field` — Extract a specific field by address (e.g. "PID-5", "MSH-9.1")
- `hl7_validate` — Check message for structural issues (missing required fields, length violations, unknown segments)
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

## Test Messages

Sample HL7 messages for testing (not included in repo):
- ADR^A19 response (v2.5), 5 segments: MSH, MSA, QRD, PID, PV1
- QRY^A19 query (v2.3.1), 2 segments: MSH, QRD
