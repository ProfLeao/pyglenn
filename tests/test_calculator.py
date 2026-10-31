#!/usr/bin/env python3
"""Pytest-based tests for pyglenn thermochemical calculator."""

import math
import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from pyglenn import (
    R_GLENN,
    R_UNIVERSAL,
    DatabaseNotConnectedError,
    R,
    SpeciesNotFoundError,
    TemperatureOutOfRangeError,
    ThermoCalcError,
    ThermochemicalCalculator,
    ThermoDBBuilder,
    ThermoDBQuery,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_db_path() -> Generator[Path, None, None]:
    """Create a temporary SQLite database with known test data."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys = ON')
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS species (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            formula TEXT,
            comments TEXT,
            reference_code TEXT,
            phase TEXT CHECK(phase IN ('gas', 'condensed')),
            molecular_weight REAL,
            heat_of_formation_298K REAL,
            num_intervals INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS temperature_intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            interval_number INTEGER NOT NULL,
            temp_min REAL NOT NULL,
            temp_max REAL NOT NULL,
            h_298_to_0 REAL,
            FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
            UNIQUE(species_id, interval_number)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interval_id INTEGER NOT NULL UNIQUE,
            a1 REAL, a2 REAL, a3 REAL, a4 REAL, a5 REAL,
            a6 REAL, a7 REAL,
            b1 REAL, b2 REAL,
            FOREIGN KEY (interval_id)
                REFERENCES temperature_intervals(id) ON DELETE CASCADE
        )
    """)

    # Insert O2 with known NASA-7 coefficients (two intervals: 200-1000, 1000-6000)
    cur.execute(
        'INSERT INTO species (name, formula, phase, molecular_weight, '
        'heat_of_formation_298K, num_intervals) '
        "VALUES ('O2', 'O2', 'gas', 31.9988, 0.0, 2)"
    )
    o2_id = cur.lastrowid

    # Interval 1: 200–1000 K
    cur.execute(
        'INSERT INTO temperature_intervals '
        '(species_id, interval_number, temp_min, temp_max, h_298_to_0) '
        'VALUES (?, 1, 200.0, 1000.0, 8680.0)',
        (o2_id,),
    )
    interval1_id = cur.lastrowid

    cur.execute(
        'INSERT INTO coefficients '
        '(interval_id, a1, a2, a3, a4, a5, a6, a7, b1, b2) '
        'VALUES (?, '
        '-3.42556342E+04, 4.84700097E+02, 1.11901096E+00, '
        '4.29388924E-02, -6.83630052E-05, 5.51320286E-08, '
        '-1.76439230E-11, -3.39145487E+03, 1.84969947E+01)',
        (interval1_id,),
    )

    # Interval 2: 1000–6000 K
    cur.execute(
        'INSERT INTO temperature_intervals '
        '(species_id, interval_number, temp_min, temp_max, h_298_to_0) '
        'VALUES (?, 2, 1000.0, 6000.0, 8680.0)',
        (o2_id,),
    )
    interval2_id = cur.lastrowid

    cur.execute(
        'INSERT INTO coefficients '
        '(interval_id, a1, a2, a3, a4, a5, a6, a7, b1, b2) '
        'VALUES (?, '
        '-1.03793902E+06, 2.34483028E+03, 1.81973204E+00, '
        '1.26784758E-03, -2.18806799E-07, 2.05371957E-11, '
        '-8.19346705E-16, -1.68901093E+04, 1.73871651E+01)',
        (interval2_id,),
    )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def calc(sample_db_path: Path) -> Generator[ThermochemicalCalculator, None, None]:
    """Provide a connected ThermochemicalCalculator instance."""
    c = ThermochemicalCalculator(str(sample_db_path))
    c.connect()
    yield c
    c.close()


def _fortran_field(value: float) -> str:
    """Format one fixed-width FORTRAN double-precision field."""
    return f'{value:16.9E}'.replace('E', 'D')


def _species_block(name: str, num_intervals: int = 1) -> str:
    """Create a minimal valid fixed-width NASA thermo species block."""
    general_info = [' '] * 80
    general_info[0:2] = f'{num_intervals:2d}'
    general_info[3:9] = 'test  '
    general_info[50:52] = ' 0'
    general_info[52:65] = f'{31.9988:13.7f}'
    general_info[65:80] = f'{0.0:15.3f}'

    temperature = f'{200.0:11.3f}{1000.0:11.3f}7' + ' ' * 42 + f'{0.0:15.3f}'
    coefficient_line_1 = ''.join(_fortran_field(value) for value in range(1, 6))
    coefficient_line_2 = (
        _fortran_field(6.0)
        + _fortran_field(7.0)
        + ' ' * 16
        + _fortran_field(8.0)
        + _fortran_field(9.0)
    )
    return '\n'.join(
        [
            f'{name:<16}  test species',
            ''.join(general_info),
            temperature,
            coefficient_line_1,
            coefficient_line_2,
        ]
    )


# ---------------------------------------------------------------------------
# Test: version and package metadata
# ---------------------------------------------------------------------------


