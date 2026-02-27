"""Anonymization of PHI-bearing segments (PID, NK1, GT1, IN1, MRG) and non-ASCII transliteration."""

import copy
import random
import unicodedata

from .parser import (
    ParsedMessage, Field, Component, Repetition, split_components,
    reparse_field, rebuild_raw_line,
)

# ---------------------------------------------------------------------------
# Name / address / city pools (16 each)
# ---------------------------------------------------------------------------

ASCII_NAMES = [
    ("Smith", "John"), ("Doe", "Jane"), ("Johnson", "Robert"),
    ("Williams", "Mary"), ("Brown", "James"), ("Davis", "Patricia"),
    ("Miller", "Michael"), ("Wilson", "Jennifer"), ("Moore", "David"),
    ("Taylor", "Linda"), ("Anderson", "William"), ("Thomas", "Barbara"),
    ("Jackson", "Richard"), ("White", "Susan"), ("Harris", "Joseph"),
    ("Martin", "Karen"),
]

ESTONIAN_NAMES = [
    # Every name maximizes Õ, Ä, Ö, Ü, Š, Ž coverage for stress testing
    ("\u00d6\u00f6\u00fcmin", "\u00d5gvard\u017e"),      # Ööümin, Õgvardž
    ("T\u00e4\u00e4g\u00f5r\u0161", "\u017d\u00fc\u00f6\u00e4"),  # Täägõrš, Žüöä
    ("P\u00f5ld\u00f6\u00e4\u0161", "K\u00fc\u00f5\u017elli"),    # Põldöäš, Küõželli
    ("\u0160\u017e\u00f5\u00e4n", "\u00dc\u00d6\u00d5la"),        # Šžõän, ÜÖÕla
    ("K\u00e4\u00e4r\u00f6\u017e", "\u00d5\u00fc\u0161\u00e4"),   # Kääröž, Õüšä
    ("M\u00f5\u00f6\u00e4\u017eus", "T\u00f5\u00fc\u0161"),       # Mõöäžus, Tõüš
    ("S\u00f5\u0161tar\u00e4", "\u00d5\u00d6\u017enna"),          # Sõštarä, ÕÖŽenna
    ("P\u00e4\u00e4\u0161\u00f6ke", "S\u00fc\u00f5r\u017e"),      # Pääšöke, Süõrž
    ("L\u00f5\u00e4\u017emus", "R\u00e4\u00fc\u0161"),            # Lõäžmus, Räüš
    ("V\u00e4\u00f6\u017e\u00f5r", "\u00d6\u00d5\u0160\u00fcn"), # Väöžõr, ÖÕŠün
    ("N\u00f5\u017e\u00e4k", "K\u00e4\u00f6\u00fc\u0161"),       # Nõžäk, Käöüš
    ("T\u00f5\u017eiss\u00f6n", "\u00d5\u00e4\u017ee"),           # Tõžissön, Õäže
    ("R\u00e4\u00f5\u0161la", "J\u00fc\u017eri"),                 # Räõšla, Jüžeri
    ("K\u00f5r\u017e\u00e4\u00fc", "\u0160\u00f5\u00f6l\u00e4"), # Kõržäü, Šõölä
    ("\u017dele\u017e\u00f5\u00e4", "\u00dc\u00f6\u0161le"),      # Železõä, Üöšle
    ("P\u00f5\u00e4\u017eer\u00fc", "M\u00e4\u00f6\u00fc\u0161\u017e"),  # Põäžerü, Mäöüšž
]

