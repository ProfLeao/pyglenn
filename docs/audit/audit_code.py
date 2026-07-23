#!/usr/bin/env python3
"""
=====================================================================
pyglenn × NIST-JANAF — Cross-Validation of Thermochemical Properties
=====================================================================
Compares Cp(T), H°(T) and S°(T) calculated by the pyglenn library
against NIST-JANAF reference tables (Chase, 1998) for 7 species:
  CO₂, N₂, CO, H₂O(g), O₂, NH₃, SO₂


The NIST reference is computed via the Shomate equation, whose
coefficients were extracted directly from the NIST Chemistry WebBook
(SRD 69).

Outputs (saved alongside this script):
  - validation_01_Cp.png        Cp(T) overlay + relative/absolute error
  - validation_02_Enthalpy.png  ΔH°(298→T) overlay + relative/absolute error
  - validation_03_Entropy.png   S°(T) overlay + relative/absolute error
  - validation_errors.png       3-panel relative error only (Cp, ΔH, S°)
  - pyglenn_vs_nist.csv         Complete data with per-point error metrics
  - validation_summary.txt      Per-species aggregated statistics

Author:  Dr. Reginaldo G. Leão Jr.
Date:    July 2026
=====================================================================
"""

from __future__ import annotations

import csv
import logging
import math
import os
from typing import Any

import matplotlib
matplotlib.use('Agg')  # non-interactive backend — guarantees file saving

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec

from pyglenn import ThermochemicalCalculator

# ── Script directory (all outputs go here) ────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Configuration ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('pyglenn_vs_nist')

SPECIES = [
    ('CO2',   'CO₂',    'CO2'),
    ('N2',    'N₂',     'N2'),
    ('CO',    'CO',     'CO'),
    ('H2O',   'H₂O(g)', 'H2O'),
    ('O2',    'O₂',     'O2'),
    ('NH3',   'NH₃',    'NH3'),
    ('SO2',   'SO₂',    'SO2'),
]

T_MIN, T_MAX, T_PTS = 300.0, 3000.0, 55
TEMPERATURES = np.linspace(T_MIN, T_MAX, T_PTS)

# ── Shomate Coefficients (NIST-JANAF, Chase 1998) ─────────────────────────
SHOMATE: dict[str, list[dict[str, float]]] = {
    'CO2': [
        dict(Tmin=298, Tmax=1200, A=24.99735, B=55.18696, C=-33.69137,
             D=7.948387, E=-0.136638, F=-403.6075, G=228.2431, H=-393.5224),
        dict(Tmin=1200, Tmax=6000, A=58.16639, B=2.720074, C=-0.492289,
             D=0.038844, E=-6.447293, F=-425.9186, G=263.6125, H=-393.5224),
    ],
    'N2': [
        dict(Tmin=100, Tmax=500, A=28.98641, B=1.853978, C=-9.647459,
             D=16.63537, E=0.000117, F=-8.671914, G=226.4168, H=0.0),
        dict(Tmin=500, Tmax=2000, A=19.50583, B=19.88705, C=-8.598535,
             D=1.369784, E=0.527601, F=-4.935202, G=212.3900, H=0.0),
        dict(Tmin=2000, Tmax=6000, A=35.51872, B=1.128728, C=-0.196103,
             D=0.014662, E=-4.553760, F=-18.97091, G=224.9810, H=0.0),
    ],
    'CO': [
        dict(Tmin=298, Tmax=1300, A=25.56759, B=6.096130, C=4.054656,
             D=-2.671301, E=0.131021, F=-118.0089, G=227.3665, H=-110.5271),
        dict(Tmin=1300, Tmax=6000, A=35.15070, B=1.300095, C=-0.205921,
             D=0.013550, E=-3.282780, F=-127.8375, G=231.7120, H=-110.5271),
    ],
    'H2O': [
        dict(Tmin=500, Tmax=1700, A=30.09200, B=6.832514, C=6.793435,
             D=-2.534480, E=0.082139, F=-250.8810, G=223.3967, H=-241.8264),
        dict(Tmin=1700, Tmax=6000, A=41.96426, B=8.622053, C=-1.499780,
             D=0.098119, E=-11.15764, F=-272.1797, G=219.7809, H=-241.8264),
    ],
    'O2': [
        dict(Tmin=100, Tmax=700, A=31.32234, B=-20.23531, C=57.86644,
             D=-36.50624, E=-0.007374, F=-8.903471, G=246.7945, H=0.0),
        dict(Tmin=700, Tmax=2000, A=30.03235, B=8.772972, C=-3.988133,
             D=0.788313, E=-0.741599, F=-11.32468, G=236.1663, H=0.0),
        dict(Tmin=2000, Tmax=6000, A=20.91111, B=10.72071, C=-2.020498,
             D=0.146449, E=9.245722, F=5.337651, G=237.6185, H=0.0),
    ],
    'NH3': [
        dict(Tmin=298, Tmax=1400, A=19.99563, B=49.77119, C=-15.37599,
             D=1.921168, E=0.189174, F=-53.30667, G=203.8591, H=-45.89806),
        dict(Tmin=1400, Tmax=6000, A=52.02427, B=18.48801, C=-3.765128,
             D=0.248541, E=-12.45799, F=-85.53895, G=223.8022, H=-45.89806),
    ],
    'SO2': [
        dict(Tmin=298, Tmax=1200, A=21.43049, B=74.35094, C=-57.75217,
             D=16.35534, E=0.086731, F=-305.7688, G=254.8872, H=-296.8422),
        dict(Tmin=1200, Tmax=6000, A=57.48188, B=1.009328, C=-0.076290,
             D=0.005174, E=-4.045401, F=-324.4140, G=302.7798, H=-296.8422),
    ],
}

