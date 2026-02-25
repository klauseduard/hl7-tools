# HL7 Terminal Viewer — Implementation-Specific Features

Supplements `hl7-viewer-spec.md` (the base functional specification) with features
and design specific to a Linux terminal (CLI + TUI) implementation.

---

## 1. Architecture

### 1.1 Language and dependencies

- Python 3 (available on target systems)
- Minimal external dependencies; prefer stdlib where practical
- TUI library (e.g., `curses`, `textual`, or `rich`) for interactive mode
- Single script or small package — easy to install and run

### 1.2 Dual-mode operation

- **Non-interactive mode**: parse, format, print to stdout, exit
  - Default when input is piped or output is redirected
  - Suitable for scripting, composition with other tools
- **Interactive mode**: full-screen TUI with navigation
  - Default when running in a terminal with no pipe
  - Force with `--interactive` / `-i`

---

## 2. Input Sources

### 2.1 File arguments

```
hl7view file.hl7
hl7view file1.hl7 file2.hl7 file3.hl7
```

Multiple files: parse and display sequentially (non-interactive) or navigate between them (interactive).

### 2.2 Standard input

```
cat file.hl7 | hl7view
xclip -o | hl7view
```

Read from stdin when no file arguments given and stdin is not a terminal.

### 2.3 Clipboard

```
hl7view --clipboard
```

Read X clipboard via `xclip -o` (mirrors existing `hl7_message_viewer_clipboard` wrapper).

### 2.4 Interactive input

In interactive mode with no file/pipe: prompt user to paste message, end with Ctrl+D or blank line.

---

## 3. Non-Interactive Output

### 3.1 Default table format

Colored, columnar output to terminal:

```
ADT^A01 v2.5 | 5 segments | UTF-8 file | MSH-18: UNICODE UTF-8
════════════════════════════════════════════════════════════════
── MSH  Message Header ────────────────────────────────────────
MSH-1     Field Separator          ST   |
MSH-2     Encoding Characters      ST   ^~\&
MSH-9     Message Type             MSG  ADT^A01
MSH-12    Version ID               VID  2.5
── PID  Patient Identification ────────────────────────────────
PID-3     Patient Identifier List  CX   PAT78432^^^HOSP^PI [2x]
PID-5     Patient Name             XPN  Tamm^Kristjan^Aleksander^Jr
PID-7     Date/Time of Birth       TS   19920715
PID-11    Patient Address          XAD  Tamme tee 15^^Tallinn^^10615^EST
```

- Empty fields hidden by default
- Color auto-detected via `isatty()`; disable with `--no-color`
- Same color semantics as base spec (segment=red, field=green, type=orange, address=blue)

### 3.2 Verbose mode

`--verbose` / `-v`: expand components inline, indented under parent field:

```
PID-5     Patient Name             XPN  Tamm^Kristjan^Aleksander^Jr
  .1      Family Name              FN   Tamm
  .2      Given Name               ST   Kristjan
  .3      Second Name              ST   Aleksander
  .4      Suffix                   ST   Jr
```

### 3.3 Output options

| Flag | Output |
|------|--------|
| (default) | Colored table |
| `--no-color` | Plain text table |
| `--raw` | Raw segment lines (post-normalization) |
| `--json` | JSON representation of parsed message |
| `-e`, `--empty` | Include empty fields |
| `-f`, `--field SEG-N` | Single field value only (e.g., `-f PID-3`) — for scripting |

`--anon` and `--anon-non-ascii` combinable with any output format.

---

## 4. Interactive Mode (TUI)

### 4.1 Layout

Full-screen terminal UI:

