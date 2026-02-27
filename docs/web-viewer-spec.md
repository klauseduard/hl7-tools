# HL7 Web Viewer — Implementation-Specific Features

Supplements `hl7-viewer-spec.md` (the base functional specification) with features
and constraints specific to the browser-based HTML/JS implementation.

Reference implementation: `hl7-viewer.html`

---

## 1. Architecture

### 1.1 Single-file, zero-dependency

- Entire viewer is one self-contained HTML file (HTML + CSS + JS)
- No build step, no external dependencies, no framework
- Works from `file://` protocol — no web server required
- Open directly in Firefox (primary target) or any modern browser

### 1.2 No server-side component

- All processing is client-side JavaScript
- No data leaves the browser — important for patient data privacy
- Minimal persistent storage via localStorage (empty-field toggle preference, external message injection)
- All other state exists only in memory for the duration of the page session

---

## 2. Layout

### 2.1 Four-tab layout

Fixed layout, no resizable panes:

- **Left panel** (62% width): tabbed — Input | Parsed | Raw | Compare
- **Right panel** (remaining): field detail
- **Toolbar** (top): version selector, buttons, search, profile indicator, compare indicator
- **Encoding info bar** (below toolbar, shown after parsing)
- **Anonymization indicator bar** (below toolbar, shown when active)

### 2.2 Tab switching

Four tabs in the left panel, switched by clicking tab headers:
- **Input tab**: textarea for message input + action buttons (Parse, Clear, Sample)
- **Parsed tab**: field table (primary working view)
- **Raw tab**: syntax-colored raw segments
- **Compare tab**: field-level diff of two messages

After parsing, auto-switches to the Parsed tab.

---

## 3. Input Methods

### 3.1 Textarea paste

- Paste HL7 message into textarea
- Press **Parse** button or **Ctrl+Enter** to parse
- Input source tracked as "paste" for encoding display

### 3.2 File Open button

- Toolbar **Open** button triggers a hidden `<input type="file">`
- Accepts `.hl7`, `.txt`, `.dat`, `.msg` extensions
- File is read as `ArrayBuffer` for byte-level encoding detection
- Decoded using detected encoding (not browser default UTF-8)
- Input source tracked as "file" with encoding metadata

### 3.3 Drag and drop

- Drag a file onto the textarea
- Visual feedback: border turns green, subtle background change
- Drop triggers the same file-reading path as Open button
- Dragleave restores normal appearance

### 3.4 Embedded sample message

- **Sample** button loads a hardcoded ADR^A19 v2.5 message
- 5 segments: MSH, MSA, QRD, PID, PV1
- Input source tracked as "sample"

### 3.5 Clear

- **Clear** button resets all state: input, parsed data, raw view, detail panel,
  encoding info, anonymization, profile remains loaded

---

## 4. Toolbar

Left to right:
1. **Version selector** — dropdown: Auto-detect, v2.3, v2.5
2. **Open** button — file picker
3. **Load Profile** button — JSON file picker
4. **Profile indicator** — shown when profile loaded (name + unload ✕ button)
5. **Anon** button — toggle anonymization (highlighted yellow when active)
6. **Non-ASCII** checkbox — toggle Estonian name pool for anonymization
7. **Empty** button — toggle empty field visibility (highlighted yellow when active, persisted in localStorage)
8. **?** button — opens help modal
9. **Search input** — text field for live filtering
10. **Title** — "HL7 Message Viewer" (right-aligned)

---

## 5. Interaction Model

### 5.1 Click-driven selection

- Click a field row in parsed table → selects it, shows detail, highlights in raw view
- Click a field span in raw view → selects it, switches to parsed tab, scrolls to row, shows detail
- Click segment header → no detail, but can collapse/expand
- Click expand icon (▶/▼) → toggle component sub-rows
- Click data type link in detail panel → browse data type definition

### 5.2 Keyboard shortcuts

| Shortcut | Context | Action |
|----------|---------|--------|
| `↑` / `↓` | Parsed tab focused | Navigate field rows |
| `Enter` | Field row selected | Expand/collapse components |
| `Esc` | Search focused | Clear search and blur |
| `Esc` | Help modal open | Close help modal |
| `Ctrl+C` | Field row selected | Copy value to clipboard |
| `E` | Parsed tab focused | Toggle empty field visibility |
| `Ctrl+Shift+A` | Any context | Toggle anonymization |
| `Ctrl+Enter` | Textarea focused | Parse message |

Keyboard navigation skips hidden rows (search-filtered, collapsed, or empty-filtered).

### 5.3 Search

- Typing in the search input triggers live filtering
- Matches against the full text content of each field row (address, name, type, value)
- Non-matching rows hidden; segment headers hidden if no children match
- Works in both Parsed tab and Compare tab (filters diff rows the same way)
- Case-insensitive

---

## 6. Visual Theme

### 6.1 Dark theme (Catppuccin Mocha palette)

Fixed dark theme, not configurable:

| Element | Color variable | Hex |
|---------|---------------|-----|
| Background | `--bg` | #1e1e2e |
| Surface/borders | `--surface` | #45475a |
| Text | `--text` | #cdd6f4 |
| Subdued text | `--subtext` | #a6adc8 |
| Segment names | `--rose` | #f38ba8 |
| Field names | `--green` | #a6e3a1 |
| Data types | `--orange` | #fab387 |
| Addresses | `--blue` | #89b4fa |
| Escape sequences | `--yellow` | #f9e2af |
| Profile badges | `--mauve` | #cba6f7 |
| Errors/warnings | `--red` / `--orange` | #f38ba8 / #fab387 |

### 6.2 Typography

- Monospace font stack: JetBrains Mono, Fira Code, Cascadia Code, Consolas
- Base size: 13px
- Component rows: 12px
- Toolbar/status: 11–12px

### 6.3 Custom scrollbars

Webkit-styled scrollbars matching the dark theme (thin, surface-colored thumb).

---

## 7. Help Modal

- Opened by **?** button in toolbar
- Overlay with centered modal (750px wide, max 85vh height, scrollable)
- Close via ✕ button, Esc key, or clicking outside the modal

**Content:**
- What profiles are and how they work
- Profile JSON schema documentation with examples
- Field definition reference table (customName, description, notes, dt, valueMap, components)
- Z-segment example
- Keyboard shortcuts reference

---

## 8. Message Comparison (Compare Tab)

### 8.1 Workflow

1. Parse Message A normally (paste/open) — appears in Parsed/Raw tabs
2. Click **Compare** tab — Message A info shown automatically (type + segment count from parsed input)
3. Paste or open Message B in the input area
4. Click **Compare** — diff renders, input area collapses
5. Toolbar shows "Comparing A vs B" indicator with ✕ to exit
6. Parsed/Raw tabs still show Message A — user can switch freely
7. Click **Edit** in the summary bar to show/hide the input area (to modify Message B and re-compare)
8. Click **Reset** to clear the comparison entirely and start over

### 8.2 Diff table

- 5 columns: Address | Field Name | Message A | Message B | Status
- Segments indexed by `(name, occurrence)`, fields compared by `field_num` using exact `raw_value` match
- Status values: `modified`, `a_only`, `b_only`, `identical`
- Character-level highlighting on modified fields: the exact differing characters are highlighted with an orange/peach background
- Smart truncation for long values: ensures the diff region is visible even when the value exceeds the column width
- Segment header rows with status badges for A-only / B-only segments

### 8.3 Detail panel (compare mode)

Clicking a diff row shows:
- Field metadata (segment, name, data type)
- Side-by-side values table with character-level highlighting on the raw row
- Component breakdown with per-component character-level highlighting for changed components

### 8.4 Filter and summary

- Summary bar: "N differences across M segments: X modified, Y A-only, Z B-only"
- "Show identical" checkbox to toggle visibility of unchanged fields
- Reset button to clear comparison and allow entering a new Message B

---

## 9. Limitations (browser-imposed)

### 9.1 No raw TCP

- Cannot open TCP sockets from browser JavaScript
- **MLLP send/receive is not possible** — no way to send HL7 messages to a listening port or act as an MLLP server
- Workaround would require a local bridge process (breaks the single-file model)

### 9.2 No filesystem access

- Cannot read files without user action (Open button or drag-and-drop)
- Cannot save/write files (only clipboard copy)
- Cannot watch a directory for new messages

### 9.3 Limited persistent state

- Closing the tab loses all in-memory state
- No recent files, no saved profiles — profile must be reloaded each session
- **localStorage** used for: empty-field toggle preference (`hl7viewer.showEmpty`), external message injection (`hl7viewer.pending`)

### 9.4 Single message at a time

- No batch processing of multiple files
- No message queue or history navigation
- Loading a new message replaces the current one
- **Exception**: Compare tab allows loading a second message (Message B) for field-level diff against the current message (Message A)

---

## 10. External Integration (localStorage)

### 10.1 Purpose

Allows external components (e.g., a HIS application) to inject HL7 messages into the viewer without user file interaction. The viewer checks `localStorage` on page load and consumes any pending message.

### 10.2 Contract

The external component writes a JSON object to `localStorage` key `hl7viewer.pending`:

```json
{
  "raw": "MSH|^~\\&|...",
  "rawBytes": "<base64-encoded original bytes>",
  "profile": { ... },
  "timestamp": 1740000000000
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `raw` | One of `raw`/`rawBytes` | Decoded message text (UTF-8 string) |
| `rawBytes` | One of `raw`/`rawBytes` | Base64-encoded original bytes — enables byte-level encoding detection |
| `profile` | No | Integration profile object (same schema as profile JSON files) |
| `timestamp` | Yes | Unix epoch milliseconds — message must be < 30 seconds old |

### 10.3 Behavior

1. On page load, check for `localStorage.getItem('hl7viewer.pending')`
2. If found, parse JSON and immediately remove the key
3. Reject if timestamp is older than 30 seconds (stale message)
4. If `rawBytes` is provided, decode base64 to `ArrayBuffer` and run byte-level encoding detection (same path as file loading)
5. If only `raw` is provided, use the text directly
6. If `profile` is provided, activate it (same as loading via toolbar)
7. Populate the textarea and trigger parsing
8. If anything fails, the viewer remains functional with no message loaded