def test_version() -> None:
    """Verify package version is a valid string."""
    from pyglenn import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_imports() -> None:
    """Verify all public symbols are importable."""
    assert ThermochemicalCalculator is not None
    assert ThermoDBQuery is not None
    assert ThermoDBBuilder is not None
    assert isinstance(R, float)
    assert issubclass(ThermoCalcError, Exception)
    assert issubclass(DatabaseNotConnectedError, ThermoCalcError)
    assert issubclass(SpeciesNotFoundError, ThermoCalcError)
    assert issubclass(TemperatureOutOfRangeError, ThermoCalcError)


# ---------------------------------------------------------------------------
# Test: Gas constant
# ---------------------------------------------------------------------------


def test_gas_constant_value() -> None:
    """Verify the universal and NASA Glenn reference constants."""
    assert R == R_UNIVERSAL
    assert math.isclose(R_UNIVERSAL, 8.31446261815324, rel_tol=1e-15)
    assert R_GLENN == 8.314510


# ---------------------------------------------------------------------------
# Test: Database connection
# ---------------------------------------------------------------------------


def test_connect_to_valid_db(sample_db_path: Path) -> None:
    """Test connecting to a valid database."""
    q = ThermoDBQuery(str(sample_db_path))
    assert q.connect() is True
    q.close()


def test_connect_to_nonexistent_db() -> None:
    """Test connecting to a nonexistent database returns False."""
    q = ThermoDBQuery('nonexistent_file.db')
    assert q.connect() is False


def test_reference_gas_constant_auto_migration(
    sample_db_path: Path,
) -> None:
    """Legacy databases are migrated automatically on connect (D3)."""
    q = ThermoDBQuery(str(sample_db_path))
    assert q.connect() is True

    assert q.get_gas_constant_ref() == R_GLENN
    q.migrate_metadata()  # idempotent

    assert q.cursor is not None
    metadata = dict(q.cursor.execute('SELECT key, value FROM metadata').fetchall())
    assert metadata['gas_constant_ref'] == '8.314510'
    assert (
        metadata['gas_constant_ref_source'] == 'NASA Glenn/CEA thermo.inp (CODATA 1986)'
    )
    q.close()


def test_reference_gas_constant_invalid_metadata_falls_back(
    sample_db_path: Path,
) -> None:
    """Invalid metadata cannot silently alter thermochemical calculations."""
    q = ThermoDBQuery(str(sample_db_path))
    assert q.connect() is True
    q.migrate_metadata()
    assert q.cursor is not None
    assert q.conn is not None

    q.cursor.execute(
        "UPDATE metadata SET value = 'not-a-number' WHERE key = 'gas_constant_ref'"
    )
    q.conn.commit()
    assert q.get_gas_constant_ref() == R_UNIVERSAL

    q.cursor.execute(
        "UPDATE metadata SET value = '10.0' WHERE key = 'gas_constant_ref'"
    )
    q.conn.commit()
    assert q.get_gas_constant_ref() == R_UNIVERSAL
    q.close()


def test_calculator_connect(calc: ThermochemicalCalculator) -> None:
    """Test calculator connection property."""
    assert calc.connected is True


def test_calculator_not_connected() -> None:
    """Test calculator not connected returns empty results."""
    c = ThermochemicalCalculator('nonexistent.db')
    assert c.connected is False
    assert c.get_available_species() == []
    with pytest.raises(DatabaseNotConnectedError):
        c.calculate_properties(1, 300.0)
    # calculate_formation_enthalpy and calculate_enthalpy_change have
    # their own not-connected guards that return None for backward compat.
    assert c.calculate_formation_enthalpy(1) is None
    assert c.calculate_enthalpy_change(1, 300, 400) is None
    with pytest.warns(DeprecationWarning):
        assert c.get_properties_range(1, [300, 400]) is None


# ---------------------------------------------------------------------------
# Test: Context manager
# ---------------------------------------------------------------------------


def test_context_manager(sample_db_path: Path) -> None:
    """Test context manager connects and disconnects automatically."""
    with ThermochemicalCalculator(str(sample_db_path)) as calc:
        assert calc.connected is True
        species = calc.get_available_species()
        assert len(species) > 0
    assert calc.connected is False


# ---------------------------------------------------------------------------
# Test: Species lookup
# ---------------------------------------------------------------------------


def test_get_all_species(calc: ThermochemicalCalculator) -> None:
    """Test retrieving all species."""
    species = calc.get_available_species()
    assert len(species) == 1
    assert species[0].name == 'O2'


def test_find_species_by_name(calc: ThermochemicalCalculator) -> None:
    """Test searching species by name."""
    species = calc.get_available_species('O2')
    assert len(species) == 1
    assert species[0].name == 'O2'


def test_find_nonexistent_species(calc: ThermochemicalCalculator) -> None:
    """Test searching for a nonexistent species."""
    species = calc.get_available_species('XYZ123')
    assert len(species) == 0


# ---------------------------------------------------------------------------
# Test: Thermochemical calculations
# ---------------------------------------------------------------------------


