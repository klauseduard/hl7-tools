# HL7 Viewer — Functional Specification

Describes **what** the HL7 viewer does, independent of implementation technology.
Derived from the web viewer (`hl7-viewer.html`) as the reference implementation.

---

## 1. Input

### 1.1 Message sources

The viewer accepts HL7 messages from:
- **File** — read from filesystem (`.hl7`, `.txt`, `.dat`, `.msg` extensions common)
- **Text input** — pasted or typed directly
- **Clipboard** — read from system clipboard

Multiple messages can be loaded sequentially; only one is active at a time.

### 1.2 Encoding detection

Detect character encoding at the byte level before decoding text:

1. **BOM check**: UTF-8 BOM (`EF BB BF`), UTF-16 LE (`FF FE`), UTF-16 BE (`FE FF`)
2. **Byte heuristic**: scan for valid UTF-8 multi-byte sequences
   - All bytes < 0x80 → ASCII
   - High bytes present + valid UTF-8 sequences → UTF-8
   - High bytes present + invalid UTF-8 → ISO-8859-1 (decode as windows-1252)
3. Report detected encoding alongside the message

### 1.3 Message normalization

Before parsing, normalize the raw input:

1. **Strip MLLP framing**: leading `0x0B` (VT), trailing `0x1C` (FS) + optional CR
2. **Strip log/dump artifacts**: `<VT>`, `<FS>`, `<CR>`, `<SB>`, `<EB>` text markers; stray `0x0B`/`0x1C` mid-message
3. **Normalize line endings**:
   - Collapse `\r\n` → `\r`
   - If `\r` present, use as segment delimiter (standard HL7)
   - If only `\n` present, use as segment delimiter (unix-ified files)
   - If single line with no delimiters, detect segment boundaries by known segment names and split
4. **Handle mixed newlines**: when `\r` is the delimiter but `\n` appears mid-segment (Java-style "illegal newlines"), keep `\n` within the segment data rather than splitting

---

## 2. Parsing

### 2.1 Segment and field extraction

- Split each segment line on `|` (field separator)
- First token is the segment name (3-letter code, or Z-segment pattern `Z[A-Z][A-Z0-9]`)

**MSH special handling:**
- MSH-1 = `|` (the field separator itself — implicit, not present in pipe-split output)
- MSH-2 = encoding characters (`^~\&`), from `fields[1]`
- MSH-3 onwards = `fields[2]`, `fields[3]`, ... with field number = array index + 1

**All other segments:**
- `fields[1]` = SEG-1, `fields[2]` = SEG-2, etc.

### 2.2 Repeated segments

Track occurrence count per segment name within a message. Addresses for repeated segments use bracket notation: first PID → `PID-3`, second PID → `PID[2]-3`.

### 2.3 Component and subcomponent splitting

- **Components**: split field value on `^` (component separator)
- **Subcomponents**: split each component on `&` (subcomponent separator)

### 2.4 Field repetitions

- Split field value on `~` (repetition separator)
- Each repetition gets its own independent component breakdown
- Repetitions are addressed as `PID-3~1`, `PID-3~2`, etc.
- Display repetition count badge (e.g., `[2x]`) on the parent field

### 2.5 Version detection

- Read MSH-12 (Version ID), extract first component (before `^`)
- Version mapping:
  - `2.3.*`, `2.4` → use v2.3 definitions
  - `2.5.*`, `2.6.*`, `2.7.*`, `2.8.*` → use v2.5 definitions
- Allow manual version override
- Default when undetectable: v2.5

### 2.6 Message metadata extraction

- **Message type**: from MSH-9 (e.g., `ADT^A01`, `ORU^R01`)
- **Declared charset**: from MSH-18 (e.g., `UNICODE UTF-8`, `8859/1`)
- Display in summary: message type, version, segment count

---

## 3. HL7 Definitions (embedded data)

### 3.1 Segment definitions

Two definition sets: **v2.3** and **v2.5** (v2.5 is v2.3 extended with additional fields/segments).