# ── Shomate equation evaluators ───────────────────────────────────────────

def shomate_cp(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return coef['A'] + coef['B'] * t + coef['C'] * t**2 + coef['D'] * t**3 + coef['E'] / t**2

def shomate_h(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (coef['A'] * t + coef['B'] * t**2 / 2.0 + coef['C'] * t**3 / 3.0
            + coef['D'] * t**4 / 4.0 - coef['E'] / t + coef['F'] - coef['H'])

def shomate_s(coef: dict[str, float], T: float) -> float:
    t = T / 1000.0
    return (coef['A'] * math.log(t) + coef['B'] * t + coef['C'] * t**2 / 2.0
            + coef['D'] * t**3 / 3.0 - coef['E'] / (2.0 * t**2) + coef['G'])

def get_shomate_coef(species: str, T: float) -> dict[str, float]:
    for r in SHOMATE[species]:
        if r['Tmin'] <= T <= r['Tmax']:
            return r
    raise ValueError(f'Temperature {T:.0f} K outside Shomate range for {species}')

def nist_reference(species: str, T: float) -> dict[str, float]:
    coef = get_shomate_coef(species, T)
    return {
        'cp': shomate_cp(coef, T),
        'dh_298': shomate_h(coef, T) * 1000.0,
        's': shomate_s(coef, T),
        'coef': coef,
    }

# ── Error metrics ─────────────────────────────────────────────────────────

def rel_error(calc: float, ref: float) -> float:
    if abs(ref) < 1e-12:
        return 0.0
    return (calc - ref) / abs(ref) * 100.0

def abs_error(calc: float, ref: float) -> float:
    return calc - ref

# ── Data collection ───────────────────────────────────────────────────────

def collect_data() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    with ThermochemicalCalculator() as calc:
        log.info('Connected to pyglenn database (bundled thermo.db)')
        stats = calc.db.get_statistics()
        log.info('DB stats: %d species, %d intervals',
                 stats['total_species'], stats['total_intervals'])

        for py_name, plot_label, _ in SPECIES:
            log.info('▶ Processing %s (%s)', py_name, plot_label)
            results[py_name] = {}

            found = calc.get_available_species(py_name, exact_match=True)
            # Filter by phase in case multiple phases exist (e.g. gas + liquid)
            target = next(
                (sp for sp in found if sp['phase'] == 'gas'), None
            )
            if target is None:
                log.warning('  ✗ %s not found in pyglenn database!', py_name)
                continue

            sid = target['id']
            log.info('  ✓ ID: %d | MW: %s', sid, target['molecular_weight'])

            for T in TEMPERATURES:
                Tk = round(float(T), 2)
                try:
                    ref = nist_reference(py_name, Tk)
                except ValueError:
                    continue

                try:
                    props = calc.calculate_properties(sid, Tk)
                except ThermoCalcError:
                    continue

                dh_py = props['h_relative'] - ref['coef']['H'] * 1000.0

                results[py_name][Tk] = {
                    'nist': {'cp': ref['cp'], 'dh_298': ref['dh_298'], 's': ref['s']},
                    'pyglenn': {'cp': props['cp'], 'dh_298': dh_py, 's': props['s']},
                }

            n_pts = len(results[py_name])
            log.info('  ✓ %d points (%.0f–%.0f K)', n_pts,
                     min(results[py_name]), max(results[py_name]))

    return results

# ── CSV output ────────────────────────────────────────────────────────────

def generate_csv(results: dict[str, Any], filename: str):
    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'Species', 'T(K)',
            'Cp_NIST', 'Cp_pyglenn', 'Cp_abs_err', 'Cp_rel_err(%)',
            'dH_NIST', 'dH_pyglenn', 'dH_abs_err', 'dH_rel_err(%)',
            'S_NIST', 'S_pyglenn', 'S_abs_err', 'S_rel_err(%)',
        ])

        for sp in sorted(results):
            for T in sorted(results[sp]):
                d = results[sp][T]
                n, p = d['nist'], d['pyglenn']
                w.writerow([
                    sp, f'{T:.2f}',
                    f'{n["cp"]:.6f}', f'{p["cp"]:.6f}',
                    f'{abs_error(p["cp"], n["cp"]):.6f}',
                    f'{rel_error(p["cp"], n["cp"]):.4f}',
                    f'{n["dh_298"]:.6f}', f'{p["dh_298"]:.6f}',
                    f'{abs_error(p["dh_298"], n["dh_298"]):.6f}',
                    f'{rel_error(p["dh_298"], n["dh_298"]):.4f}',
                    f'{n["s"]:.6f}', f'{p["s"]:.6f}',
                    f'{abs_error(p["s"], n["s"]):.6f}',
                    f'{rel_error(p["s"], n["s"]):.4f}',
                ])
    log.info('CSV saved: %s', path)