# Streets/cities: Estonian-only pool used when use_non_ascii=True, ASCII pool otherwise
_ESTONIAN_STREETS = [
    "T\u00f5nis\u00e4\u00f6 tee 5", "P\u00e4rnu\u00f5 mnt 42",
    "\u00d5\u00e4\u017eu t\u00e4nav 3", "K\u00fc\u00f6\u0161e tee 8",
    "S\u00fc\u00f5\u017ea p\u00f5ik 11", "V\u00e4\u00f6r\u00fc tee 7",
    "L\u00f5\u017e\u00e4 mnt 15", "\u0160\u00f6\u00e4\u00fc t\u00e4n 9",
    "P\u00f5\u00e4\u017ea tee 22", "T\u00e4\u00fc\u017e\u00f5 tn 6",
    "K\u00e4\u00f6\u0161\u00f5 p\u00f5ik 13", "R\u00e4\u00fc\u017ea mnt 4",
    "\u017d\u00f5\u00e4\u00fc tee 19", "\u00d5\u00e4\u0161\u00fc tn 31",
    "\u00dc\u017e\u00f5\u00e4 allee 2", "M\u00f6\u00f5\u0161\u00e4 tee 17",
]

_ASCII_STREETS = [
    "Tamme tee 5", "Oak Street 12", "Maple Avenue 7", "Cedar Lane 3",
    "Elm Road 21", "Birch Drive 9", "Pine Street 14", "Willow Lane 6",
    "Main Street 33", "Park Avenue 18", "River Road 25", "Lake Drive 10",
    "Hill Street 42", "Forest Lane 8", "Valley Road 15", "Bridge Street 77",
]

_ESTONIAN_CITIES = [
    "T\u00f5\u00e4\u017eelu", "P\u00e4r\u00f6\u00fc",
    "K\u00fc\u00f5\u0161avere", "S\u00e4\u00e4\u017eevald",
    "V\u00f5\u00e4r\u00fc", "\u00d5\u00e4\u017e\u00fcla",
    "L\u00f5\u00e4\u0161k\u00fc", "\u0160\u00f6\u00e4\u00fcri",
    "R\u00e4\u00f6\u017e\u00f5", "N\u00f5\u00fc\u0161\u00e4",
    "T\u00e4\u00f6\u017e\u00f5k\u00fc", "P\u00f5\u017e\u00e4le",
    "K\u00e4\u00fc\u0161\u00f5la", "M\u00f6\u00e4\u017e\u00fc",
    "\u00dc\u017e\u00f5\u00e4vere", "J\u00f5\u00e4\u0161\u00fc",
]

_ASCII_CITIES = [
    "Tallinn", "Tartu", "Springfield", "Riverside",
    "Greenville", "Fairview", "Madison", "Georgetown",
    "Portland", "Bristol", "Chester", "Lakewood",
    "Ashland", "Clayton", "Franklin", "Kingston",
]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _randomize_digits(s):
    """Replace each digit with a random digit, preserve everything else."""
    return "".join(
        str(random.randint(0, 9)) if ch.isdigit() else ch
        for ch in s
    )


def _randomize_alphanum(s):
    """Replace digits with random digits and letters with random letters."""
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(str(random.randint(0, 9)))
        elif ch.isalpha():
            repl = chr(random.randint(ord('A'), ord('Z')))
            out.append(repl if ch.isupper() else repl.lower())
        else:
            out.append(ch)
    return "".join(out)


def _pick_name(pool):
    """Pick a random (family, given) from the pool."""
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Per-field anonymization
# ---------------------------------------------------------------------------

def _generate_fake_city(use_non_ascii=False):
    """Pick a random city from the ASCII or Estonian pool."""
    cities = _ESTONIAN_CITIES if use_non_ascii else _ASCII_CITIES
    return random.choice(cities)


def _generate_fake_id(raw_value):
    """Anonymize CX-type field: randomize digits in component 1."""
    if not raw_value:
        return raw_value
    reps = raw_value.split("~")
    out_reps = []
    for rep in reps:
        parts = rep.split("^")
        if parts:
            parts[0] = _randomize_digits(parts[0])
        out_reps.append("^".join(parts))
    return "~".join(out_reps)


def _generate_fake_name(raw_value, pool):
    """Anonymize XPN-type field: replace family/given, clear middle."""
    if not raw_value:
        return raw_value
    reps = raw_value.split("~")
    out_reps = []
    for rep in reps:
        parts = rep.split("^")
        family, given = _pick_name(pool)
        if len(parts) > 0:
            parts[0] = family
        if len(parts) > 1:
            parts[1] = given
        if len(parts) > 2:
            parts[2] = ""  # clear middle name
        out_reps.append("^".join(parts))
    return "~".join(out_reps)


