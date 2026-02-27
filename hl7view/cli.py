"""CLI entry point for hl7view: argparse, input routing, output dispatch."""

import argparse
import json
import os
import subprocess
import sys

from . import __version__
from .encoding import detect_encoding
from .definitions import resolve_version, MSH18_TO_ENCODING
from .formatter import format_diff, format_encoding_header, format_field_value, format_message, format_raw
from .mllp import mllp_send, reconstruct_message
from .parser import parse_hl7
from .profile import load_profile


def read_file(path):
    """Read a file as bytes, detect encoding, decode, return (text, enc_info)."""
    with open(path, 'rb') as f:
        raw = f.read()
    enc = detect_encoding(raw)
    label = enc['decoder_label']
    text = raw.decode(label)
    return text, enc


def read_clipboard():
    """Read HL7 from X clipboard via xclip."""
    try:
        result = subprocess.run(
            ['xclip', '-o', '-selection', 'clipboard'],
            capture_output=True, timeout=5
        )
        if result.returncode != 0:
            print('Error: xclip failed. Is it installed?', file=sys.stderr)
            sys.exit(1)
        raw = result.stdout
        enc = detect_encoding(raw)
        text = raw.decode(enc['decoder_label'])
        return text, enc
    except FileNotFoundError:
        print('Error: xclip not found. Install it: apt install xclip', file=sys.stderr)
        sys.exit(1)


def _process_message(text, enc_info, args, use_color):
    """Parse and output a single HL7 message (non-interactive)."""
    parsed = parse_hl7(text)
    if not parsed:
        print('Error: no HL7 segments found in input', file=sys.stderr)
        return False

    # Anonymize if requested
    if args.anon or args.anon_non_ascii:
        from .anonymize import anonymize_message
        parsed = anonymize_message(parsed, use_non_ascii=args.anon_non_ascii)

    # Send mode: dispatch to MLLP send instead of display
    if args.send:
        return _send_message(parsed, args, use_color)

    version = args.hl7_version if args.hl7_version else resolve_version(parsed.version)

    # Encoding header
    enc_header = format_encoding_header(enc_info, parsed.declared_charset, use_color)
    if enc_header:
        print(enc_header)

    # Output routing
    if args.field:
        val = format_field_value(parsed, args.field, version)
        if val is None:
            print(f'Field {args.field} not found', file=sys.stderr)
            return False
        print(val)
    elif args.raw:
        print(format_raw(parsed), end='')
    else:
        print(format_message(
            parsed,
            version=version,
            verbose=args.verbose,
            show_empty=args.empty,
            no_color=args.no_color,
            profile=args._profile,
        ), end='')

    return True


def _build_tls_config(args):
    """Build tls_config dict from CLI args. Returns None for plain TCP."""
    use_tls = args.tls or args.tls_ca or args.tls_cert or args.tls_insecure
    if not use_tls:
        return None
    if args.tls_cert and not args.tls_key:
        print('Error: --tls-cert requires --tls-key', file=sys.stderr)
        sys.exit(1)
    config = {}
    if args.tls_ca:
        config["ca_cert"] = args.tls_ca
    if args.tls_cert:
        config["client_cert"] = args.tls_cert
    if args.tls_key:
        config["client_key"] = args.tls_key
    if args.tls_insecure:
        config["insecure"] = True
    return config


