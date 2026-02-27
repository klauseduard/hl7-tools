"""Performance benchmarks for large HL7 messages (500+ OBX segments)."""

import json
import time
from pathlib import Path

import pytest

from hl7view.parser import parse_hl7
from hl7view.mcp_server import _serialize_parsed, hl7_validate
from hl7view.definitions import resolve_version

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

# LOINC codes for a realistic large lab panel (CBC + CMP + extras)
LOINC_POOL = [
    ("6690-2", "Leukocytes", "10*3/uL", "4.5-11.0"),
    ("789-8", "Erythrocytes", "10*6/uL", "4.10-5.10"),
    ("718-7", "Hemoglobin", "g/dL", "12.0-16.0"),
    ("4544-3", "Hematocrit", "%", "36.0-46.0"),
    ("777-3", "Platelets", "10*3/uL", "150-400"),
    ("787-2", "MCV", "fL", "80.0-100.0"),
    ("785-6", "MCH", "pg", "27.0-33.0"),
    ("786-4", "MCHC", "g/dL", "32.0-36.0"),
    ("788-0", "RDW", "%", "11.5-14.5"),
    ("32623-1", "MPV", "fL", "7.0-12.0"),
    ("26515-7", "Platelet count", "10*3/uL", "150-400"),
    ("770-8", "Neutrophils %", "%", "40.0-70.0"),
    ("736-9", "Lymphocytes %", "%", "20.0-45.0"),
    ("5905-5", "Monocytes %", "%", "2.0-10.0"),
    ("713-8", "Eosinophils %", "%", "1.0-4.0"),
    ("706-2", "Basophils %", "%", "0.0-1.0"),
    ("751-8", "Neutrophils #", "10*3/uL", "1.8-7.7"),
    ("731-0", "Lymphocytes #", "10*3/uL", "1.0-4.8"),
    ("742-7", "Monocytes #", "10*3/uL", "0.1-0.8"),
    ("711-2", "Eosinophils #", "10*3/uL", "0.0-0.5"),
    ("704-7", "Basophils #", "10*3/uL", "0.0-0.2"),
    ("2951-2", "Sodium", "mmol/L", "136-145"),
    ("2823-3", "Potassium", "mmol/L", "3.5-5.1"),
    ("2075-0", "Chloride", "mmol/L", "98-106"),
    ("1963-8", "Bicarbonate", "mmol/L", "22-29"),
    ("2345-7", "Glucose", "mg/dL", "70-99"),
    ("3094-0", "BUN", "mg/dL", "7-20"),
    ("2160-0", "Creatinine", "mg/dL", "0.7-1.3"),
    ("17861-6", "Calcium", "mg/dL", "8.5-10.5"),
    ("2885-2", "Total Protein", "g/dL", "6.0-8.3"),
]