```
┌─ Toolbar ──────────────────────────────────────────────────────┐
│ v2.5 (auto) │ file.hl7 │ [Profile: Acme PACS] │ [ANON]       │
├─ Field List (scrollable) ──────────┬─ Detail ─────────────────┤
│ ── MSH  Message Header ──────     │ PID-5                     │
│ MSH-1   Field Separator    ST |   │                           │
│ MSH-2   Encoding Chars     ST ^~  │ Specification             │
│ ...                               │  Segment: PID - Patient   │
│ ── PID  Patient Ident ──────     │  Field:   Patient Name    │
│ PID-3   Patient ID List    CX ... │  Type:    XPN             │
│▸PID-5   Patient Name       XPN .. │  Opt:     Required (R)    │
│   .1    Family Name        FN  Ta │                           │
│   .2    Given Name         ST  Kr │ Components (XPN)          │
│ PID-7   Date/Time of Birth TS  19 │  1 Family Name    FN Tamm │
│ ...                               │  2 Given Name     ST Kris │
├─ Status ──────────────────────────┴───────────────────────────┤
│ ADT^A01 v2.5 │ 5 segments │ UTF-8 │ /search: pid             │
└───────────────────────────────────────────────────────────────┘
```

- **Left panel**: segment/field list with collapse, expand, scroll
- **Right panel**: detail for selected field (same content as base spec section 4.2)
- **Status bar**: message summary, encoding, warnings, search term, anonymization state

### 4.2 Keyboard bindings

| Key | Action |
|-----|--------|
| `↑` / `↓` / `j` / `k` | Navigate field rows |
| `Enter` | Expand/collapse components on field row; toggle collapse on segment header |
| `Tab` | Switch focus between panels |
| `/` | Start search (filter fields) |
| `Esc` | Clear search / cancel input |
| `c` | Copy current field value to clipboard (`xclip`) |
| `a` | Toggle anonymization |
| `n` | Toggle non-ASCII anonymization names |
| `r` | Toggle raw view |
| `v` | Cycle version: auto → 2.3 → 2.5 → auto |
| `s` | Open send dialog (see section 5) |
| `l` | Open listen dialog (see section 6) |
| `?` | Show help overlay |
| `q` | Quit |

### 4.3 Multiple files

When multiple files are provided:
- Show file navigation (e.g., `[1/3] file.hl7`)
- `←` / `→` or `[` / `]` to switch between files
- Each file maintains independent parse state

---

## 5. MLLP Client (send)

### 5.1 Non-interactive

```
hl7view --send host:port file.hl7
hl7view --send host:port --anon file.hl7
cat file.hl7 | hl7view --send host:port
```

### 5.2 Protocol

1. Open TCP connection to `host:port`
2. Wrap message in MLLP frame: `0x0B` + message content + `0x1C` + `0x0D`
3. Send framed message
4. Wait for response (ACK/NAK)
5. Strip MLLP framing from response
6. Display response (parse and show if valid HL7, raw otherwise)
7. Close connection

### 5.3 Options

| Flag | Description |
|------|-------------|
| `--send HOST:PORT` | Target MLLP endpoint |
| `--send-timeout N` | ACK wait timeout in seconds (default: 10) |
| `--send-no-wait` | Fire and forget — don't wait for ACK |

### 5.4 Interactive send

- Press `s` in interactive mode
- Prompt for `host:port` (remember last used within session)
- Send the currently displayed message (including anonymized version if active)
- Show ACK response in a transient overlay or parse it into a new view
- Connection errors shown in status bar

### 5.5 Sending anonymized messages

When anonymization is active, the sent message is the anonymized version.
This enables a workflow: load real message → anonymize → send to test system.

---

## 6. MLLP Server (listen)

### 6.1 Non-interactive

```
hl7view --listen port
hl7view --listen port --ack
hl7view --listen port --log-dir /path/to/logs
```

Listen on a TCP port for incoming MLLP-framed HL7 messages.

### 6.2 Receive behavior

1. Bind to `0.0.0.0:port` (or `--bind-address` to restrict)
2. Accept TCP connections
3. Read MLLP-framed message: expect `0x0B`, read until `0x1C 0x0D`
4. Strip framing
5. Parse and display the received message
6. Optionally send ACK response (see 6.3)
7. Wait for next message (persistent listener) or exit after first (`--once`)