def test_calculate_properties_o2_298K(calc: ThermochemicalCalculator) -> None:
    """Test O2 properties at 298.15 K — verifies structure and correctness."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    props = calc.calculate_properties(species_id, 298.15)
    assert props is not None
    assert props.species_name == 'O2'
    assert props.phase == 'gas'

    # Verify Cp is positive and within physically reasonable bounds
    assert props.cp > 0
    assert props.cp < 200  # J/(mol·K) — well above any reasonable upper bound

    # Temperature interval check
    assert props.temp_interval[0] == 200.0
    assert props.temp_interval[1] == 1000.0

    # All properties should be finite numbers
    assert math.isfinite(props.cp)
    assert math.isfinite(props.h_relative)
    assert math.isfinite(props.s)


def test_calculate_properties_o2_500K(calc: ThermochemicalCalculator) -> None:
    """Test O2 properties at 500 K."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    props = calc.calculate_properties(species_id, 500.0)
    assert props is not None

    # Cp should be positive and finite
    assert props.cp > 0
    assert math.isfinite(props.cp)

    # H should increase with T (check vs 298 K)
    props_298 = calc.calculate_properties(species_id, 298.15)
    assert props_298 is not None
    assert props.h_relative > props_298.h_relative


def test_calculate_properties_out_of_range(calc: ThermochemicalCalculator) -> None:
    """Test requesting properties outside valid temperature range."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    # Below valid range
    with pytest.raises(TemperatureOutOfRangeError):
        calc.calculate_properties(species_id, 100.0)

    # Above valid range (O2 now has intervals 200-1000 and 1000-6000)
    with pytest.raises(TemperatureOutOfRangeError):
        calc.calculate_properties(species_id, 7000.0)


def test_calculate_properties_invalid_species(calc: ThermochemicalCalculator) -> None:
    """Test requesting properties for nonexistent species ID."""
    with pytest.raises(SpeciesNotFoundError):
        calc.calculate_properties(99999, 300.0)


# ---------------------------------------------------------------------------
# Test: Formation enthalpy
# ---------------------------------------------------------------------------


def test_formation_enthalpy(calc: ThermochemicalCalculator) -> None:
    """Test formation enthalpy retrieval."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    h_f = calc.calculate_formation_enthalpy(species_id)
    # O2(g) reference element → ΔH°f = 0
    assert h_f is not None
    assert math.isclose(h_f, 0.0, abs_tol=1.0)


# ---------------------------------------------------------------------------
# Test: Enthalpy change
# ---------------------------------------------------------------------------


def test_enthalpy_change(calc: ThermochemicalCalculator) -> None:
    """Test enthalpy change between two temperatures."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    delta_h = calc.calculate_enthalpy_change(species_id, 298.15, 500.0)
    assert delta_h is not None
    # ΔH should be positive (heating up)
    assert delta_h > 0
    # ΔH should be finite and reasonable (less than 1e6 J/mol for ~200 K ΔT)
    assert delta_h < 1e6


def test_enthalpy_change_zero_delta(calc: ThermochemicalCalculator) -> None:
    """Test enthalpy change between same temperature is zero."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    delta_h = calc.calculate_enthalpy_change(species_id, 400.0, 400.0)
    assert delta_h is not None
    assert math.isclose(delta_h, 0.0, abs_tol=1e-6)


def test_h_sensible_to_matches_enthalpy_change(
    calc: ThermochemicalCalculator,
) -> None:
    """h_sensible_to is an alias of calculate_enthalpy_change(298.15, T)."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    assert calc.h_sensible_to(species_id, 1000.0) == pytest.approx(
        calc.calculate_enthalpy_change(species_id, 298.15, 1000.0)
    )


def test_formation_plus_sensible_equals_total() -> None:
    """Decomposition identity: h_formation + h_sensible == h_relative."""
    with ThermochemicalCalculator() as calc:
        ch4 = calc.get_available_species('CH4', exact_match=True)[0]
        hf = calc.calculate_formation_enthalpy(ch4.id)
        sensible = calc.h_sensible_to(ch4.id, 1000.0)
        total = calc.calculate_properties(ch4.id, 1000.0).h_relative

        assert hf is not None
        assert sensible is not None
        assert hf + sensible == pytest.approx(total, rel=1e-9)


def test_dcp_dt_matches_finite_difference(calc: ThermochemicalCalculator) -> None:
    """Analytical dCp/dT agrees with a central finite difference."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id
    T = 500.0
    eps = 1e-4
    numeric = (
        calc.calculate_properties(species_id, T + eps).cp
        - calc.calculate_properties(species_id, T - eps).cp
    ) / (2 * eps)
    assert calc.dcp_dt(species_id, T) == pytest.approx(numeric, rel=1e-6)


def test_gamma_monoatomic_argon() -> None:
    """Gamma for a monoatomic ideal gas (Ar) is 5/3."""
    with ThermochemicalCalculator() as calc:
        ar = calc.get_available_species('Ar', exact_match=True)
        assert ar, 'Ar not found in database'
        gamma = calc.gamma(ar[0].id, 298.15)
    assert gamma == pytest.approx(5.0 / 3.0, rel=1e-4)