def _shift_date(raw_value):
    """Anonymize date/time field: shift year ±1–20, preserve format."""
    if not raw_value or len(raw_value) < 4:
        return raw_value
    try:
        year = int(raw_value[:4])
    except ValueError:
        return raw_value
    shift = random.choice([-1, 1]) * random.randint(1, 20)
    new_year = max(1900, min(2099, year + shift))
    return str(new_year) + raw_value[4:]


def _generate_fake_address(raw_value, use_non_ascii=False):
    """Anonymize XAD-type field: replace street/city/zip."""
    if not raw_value:
        return raw_value
    streets = _ESTONIAN_STREETS if use_non_ascii else _ASCII_STREETS
    cities = _ESTONIAN_CITIES if use_non_ascii else _ASCII_CITIES
    reps = raw_value.split("~")
    out_reps = []
    for rep in reps:
        parts = rep.split("^")
        # XAD: 0=street, 1=other, 2=city, 3=state, 4=zip, 5=country, 6=type
        if len(parts) > 0:
            parts[0] = random.choice(streets)
        if len(parts) > 1:
            parts[1] = ""
        if len(parts) > 2:
            parts[2] = random.choice(cities)
        if len(parts) > 4:
            parts[4] = _randomize_digits(parts[4]) if parts[4] else ""
        out_reps.append("^".join(parts))
    return "~".join(out_reps)


def _generate_fake_phone(raw_value):
    """Anonymize XTN-type field: randomize all digits."""
    if not raw_value:
        return raw_value
    reps = raw_value.split("~")
    out_reps = []
    for rep in reps:
        parts = rep.split("^")
        out_parts = [_randomize_digits(p) for p in parts]
        out_reps.append("^".join(out_parts))
    return "~".join(out_reps)


# ---------------------------------------------------------------------------
# Segment reconstruction
# ---------------------------------------------------------------------------

