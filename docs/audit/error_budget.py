#!/usr/bin/env python3
"""
UQ-1 — Per-species thermochemical error budget.

Compares pyglenn (NASA-7 polynomials) against NIST-JANAF (Shomate equation)
for every species in ``shomate_reference.json`` and writes aggregated,
per-species error statistics to ``species_error.csv``.

Comparison convention:

- Cp : relative error in percent,  (Cp_pyglenn - Cp_NIST) / Cp_NIST * 100
- H  : sensible enthalpy ΔH(298.15 -> T), absolute error in J/mol and,
       where |H| >= H_REL_FLOOR, relative error in percent
- S  : absolute error in J/(mol*K), reported as bias, max and RMS

Sampling is log-spaced over the overlap between the pyglenn valid range and
the Shomate range, starting no lower than 300 K.
"""

from __future__ import annotations

import csv
import json
import math
import os
from typing import Any

from pyglenn import ThermochemicalCalculator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_FILE = os.path.join(SCRIPT_DIR, 'shomate_reference.json')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'species_error.csv')

N_POINTS = 16
T_FLOOR = 300.0
H_REL_FLOOR = 1000.0  # J/mol; below this relative H error is meaningless

CSV_FIELDS = [
    'species',
    'phase',
    'T_min',
    'T_max',
    'n_points',
    'cp_rel_bias_pct',
    'cp_rel_max_pct',
    'cp_rel_rms_pct',
    'h_abs_bias_Jmol',
    'h_abs_max_Jmol',
    's_abs_bias_JmolK',
    's_abs_max_JmolK',
    'h_rel_bias_pct',
    'h_rel_max_pct',
    'h_rel_rms_pct',
    's_abs_rms_JmolK',
]


def shomate_cp(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (
        coef['A']
        + coef['B'] * t
        + coef['C'] * t**2
        + coef['D'] * t**3
        + coef['E'] / t**2
    )


def shomate_h(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (
        coef['A'] * t
        + coef['B'] * t**2 / 2.0
        + coef['C'] * t**3 / 3.0
        + coef['D'] * t**4 / 4.0
        - coef['E'] / t
        + coef['F']
        - coef['H']
    )


def shomate_s(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (
        coef['A'] * math.log(t)
        + coef['B'] * t
        + coef['C'] * t**2 / 2.0
        + coef['D'] * t**3 / 3.0
        - coef['E'] / (2.0 * t**2)
        + coef['G']
    )


def get_coef(species: dict[str, Any], T: float) -> dict[str, float]:
    for r in species['ranges']:
        # Small tolerance so a sampled point at a range boundary (floating
        # point rounding) still resolves to a valid range.
        if r['Tmin'] - 1e-9 <= T <= r['Tmax'] + 1e-9:
            return r
    raise ValueError(f'T={T} outside Shomate ranges')


def rel_pct(calc: float, ref: float) -> float:
    return (calc - ref) / ref * 100.0


def collect() -> list[dict[str, Any]]:
    with open(REFERENCE_FILE, encoding='utf-8') as f:
        reference = json.load(f)
    rows: list[dict[str, Any]] = []

    with ThermochemicalCalculator() as calc:
        for name in sorted(reference['species']):
            nist = reference['species'][name]

            found = calc.get_available_species(name, exact_match=True)
            target = next((sp for sp in found if sp.phase == nist['phase']), None)
            if target is None:
                print(f'  ! {name} (phase={nist["phase"]}) not found in pyglenn')
                continue
            sid = target.id

            bounds = calc.db.get_temperature_bounds(sid)
            if bounds is None:
                continue
            t_min = max(bounds[0], nist['ranges'][0]['Tmin'], T_FLOOR)
            t_max = min(bounds[1], nist['ranges'][-1]['Tmax'])
            if t_max <= t_min:
                print(f'  ! {name}: empty overlap')
                continue

            temps = [
                math.exp(
                    math.log(t_min)
                    + (math.log(t_max) - math.log(t_min)) * i / (N_POINTS - 1)
                )
                for i in range(N_POINTS)
            ]

            cp_rel = []
            h_abs = []
            h_rel = []
            s_abs = []
            for T in temps:
                coef = get_coef(nist, T)
                props = calc.calculate_properties(sid, T)
                h_sensible = calc.h_sensible_to(sid, T)
                assert h_sensible is not None

                h_ref = shomate_h(coef, T) * 1000.0
                cp_rel.append(rel_pct(props.cp, shomate_cp(coef, T)))
                h_abs.append(h_sensible - h_ref)
                if abs(h_ref) >= H_REL_FLOOR:
                    h_rel.append(rel_pct(h_sensible, h_ref))
                s_abs.append(props.s - shomate_s(coef, T))

            rows.append(
                {
                    'species': name,
                    'phase': nist['phase'],
                    'T_min': round(t_min, 1),
                    'T_max': round(t_max, 1),
                    'n_points': len(temps),
                    'cp_rel_bias_pct': round(sum(cp_rel) / len(cp_rel), 4),
                    'cp_rel_max_pct': round(max(abs(e) for e in cp_rel), 4),
                    'cp_rel_rms_pct': round(
                        math.sqrt(sum(e * e for e in cp_rel) / len(cp_rel)), 4
                    ),
                    'h_abs_bias_Jmol': round(sum(h_abs) / len(h_abs), 2),
                    'h_abs_max_Jmol': round(max(abs(e) for e in h_abs), 2),
                    's_abs_bias_JmolK': round(sum(s_abs) / len(s_abs), 4),
                    's_abs_max_JmolK': round(max(abs(e) for e in s_abs), 4),
                    'h_rel_bias_pct': (
                        round(sum(h_rel) / len(h_rel), 4) if h_rel else None
                    ),
                    'h_rel_max_pct': (
                        round(max(abs(e) for e in h_rel), 4) if h_rel else None
                    ),
                    'h_rel_rms_pct': (
                        round(math.sqrt(sum(e * e for e in h_rel) / len(h_rel)), 4)
                        if h_rel
                        else None
                    ),
                    's_abs_rms_JmolK': round(
                        math.sqrt(sum(e * e for e in s_abs) / len(s_abs)), 4
                    ),
                }
            )
            print(
                f'  {name:<4} T={rows[-1]["T_min"]:g}-{rows[-1]["T_max"]:g} K | '
                f'Cp bias {rows[-1]["cp_rel_bias_pct"]:+.3f}% '
                f'(max {rows[-1]["cp_rel_max_pct"]:.3f}%) | '
                f'S bias {rows[-1]["s_abs_bias_JmolK"]:+.3f} J/(mol·K)'
            )

    return rows


def write_csv(rows: list[dict[str, Any]]) -> None:
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in CSV_FIELDS})


def main() -> int:
    rows = collect()
    write_csv(rows)
    print(f'wrote {len(rows)} rows -> {OUTPUT_FILE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
