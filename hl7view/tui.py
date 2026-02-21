"""Interactive TUI for HL7 message viewing using Textual."""

import configparser
import os
import subprocess

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import DirectoryTree, Footer, Header, Input, Static, Tree
from textual.widget import Widget
from textual import work
from rich.table import Table
from rich.text import Text

from .definitions import (
    DATA_TYPES, get_seg_def, get_field_def, resolve_version,
    MSH18_TO_ENCODING, HL7_DEFS,
)
from .mllp import mllp_send, reconstruct_message
from .parser import ParsedMessage, parse_hl7, reparse_field, rebuild_raw_line
from .anonymize import anonymize_message, transliterate
from .cli import read_file, read_clipboard
from .encoding import detect_encoding
from .profile import get_profile_segment, get_profile_field, get_profile_component

# Catppuccin colors matching the web viewer
ROSE = "#f38ba8"
GREEN = "#a6e3a1"
ORANGE = "#fab387"
BLUE = "#89b4fa"
SAPPHIRE = "#74c7ec"
YELLOW = "#f9e2af"
TEAL = "#94e2d5"
DIM = "#585b70"
SURFACE = "#313244"
BASE = "#1e1e2e"


def _resolve_obx5_type(fields):
    """Get OBX-5 data type from OBX-2 value."""
    for f in fields:
        if f.field_num == 2 and f.value:
            return f.value
    return None


def _field_data_type(seg_name, field, field_def, obx5_type):
    """Determine effective data type for a field."""
    if not field_def:
        return ""
    dt = field_def["dt"]
    if dt == "*" and seg_name == "OBX" and field.field_num == 5 and obx5_type:
        return obx5_type
    return dt


def load_tls_config(host, port):
    """Load TLS config for host:port from ~/.config/hl7view/tls.conf.

    Returns a tls_config dict or None if no config found.
    """
    conf_path = os.path.expanduser("~/.config/hl7view/tls.conf")
    if not os.path.isfile(conf_path):
        return None
    cp = configparser.ConfigParser()
    cp.read(conf_path)
    section = f"{host}:{port}"
    if section not in cp:
        return None
    s = cp[section]
    config = {}
    if s.get("ca_cert"):
        config["ca_cert"] = s["ca_cert"]
    if s.get("client_cert"):
        config["client_cert"] = s["client_cert"]
    if s.get("client_key"):
        config["client_key"] = s["client_key"]
    if s.getboolean("insecure", fallback=False):
        config["insecure"] = True
    if s.getboolean("tls", fallback=False) and not config:
        # tls=true with no other options — use system CA
        return {}
    return config if config else None


class HL7DirectoryTree(DirectoryTree):
    """DirectoryTree filtered to show only directories and .hl7 files."""

    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() or p.suffix.lower() == '.hl7']


class ProfileDirectoryTree(DirectoryTree):
    """DirectoryTree filtered to show only directories and .json files."""

    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() or p.suffix.lower() == '.json']


