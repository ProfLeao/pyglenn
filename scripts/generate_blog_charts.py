#!/usr/bin/env python3
"""Generate the charts used by the pyglenn release blog posts.

Reads the UQ-1 error budget (``docs/audit/species_error.csv``), the Shomate
reference (``docs/audit/shomate_reference.json``) and the bundled database,
then writes PNG figures into ``docs/source/_static/blog/``.

Charts produced:

* ``cp_bias_by_species.png`` — mean relative Cp bias (%) per validated species;
* ``phase_detail_counts.png`` — species count by ``phase_detail``;
* ``ch4_cp_comparison.png`` — Cp(T) of CH4: pyglenn vs NIST-JANAF Shomate.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
ERROR_CSV = REPO_ROOT / 'docs' / 'audit' / 'species_error.csv'
SHOMATE_JSON = REPO_ROOT / 'docs' / 'audit' / 'shomate_reference.json'
OUT_DIR = REPO_ROOT / 'docs' / 'source' / '_static' / 'blog'


def read_error_csv() -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    with open(ERROR_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append((row['species'], float(row['cp_rel_bias_pct'])))
    return rows


def shomate_cp(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (
        coef['A']
        + coef['B'] * t
        + coef['C'] * t**2
        + coef['D'] * t**3
        + coef['E'] / t**2
    )


def get_coef(ranges: list[dict[str, float]], T: float) -> dict[str, float]:
    for r in ranges:
        if r['Tmin'] <= T <= r['Tmax']:
            return r
    raise ValueError(f'T={T} outside Shomate ranges')


def chart_cp_bias(out_path: Path) -> None:
    rows = read_error_csv()
    rows.sort(key=lambda pair: pair[1])
    names = [name for name, _ in rows]
    biases = [bias for _, bias in rows]

    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    colors = ['#c0392b' if b > 2.0 else ('#2980b9' if b < -2.0 else '#27ae60') for b in biases]
    ax.barh(names, biases, color=colors)
    ax.axvline(0.0, color='black', linewidth=0.8)
    ax.set_xlabel('Cp bias relativo médio (%)')
    ax.set_title('Concordância Cp: pyglenn vs NIST-JANAF')
    for i, b in enumerate(biases):
        ax.text(b + (0.15 if b >= 0 else -0.15), i, f'{b:+.1f}', va='center',
                ha='left' if b >= 0 else 'right', fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def chart_phase_detail(out_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / 'src'))
    from pyglenn import ThermochemicalCalculator

    with ThermochemicalCalculator() as calc:
        counts = {
            'gas': len(calc.get_available_species(phase_detail='gas')),
            'liquid': len(calc.get_available_species(phase_detail='liquid')),
            'solid': len(calc.get_available_species(phase_detail='solid')),
        }

    labels = ['Gás', 'Líquido', 'Sólido']
    values = [counts['gas'], counts['liquid'], counts['solid']]
    colors = ['#2980b9', '#e67e22', '#8e44ad']

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    bars = ax.bar(labels, values, color=colors)
    ax.set_ylabel('Número de espécies')
    ax.set_title('Espécies por estado físico (phase_detail)')
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 20, str(value),
                ha='center', fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def chart_ch4_cp(out_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / 'src'))
    from pyglenn import ThermochemicalCalculator

    with open(SHOMATE_JSON, encoding='utf-8') as f:
        reference = json.load(f)
    ch4_ranges = reference['species']['CH4']['ranges']

    temps = [300 + i * 50 for i in range(115)]  # 300..6000 K in 50 K steps
    with ThermochemicalCalculator() as calc:
        sid = calc.get_available_species('CH4', exact_match=True)[0].id
        pyglenn_cp = [calc.calculate_properties(sid, T).cp for T in temps]
    nist_cp = [shomate_cp(get_coef(ch4_ranges, T), T) for T in temps]

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(temps, pyglenn_cp, label='pyglenn (NASA-7)', color='#2980b9')
    ax.plot(temps, nist_cp, label='NIST-JANAF (Shomate)', color='#c0392b', linestyle='--')
    ax.set_xlabel('Temperatura (K)')
    ax.set_ylabel('Cp (J/(mol·K))')
    ax.set_title('Cp do CH4: dois conjuntos de dados')
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chart_cp_bias(OUT_DIR / 'cp_bias_by_species.png')
    chart_phase_detail(OUT_DIR / 'phase_detail_counts.png')
    chart_ch4_cp(OUT_DIR / 'ch4_cp_comparison.png')
    print(f'charts written to {OUT_DIR}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