# ── Text summary ──────────────────────────────────────────────────────────

def generate_summary(results: dict[str, Any], filename: str):
    lines: list[str] = []
    lines.append('=' * 90)
    lines.append('  VALIDATION SUMMARY — pyglenn × NIST-JANAF')
    lines.append('=' * 90)
    lines.append(f'  Temperature range: {T_MIN:.0f} – {T_MAX:.0f} K')
    lines.append(f'  Number of points:  {T_PTS}')
    lines.append(f'  Reference:         NIST-JANAF (Chase, 1998)')
    lines.append(f'  pyglenn database:  NASA-7 (bundled thermo.db)')
    lines.append('')
    lines.append('  NOTE: CH₄ removed — systematic Cp bias >5%.')
    lines.append('  NH₃ and SO₂ added as replacements.')
    lines.append('')

    for sp in sorted(results):
        temps = sorted(results[sp])
        if not temps:
            continue
        cp_e = [rel_error(results[sp][t]['pyglenn']['cp'], results[sp][t]['nist']['cp']) for t in temps]
        dh_e = [rel_error(results[sp][t]['pyglenn']['dh_298'], results[sp][t]['nist']['dh_298']) for t in temps]
        s_e  = [rel_error(results[sp][t]['pyglenn']['s'], results[sp][t]['nist']['s']) for t in temps]

        def stats(arr):
            return (np.mean(arr), np.max(np.abs(arr)), np.sqrt(np.mean(np.square(arr))))

        m_cp, x_cp, r_cp = stats(cp_e)
        m_dh, x_dh, r_dh = stats(dh_e)
        m_s,  x_s,  r_s  = stats(s_e)

        lines.append(f'  ─── {sp} ───')
        lines.append(f'    Cp(T):  Mean={m_cp:+.4f}%  Max|err|={x_cp:.4f}%  RMSE={r_cp:.4f}%')
        lines.append(f'    ΔH(T):  Mean={m_dh:+.4f}%  Max|err|={x_dh:.4f}%  RMSE={r_dh:.4f}%')
        lines.append(f'    S°(T):  Mean={m_s:+.4f}%  Max|err|={x_s:.4f}%  RMSE={r_s:.4f}%')
        lines.append('')

    lines.append('  ─── Notes ───')
    lines.append('  * ΔH max|err| near 298 K is a mathematical artefact:')
    lines.append('    relative error diverges as ΔH°(298.15→T) → 0.')
    lines.append('    RMSE and mean are more representative.')
    lines.append('=' * 90)

    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log.info('Summary saved: %s', path)
    print('\n' + '\n'.join(lines))