_rebuild_raw_line = rebuild_raw_line
_reparse_field = reparse_field


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def anonymize_message(parsed, use_non_ascii=False):
    """Deep-copy parsed message, anonymize PHI-bearing segments, rebuild raw_lines.

    Processes PID, NK1, GT1, IN1, and MRG segments.

    Args:
        parsed: ParsedMessage to anonymize.
        use_non_ascii: If True, use Estonian name pool; otherwise ASCII.

    Returns:
        A new ParsedMessage with PHI fields anonymized.
    """
    result = copy.deepcopy(parsed)
    pool = ESTONIAN_NAMES if use_non_ascii else ASCII_NAMES

    for seg in result.segments:
        if seg.name == "PID":
            for fld in seg.fields:
                new_raw = None
                if fld.field_num in (2, 3):
                    new_raw = _generate_fake_id(fld.raw_value)
                elif fld.field_num in (5, 6, 9):
                    new_raw = _generate_fake_name(fld.raw_value, pool)
                elif fld.field_num == 7:
                    new_raw = _shift_date(fld.raw_value)
                elif fld.field_num == 11:
                    new_raw = _generate_fake_address(fld.raw_value, use_non_ascii)
                elif fld.field_num in (13, 14):
                    new_raw = _generate_fake_phone(fld.raw_value)
                elif fld.field_num in (18, 21):
                    new_raw = _generate_fake_id(fld.raw_value)
                elif fld.field_num in (19, 20):
                    new_raw = _randomize_alphanum(fld.raw_value) if fld.raw_value else None
                elif fld.field_num == 23:
                    new_raw = _generate_fake_city(use_non_ascii) if fld.raw_value else None
                if new_raw is not None:
                    _reparse_field(fld, new_raw)
            seg.raw_line = _rebuild_raw_line(seg.name, seg.fields)

        elif seg.name == "NK1":
            # NK1-2: name (XPN), NK1-4: address (XAD),
            # NK1-5: phone (XTN), NK1-6: business phone (XTN)
            for fld in seg.fields:
                new_raw = None
                if fld.field_num == 2:
                    new_raw = _generate_fake_name(fld.raw_value, pool)
                elif fld.field_num == 4:
                    new_raw = _generate_fake_address(fld.raw_value, use_non_ascii)
                elif fld.field_num in (5, 6):
                    new_raw = _generate_fake_phone(fld.raw_value)
                if new_raw is not None:
                    _reparse_field(fld, new_raw)
            seg.raw_line = _rebuild_raw_line(seg.name, seg.fields)

        elif seg.name == "GT1":
            # GT1-3: name (XPN), GT1-5: address (XAD),
            # GT1-6/7: phone (XTN), GT1-8: date (TS), GT1-12: SSN
            for fld in seg.fields:
                new_raw = None
                if fld.field_num == 3:
                    new_raw = _generate_fake_name(fld.raw_value, pool)
                elif fld.field_num == 5:
                    new_raw = _generate_fake_address(fld.raw_value, use_non_ascii)
                elif fld.field_num in (6, 7):
                    new_raw = _generate_fake_phone(fld.raw_value)
                elif fld.field_num == 8:
                    new_raw = _shift_date(fld.raw_value)
                elif fld.field_num == 12:
                    new_raw = _randomize_digits(fld.raw_value) if fld.raw_value else None
                if new_raw is not None:
                    _reparse_field(fld, new_raw)
            seg.raw_line = _rebuild_raw_line(seg.name, seg.fields)

        elif seg.name == "IN1":
            # IN1-16: name (XPN), IN1-18: date (TS), IN1-19: address (XAD)
            for fld in seg.fields:
                new_raw = None
                if fld.field_num == 16:
                    new_raw = _generate_fake_name(fld.raw_value, pool)
                elif fld.field_num == 18:
                    new_raw = _shift_date(fld.raw_value)
                elif fld.field_num == 19:
                    new_raw = _generate_fake_address(fld.raw_value, use_non_ascii)
                if new_raw is not None:
                    _reparse_field(fld, new_raw)
            seg.raw_line = _rebuild_raw_line(seg.name, seg.fields)

        elif seg.name == "MRG":
            # MRG-1..4: prior IDs (CX), MRG-7: prior name (XPN)
            for fld in seg.fields:
                new_raw = None
                if fld.field_num in (1, 2, 3, 4):
                    new_raw = _generate_fake_id(fld.raw_value)
                elif fld.field_num == 7:
                    new_raw = _generate_fake_name(fld.raw_value, pool)
                if new_raw is not None:
                    _reparse_field(fld, new_raw)
            seg.raw_line = _rebuild_raw_line(seg.name, seg.fields)

    return result


def transliterate(text):
    """Replace non-ASCII characters with closest ASCII equivalents.

    Uses Unicode NFKD decomposition to strip combining marks, with
    manual fallbacks for characters that don't decompose cleanly.
    """
    if not text:
        return text

    # Check fast path: all ASCII
    try:
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        pass

    # Manual mapping for common chars that NFKD doesn't handle well
    _EXTRA = {
        "\u00d0": "D",   # Ð
        "\u00f0": "d",   # ð
        "\u00de": "Th",  # Þ
        "\u00fe": "th",  # þ
        "\u00df": "ss",  # ß
        "\u00c6": "AE",  # Æ
        "\u00e6": "ae",  # æ
        "\u0152": "OE",  # Œ
        "\u0153": "oe",  # œ
        "\u0160": "S",   # Š
        "\u0161": "s",   # š
        "\u017d": "Z",   # Ž
        "\u017e": "z",   # ž
    }

    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
            continue
        if ch in _EXTRA:
            out.append(_EXTRA[ch])
            continue
        # NFKD decomposition: strip combining marks
        decomposed = unicodedata.normalize("NFKD", ch)
        ascii_chars = "".join(c for c in decomposed if ord(c) < 128)
        out.append(ascii_chars if ascii_chars else "?")

    return "".join(out)