def test_h_at_298_equals_formation_enthalpy() -> None:
    """NASA-7 convention: H°(298.15 K) equals ΔH°f(298.15 K) across species.

    This is the identity ``h_total - h_sensible == h_formation`` evaluated at
    298.15 K, where the sensible term is zero by definition.
    """
    with ThermochemicalCalculator() as calc:
        checked = 0
        for sp in calc.db.list_all_species():
            hf = sp.heat_of_formation_298K
            if hf is None:
                continue
            try:
                h = calc.calculate_properties(sp.id, 298.15).h_relative
            except TemperatureOutOfRangeError:
                continue
            assert h == pytest.approx(hf, rel=1e-6, abs=1.0), sp.name
            checked += 1
        assert checked > 100  # a meaningful fraction of the dataset


def test_reaction_enthalpy_methane_combustion() -> None:
    """CH4 + 2 O2 -> CO2 + 2 H2O: package formation enthalpies vs NIST values.

    At 298.15 K the sensible term is zero, so the reaction enthalpy is the
    stoichiometric sum of formation enthalpies, compared against textbook
    NIST-JANAF values.
    """
    nist_hf = {
        'CH4': -74.6e3,
        'O2': 0.0,
        'CO2': -393.522e3,
        'H2O': -241.826e3,
    }
    with ThermochemicalCalculator() as calc:
        ids = {
            name: calc.get_available_species(name, exact_match=True)[0].id
            for name in nist_hf
        }
        hf = {
            name: calc.calculate_formation_enthalpy(sid)
            for name, sid in ids.items()
        }
        assert all(value is not None for value in hf.values())

        dh_r = hf['CO2'] + 2 * hf['H2O'] - hf['CH4'] - 2 * hf['O2']
        expected = (
            nist_hf['CO2']
            + 2 * nist_hf['H2O']
            - nist_hf['CH4']
            - 2 * nist_hf['O2']
        )
        assert dh_r == pytest.approx(expected, rel=1e-3)


# ---------------------------------------------------------------------------
# Test: Properties range
# ---------------------------------------------------------------------------


def test_get_properties_range(calc: ThermochemicalCalculator) -> None:
    """Test calculating properties at multiple temperatures."""
    species = calc.get_available_species('O2')
    species_id = species[0].id

    with pytest.warns(DeprecationWarning):
        results = calc.get_properties_range(species_id, [298.15, 500.0, 800.0])
    assert results is not None
    assert len(results) == 3
    assert 298.15 in results
    assert 500.0 in results
    assert 800.0 in results

    # Cp should increase with temperature
    assert results[500.0].cp > results[298.15].cp


def test_get_properties_range_deprecation_warning(
    calc: ThermochemicalCalculator,
) -> None:
    """get_properties_range emits a DeprecationWarning pointing to the new API."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id
    with pytest.warns(DeprecationWarning, match='calculate_properties_range'):
        calc.get_properties_range(species_id, [298.15])


def test_calculate_properties_range_typed(calc: ThermochemicalCalculator) -> None:
    """Typed range API loads data once and preserves input order."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    results = calc.calculate_properties_range(species_id, [500.0, 298.15, 1500.0])
    assert [r.temperature for r in results] == [500.0, 298.15, 1500.0]

    scalar = calc.calculate_properties(species_id, 500.0)
    assert results[0] == scalar


def test_calculate_properties_range_skips_out_of_range(
    calc: ThermochemicalCalculator,
) -> None:
    """Non-strict range API skips out-of-range temperatures."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    results = calc.calculate_properties_range(species_id, [100.0, 500.0, 7000.0])
    assert [r.temperature for r in results] == [500.0]


def test_calculate_properties_range_strict_raises(
    calc: ThermochemicalCalculator,
) -> None:
    """Strict range API raises on the first out-of-range temperature."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    with pytest.raises(TemperatureOutOfRangeError):
        calc.calculate_properties_range(species_id, [500.0, 7000.0], strict=True)


