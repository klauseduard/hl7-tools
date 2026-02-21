"""Byte-level encoding detection for HL7 message files."""


def detect_encoding(raw_bytes):
    """Detect encoding of raw bytes.

    Returns dict with keys: encoding, decoder_label, has_bom, has_high_bytes.
    """
    if not raw_bytes:
        return {"encoding": "ASCII", "decoder_label": "utf-8",
                "has_bom": False, "has_high_bytes": False}

    b = raw_bytes

    # BOM check
    if len(b) >= 3 and b[0] == 0xEF and b[1] == 0xBB and b[2] == 0xBF:
        return {"encoding": "UTF-8", "decoder_label": "utf-8",
                "has_bom": True, "has_high_bytes": True}
    if len(b) >= 2 and b[0] == 0xFF and b[1] == 0xFE:
        return {"encoding": "UTF-16 LE", "decoder_label": "utf-16-le",
                "has_bom": True, "has_high_bytes": True}
    if len(b) >= 2 and b[0] == 0xFE and b[1] == 0xFF:
        return {"encoding": "UTF-16 BE", "decoder_label": "utf-16-be",
                "has_bom": True, "has_high_bytes": True}

    # No BOM: scan bytes for UTF-8 validity
    has_high = False
    valid_utf8 = True
    has_multibyte = False
    i = 0
    while i < len(b):
        byte = b[i]
        if byte < 0x80:
            i += 1
            continue
        has_high = True
        # Check UTF-8 multi-byte sequence
        if (byte & 0xE0) == 0xC0:
            seq_len = 2
        elif (byte & 0xF0) == 0xE0:
            seq_len = 3
        elif (byte & 0xF8) == 0xF0:
            seq_len = 4
        else:
            valid_utf8 = False
            break
        if i + seq_len > len(b):
            valid_utf8 = False
            break
        for j in range(1, seq_len):
            if (b[i + j] & 0xC0) != 0x80:
                valid_utf8 = False
                break
        if not valid_utf8:
            break
        has_multibyte = True
        i += seq_len

    if not has_high:
        return {"encoding": "ASCII", "decoder_label": "utf-8",
                "has_bom": False, "has_high_bytes": False}
    if valid_utf8 and has_multibyte:
        return {"encoding": "UTF-8", "decoder_label": "utf-8",
                "has_bom": False, "has_high_bytes": True}
    # Invalid UTF-8 with high bytes -> ISO-8859-1
    return {"encoding": "ISO-8859-1", "decoder_label": "iso-8859-1",
            "has_bom": False, "has_high_bytes": True}
