# pyglenn — Thermochemical Properties Calculator

[![CI](https://github.com/ProfLeao/pyglenn/actions/workflows/ci.yml/badge.svg)](https://github.com/ProfLeao/pyglenn/actions/workflows/ci.yml)
[![Docs](https://github.com/ProfLeao/pyglenn/actions/workflows/docs.yml/badge.svg)](https://profleao.github.io/pyglenn)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Computes **Cp(T)**, **H°(T)**, **S°(T)** from NASA polynomial coefficients stored in a SQLite database, converted from FORTRAN `thermo.inp` files.

**Author:** Dr. Reginaldo G. Leão Jr. — [prof.reginaldo.leao@gmail.com](mailto:prof.reginaldo.leao@gmail.com)

📖 **Documentation:** [profleao.github.io/pyglenn](https://profleao.github.io/pyglenn)

## Features

- Parse NASA-format `thermo.inp` (FORTRAN Appendix C) → SQLite3 database
- Query species by name, phase, molecular weight
- Calculate Cp(T), H°(T), S°(T) at any valid temperature
- Enthalpy of formation lookup
- Enthalpy change between two temperatures
- Command-line interface
- ~2030 species, 3772 temperature intervals

## Installation

### From PyPI (pip)

```bash
pip install pyglenn
```

### From source

```bash
git clone https://github.com/ProfLeao/pyglenn.git
cd pyglenn
pip install .
```

### Conda

```bash
conda install conda-forge::pyglenn
```

## Quick Start

The database is **bundled with the package** — no manual build step needed.

### Python API

```python
from pyglenn import ThermochemicalCalculator

# No need to specify a DB file — uses the bundled thermo.db
calc = ThermochemicalCalculator()
calc.connect()

# Find O2
species = calc.get_available_species('O2')
o2 = species[0]

# Calculate properties at 1000 K
props = calc.calculate_properties(o2['id'], 1000.0)
print(f"Cp = {props['cp']:.2f} J/(mol·K)")
print(f"H° = {props['h_relative']:.1f} J/mol")
print(f"S° = {props['s']:.3f} J/(mol·K)")

calc.close()
```

Or use the **context manager** for automatic cleanup:

```python
from pyglenn import ThermochemicalCalculator

with ThermochemicalCalculator() as calc:
    species = calc.get_available_species('CH4')
    props = calc.calculate_properties(species[0]['id'], 500.0)
    print(f"Cp = {props['cp']:.2f} J/(mol·K)")
```

### CLI

```bash
pyglenn query -s O2
```

### Rebuilding the database

Only needed if the database is corrupted or you modify ``thermo.inp`` manually:

```bash
pyglenn build -i thermo.inp -o thermo.db
```

## Database Structure

| Table | Description |
|---|---|
| `species` | Chemical species (name, formula, phase, MW, ΔH°f) |
| `temperature_intervals` | Valid T ranges per species |
| `coefficients` | NASA-7 polynomial coefficients (a1–a7, b1, b2) |
| `file_metadata` | Global file metadata |

## Citing

If you use pyglenn in your research, please cite it as:

```bibtex
@software{goncalves_leao_junior_2026_21324586,
  author    = {Gonçalves Leão Junior, Reginaldo},
  title     = {pyglenn: A Python Toolkit for Thermochemical
               Properties Calculation from NASA Polynomials},
  month     = jul,
  year      = 2026,
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21324586},
  url       = {https://doi.org/10.5281/zenodo.21324586},
}
```

## Requirements

- Python ≥ 3.9
- SQLite3 (stdlib)

## License

MIT — see [LICENSE](LICENSE) file.
