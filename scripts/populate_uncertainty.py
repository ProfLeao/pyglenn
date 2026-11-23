#!/usr/bin/env python3
"""Populate the ``species_uncertainty`` table from the validated error budget.

Reads ``docs/audit/species_error.csv`` (the UQ-1 pilot), fits a **per-phase**
tier model (gas / condensed) on the validated subset, and writes a per-species
uncertainty envelope for every species in the database:

* validated species  -> ``source='nist-janaf'`` with their own measured stats;
* all other species  -> ``source='extrapolated'`` with the tier statistics
  (zero bias, two-sigma spread pooled from the validated species of the same
  phase).

The operation is idempotent (upsert on ``species_id``) and leaves the
thermochemical rows untouched.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = REPO_ROOT / 'docs' / 'audit' / 'species_error.csv'
DEFAULT_DB = REPO_ROOT / 'src' / 'pyglenn' / 'data' / 'thermo.db'

TIERS = ('gas', 'condensed')


def _pooled_rms(values: list[float]) -> float | None:
    """Root mean square of a list, or None when the list is empty."""
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


def _two_sigma(values: list[float | None]) -> float | None:
    """Two-sigma spread (2 x RMS) of the non-None values, or None if empty."""
    present = [v for v in values if v is not None]
    rms = _pooled_rms(present)
    return 2 * rms if rms is not None else None


def _f(row: dict[str, str], key: str) -> float | None:
    """Return a CSV cell as float, or None when empty."""
    text = row.get(key, '').strip()
    return float(text) if text else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=DEFAULT_CSV)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / 'src'))

    from pyglenn.database import ThermoDBQuery

    if not args.csv.exists():
        print(f'ERROR: csv not found: {args.csv}', file=sys.stderr)
        return 1
    if not args.db.exists():
        print(f'ERROR: database not found: {args.db}', file=sys.stderr)
        return 1

    with open(args.csv, newline='', encoding='utf-8') as f:
        validated = list(csv.DictReader(f))

    by_phase: dict[str, list[dict[str, str]]] = {p: [] for p in TIERS}
    for row in validated:
        phase = row['phase']
        if phase in by_phase:
            by_phase[phase].append(row)

    # Two-sigma spread per phase, pooled over the validated species.
    tiers: dict[str, dict[str, float | None]] = {}
    for phase in TIERS:
        rows = by_phase[phase]
        tiers[phase] = {
            'cp_2sigma': _two_sigma([_f(r, 'cp_rel_rms_pct') for r in rows]),
            'h_2sigma': _two_sigma([_f(r, 'h_rel_rms_pct') for r in rows]),
            's_2sigma': _two_sigma([_f(r, 's_abs_rms_JmolK') for r in rows]),
        }

    query = ThermoDBQuery(str(args.db))
    if not query.connect():
        print('ERROR: could not connect to database', file=sys.stderr)
        return 1

    validated_rows: list[dict[str, object]] = []
    validated_ids: set[int] = set()
    for row in validated:
        found = query.find_species(row['species'], exact_match=True)
        if not found:
            print(
                f'WARNING: species not found in DB: {row["species"]}',
                file=sys.stderr,
            )
            continue
        species_id = found[0].id
        validated_ids.add(species_id)

        h_rms = _f(row, 'h_rel_rms_pct')
        tier = tiers[row['phase']]
        validated_rows.append(
            {
                'species_id': species_id,
                'cp_rel_bias': _f(row, 'cp_rel_bias_pct'),
                'cp_rel_2sigma': 2 * (_f(row, 'cp_rel_rms_pct') or 0.0),
                'h_rel_bias': _f(row, 'h_rel_bias_pct') or 0.0,
                'h_rel_2sigma': 2 * h_rms if h_rms is not None else tier['h_2sigma'],
                's_abs_2sigma': 2 * (_f(row, 's_abs_rms_JmolK') or 0.0),
                'n_ref_points': int(_f(row, 'n_points') or 0),
                'source': 'nist-janaf',
            }
        )

    extrapolated_rows: list[dict[str, object]] = []
    for info in query.list_all_species():
        if info.id in validated_ids:
            continue
        phase = info.phase if info.phase in TIERS else 'gas'
        tier = tiers.get(phase)
        if tier is None:
            print(f'WARNING: no tier for phase {phase!r}; skipping {info.name}')
            continue
        extrapolated_rows.append(
            {
                'species_id': info.id,
                'cp_rel_bias': 0.0,
                'cp_rel_2sigma': tier['cp_2sigma'],
                'h_rel_bias': 0.0,
                'h_rel_2sigma': tier['h_2sigma'],
                's_abs_2sigma': tier['s_2sigma'],
                'n_ref_points': 0,
                'source': 'extrapolated',
            }
        )

    written = query.populate_uncertainty(validated_rows + extrapolated_rows)

    for phase in TIERS:
        t = tiers[phase]
        print(
            f'tier {phase}: cp_2sigma={t["cp_2sigma"]:.3f}% '
            f'h_2sigma={t["h_2sigma"]:.3f}% '
            f's_2sigma={t["s_2sigma"]:.4f} J/(mol·K)'
        )
    print(
        f'populated {written} rows '
        f'({len(validated_rows)} nist-janaf, {len(extrapolated_rows)} extrapolated)'
    )

    report = query.validate_database()
    query.close()

    if not report['valid']:
        print('ERROR: validation failed', file=sys.stderr)
        for err in report['errors']:
            print(f'  - {err}', file=sys.stderr)
        return 1
    print('OK: database valid')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
