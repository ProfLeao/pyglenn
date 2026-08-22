#!/usr/bin/env python3
"""Rebuild the bundled pyglenn database from thermo.inp, atomically.

The database is built into a temporary file, validated, and only replaces the
bundled ``thermo.db`` after every release gate passes. A failed rebuild leaves
the previous database untouched.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INP = REPO_ROOT / 'src' / 'pyglenn' / 'data' / 'thermo.inp'
DEFAULT_DB = REPO_ROOT / 'src' / 'pyglenn' / 'data' / 'thermo.db'

# Release gates for the canonical NASA Glenn/CEA dataset.
EXPECTED_SPECIES = 2035
EXPECTED_INTERVALS = 3779
EXPECTED_COEFFS = 3779


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-i', '--input', type=Path, default=DEFAULT_INP)
    parser.add_argument('-o', '--output', type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / 'src'))

    from pyglenn.builder import ThermoDBBuilder
    from pyglenn.database import ThermoDBQuery

    inp: Path = args.input
    out: Path = args.output
    if not inp.exists():
        print(f'ERROR: input file not found: {inp}', file=sys.stderr)
        return 1

    tmp_dir = tempfile.mkdtemp(prefix='pyglenn-rebuild-')
    tmp_db = Path(tmp_dir) / 'thermo.db'

    try:
        builder = ThermoDBBuilder(str(inp), str(tmp_db))
        builder.connect()
        builder.create_tables()
        builder.parse_and_load()
        builder.close()
    except Exception:
        print(
            'ERROR: build failed; bundled database left untouched',
            file=sys.stderr,
        )
        raise

    query = ThermoDBQuery(str(tmp_db))
    if not query.connect():
        print('ERROR: could not reopen temporary database', file=sys.stderr)
        return 1
    report = query.validate_database()
    query.close()

    if not report['valid']:
        print('ERROR: validation failed', file=sys.stderr)
        for err in report['errors']:
            print(f'  - {err}', file=sys.stderr)
        return 1

    counts = report['counts']
    gate_failures = []
    if counts['total_species'] != EXPECTED_SPECIES:
        gate_failures.append(
            f"species {counts['total_species']} != {EXPECTED_SPECIES}"
        )
    if counts['total_intervals'] != EXPECTED_INTERVALS:
        gate_failures.append(
            f"intervals {counts['total_intervals']} != {EXPECTED_INTERVALS}"
        )
    if counts['total_coeff_sets'] != EXPECTED_COEFFS:
        gate_failures.append(
            f"coefficients {counts['total_coeff_sets']} != {EXPECTED_COEFFS}"
        )
    if gate_failures:
        print('ERROR: release gates failed', file=sys.stderr)
        for failure in gate_failures:
            print(f'  - {failure}', file=sys.stderr)
        return 1

    os.replace(tmp_db, out)
    print(f'OK: rebuilt database -> {out}')
    print(
        f"    species={counts['total_species']} "
        f"intervals={counts['total_intervals']} "
        f"coefficients={counts['total_coeff_sets']}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