def _send_message(parsed, args, use_color):
    """Send parsed message via MLLP and display the response."""
    host, port = _parse_host_port(args.send)
    if host is None:
        print(f'Error: invalid send target "{args.send}" — expected host:port',
              file=sys.stderr)
        return False

    tls_config = _build_tls_config(args)
    wire_text = reconstruct_message(parsed)
    wait = not args.send_no_wait

    try:
        response_text, elapsed_ms = mllp_send(
            host, port, wire_text,
            timeout=args.send_timeout,
            wait_for_ack=wait,
            tls_config=tls_config,
        )
    except (ConnectionError, TimeoutError, OSError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return False

    tls_label = ""
    if tls_config:
        tls_label = " mTLS" if tls_config.get("client_cert") else " TLS"

    if not wait:
        print(f'Sent to {host}:{port} ({elapsed_ms}ms,{tls_label} no-wait)')
        return True

    if not response_text:
        print(f'Error: empty response from {host}:{port}', file=sys.stderr)
        return False

    print(f'Response from {host}:{port} ({elapsed_ms}ms{tls_label}):')
    resp_parsed = parse_hl7(response_text)
    if resp_parsed:
        version = args.hl7_version if args.hl7_version else resolve_version(resp_parsed.version)
        print(format_message(
            resp_parsed,
            version=version,
            verbose=args.verbose,
            show_empty=args.empty,
            no_color=args.no_color,
            profile=args._profile,
        ), end='')
        # Check ACK status for exit code
        ack_code = _get_ack_code(resp_parsed)
        return ack_code in (None, 'AA', 'CA')
    else:
        # Raw response if not parseable as HL7
        print(response_text)
        return True


def _parse_host_port(target):
    """Parse 'host:port' string. Returns (host, port) or (None, None)."""
    if ':' not in target:
        return None, None
    parts = target.rsplit(':', 1)
    try:
        port = int(parts[1])
    except ValueError:
        return None, None
    return parts[0], port


def _get_ack_code(parsed):
    """Extract MSA-1 acknowledgment code from a parsed response."""
    for seg in parsed.segments:
        if seg.name == 'MSA':
            for fld in seg.fields:
                if fld.field_num == 1:
                    return fld.value
    return None


def _wants_interactive(args):
    """Determine if we should launch the interactive TUI."""
    # Flags that imply non-interactive output
    if args.no_interactive or args.field or args.raw or args.verbose or args.no_color:
        return False
    # --send / --diff implies non-interactive
    if args.send or args.diff:
        return False
    # --anon flags imply non-interactive
    if args.anon or args.anon_non_ascii:
        return False
    # Must have a TTY on stdout
    if not sys.stdout.isatty():
        return False
    return True


def _launch_tui(text, enc_info, args, filename=None):
    """Parse message and launch the interactive TUI."""
    parsed = parse_hl7(text)
    if not parsed:
        print('Error: no HL7 segments found in input', file=sys.stderr)
        sys.exit(1)

    from .tui import HL7ViewerApp
    app = HL7ViewerApp(
        parsed,
        version=args.hl7_version,
        filename=filename,
        enc_info=enc_info,
        profile=args._profile,
    )
    app.run()


def _launch_tui_with_messages(parsed, enc_info, args, filename=None,
                              extra_messages=None):
    """Launch TUI with first message and additional messages in history."""
    from .tui import HL7ViewerApp
    app = HL7ViewerApp(
        parsed,
        version=args.hl7_version,
        filename=filename,
        enc_info=enc_info,
        extra_messages=extra_messages,
        profile=args._profile,
    )
    app.run()


def main():
    parser = argparse.ArgumentParser(
        prog='hl7view',
        description='HL7 v2.x message viewer for the terminal',
    )
    parser.add_argument('files', nargs='*', metavar='FILE',
                        help='HL7 files to parse')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show component breakdown')
    parser.add_argument('-e', '--empty', action='store_true',
                        help='include empty fields')
    parser.add_argument('-f', '--field', metavar='SEG-N',
                        help='extract single field value (e.g. PID-5)')
    parser.add_argument('--raw', action='store_true',
                        help='show raw segment lines')
    parser.add_argument('--no-color', action='store_true',
                        help='disable colors')
    parser.add_argument('--no-interactive', action='store_true',
                        help='force non-interactive table output')
    parser.add_argument('--clipboard', action='store_true',
                        help='read from X clipboard (xclip -o)')
    parser.add_argument('--anon', action='store_true',
                        help='anonymize PHI fields (ASCII name pool)')
    parser.add_argument('--anon-non-ascii', action='store_true',
                        help='anonymize PHI fields (Estonian name pool with non-ASCII chars)')
    parser.add_argument('--send', metavar='HOST:PORT',
                        help='send message via MLLP to host:port')
    parser.add_argument('--send-timeout', type=int, default=10, metavar='N',
                        help='MLLP send timeout in seconds (default: 10)')
    parser.add_argument('--send-no-wait', action='store_true',
                        help='fire and forget (do not wait for ACK)')
    parser.add_argument('--tls', action='store_true',
                        help='enable TLS for --send')
    parser.add_argument('--tls-ca', metavar='PATH',
                        help='CA certificate PEM for server verification')
    parser.add_argument('--tls-cert', metavar='PATH',
                        help='client certificate PEM (enables mTLS)')
    parser.add_argument('--tls-key', metavar='PATH',
                        help='client private key PEM')
    parser.add_argument('--tls-insecure', action='store_true',
                        help='skip server certificate verification')
    parser.add_argument('--diff', action='store_true',
                        help='compare two HL7 files field-by-field (requires exactly 2 files)')
    parser.add_argument('--profile', metavar='PATH',
                        help='load integration profile JSON for custom field names')
    parser.add_argument('--version', dest='hl7_version', metavar='VER',
                        choices=['2.3', '2.5'],
                        help='force HL7 version (2.3 or 2.5)')
    parser.add_argument('-V', action='version',
                        version=f'%(prog)s {__version__}')

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty()

    # Load integration profile if specified
    profile = None
    if args.profile:
        try:
            profile = load_profile(args.profile)
        except (OSError, IOError, ValueError, json.JSONDecodeError) as e:
            print(f'Error loading profile: {e}', file=sys.stderr)
            sys.exit(1)
    args._profile = profile

    if args.clipboard:
        text, enc_info = read_clipboard()
        if _wants_interactive(args):
            _launch_tui(text, enc_info, args, filename="(clipboard)")
        else:
            _process_message(text, enc_info, args, use_color)
        return

    if args.diff:
        if len(args.files) != 2:
            print('Error: --diff requires exactly 2 files', file=sys.stderr)
            sys.exit(1)
        from .diff import diff_messages
        texts = []
        for path in args.files:
            try:
                text, _ = read_file(path)
            except (OSError, IOError) as e:
                print(f'Error reading {path}: {e}', file=sys.stderr)
                sys.exit(1)
            parsed = parse_hl7(text)
            if not parsed:
                print(f'Error: no HL7 segments found in {path}', file=sys.stderr)
                sys.exit(1)
            texts.append(parsed)
        diff_result = diff_messages(texts[0], texts[1])
        print(format_diff(diff_result, no_color=args.no_color, show_identical=args.empty), end='')
        return

    if args.files:
        if _wants_interactive(args):
            # Interactive TUI: load all files into history
            messages = []
            for path in args.files:
                try:
                    text, enc_info = read_file(path)
                except (OSError, IOError) as e:
                    print(f'Error reading {path}: {e}', file=sys.stderr)
                    continue
                parsed = parse_hl7(text)
                if parsed:
                    messages.append((parsed, os.path.basename(path), enc_info))
                else:
                    print(f'Warning: no HL7 segments in {path}', file=sys.stderr)
            if not messages:
                print('Error: no valid HL7 messages found', file=sys.stderr)
                sys.exit(1)
            first_parsed, first_name, first_enc = messages[0]
            _launch_tui_with_messages(first_parsed, first_enc, args,
                                      filename=first_name,
                                      extra_messages=messages[1:])
        else:
            # Non-interactive: process all files
            ok = True
            for i, path in enumerate(args.files):
                if i > 0:
                    print()  # blank line between messages
                try:
                    text, enc_info = read_file(path)
                except (OSError, IOError) as e:
                    print(f'Error reading {path}: {e}', file=sys.stderr)
                    ok = False
                    continue
                if not _process_message(text, enc_info, args, use_color):
                    ok = False
            if not ok:
                sys.exit(1)
        return

    # No files — check stdin
    if not sys.stdin.isatty():
        raw = sys.stdin.buffer.read()
        enc = detect_encoding(raw)
        text = raw.decode(enc['decoder_label'])
        _process_message(text, enc, args, use_color)
        return

    # Interactive terminal, no input
    print('Usage: hl7view [OPTIONS] [FILE...]', file=sys.stderr)
    print('       cat message.hl7 | hl7view', file=sys.stderr)
    print('       hl7view --clipboard', file=sys.stderr)
    print(f'\nRun hl7view -h for full help.', file=sys.stderr)
    sys.exit(1)
