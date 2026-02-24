"""Shared fixtures: parsed sample messages and profile."""

from pathlib import Path

import pytest

from hl7view.parser import parse_hl7
from hl7view.profile import load_profile

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
PROFILES_DIR = Path(__file__).parent.parent / "profiles"


@pytest.fixture
def adt_raw():
    return (SAMPLES_DIR / "adt-a01-admit-v25.hl7").read_text()


@pytest.fixture
def adt_parsed(adt_raw):
    return parse_hl7(adt_raw)


@pytest.fixture
def orm_raw():
    return (SAMPLES_DIR / "orm-o01-order-v23.hl7").read_text()


@pytest.fixture
def orm_parsed(orm_raw):
    return parse_hl7(orm_raw)


@pytest.fixture
def oru_raw():
    return (SAMPLES_DIR / "oru-r01-lab-v25.hl7").read_text()


@pytest.fixture
def oru_parsed(oru_raw):
    return parse_hl7(oru_raw)


@pytest.fixture
def sample_profile():
    return load_profile(PROFILES_DIR / "sample-profile.json")