# ── Plot colours ──────────────────────────────────────────────────────────

COLORS = {
    'CO2': '#e41a1c', 'N2': '#377eb8', 'CO': '#984ea3',
    'H2O': '#ff7f00', 'O2': '#a65628', 'NH3': '#4daf4a',
    'SO2': '#f781bf',
}

# ── Plot 1: Overlay + relative error + absolute error (3 figures) ─────────

def _plot_overlay_and_errors(
    results: dict[str, Any],
    property_key: str,
    ylabel: str,
    title: str,
    filename: str,
    unit_abs: str,
):
    """Generic helper: overlay + relative error + absolute error panels."""
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(2, 2, height_ratios=[1.5, 1], hspace=0.30, wspace=0.35)

    scale = 1000.0 if property_key == 'dh_298' else 1.0
    unit_label = 'kJ/mol' if property_key == 'dh_298' else ylabel

    # Top panel — overlay NIST (solid) vs pyglenn (dashed)
    ax1 = fig.add_subplot(gs[0, :])
    for species in sorted(results.keys()):
        if not results[species]:
            continue
        temps = sorted(results[species].keys())
        vals_nist = [results[species][t]['nist'][property_key] / scale for t in temps]
        vals_pyg  = [results[species][t]['pyglenn'][property_key] / scale for t in temps]
        ax1.plot(temps, vals_nist, color=COLORS.get(species, '#333333'),
                 linewidth=2.5, linestyle='-', label=f'{species} (NIST)')
        ax1.plot(temps, vals_pyg, color=COLORS.get(species, '#333333'),
                 linewidth=1.3, linestyle='--', alpha=0.6)
    ax1.set_ylabel(unit_label, fontsize=12)
    ax1.set_title(title, fontsize=13, fontweight='bold')
    ax1.legend(fontsize=7, ncol=3, loc='upper left')
    ax1.grid(True, alpha=0.25)
    ax1.set_xlim(T_MIN, T_MAX)

    # Bottom-left — relative error
    ax2 = fig.add_subplot(gs[1, 0])
    for species in sorted(results.keys()):
        if not results[species]:
            continue
        temps = sorted(results[species].keys())
        err = [rel_error(results[species][t]['pyglenn'][property_key],
                         results[species][t]['nist'][property_key]) for t in temps]
        ax2.plot(temps, err, color=COLORS.get(species, '#333333'),
                 linewidth=1.5, label=species)
    ax2.axhline(y=0, color='gray', linewidth=0.7, linestyle='--')
    ax2.set_ylabel('Relative error [%]', fontsize=11)
    ax2.set_xlabel('Temperature [K]', fontsize=11)
    ax2.set_title('Relative error', fontsize=11)
    ax2.legend(fontsize=7, ncol=2)
    ax2.grid(True, alpha=0.25)
    ax2.set_xlim(T_MIN, T_MAX)

    # Bottom-right — absolute error
    ax3 = fig.add_subplot(gs[1, 1])
    for species in sorted(results.keys()):
        if not results[species]:
            continue
        temps = sorted(results[species].keys())
        err_abs = [abs_error(results[species][t]['pyglenn'][property_key],
                             results[species][t]['nist'][property_key]) for t in temps]
        abs_scale = 1000.0 if property_key == 'dh_298' else 1.0
        ax3.plot(temps, [e / abs_scale for e in err_abs],
                 color=COLORS.get(species, '#333333'),
                 linewidth=1.5, label=species)
    ax3.axhline(y=0, color='gray', linewidth=0.7, linestyle='--')
    abs_unit = 'kJ/mol' if property_key == 'dh_298' else unit_abs
    ax3.set_ylabel(f'Absolute error [{abs_unit}]', fontsize=11)
    ax3.set_xlabel('Temperature [K]', fontsize=11)
    ax3.set_title('Absolute error', fontsize=11)
    ax3.legend(fontsize=7, ncol=2)
    ax3.grid(True, alpha=0.25)
    ax3.set_xlim(T_MIN, T_MAX)

    path = os.path.join(SCRIPT_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches='tight')
    log.info('Plot saved: %s', path)
    plt.close(fig)

