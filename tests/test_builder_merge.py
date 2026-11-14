"""Regression tests for duplicate-species merging (porting guide Fix 4)."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from pyglenn import ThermoDBBuilder

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _fortran_field(value: float) -> str:
    return f'{value:16.9E}'.replace('E', 'D')


def _species_block(name: str, t_min: float, t_max: float) -> str:
    """Minimal valid single-interval species block (name, [t_min, t_max])."""
    header = f'{name:<16}'.ljust(33) + 'reference comment'

    info = [' '] * 80
    info[0:2] = ' 1'
    info[3:9] = 'test  '
    info[50:52] = ' 0'
    info[52:65] = f'{28.0:13.7f}'
    info[65:80] = f'{0.0:15.3f}'
    general = ''.join(info)

    temp = f'{t_min:11.3f}{t_max:11.3f}7' + ' ' * 42 + f'{0.0:15.3f}'
    line1 = ''.join(_fortran_field(v) for v in (1.0, 2.0, 3.0, 4.0, 5.0))
    line2 = (
        _fortran_field(6.0)
        + _fortran_field(7.0)
        + ' ' * 16
        + _fortran_field(8.0)
        + _fortran_field(9.0)
    )
    return '\n'.join([header, general, temp, line1, line2])


def _build(tmp_path: Path, blocks: list[str], *, merge_duplicates: bool) -> Path:
    """Write a thermo.inp from blocks, build the DB and return its path."""
    inp = tmp_path / 'thermo.inp'
    db = tmp_path / 'thermo.db'
    inp.write_text(
        'THERMO\n  200.000    500.000   1500.000  6000.000\n' + '\n'.join(blocks)
    )
    builder = ThermoDBBuilder(str(inp), str(db))
    builder.connect()
    builder.create_tables()
    builder.parse_and_load(merge_duplicates=merge_duplicates)
    builder.close()
    return db


def _intervals(db: Path, name: str) -> list[tuple[float, float]]:
    con = sqlite3.connect(db)
    try:
        return [
            (row[0], row[1])
            for row in con.execute(
                'SELECT ti.temp_min, ti.temp_max '
                'FROM temperature_intervals ti '
                'JOIN species s ON s.id = ti.species_id '
                'WHERE s.name = ? ORDER BY ti.interval_number',
                (name,),
            )
        ]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stray_coefficient_line_is_not_a_species(tmp_path: Path) -> None:
    """A coefficient line is never mistaken for a species header (Fix 1)."""
    db = _build(
        tmp_path,
        [
            '-1.302004763D+06 5.407120940D+02-1.596697810D+00 1.23D+01',
            _species_block('O2', 200.0, 1000.0),
        ],
        merge_duplicates=False,
    )

    con = sqlite3.connect(db)
    try:
        names = [row[0] for row in con.execute('SELECT name FROM species')]
        assert names == ['O2']
    finally:
        con.close()


def test_merge_disabled_keeps_first_record(tmp_path: Path) -> None:
    """Default (merge off): the repeated name is skipped, first record wins."""
    db = _build(
        tmp_path,
        [
            _species_block('Cr(cr)', 200.0, 1000.0),
            _species_block('Cr(cr)', 1000.0, 2000.0),
        ],
        merge_duplicates=False,
    )

    con = sqlite3.connect(db)
    try:
        assert con.execute('SELECT COUNT(*) FROM species').fetchone()[0] == 1
    finally:
        con.close()
    assert _intervals(db, 'Cr(cr)') == [(200.0, 1000.0)]


def test_merge_duplicates_contiguous(tmp_path: Path) -> None:
    """Merge on: contiguous repeated ranges become two intervals."""
    db = _build(
        tmp_path,
        [
            _species_block('Cr(cr)', 200.0, 1000.0),
            _species_block('Cr(cr)', 1000.0, 2000.0),
        ],
        merge_duplicates=True,
    )

    con = sqlite3.connect(db)
    try:
        assert con.execute('SELECT COUNT(*) FROM species').fetchone()[0] == 1
    finally:
        con.close()
    assert _intervals(db, 'Cr(cr)') == [(200.0, 1000.0), (1000.0, 2000.0)]


def test_merge_duplicates_identical_range(tmp_path: Path) -> None:
    """Merge on: an identical range is deduplicated."""
    db = _build(
        tmp_path,
        [
            _species_block('X', 200.0, 1000.0),
            _species_block('X', 200.0, 1000.0),
        ],
        merge_duplicates=True,
    )

    assert _intervals(db, 'X') == [(200.0, 1000.0)]


def test_merge_updates_num_intervals(tmp_path: Path) -> None:
    """After merging, species.num_intervals reflects the total row count."""
    db = _build(
        tmp_path,
        [
            _species_block('Cr(cr)', 200.0, 1000.0),
            _species_block('Cr(cr)', 1000.0, 2000.0),
        ],
        merge_duplicates=True,
    )

    con = sqlite3.connect(db)
    try:
        assert (
            con.execute(
                'SELECT num_intervals FROM species WHERE name = ?', ('Cr(cr)',)
            ).fetchone()[0]
            == 2
        )
    finally:
        con.close()


def test_bundled_rebuild_merge_recovers_intervals(tmp_path: Path) -> None:
    """Rebuilding the bundled thermo.inp with merging recovers 16 intervals."""
    inp = resources.files('pyglenn.data') / 'thermo.inp'
    db = tmp_path / 'thermo.db'

    builder = ThermoDBBuilder(str(inp), str(db))
    builder.connect()
    builder.create_tables()
    builder.parse_and_load(merge_duplicates=True)
    builder.close()

    con = sqlite3.connect(db)
    try:
        assert con.execute('SELECT COUNT(*) FROM species').fetchone()[0] == 2035
        assert (
            con.execute('SELECT COUNT(*) FROM temperature_intervals').fetchone()[0]
            == 3795
        )
        assert con.execute('SELECT COUNT(*) FROM coefficients').fetchone()[0] == 3795

        cr = con.execute(
            'SELECT temp_min, temp_max FROM temperature_intervals ti '
            'JOIN species s ON s.id = ti.species_id '
            'WHERE s.name = ? ORDER BY temp_min',
            ('Cr(cr)',),
        ).fetchall()
        assert len(cr) == 3
        assert cr[0][0] == pytest.approx(200.0)
        assert cr[-1][1] == pytest.approx(2130.0)
    finally:
        con.close()