def test_exception_context(calc: ThermochemicalCalculator) -> None:
    """Specialised exceptions carry diagnostic context attributes."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    with pytest.raises(SpeciesNotFoundError) as exc_info:
        calc.calculate_properties(99999, 300.0)
    assert exc_info.value.species_id == 99999

    with pytest.raises(TemperatureOutOfRangeError) as exc_info:
        calc.calculate_properties(species_id, 100.0)
    assert exc_info.value.temperature == 100.0
    assert exc_info.value.species_name == 'O2'
    assert exc_info.value.temp_bounds == (200.0, 6000.0)


def test_bundled_reference_values_glenn() -> None:
    """Cross-language regression anchors for the bundled NASA Glenn/CEA data.

    Values computed with R_GLENN = 8.314510 and cross-checked against the
    NIST-JANAF audit (docs/audit). O2 has zero formation enthalpy; CO2
    carries a nonzero formation enthalpy.
    """
    with ThermochemicalCalculator() as calc:
        o2 = calc.get_available_species('O2', exact_match=True)[0]

        props = calc.calculate_properties(o2.id, 298.15)
        assert props.cp == pytest.approx(29.378353377156, rel=1e-9)
        assert props.s == pytest.approx(205.149467367314, rel=1e-9)

        props = calc.calculate_properties(o2.id, 1000.0)
        assert props.cp == pytest.approx(34.882545009141, rel=1e-9)
        assert props.h_relative == pytest.approx(22707.210697094983, rel=1e-9)
        assert props.s == pytest.approx(243.587313877898, rel=1e-9)

        co2 = calc.get_available_species('CO2', exact_match=True)[0]
        assert co2.heat_of_formation_298K == pytest.approx(-393510.0, rel=1e-9)


# ---------------------------------------------------------------------------
# Test: Database statistics
# ---------------------------------------------------------------------------


def test_database_statistics(calc: ThermochemicalCalculator) -> None:
    """Test database statistics retrieval."""
    stats = calc.db.get_statistics()
    assert stats.total_species == 1
    assert stats.total_intervals == 2
    assert stats.total_coeff_sets == 2
    assert stats.species_by_phase == {'gas': 1}
    assert stats.avg_molecular_weight == pytest.approx(31.9988)


def test_validate_database_valid(calc: ThermochemicalCalculator) -> None:
    """A well-formed database passes all integrity checks."""
    report = calc.db.validate_database()
    assert report['valid'] is True
    assert report['errors'] == []
    assert report['counts']['total_species'] == 1


def test_validate_database_detects_orphan_coefficients(
    sample_db_path: Path,
) -> None:
    """Integrity checks flag coefficients without a matching interval."""
    conn = sqlite3.connect(str(sample_db_path))
    try:
        conn.execute('PRAGMA foreign_keys = OFF')
        conn.execute(
            'INSERT INTO coefficients '
            '(interval_id, a1, a2, a3, a4, a5, a6, a7, b1, b2) '
            'VALUES (99999, 1, 2, 3, 4, 5, 6, 7, 8, 9)'
        )
        conn.commit()
    finally:
        conn.close()

    q = ThermoDBQuery(str(sample_db_path))
    q.connect()
    try:
        report = q.validate_database()
        assert report['valid'] is False
        assert any('missing interval' in e for e in report['errors'])
    finally:
        q.close()


# ---------------------------------------------------------------------------
# Test: ThermoDBQuery standalone
# ---------------------------------------------------------------------------


def test_thermodbquery_find_species(sample_db_path: Path) -> None:
    """Test ThermoDBQuery species search."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    species = q.find_species('O2')
    assert len(species) == 1
    assert species[0].name == 'O2'
    assert species[0].phase == 'gas'

    q.close()


def test_thermodbquery_get_species_data(sample_db_path: Path) -> None:
    """Test ThermoDBQuery complete species data retrieval."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    data = q.get_species_data(1)
    assert data is not None
    assert data.name == 'O2'
    assert len(data.intervals) == 2
    assert data.intervals[0].temp_min == 200.0
    assert data.intervals[0].temp_max == 1000.0
    assert data.intervals[1].temp_min == 1000.0
    assert data.intervals[1].temp_max == 6000.0

    q.close()


def test_thermodbquery_list_all_species(sample_db_path: Path) -> None:
    """list_all_species returns every species in one ordered query."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    species = q.list_all_species()
    assert [sp.name for sp in species] == ['O2']
    assert all(isinstance(sp.id, int) for sp in species)

    q.close()