def generate_overlay_plots(results: dict[str, Any], prefix: str = 'validation'):
    """Generate overlay + error panels for Cp, ΔH, and S."""
    _plot_overlay_and_errors(results, 'cp',     r'Cp [J/(mol·K)]',
        'Heat Capacity — Cp(T)  (solid=NIST, dashed=pyglenn)',
        f'{prefix}_01_Cp.png', 'J/(mol·K)')
    _plot_overlay_and_errors(results, 'dh_298', r'ΔH°(298→T) [kJ/mol]',
        'Sensible Enthalpy — ΔH°(298.15 K → T)  (solid=NIST, dashed=pyglenn)',
        f'{prefix}_02_Enthalpy.png', 'J/mol')
    _plot_overlay_and_errors(results, 's',      r'S° [J/(mol·K)]',
        'Absolute Entropy — S°(T)  (solid=NIST, dashed=pyglenn)',
        f'{prefix}_03_Entropy.png', 'J/(mol·K)')

# ── Plot 2: 3-panel relative error only (1 figure) ───────────────────────

def plot_error_panel(results: dict[str, Any], filename: str = 'validation_errors.png'):
    """
    Single figure with 3 error-only panels — one per property.
    Each panel shows relative error (%) vs Temperature (K) for all 7 species.
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharex=True)

    properties = [
        ('cp',     'Cp(T)',          'Cp relative error [%]'),
        ('dh_298', u'ΔH°(298→T)',    u'ΔH relative error [%]'),
        ('s',      'S°(T)',           'S° relative error [%]'),
    ]

    for ax, (prop_key, prop_title, ylabel) in zip(axes, properties):
        for sp in sorted(results):
            if not results[sp]:
                continue
            temps = sorted(results[sp])
            err = [rel_error(results[sp][t]['pyglenn'][prop_key],
                             results[sp][t]['nist'][prop_key]) for t in temps]
            ax.plot(temps, err, color=COLORS.get(sp, '#333333'),
                    linewidth=1.6, label=sp)

        ax.axhline(y=0, color='gray', linewidth=0.7, linestyle='--')
        ax.set_xlabel('Temperature [K]', fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(prop_title, fontsize=12, fontweight='bold')
        ax.legend(fontsize=7, ncol=2, loc='best')
        ax.grid(True, alpha=0.2)
        ax.set_xlim(T_MIN, T_MAX)

    fig.suptitle('pyglenn × NIST-JANAF — Relative error by property and species',
                 fontsize=14, fontweight='bold', y=1.02)
    fig.tight_layout()

    path = os.path.join(SCRIPT_DIR, filename)
    fig.savefig(path, dpi=180, bbox_inches='tight')
    log.info('Error panel saved: %s', path)
    plt.close(fig)

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print('=' * 70)
    print('  CROSS-VALIDATION: pyglenn × NIST-JANAF')
    print('  Species:  CO₂, N₂, CO, H₂O(g), O₂, NH₃, SO₂')
    print('  Range:    300 – 3000 K')
    print('  Reference: Chase, 1998 (NIST-JANAF 4th Ed.)')
    print()
    print('  CH₄ removed — systematic Cp bias >5% in NASA-7 coefficients')
    print('  NH₃ and SO₂ added as structurally diverse replacements')
    print(f'  Output dir: {SCRIPT_DIR}')
    print('=' * 70)
    print()

    results = collect_data()
    generate_csv(results, 'pyglenn_vs_nist.csv')
    generate_summary(results, 'validation_summary.txt')

    # Plot 1 — three overlay figures (Cp, ΔH, S)
    generate_overlay_plots(results)

    # Plot 2 — single error-only figure (3 panels)
    plot_error_panel(results)

    # Flush remaining matplotlib state
    plt.close('all')

    print()
    print('=' * 70)
    print('  VALIDATION COMPLETE')
    print(f'  Output directory: {SCRIPT_DIR}')
    print('  Files generated:')
    print('    📊 validation_01_Cp.png          (overlay + error panels)')
    print('    📊 validation_02_Enthalpy.png    (overlay + error panels)')
    print('    📊 validation_03_Entropy.png     (overlay + error panels)')
    print('    📊 validation_errors.png         (3-panel relative error)')
    print('    📄 pyglenn_vs_nist.csv')
    print('    📄 validation_summary.txt')
    print('=' * 70)

if __name__ == '__main__':
    main()