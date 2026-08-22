"""Tests for the typed domain model (pyglenn.models)."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict

from pyglenn.models import (
    DatabaseStats,
    IntervalData,
    NASACoefficients,
    SpeciesData,
    SpeciesInfo,
    ThermoProperties,
)


def _coeffs() -> NASACoefficients:
    return NASACoefficients(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)


def test_nasa_coefficients_from_mapping_round_trip() -> None:
    """from_mapping and to_dict round-trip the nine coefficients."""
    mapping = {
        'a1': 1.0, 'a2': 2.0, 'a3': 3.0, 'a4': 4.0, 'a5': 5.0,
        'a6': 6.0, 'a7': 7.0, 'b1': 8.0, 'b2': 9.0,
    }
    coeffs = NASACoefficients.from_mapping(mapping)
    assert coeffs == _coeffs()
    assert coeffs.to_dict() == mapping
    assert asdict(coeffs) == mapping


def test_species_info_from_mapping_tolerates_missing_keys() -> None:
    """Missing columns become None rather than raising."""
    info = SpeciesInfo.from_mapping({'id': 1, 'name': 'O2'})
    assert info.id == 1
    assert info.name == 'O2'
    assert info.formula is None
    assert info.phase is None
    assert info.molecular_weight is None


def test_species_info_from_sqlite_row() -> None:
    """from_mapping accepts a sqlite3.Row directly."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            'CREATE TABLE species (id INTEGER, name TEXT, formula TEXT, '
            'phase TEXT, molecular_weight REAL)'
        )
        conn.execute(
            "INSERT INTO species VALUES (1, 'O2', 'O2', 'gas', 31.9988)"
        )
        conn.commit()
        row = conn.execute('SELECT * FROM species').fetchone()
    finally:
        conn.close()

    info = SpeciesInfo.from_mapping(row)
    assert info.id == 1
    assert info.name == 'O2'
    assert info.formula == 'O2'
    assert info.phase == 'gas'
    assert info.molecular_weight == 31.9988


def test_thermo_properties_to_dict_serialises_interval_as_list() -> None:
    """to_dict keeps the legacy dict shape (temp_interval as a list)."""
    props = ThermoProperties(
        temperature=298.15,
        cp=29.0,
        h_relative=8680.0,
        s=205.0,
        temp_interval=(200.0, 1000.0),
        species_name='O2',
        phase='gas',
    )
    data = props.to_dict()
    assert data['temp_interval'] == [200.0, 1000.0]
    assert data['species_name'] == 'O2'
    assert data['cp'] == 29.0


def test_species_data_to_dict_preserves_nested_intervals() -> None:
    """SpeciesData serialises intervals with nested coefficient dicts."""
    data = SpeciesData(
        id=1,
        name='O2',
        formula='O2',
        phase='gas',
        molecular_weight=31.9988,
        heat_of_formation_298K=0.0,
        num_intervals=1,
        intervals=(
            IntervalData(1, 200.0, 1000.0, 8680.0, _coeffs()),
        ),
    )
    payload = data.to_dict()
    assert payload['intervals'][0]['temp_min'] == 200.0
    assert payload['intervals'][0]['coefficients']['a1'] == 1.0


def test_database_stats_to_dict() -> None:
    """DatabaseStats serialises phase counts and average molecular weight."""
    stats = DatabaseStats(
        total_species=2035,
        total_intervals=3779,
        total_coeff_sets=3779,
        species_by_phase={'gas': 1266, 'condensed': 769},
        avg_molecular_weight=132.03,
    )
    assert stats.total_species == 2035
    assert stats.to_dict()['species_by_phase'] == {'gas': 1266, 'condensed': 769}
