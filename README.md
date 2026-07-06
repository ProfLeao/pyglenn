# pythermo — Thermochemical Properties Calculator

Computes **Cp(T)**, **H°(T)**, **S°(T)** from NASA polynomial coefficients stored in a SQLite database, converted from FORTRAN `thermo.inp` files.

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
pip install pythermo
```

### From source

```bash
git clone https://github.com/profr/pyglenn_novo.git
cd pyglenn_novo
pip install .
```

### Conda

```bash
conda build conda.recipe/
conda install --use-local pythermo
```

## Quick Start

### Build the database (first time only)

```bash
pythermo build -i thermo.inp -o thermo.db
```

### Query species and calculate properties

```bash
pythermo query -s O2
```

### Python API

```python
from pythermo import ThermochemicalCalculator

calc = ThermochemicalCalculator("thermo.db")
calc.connect()

# Find O2
species = calc.get_available_species("O2")
o2 = species[0]

# Calculate properties at 1000 K
props = calc.calculate_properties(o2['id'], 1000.0)
print(f"Cp = {props['cp']:.2f} J/(mol·K)")
print(f"H° = {props['h_relative']:.1f} J/mol")
print(f"S° = {props['s']:.3f} J/(mol·K)")

calc.close()
```

## Database Structure

| Table | Description |
|---|---|
| `species` | Chemical species (name, formula, phase, MW, ΔH°f) |
| `temperature_intervals` | Valid T ranges per species |
| `coefficients` | NASA-7 polynomial coefficients (a1–a7, b1, b2) |
| `file_metadata` | Global file metadata |

## Requirements

- Python ≥ 3.9
- SQLite3 (stdlib)

## License

MIT — see [LICENSE](LICENSE) file.