class HL7ViewerApp(App):
    """Interactive HL7 message viewer TUI."""

    TITLE = "HL7 Viewer"
    CSS = """
    Screen {
        background: #1e1e2e;
    }
    #msg-header {
        dock: top;
        height: 1;
        background: #313244;
        color: #cdd6f4;
        padding: 0 1;
    }
    #main-split {
        height: 1fr;
    }
    #field-tree {
        width: 60%;
        background: #1e1e2e;
        scrollbar-size: 1 1;
    }
    #field-tree > .tree--guides {
        color: transparent;
    }
    #detail-panel {
        width: 40%;
        background: #181825;
        border-left: solid #313244;
        padding: 0 1;
        scrollbar-size: 1 1;
    }
    #detail-title {
        color: #cdd6f4;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #spec-section {
        padding: 0 0 1 0;
    }
    #comp-section {
        padding: 0 0 1 0;
    }
    #rep-section {
        padding: 0 0 1 0;
    }
    #search-bar {
        dock: bottom;
        display: none;
        background: #313244;
        color: #cdd6f4;
    }
    #search-bar.visible {
        display: block;
    }
    #file-tree {
        display: none;
        height: 1fr;
        background: #1e1e2e;
    }
    #file-tree.visible {
        display: block;
    }
    #profile-tree {
        display: none;
        height: 1fr;
        background: #1e1e2e;
    }
    #profile-tree.visible {
        display: block;
    }
    #raw-panel {
        display: none;
        height: 1fr;
        background: #1e1e2e;
        padding: 0 1;
        scrollbar-size: 1 1;
    }
    #raw-panel.visible {
        display: block;
    }
    #main-split.hidden {
        display: none;
    }
    #edit-bar {
        dock: bottom;
        display: none;
        background: #313244;
        color: #cdd6f4;
    }
    #edit-bar.visible {
        display: block;
    }
    #send-bar {
        dock: bottom;
        display: none;
        background: #313244;
        color: #cdd6f4;
    }
    #send-bar.visible {
        display: block;
    }
    #send-split {
        display: none;
        height: 1fr;
    }
    #send-split.visible {
        display: block;
    }
    #send-sent {
        width: 50%;
        background: #1e1e2e;
        padding: 0 1;
        scrollbar-size: 1 1;
    }
    #send-response {
        width: 50%;
        background: #181825;
        border-left: solid #313244;
        padding: 0 1;
        scrollbar-size: 1 1;
    }
    Footer {
        background: #313244;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("v", "cycle_version", "Version"),
        Binding("c", "copy_field", "Copy"),
        Binding("e", "toggle_empty", "+Empty"),
        Binding("o", "open_file", "Open"),
        Binding("r", "toggle_raw", "Raw"),
        Binding("s", "send", "Send"),
        Binding("a", "toggle_anon", "Anon"),
        Binding("n", "toggle_non_ascii", "A/Est"),
        Binding("t", "toggle_transliterate", "A\u2192a"),
        Binding("i", "load_profile", "Profile"),
        Binding("b", "go_back", "Back"),
        Binding("f", "go_forward", "Forward"),
        Binding("l", "load_response", show=False),
        Binding("p", "paste_clipboard", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("escape", "clear_search", "Clear", show=False),
    ]

    def __init__(self, parsed: ParsedMessage, version: str = None,
                 filename: str = None, enc_info: dict = None,
                 extra_messages: list = None, profile: dict = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.original_parsed = parsed
        self.parsed = parsed
        self.filename = filename or ""
        self.enc_info = enc_info or {}
        self.show_empty = False
        self.search_query = ""
        self._profile = profile
        # Version cycling: auto (resolved), 2.3, 2.5
        self._version_override = version  # None = auto
        self._version_cycle = ["auto", "2.3", "2.5"]
        self._version_idx = 0
        if version == "2.3":
            self._version_idx = 1
        elif version == "2.5":
            self._version_idx = 2
        self._current_node_data = None
        # Anonymization state
        self._anon_active = False
        self._anon_non_ascii = False  # False=ASCII pool, True=Estonian
        self._anon_parsed = None      # cached anonymized copy
        # Transliteration state
        self._transliterate_active = False
        # Raw view state
        self._raw_view_active = False
        # Edit state
        self._modified = False
        self._editing_field_data = None
        # Send state
        self._last_send_target = "localhost:6001"
        self._send_view_active = False
        self._send_result = None
        # History state — seed with all files from CLI args
        self._history = [(parsed, filename or "", enc_info or {})]
        if extra_messages:
            for ep, ef, ee in extra_messages:
                self._history.append((ep, ef, ee))
        self._history_idx = 0
        self._restoring_history = False
        self._last_file_dir = os.getcwd()
        # Profile browser: default to profiles/ subdir if it exists
        profiles_dir = os.path.join(os.getcwd(), 'profiles')
        self._last_profile_dir = profiles_dir if os.path.isdir(profiles_dir) else os.getcwd()

    @property
    def effective_version(self):
        if self._version_cycle[self._version_idx] == "auto":
            return resolve_version(self.parsed.version)
        return self._version_cycle[self._version_idx]

    def compose(self) -> ComposeResult:
        yield Static(id="msg-header")
        with Horizontal(id="main-split"):
            yield Tree("HL7", id="field-tree")
            with ScrollableContainer(id="detail-panel"):
                yield Static(id="detail-title")
                yield Static(id="spec-section")
                yield Static(id="comp-section")
                yield Static(id="rep-section")
        with ScrollableContainer(id="raw-panel"):
            yield Static(id="raw-content")
        with Horizontal(id="send-split"):
            with ScrollableContainer(id="send-sent"):
                yield Static(id="send-sent-content")
            with ScrollableContainer(id="send-response"):
                yield Static(id="send-response-content")
        yield HL7DirectoryTree(os.getcwd(), id="file-tree")
        yield ProfileDirectoryTree(self._last_profile_dir, id="profile-tree")
        yield Input(placeholder="Search fields... (Esc to close)", id="search-bar")
        yield Input(placeholder="Edit field value (Esc to cancel)", id="edit-bar")
        yield Input(placeholder="Send via MLLP \u2014 host:port [--tls|--tls-insecure] (Esc to cancel)", id="send-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._update_header()
        self._build_tree()
        tree = self.query_one("#field-tree", Tree)
        tree.show_root = False
        tree.guide_depth = 0
        tree.focus()

    def _tx(self, text):
        """Apply transliteration if active."""
        if self._transliterate_active:
            return transliterate(text)
        return text

    def _load_message(self, parsed, filename, enc_info):
        """Central reload: set new message, reset all state, rebuild UI."""
        if not self._restoring_history:
            # Trim any forward entries after current position
            self._history = self._history[:self._history_idx + 1]
            # Push the new message
            self._history.append((parsed, filename, enc_info))
            self._history_idx = len(self._history) - 1
        self.original_parsed = parsed
        self.parsed = parsed
        self.filename = filename
        self.enc_info = enc_info
        # Reset edit state
        self._modified = False
        self._editing_field_data = None
        # Reset anon/translit
        self._anon_active = False
        self._anon_non_ascii = False
        self._anon_parsed = None
        self._transliterate_active = False
        self._raw_view_active = False
        self._send_view_active = False
        self._send_result = None
        # Hide overlays, restore main view
        self.query_one("#raw-panel").remove_class("visible")
        self.query_one("#send-split").remove_class("visible")
        self.query_one("#file-tree").remove_class("visible")
        self.query_one("#main-split").remove_class("hidden")
        # Reset search
        self.search_query = ""
        search_bar = self.query_one("#search-bar", Input)
        search_bar.value = ""
        search_bar.remove_class("visible")
        # Reset detail
        self._current_node_data = None
        self.query_one("#detail-title", Static).update("")
        self.query_one("#spec-section", Static).update("")
        self.query_one("#comp-section", Static).update("")
        self.query_one("#rep-section", Static).update("")
        # Rebuild
        self._update_header()
        self._build_tree()

    def _open_file_path(self, path):
        """Read and load a file by path."""
        path = path.strip()
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            self.notify(f"File not found: {path}", severity="error", timeout=3)
            return
        try:
            text, enc_info = read_file(path)
        except (OSError, IOError) as e:
            self.notify(f"Error: {e}", severity="error", timeout=3)
            return
        parsed = parse_hl7(text)
        if not parsed:
            self.notify("No HL7 segments found", severity="error", timeout=3)
            return
        self._last_file_dir = os.path.dirname(os.path.abspath(path))
        self._load_message(parsed, os.path.basename(path), enc_info)
        self.notify(f"Loaded {os.path.basename(path)}", timeout=2)

    def _update_header(self) -> None:
        msg_type = self.parsed.message_type or "???"
        ver_raw = self.parsed.version or "?"
        ver_eff = self.effective_version
        ver_mode = self._version_cycle[self._version_idx]
        if ver_mode == "auto":
            ver_display = f"v{ver_raw} (auto\u2192{ver_eff})"
        else:
            ver_display = f"v{ver_eff} (forced)"
        seg_count = len(self.parsed.segments)
        enc = self.enc_info.get("encoding", "")
        parts = [msg_type, ver_display, f"{seg_count} segs"]
        if self.filename:
            parts.append(self.filename)
        if enc:
            parts.append(enc)
        charset = self.parsed.declared_charset
        if charset:
            mapped = MSH18_TO_ENCODING.get(charset, charset)
            parts.append(f"MSH-18:{charset}")
            if enc and mapped and enc != mapped and enc != "ASCII":
                parts.append("[MISMATCH]")
        if self._anon_active:
            pool_label = "EST" if self._anon_non_ascii else "ASCII"
            parts.append(f"[ANON:{pool_label}]")
        if self._raw_view_active:
            parts.append("[RAW]")
        if self._transliterate_active:
            parts.append("[A\u2192a]")
        if self._profile:
            parts.append(f"[Profile:{self._profile['name']}]")
        if self._modified:
            parts.append("[MODIFIED]")
        if self.show_empty:
            parts.append("[+empty]")
        if self.search_query:
            parts.append(f'/{self.search_query}')
        if len(self._history) > 1:
            parts.append(f"[{self._history_idx + 1}/{len(self._history)}]")
        header_widget = self.query_one("#msg-header", Static)
        header_widget.update(" \u2502 ".join(parts))

    def _build_tree(self) -> None:
        tree = self.query_one("#field-tree", Tree)
        tree.clear()
        version = self.effective_version
        query = self.search_query.lower()

        for seg in self.parsed.segments:
            seg_def = get_seg_def(seg.name, version)
            seg_desc = seg_def["name"] if seg_def else ""
            p_seg = get_profile_segment(self._profile, seg.name)
            if not seg_desc and p_seg:
                seg_desc = p_seg.get("description", "")
            rep_label = f"[{seg.rep_index}]" if seg.rep_index > 1 else ""

            obx5_type = None
            if seg.name == "OBX":
                obx5_type = _resolve_obx5_type(seg.fields)

            # Collect field nodes (for search filtering)
            field_items = []
            for fld in seg.fields:
                fld_def = get_field_def(seg.name, fld.field_num, version)
                dt = _field_data_type(seg.name, fld, fld_def, obx5_type)
                fname = fld_def["name"] if fld_def else ""

                if not fld.value and not fld.raw_value and not self.show_empty:
                    continue

                # Search filter
                if query:
                    searchable = f"{fld.address} {fname} {dt} {fld.value}".lower()
                    if query not in searchable:
                        continue

                field_items.append((fld, fld_def, dt, fname))

            # Skip empty segments (after filtering)
            if not field_items and query:
                continue

            # Segment node
            seg_label = Text()
            seg_label.append(f"{seg.name}{rep_label}", style=f"bold {ROSE}")
            if seg_desc:
                seg_label.append(f"  {self._tx(seg_desc)}", style=ROSE)
            if p_seg:
                seg_label.append("  Profile", style=TEAL)
            seg_node = tree.root.add(
                seg_label,
                data={"type": "segment", "segment": seg, "seg_def": seg_def},
                expand=True,
            )

            for fld, fld_def, dt, fname in field_items:
                # Profile overlay for field name
                p_fld = get_profile_field(self._profile, seg.name, fld.field_num)
                display_name = fname
                if p_fld and p_fld.get("customName"):
                    display_name = p_fld["customName"]

                # Build field label
                fld_label = Text()
                fld_label.append(f"{fld.address:<12}", style=BLUE)
                if display_name:
                    fld_label.append(f"{self._tx(display_name):<28}", style=GREEN)
                if dt:
                    dt_suffix = ""
                    if fld_def and fld_def["dt"] == "*" and seg.name == "OBX" and fld.field_num == 5:
                        dt_suffix = "\u21902"
                    fld_label.append(f" {dt}{dt_suffix:<5}", style=ORANGE)
                # Value (truncated for display)
                val = self._tx(fld.value or "")
                if len(val) > 40:
                    val = val[:37] + "..."
                if val:
                    fld_label.append(f"  {val}", style="#cdd6f4")
                    # Profile valueMap lookup
                    if p_fld and p_fld.get("valueMap") and fld.value:
                        mapped = p_fld["valueMap"].get(fld.value)
                        if mapped:
                            fld_label.append(f" ({mapped})", style=TEAL)
                elif self.show_empty:
                    fld_label.append("  (empty)", style=DIM)
                # Repetition badge
                if fld.repetitions and len(fld.repetitions) > 1:
                    fld_label.append(f" [{len(fld.repetitions)}x]", style=YELLOW)

                fld_node = seg_node.add(
                    fld_label,
                    data={
                        "type": "field",
                        "segment": seg,
                        "field": fld,
                        "field_def": fld_def,
                        "data_type": dt,
                    },
                )

                # Component children (collapsed by default)
                dt_info = DATA_TYPES.get(dt, {})
                comp_defs = dt_info.get("components", [])
                if fld.components:
                    for comp in fld.components:
                        if not comp.value and not self.show_empty:
                            continue
                        comp_name = ""
                        comp_dt = ""
                        if comp.index <= len(comp_defs):
                            comp_name = comp_defs[comp.index - 1].get("name", "")
                            comp_dt = comp_defs[comp.index - 1].get("dt", "")

                        comp_label = Text()
                        comp_label.append(f".{comp.index:<3}", style=SAPPHIRE)
                        if comp_name:
                            comp_label.append(f"{self._tx(comp_name):<26}", style=GREEN)
                        if comp_dt:
                            comp_label.append(f" {comp_dt:<4}", style=ORANGE)
                        comp_val = self._tx(comp.value) if comp.value else "(empty)"
                        comp_style = "#cdd6f4" if comp.value else DIM
                        comp_label.append(f"  {comp_val}", style=comp_style)

                        fld_node.add_leaf(
                            comp_label,
                            data={
                                "type": "component",
                                "segment": seg,
                                "field": fld,
                                "component": comp,
                                "comp_def": comp_defs[comp.index - 1] if comp.index <= len(comp_defs) else None,
                                "comp_dt": comp_dt,
                            },
                        )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Edit field when Enter is pressed on a leaf tree node."""
        if not isinstance(event.node.data, dict):
            return
        node = event.node
        data = node.data
        if not data:
            return
        self._current_node_data = data
        # Only edit leaf nodes (fields without components, or components)
        if node.children:
            return
        self.action_edit_field()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Update detail panel when a tree node is highlighted."""
        if not isinstance(event.node.data, dict):
            return
        node = event.node
        data = node.data
        if not data:
            return
        self._current_node_data = data
        self._update_detail(data)

    def _update_detail(self, data: dict) -> None:
        title_w = self.query_one("#detail-title", Static)
        spec_w = self.query_one("#spec-section", Static)
        comp_w = self.query_one("#comp-section", Static)
        rep_w = self.query_one("#rep-section", Static)

        node_type = data["type"]

        if node_type == "segment":
            seg = data["segment"]
            seg_def = data.get("seg_def")
            p_seg = get_profile_segment(self._profile, seg.name)
            seg_desc = self._tx(seg_def['name']) if seg_def else 'Unknown'
            if not seg_def and p_seg:
                seg_desc = p_seg.get("description", "Unknown")
            title_w.update(Text(f"{seg.name} \u2014 {seg_desc}", style=f"bold {ROSE}"))
            spec = Table(show_header=False, box=None, padding=(0, 1))
            spec.add_column("Key", style=DIM, width=14)
            spec.add_column("Value")
            spec.add_row("Segment", Text(seg.name, style=f"bold {ROSE}"))
            rep_label = f"[{seg.rep_index}]" if seg.rep_index > 1 else "1"
            spec.add_row("Occurrence", rep_label)
            spec.add_row("Fields", str(len(seg.fields)))
            spec.add_row("HL7 Version", self.effective_version)
            if seg_def:
                spec.add_row("Description", self._tx(seg_def["name"]))
            if p_seg:
                if p_seg.get("description"):
                    spec.add_row("Profile", Text(p_seg["description"], style=TEAL))
                if p_seg.get("custom"):
                    spec.add_row("Custom", Text("Yes (Z-segment)", style=TEAL))
            spec_w.update(spec)
            comp_w.update("")
            # Show raw segment line
            raw_text = Text()
            raw_text.append("Raw segment:\n", style=f"bold {DIM}")
            raw_line = self._tx(seg.raw_line)
            if len(raw_line) > 500:
                raw_line = raw_line[:500] + "..."
            raw_text.append(raw_line, style=DIM)
            rep_w.update(raw_text)
            return

        if node_type == "field":
            seg = data["segment"]
            fld = data["field"]
            fld_def = data.get("field_def")
            dt = data.get("data_type", "")
            p_fld = get_profile_field(self._profile, seg.name, fld.field_num)

            fname = self._tx(fld_def["name"]) if fld_def else "Unknown"
            display_name = fname
            if p_fld and p_fld.get("customName"):
                display_name = p_fld["customName"]
            title_w.update(Text(f"{fld.address} \u2014 {display_name}", style=f"bold {GREEN}"))

            # Specification table
            spec = Table(show_header=False, box=None, padding=(0, 1))
            spec.add_column("Key", style=DIM, width=14)
            spec.add_column("Value")
            spec.add_row("Segment", Text(seg.name, style=ROSE))
            spec.add_row("Field", Text(fld.address, style=BLUE))
            if display_name:
                spec.add_row("Name", display_name)
            if p_fld and p_fld.get("customName") and fname and fname != "Unknown":
                spec.add_row("Standard Name", Text(fname, style=DIM))
            if dt:
                dt_name = DATA_TYPES.get(dt, {}).get("name", "")
                dt_text = Text()
                dt_text.append(dt, style=ORANGE)
                if dt_name:
                    dt_text.append(f"  ({self._tx(dt_name)})", style=DIM)
                # If OBX-5 resolved from OBX-2
                if fld_def and fld_def["dt"] == "*" and seg.name == "OBX" and fld.field_num == 5:
                    dt_text.append("  \u2190OBX-2", style=YELLOW)
                spec.add_row("Data Type", dt_text)
            if fld_def:
                opt_map = {"R": "Required", "O": "Optional", "C": "Conditional", "B": "Backwards compat"}
                spec.add_row("Optionality", opt_map.get(fld_def["opt"], fld_def["opt"]))
                spec.add_row("Repeatable", "Yes" if fld_def["rep"] else "No")
                if fld_def["len"]:
                    spec.add_row("Max Length", str(fld_def["len"]))
            # Full value
            val = self._tx(fld.raw_value) if fld.raw_value else "(empty)"
            val_text = Text(val, style="#cdd6f4" if fld.raw_value else DIM)
            # ValueMap lookup
            if p_fld and p_fld.get("valueMap") and fld.value:
                mapped = p_fld["valueMap"].get(fld.value)
                if mapped:
                    val_text.append(f"  ({mapped})", style=TEAL)
            spec.add_row("Value", val_text)
            spec.add_row("HL7 Version", self.effective_version)
            # Profile description and notes
            if p_fld:
                if p_fld.get("description"):
                    spec.add_row("Profile Desc", Text(p_fld["description"], style=TEAL))
                if p_fld.get("notes"):
                    spec.add_row("Notes", Text(p_fld["notes"], style=TEAL))
            # Profile valueMap table
            if p_fld and p_fld.get("valueMap"):
                vm = p_fld["valueMap"]
                vm_text = Text()
                for code, meaning in vm.items():
                    marker = "\u25b6 " if code == fld.value else "  "
                    vm_text.append(marker)
                    vm_text.append(f"{code:<6}", style=YELLOW)
                    vm_text.append(f"{meaning}\n", style="#cdd6f4")
                spec.add_row("Value Map", vm_text)
            spec_w.update(spec)

            # Components table
            dt_info = DATA_TYPES.get(dt, {})
            comp_defs = dt_info.get("components", [])
            if comp_defs:
                ctable = Table(box=None, padding=(0, 1))
                ctable.add_column("#", style=SAPPHIRE, width=3)
                ctable.add_column("Name", style=GREEN, width=26)
                ctable.add_column("Type", style=ORANGE, width=5)
                ctable.add_column("Value")

                for i, cd in enumerate(comp_defs):
                    idx = i + 1
                    cval = ""
                    # Find component value
                    for c in fld.components:
                        if c.index == idx:
                            cval = c.value
                            break
                    disp_val = self._tx(cval) if cval else ""
                    val_text = Text(disp_val, style="#cdd6f4") if cval else Text("", style=DIM)
                    ctable.add_row(str(idx), self._tx(cd.get("name", "")), cd.get("dt", ""), val_text)
                comp_w.update(ctable)
            elif fld.components:
                # Components exist but no type definitions
                ctable = Table(box=None, padding=(0, 1))
                ctable.add_column("#", style=SAPPHIRE, width=3)
                ctable.add_column("Value")
                for c in fld.components:
                    ctable.add_row(str(c.index), self._tx(c.value) if c.value else "")
                comp_w.update(ctable)
            else:
                comp_w.update("")

            # Repetitions
            if fld.repetitions and len(fld.repetitions) > 1:
                rtable = Table(title="Repetitions", box=None, padding=(0, 1))
                rtable.add_column("~#", style=YELLOW, width=4)
                rtable.add_column("Value")
                for rep in fld.repetitions:
                    rtable.add_row(str(rep.index), self._tx(rep.value) if rep.value else "")
                rep_w.update(rtable)
            else:
                rep_w.update("")
            return

        if node_type == "component":
            seg = data["segment"]
            fld = data["field"]
            comp = data["component"]
            comp_def = data.get("comp_def")
            comp_dt = data.get("comp_dt", "")

            comp_name = self._tx(comp_def["name"]) if comp_def else "Unknown"
            comp_addr = f"{fld.address}.{comp.index}"
            title_w.update(Text(f"{comp_addr} \u2014 {comp_name}", style=f"bold {SAPPHIRE}"))

            spec = Table(show_header=False, box=None, padding=(0, 1))
            spec.add_column("Key", style=DIM, width=14)
            spec.add_column("Value")
            spec.add_row("Segment", Text(seg.name, style=ROSE))
            spec.add_row("Field", Text(fld.address, style=BLUE))
            spec.add_row("Component", Text(comp_addr, style=SAPPHIRE))
            if comp_name:
                spec.add_row("Name", comp_name)
            if comp_dt:
                dt_name = DATA_TYPES.get(comp_dt, {}).get("name", "")
                dt_text = Text()
                dt_text.append(comp_dt, style=ORANGE)
                if dt_name:
                    dt_text.append(f"  ({self._tx(dt_name)})", style=DIM)
                spec.add_row("Data Type", dt_text)
            val = self._tx(comp.value) if comp.value else "(empty)"
            spec.add_row("Value", Text(val, style="#cdd6f4" if comp.value else DIM))
            # Profile component description
            p_comp = get_profile_component(self._profile, seg.name, fld.field_num, comp.index)
            if p_comp and p_comp.get("description"):
                spec.add_row("Profile Desc", Text(p_comp["description"], style=TEAL))
            spec_w.update(spec)

            # Subcomponents
            if comp.subcomponents and len(comp.subcomponents) > 1:
                stable = Table(box=None, padding=(0, 1))
                stable.add_column("&", style=DIM, width=3)
                stable.add_column("Value")
                for si, sv in enumerate(comp.subcomponents, 1):
                    stable.add_row(str(si), self._tx(sv) if sv else "")
                comp_w.update(stable)
            else:
                comp_w.update("")
            rep_w.update("")

    # ---- Key binding actions ----

    def action_search(self) -> None:
        search_bar = self.query_one("#search-bar", Input)
        search_bar.add_class("visible")
        search_bar.focus()

    def action_clear_search(self) -> None:
        # Close edit-bar if visible
        edit_bar = self.query_one("#edit-bar", Input)
        if edit_bar.has_class("visible"):
            edit_bar.remove_class("visible")
            edit_bar.value = ""
            self._editing_field_data = None
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            return
        # Close send-bar if visible
        send_bar = self.query_one("#send-bar", Input)
        if send_bar.has_class("visible"):
            send_bar.remove_class("visible")
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            return
        # Close send split view if visible
        if self._send_view_active:
            self._close_send_view()
            return
        # Close file browser if visible
        file_tree = self.query_one("#file-tree", HL7DirectoryTree)
        if file_tree.has_class("visible"):
            file_tree.remove_class("visible")
            if self._raw_view_active:
                self.query_one("#raw-panel").add_class("visible")
            elif self._send_view_active:
                self.query_one("#send-split").add_class("visible")
            else:
                self.query_one("#main-split").remove_class("hidden")
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            return
        # Close profile browser if visible
        profile_tree = self.query_one("#profile-tree", ProfileDirectoryTree)
        if profile_tree.has_class("visible"):
            profile_tree.remove_class("visible")
            if self._raw_view_active:
                self.query_one("#raw-panel").add_class("visible")
            elif self._send_view_active:
                self.query_one("#send-split").add_class("visible")
            else:
                self.query_one("#main-split").remove_class("hidden")
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            return
        # Close search-bar if visible
        search_bar = self.query_one("#search-bar", Input)
        if search_bar.has_class("visible"):
            search_bar.remove_class("visible")
            search_bar.value = ""
            self.search_query = ""
            self._update_header()
            self._build_tree()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-bar":
            self.search_query = event.value.strip()
            self._update_header()
            self._build_tree()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar":
            # Close search bar, keep filter active
            search_bar = self.query_one("#search-bar", Input)
            search_bar.remove_class("visible")
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
        elif event.input.id == "edit-bar":
            new_value = event.value
            edit_bar = self.query_one("#edit-bar", Input)
            edit_bar.remove_class("visible")
            edit_bar.value = ""
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            if self._editing_field_data is not None:
                self._apply_edit(new_value)
                self._editing_field_data = None
        elif event.input.id == "send-bar":
            target = event.value.strip()
            send_bar = self.query_one("#send-bar", Input)
            send_bar.remove_class("visible")
            tree = self.query_one("#field-tree", Tree)
            tree.focus()
            if target:
                self._last_send_target = target
                self._show_send_pending(target)
                self._do_mllp_send(target)

    def action_cycle_version(self) -> None:
        self._version_idx = (self._version_idx + 1) % len(self._version_cycle)
        self._update_header()
        self._build_tree()

    def action_toggle_empty(self) -> None:
        self.show_empty = not self.show_empty
        self._update_header()
        self._build_tree()

    def action_open_file(self) -> None:
        """Toggle .hl7 file browser."""
        file_tree = self.query_one("#file-tree", HL7DirectoryTree)
        if file_tree.has_class("visible"):
            # Close browser, restore previous view
            file_tree.remove_class("visible")
            if self._raw_view_active:
                self.query_one("#raw-panel").add_class("visible")
            elif self._send_view_active:
                self.query_one("#send-split").add_class("visible")
            else:
                self.query_one("#main-split").remove_class("hidden")
            self.query_one("#field-tree", Tree).focus()
            return
        # Open browser
        file_tree.path = self._last_file_dir
        self.query_one("#main-split").add_class("hidden")
        self.query_one("#raw-panel").remove_class("visible")
        self.query_one("#send-split").remove_class("visible")
        file_tree.add_class("visible")
        file_tree.focus()

    def action_load_profile(self) -> None:
        """Toggle profile browser, or unload current profile."""
        profile_tree = self.query_one("#profile-tree", ProfileDirectoryTree)
        if profile_tree.has_class("visible"):
            # Close browser, restore previous view
            profile_tree.remove_class("visible")
            if self._raw_view_active:
                self.query_one("#raw-panel").add_class("visible")
            elif self._send_view_active:
                self.query_one("#send-split").add_class("visible")
            else:
                self.query_one("#main-split").remove_class("hidden")
            self.query_one("#field-tree", Tree).focus()
            return
        if self._profile:
            # Unload current profile
            self._profile = None
            self._update_header()
            self._build_tree()
            if self._current_node_data:
                self._update_detail(self._current_node_data)
            self.notify("Profile unloaded", timeout=2)
            return
        # Open profile browser
        profile_tree.path = self._last_profile_dir
        self.query_one("#main-split").add_class("hidden")
        self.query_one("#raw-panel").remove_class("visible")
        self.query_one("#send-split").remove_class("visible")
        profile_tree.add_class("visible")
        profile_tree.focus()

    def _load_profile_path(self, path):
        """Load a profile JSON file by path."""
        from .profile import load_profile
        try:
            profile = load_profile(path)
        except (OSError, IOError, ValueError) as e:
            self.notify(f"Error: {e}", severity="error", timeout=3)
            return
        except Exception as e:
            self.notify(f"Invalid JSON: {e}", severity="error", timeout=3)
            return
        self._profile = profile
        self._last_profile_dir = os.path.dirname(os.path.abspath(path))
        self._update_header()
        self._build_tree()
        if self._current_node_data:
            self._update_detail(self._current_node_data)
        self.notify(f"Profile: {profile['name']}", timeout=2)

    def action_paste_clipboard(self) -> None:
        """Read HL7 from clipboard and load it."""
        try:
            result = subprocess.run(
                ['xclip', '-o', '-selection', 'clipboard'],
                capture_output=True, timeout=5
            )
            if result.returncode != 0:
                self.notify("xclip failed", severity="error", timeout=3)
                return
            raw = result.stdout
            if not raw.strip():
                self.notify("Clipboard empty", severity="warning", timeout=2)
                return
            enc = detect_encoding(raw)
            text = raw.decode(enc['decoder_label'])
            parsed = parse_hl7(text)
            if not parsed:
                self.notify("No HL7 segments in clipboard", severity="error", timeout=3)
                return
            self._load_message(parsed, "(clipboard)", enc)
            self.notify("Loaded from clipboard", timeout=2)
        except FileNotFoundError:
            self.notify("xclip not found", severity="error", timeout=3)
        except subprocess.TimeoutExpired:
            self.notify("xclip timed out", severity="error", timeout=3)

    def action_toggle_anon(self) -> None:
        """Toggle anonymization on/off."""
        if self._anon_active:
            # Restore original
            self._anon_active = False
            self._anon_parsed = None
            self.parsed = self.original_parsed
        else:
            # Anonymize
            self._anon_active = True
            self._anon_parsed = anonymize_message(
                self.original_parsed, use_non_ascii=self._anon_non_ascii
            )
            self.parsed = self._anon_parsed
        self._current_node_data = None
        self._update_header()
        self._refresh_view()
        self._clear_detail()

    def action_toggle_non_ascii(self) -> None:
        """Toggle ASCII/Estonian name pool, re-anonymize if active."""
        self._anon_non_ascii = not self._anon_non_ascii
        if self._anon_active:
            self._anon_parsed = anonymize_message(
                self.original_parsed, use_non_ascii=self._anon_non_ascii
            )
            self.parsed = self._anon_parsed
            self._current_node_data = None
            self._refresh_view()
            self._clear_detail()
        self._update_header()
        pool = "Estonian" if self._anon_non_ascii else "ASCII"
        self.notify(f"Name pool: {pool}", timeout=2)

    def _refresh_view(self):
        """Rebuild whichever view (tree or raw) is currently active."""
        if self._raw_view_active:
            self._build_raw_view()
        else:
            self._build_tree()

    def action_toggle_transliterate(self) -> None:
        """Toggle non-ASCII transliteration in display."""
        self._transliterate_active = not self._transliterate_active
        self._update_header()
        if self._raw_view_active:
            self._build_raw_view()
        else:
            self._build_tree()
            if self._current_node_data:
                self._update_detail(self._current_node_data)

    def action_toggle_raw(self) -> None:
        """Toggle between tree view and raw message view."""
        self._raw_view_active = not self._raw_view_active
        main_split = self.query_one("#main-split")
        raw_panel = self.query_one("#raw-panel")
        if self._raw_view_active:
            main_split.add_class("hidden")
            raw_panel.add_class("visible")
            self._build_raw_view()
        else:
            raw_panel.remove_class("visible")
            main_split.remove_class("hidden")
        self._update_header()

    def _build_raw_text(self, parsed) -> Text:
        """Build highlighted raw message Text from a ParsedMessage."""
        output = Text()
        for seg in parsed.segments:
            raw_line = self._tx(seg.raw_line)
            fields = raw_line.split("|")
            seg_name = fields[0] if fields else ""

            # Segment name
            output.append(seg_name, style=f"bold {ROSE}")

            if seg_name == "MSH":
                # MSH-1 is the | separator itself
                output.append("|", style=DIM)
                # MSH-2: encoding characters
                if len(fields) > 1:
                    output.append(fields[1], style=YELLOW)
                # MSH-3 onwards
                for i in range(2, len(fields)):
                    output.append("|", style=DIM)
                    self._append_raw_field(output, fields[i])
            else:
                for i in range(1, len(fields)):
                    output.append("|", style=DIM)
                    self._append_raw_field(output, fields[i])
            output.append("\n")

        return output

    def _build_raw_view(self) -> None:
        """Build the highlighted raw message view."""
        raw_w = self.query_one("#raw-content", Static)
        raw_w.update(self._build_raw_text(self.parsed))

    def _append_raw_field(self, text, value):
        """Append a field value to raw view with component highlighting."""
        if not value:
            return
        # Split on ^ for component highlighting, but keep ~ and & visible
        if "~" in value:
            reps = value.split("~")
            for ri, rep in enumerate(reps):
                if ri > 0:
                    text.append("~", style=TEAL)
                self._append_raw_components(text, rep)
        else:
            self._append_raw_components(text, value)

    def _append_raw_components(self, text, value):
        """Append component-split value with ^ and & highlighting."""
        if "^" not in value:
            text.append(value, style="#cdd6f4")
            return
        parts = value.split("^")
        for ci, comp in enumerate(parts):
            if ci > 0:
                text.append("^", style=DIM)
            if "&" in comp:
                subs = comp.split("&")
                for si, sub in enumerate(subs):
                    if si > 0:
                        text.append("&", style=DIM)
                    text.append(sub, style="#cdd6f4")
            else:
                text.append(comp, style="#cdd6f4")

    def _clear_detail(self):
        """Clear all detail panel widgets."""
        self.query_one("#detail-title", Static).update("")
        self.query_one("#spec-section", Static).update("")
        self.query_one("#comp-section", Static).update("")
        self.query_one("#rep-section", Static).update("")

    def action_copy_field(self) -> None:
        """Copy current field value to clipboard via xclip."""
        if not self._current_node_data:
            self.notify("No field selected", severity="warning", timeout=2)
            return
        data = self._current_node_data
        if data["type"] == "field":
            val = data["field"].raw_value or ""
        elif data["type"] == "component":
            val = data["component"].value or ""
        elif data["type"] == "segment":
            val = data["segment"].raw_line or ""
        else:
            val = ""
        if not val:
            self.notify("Empty value", severity="warning", timeout=2)
            return
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=val.encode(), check=True, timeout=5,
            )
            addr = ""
            if data["type"] == "field":
                addr = data["field"].address
            elif data["type"] == "component":
                addr = f"{data['field'].address}.{data['component'].index}"
            self.notify(f"Copied {addr}", timeout=2)
        except (FileNotFoundError, subprocess.SubprocessError):
            self.notify("xclip not available", severity="error", timeout=2)

    def action_edit_field(self) -> None:
        """Edit the currently highlighted field or component."""
        # Don't intercept Enter when an input bar is focused
        focused = self.focused
        if isinstance(focused, Input):
            return
        if not self._current_node_data:
            self.notify("No field selected", severity="warning", timeout=2)
            return
        data = self._current_node_data
        if data["type"] == "segment":
            self.notify("Select a field to edit", severity="warning", timeout=2)
            return

        self._editing_field_data = data
        edit_bar = self.query_one("#edit-bar", Input)

        if data["type"] == "field":
            fld = data["field"]
            edit_bar.value = fld.raw_value or ""
            edit_bar.placeholder = f"{fld.address} (Esc to cancel)"
        elif data["type"] == "component":
            comp = data["component"]
            fld = data["field"]
            comp_addr = f"{fld.address}.{comp.index}"
            edit_bar.value = comp.value or ""
            edit_bar.placeholder = f"{comp_addr} (Esc to cancel)"

        edit_bar.add_class("visible")
        edit_bar.focus()

    def _apply_edit(self, new_value: str) -> None:
        """Apply an edit from the edit bar to the field/component."""
        data = self._editing_field_data
        if not data:
            return

        seg = data["segment"]

        if data["type"] == "field":
            fld = data["field"]
            reparse_field(fld, new_value)
            seg.raw_line = rebuild_raw_line(seg.name, seg.fields)
        elif data["type"] == "component":
            comp = data["component"]
            fld = data["field"]
            comp.value = new_value
            # Rebuild field raw_value from all components
            comp_values = []
            for c in fld.components:
                comp_values.append(c.value)
            new_raw = "^".join(comp_values)
            # If field has repetitions, rebuild with repetitions
            if fld.repetitions:
                # Update first repetition's components
                fld.repetitions[0].value = new_raw
                fld.repetitions[0].components = fld.components
                rep_values = [r.value for r in fld.repetitions]
                new_raw = "~".join(rep_values)
            reparse_field(fld, new_raw)
            seg.raw_line = rebuild_raw_line(seg.name, seg.fields)

        self._modified = True
        self._update_header()
        self._build_tree()
        # Refresh detail panel
        if self._current_node_data:
            self._update_detail(self._current_node_data)

    def action_send(self) -> None:
        """Show send target input bar."""
        send_bar = self.query_one("#send-bar", Input)
        send_bar.value = self._last_send_target
        send_bar.add_class("visible")
        send_bar.focus()

    def _tls_label(self, tls_config):
        """Return display label for TLS mode."""
        if not tls_config:
            return ""
        if tls_config.get("client_cert"):
            return " mTLS"
        return " TLS"

    def _show_send_pending(self, target: str) -> None:
        """Show a 'Sending...' state immediately before the background thread runs."""
        self._send_view_active = True
        _, host, port, tls_config = self._parse_send_input(target)
        tls_label = self._tls_label(tls_config)
        display_target = f"{host}:{port}" if host else target

        # Show send split, hide others
        self.query_one("#main-split").add_class("hidden")
        self.query_one("#raw-panel").remove_class("visible")
        self.query_one("#send-split").add_class("visible")

        # Left pane: sent message
        sent_w = self.query_one("#send-sent-content", Static)
        sent_header = Text()
        sent_header.append("SENT MESSAGE\n", style=f"bold {GREEN}")
        sent_header.append("─" * 40 + "\n", style=DIM)
        sent_header.append_text(self._build_raw_text(self.parsed))
        sent_w.update(sent_header)

        # Right pane: sending indicator
        resp_w = self.query_one("#send-response-content", Static)
        pending = Text()
        pending.append(
            f"Sending to {display_target} ({tls_label.strip() or 'plain'})...\n",
            style=f"bold {YELLOW}")
        resp_w.update(pending)

        # Scroll containers to top
        self.query_one("#send-sent").scroll_home(animate=False)
        self.query_one("#send-response").scroll_home(animate=False)

        # Update header
        header_widget = self.query_one("#msg-header", Static)
        msg_type = self.parsed.message_type or "???"
        parts = [f"[SENDING\u2192{display_target}{tls_label}]", msg_type]
        if self.filename:
            parts.append(self.filename)
        header_widget.update(" \u2502 ".join(parts))

    def _parse_send_input(self, target):
        """Parse send bar input into (host_port, tls_config).

        Supports:
          host:port              — plain TCP (may still get TLS from config file)
          host:port --tls        — TLS with system CA
          host:port --tls-insecure — TLS without cert verification
        """
        parts = target.split()
        host_port = parts[0]
        flags = set(parts[1:])

        tls_insecure = "--tls-insecure" in flags
        tls_flag = "--tls" in flags or tls_insecure

        # Parse host:port
        if ':' not in host_port:
            return host_port, None, None, None
        hp_parts = host_port.rsplit(':', 1)
        try:
            port = int(hp_parts[1])
        except ValueError:
            return host_port, None, None, None
        host = hp_parts[0]

        # Build TLS config: explicit flags take priority, then config file
        tls_config = None
        if tls_insecure:
            tls_config = {"insecure": True}
        elif tls_flag:
            tls_config = {}  # system CA
        else:
            # Check config file
            tls_config = load_tls_config(host, port)

        return host_port, host, port, tls_config

    @work(thread=True)
    def _do_mllp_send(self, target: str) -> None:
        """Send message via MLLP in a background thread."""
        host_port, host, port, tls_config = self._parse_send_input(target)

        if host is None:
            self.call_from_thread(self._show_send_result, {
                'error': f'Invalid target "{host_port}" — expected host:port',
            })
            return

        display_target = f"{host}:{port}"
        wire_text = reconstruct_message(self.parsed)
        try:
            response_text, elapsed_ms = mllp_send(
                host, port, wire_text, tls_config=tls_config)
        except (ConnectionError, TimeoutError, OSError) as e:
            self.call_from_thread(self._show_send_result, {
                'error': str(e),
                'target': display_target,
                'tls_config': tls_config,
            })
            return

        result = {
            'target': display_target,
            'elapsed_ms': elapsed_ms,
            'response_raw': response_text,
            'tls_config': tls_config,
        }
        if response_text:
            resp_parsed = parse_hl7(response_text)
            result['response_parsed'] = resp_parsed
        else:
            result['response_parsed'] = None

        self.call_from_thread(self._show_send_result, result)

    def _show_send_result(self, result: dict) -> None:
        """Display the send result in a split view."""
        self._send_result = result
        self._send_view_active = True

        # Hide other views, show send split
        self.query_one("#main-split").add_class("hidden")
        self.query_one("#raw-panel").remove_class("visible")
        self.query_one("#send-split").add_class("visible")

        # Scroll containers to top so new result is visible
        self.query_one("#send-sent").scroll_home(animate=False)
        self.query_one("#send-response").scroll_home(animate=False)

        # Left pane: sent message
        sent_w = self.query_one("#send-sent-content", Static)
        sent_header = Text()
        sent_header.append("SENT MESSAGE\n", style=f"bold {GREEN}")
        sent_header.append("─" * 40 + "\n", style=DIM)
        sent_text = self._build_raw_text(self.parsed)
        sent_header.append_text(sent_text)
        sent_w.update(sent_header)

        # Right pane: response or error
        resp_w = self.query_one("#send-response-content", Static)
        target = result.get('target', '?')
        error = result.get('error')

        if error:
            resp_output = Text()
            resp_output.append("ERROR\n", style="bold red")
            resp_output.append("─" * 40 + "\n", style=DIM)
            resp_output.append(error, style="red")
            resp_w.update(resp_output)
        else:
            elapsed = result.get('elapsed_ms', 0)
            resp_output = Text()
            resp_output.append(f"RESPONSE from {target} ({elapsed}ms)\n",
                               style=f"bold {GREEN}")
            resp_output.append("─" * 40 + "\n", style=DIM)
            resp_parsed = result.get('response_parsed')
            if resp_parsed:
                resp_output.append_text(self._build_raw_text(resp_parsed))
                resp_output.append("\n")
                resp_output.append("Press l to load response into viewer", style=DIM)
            elif result.get('response_raw'):
                resp_output.append(result['response_raw'], style="#cdd6f4")
            else:
                resp_output.append("(empty response)", style=DIM)
            resp_w.update(resp_output)

        # Update header
        elapsed = result.get('elapsed_ms', 0)
        tls_config = result.get('tls_config')
        if error:
            self._update_header_with_send(target, elapsed, error=True,
                                          tls_config=tls_config)
        else:
            self._update_header_with_send(target, elapsed,
                                          tls_config=tls_config)

    def _update_header_with_send(self, target, elapsed_ms, error=False,
                                tls_config=None):
        """Update header to show send status."""
        tls_label = self._tls_label(tls_config)
        header_widget = self.query_one("#msg-header", Static)
        parts = []
        if error:
            parts.append(f"[SEND FAILED\u2192{target}]")
        else:
            parts.append(f"[SENT\u2192{target}{tls_label} {elapsed_ms}ms]")
        msg_type = self.parsed.message_type or "???"
        parts.append(msg_type)
        if self.filename:
            parts.append(self.filename)
        header_widget.update(" \u2502 ".join(parts))

    def _close_send_view(self) -> None:
        """Close the send split view and restore previous view."""
        self._send_view_active = False
        self._send_result = None
        self.query_one("#send-split").remove_class("visible")
        if self._raw_view_active:
            self.query_one("#raw-panel").add_class("visible")
        else:
            self.query_one("#main-split").remove_class("hidden")
        self._update_header()

    def action_load_response(self) -> None:
        """Load the MLLP response message into the main viewer."""
        if not self._send_view_active or not self._send_result:
            return
        resp_parsed = self._send_result.get('response_parsed')
        if not resp_parsed:
            self.notify("No parsed response to load", severity="warning", timeout=2)
            return
        target = self._send_result.get('target', '?')
        self._load_message(resp_parsed, f"(response from {target})", {})
        self.notify("Loaded response message", timeout=2)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Load selected file from a file browser."""
        path = str(event.path)
        # Determine which tree fired the event
        profile_tree = self.query_one("#profile-tree", ProfileDirectoryTree)
        if profile_tree.has_class("visible"):
            # Profile file selected
            profile_tree.remove_class("visible")
            self.query_one("#main-split").remove_class("hidden")
            self._load_profile_path(path)
            self.query_one("#field-tree", Tree).focus()
            return
        # HL7 file selected
        file_tree = self.query_one("#file-tree", HL7DirectoryTree)
        file_tree.remove_class("visible")
        self.query_one("#main-split").remove_class("hidden")
        self._open_file_path(path)
        self.query_one("#field-tree", Tree).focus()

    def action_go_back(self) -> None:
        """Navigate to the previous message in history."""
        if self._history_idx <= 0:
            self.notify("No previous message", severity="warning", timeout=2)
            return
        self._history_idx -= 1
        self._restore_from_history()

    def action_go_forward(self) -> None:
        """Navigate to the next message in history."""
        if self._history_idx >= len(self._history) - 1:
            self.notify("No next message", severity="warning", timeout=2)
            return
        self._history_idx += 1
        self._restore_from_history()

    def _restore_from_history(self) -> None:
        """Restore a message from history by current index."""
        parsed, filename, enc_info = self._history[self._history_idx]
        self._restoring_history = True
        self._load_message(parsed, filename, enc_info)
        self._restoring_history = False

    def action_cursor_down(self) -> None:
        tree = self.query_one("#field-tree", Tree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        tree = self.query_one("#field-tree", Tree)
        tree.action_cursor_up()