def generate_large_oru(n_obx: int) -> str:
    """Build a synthetic ORU^R01 v2.8 message with N OBX segments."""
    lines = [
        "MSH|^~\\&|ANALYZER^2.16.840.1.113883.3.111^ISO|CENTRAL_LAB^1.2.372.1^ISO"
        "|LIS^2.16.840.1.113883.3.222^ISO|CENTRAL_HOSP^1.2.372.2^ISO"
        "|20260227093000||ORU^R01^ORU_R01|MSG20260227500|P|2.8|||AL|NE|EST"
        "|UNICODE UTF-8|||CENTRAL_LAB^1.2.372.1^ISO|CENTRAL_HOSP^1.2.372.2^ISO",
        "PID|1||PAT99201^^^CENTRAL_HOSP^PI||Koppel^Maria^Liisa||19851103|F"
        "|||Parnu mnt 45^^Tallinn^^10134^EST||+3725550199",
        "PV1|1|O|LAB^200^^CENTRAL_LAB||||20198^Mets^Kersti^^^Dr",
        "ORC|RE|ORD88010^HIS|LAB92001^ANALYZER|||||||||20198^Mets^Kersti^^^Dr",
        "OBR|1|ORD88010^HIS|LAB92001^ANALYZER|58410-2^CBC W Auto Differential panel^LN"
        "|||20260227080000|||||||||20198^Mets^Kersti^^^Dr"
        "||||||20260227092500|||F",
    ]

    for i in range(1, n_obx + 1):
        loinc, name, unit, ref_range = LOINC_POOL[(i - 1) % len(LOINC_POOL)]
        # Generate a plausible numeric value within reference range
        lo, hi = ref_range.replace(" ", "").split("-")
        mid = (float(lo) + float(hi)) / 2
        value = f"{mid:.1f}"
        lines.append(
            f"OBX|{i}|NM|{loinc}^{name}^LN||{value}"
            f"|{unit}^{unit}^UCUM|{ref_range}||||F|||20260227091500"
        )

    lines.append(
        "SPM|1|SPM20260227001^LAB||BLD^Blood^HL70487|||VENIP^Venipuncture^HL70488"
        "|LACF^Left antecubital fossa^SCT|||||4.0&mL|||||20260227080000|20260227083000"
    )
    lines.append("NTE|1||Large panel with multiple analytes. No clots or hemolysis noted.")

    return "\r".join(lines)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def test_parse_500obx():
    """parse_hl7() must complete in <1s for a 500-OBX message."""
    raw = generate_large_oru(500)
    t0 = time.perf_counter()
    parsed = parse_hl7(raw)
    elapsed = time.perf_counter() - t0

    print(f"\n  parse_hl7(500 OBX): {elapsed:.3f}s, {len(parsed.segments)} segments")
    assert elapsed < 1.0, f"parse_hl7 took {elapsed:.2f}s (limit 1s)"
    assert len(parsed.segments) == 507  # MSH+PID+PV1+ORC+OBR + 500 OBX + SPM+NTE


def test_serialize_500obx():
    """_serialize_parsed() must complete in <2s for 500 OBX."""
    raw = generate_large_oru(500)
    parsed = parse_hl7(raw)
    version = resolve_version(parsed.version)

    t0 = time.perf_counter()
    result = _serialize_parsed(parsed, version=version, show_empty=False)
    elapsed = time.perf_counter() - t0

    json_str = json.dumps(result)
    print(f"\n  _serialize_parsed(500 OBX): {elapsed:.3f}s, JSON size: {len(json_str):,} bytes")
    assert elapsed < 2.0, f"_serialize_parsed took {elapsed:.2f}s (limit 2s)"


def test_validate_500obx():
    """hl7_validate() must complete in <2s for 500 OBX."""
    raw = generate_large_oru(500)

    t0 = time.perf_counter()
    result = hl7_validate(raw)
    elapsed = time.perf_counter() - t0

    issues = json.loads(result)
    print(f"\n  hl7_validate(500 OBX): {elapsed:.3f}s, {len(issues.get('issues', []))} issues")
    assert elapsed < 2.0, f"hl7_validate took {elapsed:.2f}s (limit 2s)"


def test_json_size_500obx():
    """JSON output should be <1000KB with show_empty=False."""
    raw = generate_large_oru(500)
    parsed = parse_hl7(raw)
    version = resolve_version(parsed.version)
    result = _serialize_parsed(parsed, version=version, show_empty=False)
    json_str = json.dumps(result)

    size_kb = len(json_str) / 1024
    print(f"\n  JSON size (show_empty=False): {size_kb:.1f} KB")
    assert size_kb < 1000, f"JSON size {size_kb:.1f} KB exceeds 1000KB limit"

    # Also measure with show_empty=True for comparison
    result_full = _serialize_parsed(parsed, version=version, show_empty=True)
    json_full = json.dumps(result_full)
    full_kb = len(json_full) / 1024
    print(f"  JSON size (show_empty=True):  {full_kb:.1f} KB")


def test_generate_sample_file():
    """Generate the large sample file if it doesn't exist (or regenerate)."""
    path = SAMPLES_DIR / "oru-r01-large-500obx.hl7"
    raw = generate_large_oru(500)
    path.write_text(raw)
    assert path.exists()
    # Verify it round-trips through parser
    parsed = parse_hl7(path.read_text())
    assert len(parsed.segments) == 507
    print(f"\n  Wrote {path.name}: {len(raw):,} bytes, {len(parsed.segments)} segments")