def test_thermodbquery_get_species_info(sample_db_path: Path) -> None:
    """get_species_info returns metadata and None for missing IDs."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    info = q.get_species_info(1)
    assert info is not None
    assert info.name == 'O2'
    assert info.molecular_weight == 31.9988
    assert q.get_species_info(99999) is None

    q.close()


# ---------------------------------------------------------------------------
# Test: NASA polynomial calculation consistency
# ---------------------------------------------------------------------------


def test_polynomial_consistency(calc: ThermochemicalCalculator) -> None:
    """Verify that H/RT integration is consistent with Cp/R.

    The thermodynamic identity: d(H/RT)/dT = Cp/(R·T) - H/(R·T²)
    which simplifies to: d(H/RT)/dT = (Cp/R - H/RT) / T
    """
    species = calc.get_available_species('O2')
    species_id = species[0].id

    # Get coefficients for 500 K
    interval = calc.db.get_species_for_temperature(species_id, 500.0)
    assert interval is not None
    coeffs = interval.coefficients

    T = 500.0

    # Cp/R and H/RT at T
    cp_r = calc.db.calculate_cp(coeffs, T)
    h_rt = calc.db.calculate_h(coeffs, T)

    # Numerical derivative of H/RT with respect to T
    eps = 1e-4
    h_rt_plus = calc.db.calculate_h(coeffs, T + eps)
    h_rt_minus = calc.db.calculate_h(coeffs, T - eps)
    dhrt_dt = (h_rt_plus - h_rt_minus) / (2 * eps)

    # Thermodynamic identity: d(H/RT)/dT = (Cp/R - H/RT) / T
    expected_derivative = (cp_r - h_rt) / T
    assert math.isclose(dhrt_dt, expected_derivative, rel_tol=1e-5)


# ---------------------------------------------------------------------------
# Test: Builder parse utilities
# ---------------------------------------------------------------------------


def test_parse_float_normal() -> None:
    """Test parse_float with normal float notation."""
    assert ThermoDBBuilder.parse_float('3.14159') == 3.14159


def test_parse_float_fortran_d() -> None:
    """Test parse_float with FORTRAN D notation."""
    assert ThermoDBBuilder.parse_float('1.234D+02') == 123.4
    assert ThermoDBBuilder.parse_float('5.678D-01') == 0.5678


def test_parse_float_empty() -> None:
    """Test parse_float with empty strings."""
    assert ThermoDBBuilder.parse_float('') is None
    assert ThermoDBBuilder.parse_float('   ') is None


def test_is_coefficient_line() -> None:
    """Test coefficient line detection with regex."""
    assert ThermoDBBuilder.is_coefficient_line(' 1.234D+05 5.678D-02')
    assert ThermoDBBuilder.is_coefficient_line(' 1.0D0 2.0D+01')
    assert not ThermoDBBuilder.is_coefficient_line('O2')
    assert not ThermoDBBuilder.is_coefficient_line('200.000  1000.000')


def test_is_temperature_line() -> None:
    """Test temperature interval line detection."""
    # FORTRAN format: 10-char fields at cols 0-10 and 11-21
    assert ThermoDBBuilder.is_temperature_line(' 2.0000E+02 1.0000E+03')
    # First value greater than second → not a valid interval
    assert not ThermoDBBuilder.is_temperature_line(' 1.0000E+03 2.0000E+02')
    # Too short
    assert not ThermoDBBuilder.is_temperature_line('short')
    # Equal values
    assert not ThermoDBBuilder.is_temperature_line(' 5.0000E+02 5.0000E+02')


def test_coefficient_line_is_not_a_species_header() -> None:
    """A NASA coefficient must never be reinterpreted as a species name."""
    coefficient_line = (
        '-1.302004763D+06 3.166984180D+04-3.031242152D+02 '
        '1.602231130D+00-4.594507340D-03'
    )

    assert ThermoDBBuilder.is_coefficient_line(coefficient_line)
    assert not ThermoDBBuilder.is_species_header(coefficient_line)


def test_builder_rejects_partial_block_and_resynchronizes(tmp_path: Path) -> None:
    """A malformed species cannot leave rows behind or hide the next species."""
    inp_path = tmp_path / 'malformed_thermo.inp'
    db_path = tmp_path / 'malformed_thermo.db'
    inp_path.write_text(
        '\n'.join(
            [
                'THERMO',
                '  200.000    500.000   1500.000  6000.000',
                _species_block('BROKEN', num_intervals=2),
                _species_block('O2'),
            ]
        )
    )

    builder = ThermoDBBuilder(str(inp_path), str(db_path))
    builder.connect()
    builder.create_tables()
    builder.parse_and_load()
    builder.close()

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute('SELECT name FROM species').fetchall() == [('O2',)]
        assert (
            conn.execute('SELECT COUNT(*) FROM temperature_intervals').fetchone()[0]
            == 1
        )
        assert conn.execute('SELECT COUNT(*) FROM coefficients').fetchone()[0] == 1
    finally:
        conn.close()


def test_builder_writes_metadata_and_calculator_uses_it(tmp_path: Path) -> None:
    """New databases persist R_GLENN and use it for dimensional properties."""
    inp_path = tmp_path / 'metadata_thermo.inp'
    db_path = tmp_path / 'metadata_thermo.db'
    inp_path.write_text(
        '\n'.join(
            [
                'THERMO',
                '  200.000    500.000   1500.000  6000.000',
                _species_block('O2'),
            ]
        )
    )

    builder = ThermoDBBuilder(str(inp_path), str(db_path))
    builder.connect()
    builder.create_tables()
    builder.parse_and_load()
    builder.close()

    calc = ThermochemicalCalculator(str(db_path))
    assert calc.connect() is True
    assert calc.r_ref == R_GLENN
    species = calc.get_available_species('O2', exact_match=True)
    properties = calc.calculate_properties(species[0].id, 500.0)
    interval = calc.db.get_species_for_temperature(species[0].id, 500.0)
    assert interval is not None
    cp_r = calc.db.calculate_cp(interval.coefficients, 500.0)
    assert properties.cp == pytest.approx(cp_r * R_GLENN)
    calc.close()


def test_parse_species_record() -> None:
    """Test RECORD 1 species name and comments parsing."""
    name, comments = ThermoDBBuilder.parse_species_record(
        'O2              Ref-1 O2 gas           '
    )
    assert name == 'O2'
    assert 'O2' in comments


def test_parse_general_info_record() -> None:
    """Test RECORD 2 general information parsing."""
    # Use dummy paths — parse_general_info_record only needs self.parse_float
    builder = ThermoDBBuilder('dummy.inp', 'dummy.db')
    # Phase code '0' at cols 50-51 means gas
    info = builder.parse_general_info_record(
        ' 1  g 2/99O   2   1   2    0    00G200.000 3500.000 1000.000    1'
    )
    assert info['num_intervals'] == 1
    assert info['phase'] == 'gas'


def test_parse_general_info_record_heat_of_formation() -> None:
    """RECORD 2 extracts molecular weight and heat of formation correctly."""
    builder = ThermoDBBuilder('dummy.inp', 'dummy.db')
    line = (
        ' 3 g 9/99 C   1.00O   2.00    0.00    0.00    0.00 0   44.0095000'
        '    -393510.000'
    )
    info = builder.parse_general_info_record(line)
    assert info['num_intervals'] == 3
    assert info['molecular_weight'] == pytest.approx(44.0095)
    assert info['heat_of_formation'] == pytest.approx(-393510.0)


def test_parse_temp_interval_record() -> None:
    """Test RECORD 3 temperature interval parsing."""
    # FORTRAN format: cols 0-10 (temp_min), 11-21 (temp_max), 65-79 (h_298)
    data = ThermoDBBuilder.parse_temp_interval_record(
        ' 2.0000E+02 1.0000E+03 0.0000E+00 0.0000E+00 0.0000E+00 0'
        '               0.0000E+00 0.0000E+00 8.6800E+03'
    )
    assert data['temp_min'] == 200.0
    assert data['temp_max'] == 1000.0


def test_parse_coefficients_record() -> None:
    """Test RECORDS 4-5 coefficient parsing.

    Each coefficient occupies a 16-character FORTRAN field.
    Line 4: a1[0:16] a2[16:32] a3[32:48] a4[48:64] a5[64:80]
    Line 5: a6[0:16] a7[16:32] (skip 32:48) b1[48:64] b2[64:80]
    """
    coeffs = ThermoDBBuilder.parse_coefficients_record(
        [
            '  3.21225000E+00  1.12749000E-03 -5.75615000E-07'
            '  1.31388000E-09 -8.76854000E-13',
            ' -1.00524900E+03  6.03473800E+00  0.00000000E+00'
            '  3.69757819E+00  6.13519689E-01',
        ]
    )
    assert math.isclose(coeffs['a1'], 3.21225000, rel_tol=1e-6)
    assert math.isclose(coeffs['a2'], 1.12749000e-03, rel_tol=1e-6)
    assert math.isclose(coeffs['a6'], -1.00524900e03, rel_tol=1e-6)
    assert math.isclose(coeffs['b1'], 3.69757819, rel_tol=1e-6)
    assert math.isclose(coeffs['b2'], 6.13519689e-01, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# Test: Database pagination
# ---------------------------------------------------------------------------


def test_list_species_page(sample_db_path: Path) -> None:
    """Test paginated species listing."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    species, total_pages = q.list_species_page(page=1, page_size=10)
    assert len(species) == 1
    assert total_pages == 1
    assert species[0].name == 'O2'

    # Page beyond available data
    species, total_pages = q.list_species_page(page=2, page_size=10)
    assert len(species) == 0
    assert total_pages == 1

    q.close()


