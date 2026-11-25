#!/usr/bin/env python3
"""Tests for FI-1: ``phase_detail`` (gas/liquid/solid granularity)."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from pyglenn import ThermochemicalCalculator, ThermoDBBuilder, ThermoDBQuery


def test_classify_phase_detail() -> None:
    classify = ThermoDBBuilder.classify_phase_detail
    assert classify('CH4', '0') == 'gas'
    assert classify('Fe(a)', '1') == 'solid'
    assert classify('Ag(L)', '2') == 'liquid'
    assert classify('SiO2(b-crt)', '3') == 'solid'
    # embedded "(L)" marker (liquid fuels named with the formula)
    assert classify('C2H2(L),acetyle', '1') == 'liquid'


def test_phase_detail_partitions_bundled_db() -> None:
    """The three phase_detail values must partition the bundled dataset."""
    with ThermochemicalCalculator() as calc:
        gas = len(calc.get_available_species(phase_detail='gas'))
        liquid = len(calc.get_available_species(phase_detail='liquid'))
        solid = len(calc.get_available_species(phase_detail='solid'))
        total = len(calc.get_available_species())

        assert (gas, liquid, solid) == (1266, 296, 473)
        assert gas + liquid + solid == total


def test_find_species_phase_detail_filter() -> None:
    with ThermochemicalCalculator() as calc:
        liquids = calc.get_available_species('SiO2', phase_detail='liquid')
        solids = calc.get_available_species('SiO2', phase_detail='solid')
        assert all(s.phase_detail == 'liquid' for s in liquids)
        assert all(s.phase_detail == 'solid' for s in solids)
        assert any(s.name == 'SiO2(L)' for s in liquids)


def test_validate_flags_null_phase_detail() -> None:
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = Path(f.name)
    conn = sqlite3.connect(str(path))
    conn.execute(
        'CREATE TABLE species (id INTEGER PRIMARY KEY, name TEXT, phase TEXT, '
        'phase_detail TEXT, molecular_weight REAL, num_intervals INTEGER)'
    )
    conn.execute(
        'CREATE TABLE temperature_intervals (id INTEGER PRIMARY KEY, '
        'species_id INTEGER, interval_number INTEGER, temp_min REAL, '
        'temp_max REAL, h_298_to_0 REAL)'
    )
    conn.execute(
        'CREATE TABLE coefficients (id INTEGER PRIMARY KEY, interval_id INTEGER, '
        'a1 REAL, a2 REAL, a3 REAL, a4 REAL, a5 REAL, a6 REAL, a7 REAL, '
        'b1 REAL, b2 REAL)'
    )
    conn.execute("INSERT INTO species VALUES (1, 'X', 'condensed', NULL, 10.0, 0)")
    conn.commit()
    conn.close()

    query = ThermoDBQuery(str(path))
    assert query.connect()
    try:
        report = query.validate_database()
        assert not report['valid']
        assert any('NULL phase_detail' in e for e in report['errors'])
    finally:
        query.close()
    path.unlink(missing_ok=True)
