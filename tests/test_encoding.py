"""Tests for hl7view.encoding: detect_encoding for ASCII, UTF-8, ISO-8859-1, BOM."""

from pathlib import Path

from hl7view.encoding import detect_encoding

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_detect_ascii():
    raw = b"MSH|^~\\&|SENDING|FACILITY"
    result = detect_encoding(raw)
    assert result["encoding"] == "ASCII"
    assert result["has_high_bytes"] is False
    assert result["has_bom"] is False


def test_detect_utf8():
    # "Ö" in UTF-8 is 0xC3 0x96
    raw = b"MSH|^~\\&|TEST|\xc3\x96sterreich"
    result = detect_encoding(raw)
    assert result["encoding"] == "UTF-8"
    assert result["has_high_bytes"] is True
    assert result["has_bom"] is False


def test_detect_iso8859():
    # 0xD6 alone is "Ö" in ISO-8859-1, invalid as UTF-8 lead byte without valid continuation
    raw = b"MSH|^~\\&|TEST|\xd6sterreich"
    result = detect_encoding(raw)
    assert result["encoding"] == "ISO-8859-1"
    assert result["has_high_bytes"] is True


def test_detect_utf8_bom():
    raw = b"\xef\xbb\xbfMSH|^~\\&|SENDING|FACILITY"
    result = detect_encoding(raw)
    assert result["encoding"] == "UTF-8"
    assert result["has_bom"] is True


def test_orm_sample_encoding():
    raw_bytes = (SAMPLES_DIR / "orm-o01-order-v23.hl7").read_bytes()
    result = detect_encoding(raw_bytes)
    # ORM file on disk is UTF-8 (MSH-18 declares "8859/1" but the bytes are valid UTF-8)
    assert result["encoding"] == "UTF-8"
    assert result["has_high_bytes"] is True