# ---------------------------------------------------------------------------
# Test: NASA polynomial standalone calculation
# ---------------------------------------------------------------------------


def test_calculate_cp_standalone() -> None:
    """Test Cp/R calculation directly with known coefficients."""
    coeffs = {
        'a1': -3.42556342e04,
        'a2': 4.84700097e02,
        'a3': 1.11901096,
        'a4': 4.29388924e-02,
        'a5': -6.83630052e-05,
        'a6': 5.51320286e-08,
        'a7': -1.76439230e-11,
    }
    cp_r = ThermoDBQuery.calculate_cp(coeffs, 298.15)
    assert cp_r > 0
    assert math.isfinite(cp_r)


def test_calculate_h_standalone() -> None:
    """Test H/RT calculation directly with known coefficients."""
    coeffs = {
        'a1': -3.42556342e04,
        'a2': 4.84700097e02,
        'a3': 1.11901096,
        'a4': 4.29388924e-02,
        'a5': -6.83630052e-05,
        'a6': 5.51320286e-08,
        'a7': -1.76439230e-11,
        'b1': -3.39145487e03,
    }
    h_rt = ThermoDBQuery.calculate_h(coeffs, 298.15)
    assert math.isfinite(h_rt)


def test_calculate_s_standalone() -> None:
    """Test S/R calculation directly with known coefficients."""
    coeffs = {
        'a1': -3.42556342e04,
        'a2': 4.84700097e02,
        'a3': 1.11901096,
        'a4': 4.29388924e-02,
        'a5': -6.83630052e-05,
        'a6': 5.51320286e-08,
        'a7': -1.76439230e-11,
        'b2': 1.84969947e01,
    }
    s_r = ThermoDBQuery.calculate_s(coeffs, 298.15)
    assert math.isfinite(s_r)


# ---------------------------------------------------------------------------
# Test: Boundary temperatures (Inconsistency 2 fix)
# ---------------------------------------------------------------------------


