#!/usr/bin/env python3
"""Tests for the UQ-1 ``species_uncertainty`` table and API."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from pyglenn import (
    DatabaseNotConnectedError,
    SpeciesNotFoundError,
    TemperatureOutOfRangeError,
    ThermochemicalCalculator,
    ThermoDBQuery,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path() -> Generator[Path, None, None]:
    """Create a temporary database with a minimal but complete schema."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = Path(f.name)

    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE species (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            formula TEXT,
            comments TEXT,
            reference_code TEXT,
            phase TEXT CHECK(phase IN ('gas', 'condensed')),
            phase_detail TEXT CHECK(phase_detail IN ('gas', 'liquid', 'solid')),
            molecular_weight REAL,
            heat_of_formation_298K REAL,
            num_intervals INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE temperature_intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            interval_number INTEGER NOT NULL,
            temp_min REAL NOT NULL,
            temp_max REAL NOT NULL,
            h_298_to_0 REAL,
            FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
            UNIQUE(species_id, interval_number)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_id INTEGER NOT NULL UNIQUE,
            a1 REAL, a2 REAL, a3 REAL, a4 REAL, a5 REAL,
            a6 REAL, a7 REAL, b1 REAL, b2 REAL,
            FOREIGN KEY (interval_id)
                REFERENCES temperature_intervals(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        "INSERT INTO species (name, phase, num_intervals) VALUES ('CH4', 'gas', 2)"
    )
    cur.execute(
        "INSERT INTO species (name, phase, num_intervals) VALUES ('Ar', 'gas', 1)"
    )
    cur.execute(
        'INSERT INTO temperature_intervals '
        '(species_id, interval_number, temp_min, temp_max) '
        'VALUES (1, 1, 200.0, 1000.0)'
    )
    cur.execute(
        'INSERT INTO temperature_intervals '
        '(species_id, interval_number, temp_min, temp_max) '
        'VALUES (1, 2, 1000.0, 6000.0)'
    )
    cur.execute(
        'INSERT INTO temperature_intervals '
        '(species_id, interval_number, temp_min, temp_max) '
        'VALUES (2, 1, 200.0, 6000.0)'
    )
    for interval_id in (1, 2, 3):
        cur.execute(
            'INSERT INTO coefficients '
            '(interval_id, a1, a2, a3, a4, a5, a6, a7, b1, b2) '
            'VALUES (?, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)',
            (interval_id,),
        )
    conn.commit()
    conn.close()

    yield path
    path.unlink(missing_ok=True)


def _envelope(source: str, bias: float = 0.0) -> dict[str, object]:
    return {
        'species_id': 1,
        'cp_rel_bias': bias,
        'cp_rel_2sigma': 27.6,
        'h_rel_bias': bias,
        'h_rel_2sigma': 13.5,
        's_abs_2sigma': 17.3,
        'n_ref_points': 16 if source == 'nist-janaf' else 0,
        'source': source,
    }


# ---------------------------------------------------------------------------
# Database-level tests
# ---------------------------------------------------------------------------


def test_migrate_populate_get_roundtrip(db_path: Path) -> None:
    query = ThermoDBQuery(str(db_path))
    assert query.connect()
    try:
        assert query.get_uncertainty(1) is None  # table absent -> None

        query.migrate_uncertainty()
        extrapolated = _envelope('extrapolated')
        extrapolated['species_id'] = 2
        assert (
            query.populate_uncertainty(
                [_envelope('nist-janaf', bias=8.82), extrapolated]
            )
            == 2
        )

        row = query.get_uncertainty(1)
        assert row is not None
        assert row['source'] == 'nist-janaf'
        assert row['cp_rel_bias'] == pytest.approx(8.82)
        assert query.get_uncertainty(9999) is None
    finally:
        query.close()


def test_invalid_source_rejected(db_path: Path) -> None:
    query = ThermoDBQuery(str(db_path))
    assert query.connect()
    try:
        query.migrate_uncertainty()
        with pytest.raises(sqlite3.IntegrityError):
            query.populate_uncertainty([_envelope('bogus')])
    finally:
        query.close()


def test_validate_detects_orphan_uncertainty(db_path: Path) -> None:
    query = ThermoDBQuery(str(db_path))
    assert query.connect()
    try:
        query.migrate_uncertainty()
        orphan = _envelope('nist-janaf')
        orphan['species_id'] = 9999
        query.populate_uncertainty([orphan])

        report = query.validate_database()
        assert not report['valid']
        assert any('missing species' in e for e in report['errors'])
    finally:
        query.close()


# ---------------------------------------------------------------------------
# Calculator API tests
# ---------------------------------------------------------------------------


def test_calculator_uncertainty_validated_and_extrapolated(db_path: Path) -> None:
    with ThermochemicalCalculator(db_file=str(db_path)) as calc:
        calc.db.migrate_uncertainty()
        calc.db.populate_uncertainty(
            [
                _envelope('nist-janaf', bias=8.82),
                {
                    'species_id': 2,
                    'cp_rel_bias': 0.0,
                    'cp_rel_2sigma': 9.07,
                    'h_rel_bias': 0.0,
                    'h_rel_2sigma': 4.3,
                    's_abs_2sigma': 5.1,
                    'n_ref_points': 0,
                    'source': 'extrapolated',
                },
            ]
        )

        ch4 = calc.uncertainty(1, 1000.0)
        assert ch4 is not None
        assert ch4['source'] == 'nist-janaf'
        assert ch4['cp_rel_bias'] == pytest.approx(8.82)
        assert ch4['n_ref_points'] == 16

        ar = calc.uncertainty(2, 1000.0)
        assert ar is not None
        assert ar['source'] == 'extrapolated'
        assert ar['cp_rel_bias'] == 0.0


def test_calculator_uncertainty_none_when_unpopulated(db_path: Path) -> None:
    with ThermochemicalCalculator(db_file=str(db_path)) as calc:
        assert calc.uncertainty(1, 1000.0) is None


def test_calculator_uncertainty_out_of_range(db_path: Path) -> None:
    with ThermochemicalCalculator(db_file=str(db_path)) as calc:
        calc.db.migrate_uncertainty()
        calc.db.populate_uncertainty([_envelope('nist-janaf')])
        with pytest.raises(TemperatureOutOfRangeError):
            calc.uncertainty(1, 50.0)


def test_calculator_uncertainty_species_not_found(db_path: Path) -> None:
    calc = ThermochemicalCalculator(db_file=str(db_path))
    calc.connect()
    try:
        with pytest.raises(SpeciesNotFoundError):
            calc.uncertainty(9999, 1000.0)
    finally:
        calc.close()


def test_calculator_uncertainty_requires_connection(db_path: Path) -> None:
    calc = ThermochemicalCalculator(db_file=str(db_path))
    with pytest.raises(DatabaseNotConnectedError):
        calc.uncertainty(1, 1000.0)