**Segments defined (~23):** MSH, EVN, PID, PV1, PV2, NK1, ORC, OBR, OBX, DG1, IN1, AL1, GT1, NTE, MSA, ERR, QRD, QRF, MRG, SCH, TXA, DSP

**v2.5 additions over v2.3:**
- MSH: fields 20–21
- PID: fields 31–39
- ORC: fields 20–25
- OBR: fields 44–50
- OBX: fields 18–19
- ERR: completely redefined (12 fields)

**Per-field metadata:**
- `name` — human-readable field name (e.g., "Patient Name")
- `dt` — data type code (e.g., XPN, CX, TS)
- `opt` — optionality: R (Required), O (Optional), C (Conditional), B (Backward compatible)
- `rep` — whether the field is repeatable
- `len` — maximum length

### 3.2 Data type definitions

~30 composite types with named, ordered components. Each component has a name and its own data type.

**Primitive types (no components):** ST, NM, ID, IS, SI, TX, FT, DT, DTM, TM

**Composite types:** CQ, HD, EI, CE, CWE, CNE, CX, XPN, XCN, XAD, XTN, PL, MSG, PT, VID, TS, FN, SAD, RP, DR, DLN, FC, DLD, CP, MO, SN, ED, CF, TQ, RI, XON

### 3.3 OBX-5 dynamic type resolution

OBX-5 (Observation Value) has the special data type `*` — resolved at runtime:
- Read OBX-2 (Value Type) from the same OBX segment
- Use that value (NM, CE, ST, FT, TX, ED, etc.) as the effective data type for OBX-5
- Apply the resolved type's component definitions to OBX-5
- Display an indicator showing the type was resolved from OBX-2

---

## 4. Display

### 4.1 Views

The viewer provides four views of the message:

**Input view:**
- Shows the raw message text as entered/loaded
- Editable — user can modify and re-parse

**Parsed view (primary):**
- Table with columns: **Address** | **Field Name** | **Type** | **Value**
- Segment header rows group fields visually (segment name + description)
- Empty fields may be hidden or shown (user preference)
- Repeating fields show repetition count badge
- Component sub-rows shown indented under parent field (expandable/collapsible)
- Repetition sub-rows shown under parent field

**Raw view:**
- Reconstructed segment lines with syntax coloring
- Segment names highlighted
- Field separators visually distinct
- Individual fields are selectable (clicking highlights corresponding parsed row)

**Compare view:**
- Input area for a second message (Message B) with paste and file open
- Field-by-field diff table with columns: **Address** | **Field Name** | **Message A** | **Message B** | **Status**
- Character-level highlighting of changed characters within modified fields, with smart truncation that keeps the diff region visible in long values
- Summary bar showing difference counts (modified, A-only, B-only) with Reset button
- Filter toggle to show all fields or differences only
- Segment headers as grouping rows with status badges (A only / B only)
- Color coding: modified (orange border), A-only (red tint), B-only (green tint), identical (dimmed)
- Clicking a diff row shows side-by-side values in the detail panel with character-level highlighting in raw values and component breakdown

### 4.2 Detail panel

Selecting a field shows full details:

**Specification section:**
- Segment: name + description
- Field: name (from spec or profile)
- Data type: code + full name (navigable — can browse type definition)
- Optionality: R/O/C/B with label
- Repeatable: Yes/No
- Max length
- Full raw value (untruncated)
- Decoded value (if escape sequences present)
- HL7 version in use

**Component breakdown table** (for composite types):
- Columns: # | Name | Type | Value
- Shows all defined components, even if empty in the data
- Uses resolved type for OBX-5

**Repetition list** (if field has `~` repetitions):
- Shows each repetition's value

**Comparison view** (if comparing two messages):
- Side-by-side values for Message A and Message B
- Character-level highlighting on differing characters
- Component breakdown with per-component diff highlighting

**Profile overlay** (if profile loaded, see section 5):
- Custom name, description, notes
- Value map table with current value highlighted