def test_calculate_properties_lower_boundary(
    calc: ThermochemicalCalculator,
) -> None:
    """O2 properties at T = 200.0 K — exactly the lower interval boundary."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    props = calc.calculate_properties(species_id, 200.0)
    assert props is not None
    assert props.temp_interval == (200.0, 1000.0)
    assert math.isfinite(props.cp)
    assert math.isfinite(props.h_relative)


def test_calculate_properties_shared_boundary(
    calc: ThermochemicalCalculator,
) -> None:
    """O2 properties at T = 1000.0 K — shared boundary between intervals 1 & 2.

    Regression test for Inconsistency 2: calculate_properties() previously
    returned None at interval boundaries because of missing ORDER BY and
    floating-point edge cases in the SQL query.
    """
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    props = calc.calculate_properties(species_id, 1000.0)
    assert props is not None
    # The lower interval (interval_number=1) should be selected when both
    # intervals cover the same temperature (ORDER BY interval_number).
    assert props.temp_interval == (200.0, 1000.0)
    assert math.isfinite(props.cp)
    assert math.isfinite(props.h_relative)


def test_calculate_properties_upper_boundary(
    calc: ThermochemicalCalculator,
) -> None:
    """O2 properties at T = 6000.0 K — exactly the upper interval boundary."""
    species = calc.get_available_species('O2', exact_match=True)
    species_id = species[0].id

    props = calc.calculate_properties(species_id, 6000.0)
    assert props is not None
    assert props.temp_interval == (1000.0, 6000.0)
    assert math.isfinite(props.cp)
    assert math.isfinite(props.h_relative)


# ---------------------------------------------------------------------------
# Test: Exact match (Inconsistency 1 fix)
# ---------------------------------------------------------------------------


def test_get_available_species_exact_match(
    calc: ThermochemicalCalculator,
) -> None:
    """Exact match returns only the species whose name matches exactly."""
    # Substring search (default) — works fine for 'O2' in this small test db
    species = calc.get_available_species('O2')
    assert len(species) == 1
    assert species[0].name == 'O2'

    # Exact match — also works
    species = calc.get_available_species('O2', exact_match=True)
    assert len(species) == 1
    assert species[0].name == 'O2'

    # Exact match — case insensitive
    species = calc.get_available_species('o2', exact_match=True)
    assert len(species) == 1
    assert species[0].name == 'O2'

    # Exact match — no match
    species = calc.get_available_species('O3', exact_match=True)
    assert len(species) == 0


def test_thermodbquery_find_species_exact_match(
    sample_db_path: Path,
) -> None:
    """ThermoDBQuery.find_species with exact_match=True."""
    q = ThermoDBQuery(str(sample_db_path))
    q.connect()

    # Substring search (default)
    species = q.find_species('O2')
    assert len(species) == 1
    assert species[0].name == 'O2'

    # Exact match
    species = q.find_species('O2', exact_match=True)
    assert len(species) == 1
    assert species[0].name == 'O2'

    # Exact match — no result for partial name
    species = q.find_species('O', exact_match=True)
    assert len(species) == 0

    q.close()


# ---------------------------------------------------------------------------
# Test: CLI
# ---------------------------------------------------------------------------


def test_cli_main_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI with no arguments prints help."""
    import sys

    from pyglenn.cli import main

    # Simulate no command
    original_argv = sys.argv
    try:
        sys.argv = ['pyglenn']
        main()
    except SystemExit:
        pass
    finally:
        sys.argv = original_argv

    captured = capsys.readouterr()
    assert 'usage' in captured.out.lower() or 'usage' in captured.err.lower()


def test_cli_build_smoke(tmp_path: Path) -> None:
    """Test build command with a minimal thermo.inp file."""
    import argparse

    from pyglenn.cli import cmd_build

    # Create a minimal thermo.inp
    inp_content = (
        'THERMO\n'
        '   300.000   1000.000   5000.000\n'
        'O2               Ref-1 O2 gas                                      \n'
        ' 1  g 2/99O   2   1   2    0    0G200.000 3500.000 1000.000    1\n'
        ' 2.00000000E+02 1.00000000E+03 0.00000000E+00'
        ' 0.00000000E+00 0.00000000E+00 0\n'
        ' 3.21225000E+00 1.12749000E-03-5.75615000E-07 1.31388000E-09-8.76854000E-13\n'
        '-1.00524900E+03 6.03473800E+00 0.00000000E+00 3.69757819E+00 6.13519689E-01\n'
    )
    inp_path = tmp_path / 'test_thermo.inp'
    db_path = tmp_path / 'test_thermo.db'
    inp_path.write_text(inp_content)

    args = argparse.Namespace(input=str(inp_path), output=str(db_path), verbose=False)
    cmd_build(args)

    assert db_path.exists()
    assert db_path.stat().st_size > 0


def test_cli_query_smoke(
    sample_db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test query command runs without errors."""
    import argparse

    from pyglenn.cli import cmd_query

    args = argparse.Namespace(database=str(sample_db_path), species='O2', verbose=False)
    cmd_query(args)

    captured = capsys.readouterr()
    assert 'SUCCESS' in captured.out


def test_cli_migrate_metadata_smoke(
    sample_db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test migrate-metadata command runs without errors."""
    import argparse

    from pyglenn.cli import cmd_migrate_metadata

    args = argparse.Namespace(database=str(sample_db_path))
    cmd_migrate_metadata(args)

    captured = capsys.readouterr()
    assert 'SUCCESS' in captured.out


def test_cli_validate_smoke(
    sample_db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test validate command runs without errors."""
    import argparse

    from pyglenn.cli import cmd_validate

    args = argparse.Namespace(database=str(sample_db_path))
    cmd_validate(args)

    captured = capsys.readouterr()
    assert 'SUCCESS' in captured.out