### 6.3 ACK generation

When `--ack` is specified, automatically generate and send an ACK response:

- Build MSH segment mirroring the received message:
  - Swap MSH-3/4 (sending) with MSH-5/6 (receiving)
  - Copy MSH-10 (Message Control ID)
  - Set MSH-9 to `ACK`
- Build MSA segment:
  - MSA-1 = `AA` (Application Accept)
  - MSA-2 = received MSH-10 (Message Control ID)
- Wrap in MLLP frame and send back on same connection

Option `--nak` to send NAK (`AE`) instead (for testing error handling).

### 6.4 Options

| Flag | Description |
|------|-------------|
| `--listen PORT` | Port to listen on |
| `--bind-address ADDR` | Bind address (default: 0.0.0.0) |
| `--ack` | Auto-send ACK for each received message |
| `--nak` | Auto-send NAK instead of ACK |
| `--once` | Exit after receiving one message |
| `--log-dir DIR` | Save each received message to a timestamped `.hl7` file |
| `--listen-timeout N` | Idle timeout in seconds (0 = no timeout) |

### 6.5 Interactive listen

- Press `l` in interactive mode
- Prompt for port number
- Status bar shows "Listening on :port..."
- When a message arrives: parse and display it (replaces current view)
- ACK/NAK toggle available via `a` while listening
- Press `l` again or `Esc` to stop listening
- Message history: `[` / `]` to navigate between received messages within the session

---

## 7. Message Log (listen mode)

When `--log-dir` is specified:

- Each received message saved as `YYYYMMDD-HHMMSS-MSG_CTRL_ID.hl7`
- Raw message content (post MLLP-strip, pre-normalization)
- File encoding matches the received bytes
- If directory doesn't exist, create it
- Log file path shown in status after each save

---

## 8. CLI Synopsis

```
hl7view [OPTIONS] [FILE...]

Input:
  FILE...                      One or more HL7 files to parse
  --clipboard                  Read from X clipboard (xclip -o)
  (stdin)                      Read from pipe when no FILE given

Display:
  -i, --interactive            Force interactive TUI mode
  -v, --verbose                Expand components in non-interactive output
  -e, --empty                  Include empty fields
  -f, --field SEG-N            Extract single field value (e.g., PID-3)
      --raw                    Show raw segment lines
      --json                   Output as JSON
      --no-color               Disable ANSI colors

Parsing:
      --version 2.3|2.5        Force HL7 version
      --profile FILE           Load integration profile JSON

Anonymization:
      --anon                   Anonymize patient data in output
      --anon-non-ascii         Use Estonian non-ASCII name pool

Search:
      --search TERM            Filter to matching fields

MLLP Client:
      --send HOST:PORT         Send message to MLLP endpoint
      --send-timeout N         ACK timeout in seconds (default: 10)
      --send-no-wait           Don't wait for ACK

MLLP Server:
      --listen PORT            Listen for incoming MLLP messages
      --bind-address ADDR      Bind address (default: 0.0.0.0)
      --ack                    Auto-send ACK response
      --nak                    Auto-send NAK response
      --once                   Exit after one message
      --log-dir DIR            Save received messages to directory
      --listen-timeout N       Idle timeout seconds (0 = none)

  -h, --help                   Show help
```

---

## 9. Capabilities Unique to Terminal

Summary of features not available in the web viewer:

| Feature | Why terminal enables it |
|---------|----------------------|
| MLLP send | Raw TCP sockets available |
| MLLP listen/receive | Can bind server sockets |
| ACK/NAK generation | Natural complement to listen |
| Stdin/pipe input | Unix composability |
| Multiple file arguments | Batch processing |
| Clipboard via xclip | Direct system integration |
| JSON output | Structured output for toolchains |
| Single-field extraction | Scripting with `$(hl7view -f PID-3 file.hl7)` |
| Message logging | Filesystem write access |
| File directory watching | Could be added (inotify) |