**Data type guidance** (contextual):
- FT: note about `\.br\` line breaks and escape sequences
- TX: note about `~` misuse as line break
- NM, DT, TS, CE, etc.: format hints
- Long ST values: suggest FT/TX instead

**Validation warnings** (see section 9)

### 4.3 Data type browser

Navigable from the detail panel — selecting a data type code shows:
- Full type name
- Primitive vs composite
- Component list with names and types (each type is also navigable)

### 4.4 Color coding

Consistent color semantics across all views:
- **Segment names**: rose/red
- **Field names**: green
- **Data types**: orange
- **Addresses**: blue (segment addresses in slightly different shade for components)
- **Escape sequences**: yellow with background highlight
- **Warnings**: orange (warning) or red (error)
- **Profile badges**: purple/mauve
- **Repetition indicators**: yellow
- **Empty values**: muted/italic

### 4.5 Segment collapse

- Segment groups are collapsible — toggle hides/shows all field rows under that segment
- Visual indicator: `▼` (expanded) / `▶` (collapsed)

---

## 5. Integration Profiles

### 5.1 Purpose

Profiles overlay integration-specific context onto standard HL7 definitions. They customize field names, add descriptions and implementation notes, define value maps, and provide type information for Z-segments.

Profiles do **not** replace spec definitions — they add to them.

### 5.2 Loading

- Load from a JSON file
- One profile active at a time
- Can be unloaded to return to spec-only view
- If profile specifies `hl7Version`, use it as version hint

### 5.3 Schema

```json
{
  "name": "Integration Name (required)",
  "hl7Version": "2.3",
  "description": "Optional description",
  "segments": {
    "SEGMENT_NAME": {
      "description": "Segment-level description",
      "custom": true,
      "fields": {
        "FIELD_NUM": {
          "customName": "Override field name",
          "required": true,
          "description": "Field description",
          "notes": "Implementation notes",
          "dt": "DATA_TYPE",
          "valueMap": { "code": "human-readable meaning" },
          "components": {
            "COMP_NUM": { "description": "Component description" }
          }
        }
      }
    }
  }
}
```

### 5.4 Overlay behavior

| Profile property | Effect |
|-----------------|--------|
| `customName` | Replaces standard field name in parsed view; marked with a badge |
| `required` | Marks field as required for this integration (used for validation) |
| `description` | Shown in detail panel under profile section |
| `notes` | Implementation notes shown in detail panel |
| `dt` | Overrides data type (essential for Z-segment fields) |
| `valueMap` | Maps coded values to descriptions; current value highlighted; used for validation |
| `components` | Overrides component descriptions |
| `custom: true` | Z-segments get "Custom Segment" label instead of "Unknown" |

### 5.6 Profile-driven validation

When a profile is loaded, validation is performed inline (all interfaces: warning icons on field rows, summary counts in header/toolbar, detail panel notes; MCP server: `hl7_validate` tool):

| Check | Severity | Condition |
|-------|----------|-----------|
| Required field empty | Error | `required: true` and field has no value |
| Unexpected coded value | Warning | `valueMap` defined and field value not in map |
| Expected segment missing | Info | Profile defines a segment not present in message |

For composite fields, the value map check matches against both the full raw value and the first component (e.g., `ORM^O01` matches both `ORM^O01` and `ORM`).

### 5.5 Profile indicator

When a profile is loaded:
- Show profile name in toolbar/status area
- Fields with profile overrides show a badge
- Segment headers with profile definitions show a badge
- Provide a way to unload the profile

---

## 6. Anonymization

### 6.1 Target fields

Anonymization operates on **PID segments only**, targeting identifying fields:

| Field | Replacement method |
|-------|-------------------|
| PID-2, PID-3 (Patient IDs) | Replace digits in ID component (component 1) with random digits; preserve CX component structure and length |
| PID-5, PID-9 (Patient Name, Alias) | Replace family and given names from a fake name pool; clear middle/second name; preserve remaining XPN components (suffix, prefix, degree, name type) |
| PID-7 (Date of Birth) | Shift year by random ±1–20 years; preserve month, day, and time portion |
| PID-11 (Patient Address) | Replace street and city from fake pools; randomize zip/postal code digits; preserve country and remaining XAD components |
| PID-13, PID-14 (Phone Home, Business) | Replace all digits with random digits; preserve all non-digit characters (formatting, `+`, separators) and XTN component structure |
| PID-19 (SSN) | Replace all digits with random digits; preserve separators (dashes, spaces) |
| PID-20 (Driver's License) | Randomize digits and alpha characters in license number (component 1); preserve issuing state and expiry date components |

### 6.2 Repetition handling

Each repetition in a repeating field (e.g., two entries in PID-3 separated by `~`) gets independent random replacement values.

### 6.3 Name pools

Two pools selectable by the user:

**ASCII pool (18 names):** Common English names (Smith/John, Doe/Jane, Johnson/Robert, etc.)

**Estonian non-ASCII pool (15 names):** Names with characters Õ, Ö, Ü, Ä, Ž, Š. Useful for testing encoding handling. Examples: Ööümin/Õgvardž, Tääger/Märt, Põldmäe/Külli.

**Fake addresses:** Mix of Estonian (Tamme tee 5, Pärnu mnt 42) and English (Oak Street 12, Maple Avenue 45) streets. Cities: Tallinn, Tartu, Pärnu, Narva, Springfield, Riverside, etc.

### 6.4 Toggle behavior

- Anonymization is a reversible toggle — original data is preserved
- When activated: all PID fields are replaced, raw segment lines are reconstructed, all views update
- When deactivated: original data is restored
- Switching name pool (ASCII ↔ non-ASCII) re-anonymizes with the new pool
- Parsing a new message resets anonymization state

---

## 7. Encoding Awareness

### 7.1 MSH-18 character set mapping

| MSH-18 value | Standard encoding |
|-------------|-------------------|
| (empty) | ASCII (default) |
| `ASCII` | ASCII |
| `8859/1` through `8859/9` | ISO-8859-1 through ISO-8859-9 |
| `UNICODE` | UTF-8 |
| `UNICODE UTF-8` | UTF-8 |
| `UTF-8` | UTF-8 |

### 7.2 Encoding display

Show an encoding info bar with:
- **File encoding**: detected encoding (with BOM indicator if present)
- **MSH-18**: declared charset with mapped encoding name
- For pasted text: note "browser-decoded" / "paste" as source
- For embedded samples: note "sample"

### 7.3 Mismatch detection

When message is loaded from a file, compare detected encoding vs MSH-18 declaration:

| Detected | Declared | Severity |
|----------|----------|----------|
| UTF-8/ASCII file | ISO-8859 declared | Warning |
| ISO-8859 file | UTF-8 declared | Error |
| ISO-8859 file | empty/ASCII declared | Warning (ambiguous) |
| Unknown MSH-18 value | — | Warning |

### 7.4 MSH-18 detail guidance

When viewing MSH-18 in the detail panel, show:
- Mapping of current value to standard encoding name
- Warning for unknown values with list of common valid values
- File-detected encoding for comparison

---

## 8. HL7 Escape Sequences

### 8.1 Recognized escape sequences

| Escape | Decoded character | Name |
|--------|------------------|------|
| `\F\` | `\|` | Field separator |
| `\S\` | `^` | Component separator |
| `\T\` | `&` | Subcomponent separator |
| `\R\` | `~` | Repetition separator |
| `\E\` | `\` | Escape character |
| `\.br\` | newline | Line break |
| `\.sp\` | space | Non-breaking space |
| `\Xhh\` | hex byte(s) | Hex-encoded character(s) |

### 8.2 Display behavior

- **Detection**: test field values for escape sequence patterns
- **Value display**: show raw escape sequences in parsed view
- **Detail panel**: show both raw value and decoded version
- **Visual highlighting**: escape sequences rendered with distinct background color and tooltip/description
- **Rendered escapes**: `\.br\` shown as ↵ symbol, `\.sp\` as ␣ symbol, separator escapes shown as their character

### 8.3 Contextual guidance

For fields with text data types, show format notes in the detail panel:

- **FT (Formatted Text)**: note that line breaks should be `\.br\`; list all escape sequences; warn if no escapes found in a non-empty value
- **TX (Text Data)**: note that some systems misuse `~` (repetition separator) as line break
- **ST (String)**: warn if value is long (>80 chars) and suggest FT/TX
- **Any field with escapes**: note that decoded view is available

---

## 9. Validation and Warnings

### 9.1 OBX validation

Shown in both the parsed table (warning icon on the field row) and the detail panel (descriptive message):

| Condition | Severity | Message |
|-----------|----------|---------|
| OBX-5 has data but OBX-2 empty | Warning | OBX-2 must declare data type |
| OBX-2 = NM but OBX-5 not numeric | Warning | Value does not match NM format |
| OBX-2 = DT but OBX-5 not YYYY[MM[DD]] | Warning | Value does not match DT format |
| OBX-2 = TS but OBX-5 not timestamp | Warning | Value does not match TS format |
| OBX-2 = CE/CWE/CNE but <2 components | Warning | Coded elements typically have code^text^system |

### 9.2 Type-specific guidance

For non-text data types, show format reference in the detail panel:
- NM: "should contain a single decimal number"
- DT: "format YYYY[MM[DD]]"
- TS/DTM: "format YYYY[MM[DD[HH[MM[SS]]]]][±ZZZZ]"
- CE/CWE/CNE: "components: identifier^text^coding system"
- ED: "components: source^type^subtype^encoding^data"
- SN: "components: comparator^num1^separator^num2"
- ID/IS: "coded value from HL7/user table"

### 9.3 Repetition ambiguity warning

When a repeatable text field (FT, TX) contains `~` separators, warn that the repetitions could be actual repeats OR line breaks depending on the sending system.

---

## 10. Search and Filter

### 10.1 Search behavior

- Accept a text search term
- Case-insensitive matching against field row content (address, field name, value)
- Non-matching field rows are hidden
- Segment headers remain visible if any child field matches; hidden if no children match
- Component/sub-rows follow their parent field's visibility
- Clearing the search term restores full view

---

## 11. Keyboard Navigation

In interactive/focused contexts, support these actions:

| Action | Description |
|--------|-------------|
| Navigate up/down | Move selection through visible field rows |
| Expand/collapse | Toggle component sub-rows for the selected field |
| Search | Activate search input |
| Clear search | Clear search term and restore full view |
| Copy value | Copy current field's value to clipboard |
| Toggle anonymization | Activate/deactivate anonymization |
| Toggle non-ASCII names | Switch anonymization name pool |
| Version cycle | Cycle through auto → 2.3 → 2.5 |

---

## 12. Raw View ↔ Parsed View Correspondence

- Selecting a field in the parsed view highlights the corresponding span in the raw view
- Selecting a field span in the raw view selects the corresponding row in the parsed view and shows its details
- Both directions of selection update the detail panel

---

## 13. Appendix: Segment Definition Coverage

### v2.3 segments

MSH (19 fields), EVN (6), PID (30), PV1 (52), PV2 (30), NK1 (13), ORC (19), OBR (43), OBX (17), DG1 (16), IN1 (22), AL1 (6), GT1 (12), NTE (4), MSA (6), ERR (1), QRD (12), QRF (5), MRG (7), SCH (25), TXA (23), DSP (5)

### v2.5 extensions

MSH +2 fields (20–21), PID +9 fields (31–39), ORC +6 fields (20–25), OBR +7 fields (44–50), OBX +2 fields (18–19), ERR redefined (12 fields)

### Data types (30)

Primitive (10): ST, NM, ID, IS, SI, TX, FT, DT, DTM, TM

Composite (20): CQ (2), HD (3), EI (4), CE (6), CWE (9), CNE (9), CX (10), XPN (14), XCN (23), XAD (14), XTN (12), PL (11), MSG (3), PT (2), VID (3), TS (2), FN (5), SAD (3), RP (4), DR (2), DLN (3), FC (2), DLD (2), CP (6), MO (2), SN (4), ED (5), CF (6), TQ (12), RI (2), XON (10)

_(number in parentheses = component count)_
