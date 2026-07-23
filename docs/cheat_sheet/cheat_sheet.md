ProfLeao / pyglenn

PYGLENN CHEAT SHEET

Comprehensive API Reference and Usage Guide

---

## 1. Overview

**pyglenn** is a high-performance Python library designed to compute thermochemical properties (:math:`C_p(T)`, :math:`H^\circ(T)`, :math:`S^\circ(T)`) using the standard NASA-7 polynomial form. It ships with a bundled SQLite database containing approximately **2030 species** and **3772 temperature intervals** derived from the NASA Glenn coefficients.

**Key Features:**
- **Zero external dependencies**: Built entirely on the Python standard library (SQLite3).
- **High Precision**: Implements the CODATA 2018 universal gas constant.
- **Portable**: Bundled database ensures immediate functionality upon installation.
- **Robust**: Comprehensive exception handling for engineering and scientific applications.

---

## 2. Installation

Install via PyPI:
```bash
pip install pyglenn
```

Install via Conda (conda-forge):
```bash
conda install conda-forge::pyglenn
```

Install from source:
```bash
git clone https://github.com/ProfLeao/pyglenn.git
cd pyglenn
pip install .
```

---

## 3. Imports

The public API exposes the main calculator, database utilities, and a specific exception hierarchy.

```python
from pyglenn import (
    ThermochemicalCalculator,
    ThermoDBQuery,
    ThermoDBBuilder,
    R,
    ThermoCalcError,
    DatabaseNotConnectedError,
    SpeciesNotFoundError,
    TemperatureOutOfRangeError,
)
```

---

## 4. ThermochemicalCalculator — Main API

### 4.1 Connection
The `ThermochemicalCalculator` manages the high-level interaction with the thermochemical database.

| Method / Property | Description |
| :--- | :--- |
| `ThermochemicalCalculator(db_file=None)` | Constructor. Uses bundled `thermo.db` if `db_file` is `None`. |
| `.connect()` | Opens the SQLite connection. Returns `True` if successful. |
| `.close()` | Closes the database connection. |
| `.connected` | Boolean property indicating the current connection status. |

### 4.2 Context Manager (Recommended)
Using the context manager ensures that the database connection is automatically opened and safely closed.

```python
with ThermochemicalCalculator() as calc:
    # Connection is open here
    props = calc.calculate_properties(species_id=1, temperature=1000.0)
# Connection is closed here
```

### 4.3 Species Lookup
Search for species in the database using patterns or exact names.

```python
get_available_species(search_pattern: str = '', exact_match: bool = False)
```

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `search_pattern` | `str` | Substring or exact name to search for. |
| `exact_match` | `bool` | If `True`, performs a case-insensitive exact match. |


Nota: Since version 0.1.10, setting exact_match=True is highly recommended to avoid substring confusion (e.g., searching for 'N2' and getting 'Be3N2').


### 4.4 Calculating Properties
Compute thermochemical data for a specific species at a given temperature.

| Return Key | Unit | Description |
| :--- | :--- | :--- |
| `temperature` | K | The input temperature. |
| `cp` | J/(mol·K) | Constant pressure heat capacity. |
| `h_relative` | J/mol | Enthalpy relative to 0 K. |
| `s` | J/(mol·K) | Absolute entropy. |
| `temp_interval` | [K, K] | The valid temperature range for the coefficients used. |

**Method signature:**

```python
calculate_properties(species_id: int, temperature: float) -> dict
```
| `species_name` | str | Name of the species. |
| `phase` | str | Physical phase ('gas' or 'condensed'). |

**Exceptions raised:**

| Exception | Trigger |
|---|---|
| `DatabaseNotConnectedError` | `.connect()` was not called |
| `SpeciesNotFoundError` | `species_id` does not exist |
| `TemperatureOutOfRangeError` | Temperature outside valid intervals |

### 4.5 Enthalpy Utilities
Methods for formation data and enthalpy changes.

- `calculate_formation_enthalpy(species_id: int)`: Returns the standard enthalpy of formation at **298.15 K** in J/mol.
- `calculate_enthalpy_change(species_id: int, T1: float, T2: float)`: Returns the sensible enthalpy change :math:`\Delta H = H(T_2) - H(T_1)` in J/mol.

### 4.6 Batch Evaluation
Efficiently calculate properties for a list of temperatures.

```python
get_properties_range(species_id: int, temps: list[float])
```
**Returns:** A dictionary mapping each temperature to its corresponding property dictionary. Temperatures outside the valid range are omitted from the result.

---

## 5. ThermoDBQuery — Low-Level API

The `ThermoDBQuery` class provides direct access to the SQLite schema and raw coefficient data.

| Method | Description |
| :--- | :--- |
| `.get_statistics()` | Returns a summary of the database (total species, intervals, etc.). |
| `.find_species(name, exact_match)` | Low-level SQL search for species records. |
| `.get_species_data(species_id)` | Retrieves all metadata and intervals for a specific ID. |
| `.get_species_for_temperature(sid, T)` | Finds the specific coefficient set valid for temperature T. |

### 5.1 Standalone NASA-7 Evaluators
Static methods for manual polynomial evaluation. These return **dimensionless** values.

- `ThermoDBQuery.calculate_cp(coeffs, T)`: Returns :math:`C_p/R`.
- `ThermoDBQuery.calculate_h(coeffs, T)`: Returns :math:`H^\circ/RT`.
- `ThermoDBQuery.calculate_s(coeffs, T)`: Returns :math:`S^\circ/R`.

---

## 6. ThermoDBBuilder — FORTRAN to SQLite

Utility for generating the SQLite database from raw NASA Glenn `thermo.inp` files.

| Method | Description |
| :--- | :--- |
| `.connect()` | Initializes the SQLite file with WAL mode and foreign keys. |
| `.create_tables()` | Executes the DDL to create the normalized schema. |
| `.parse_and_load()` | Orchestrates the parsing of the input file and DB insertion. |
| `.parse_float(val)` | Static helper to convert FORTRAN `D` notation to Python `float`. |
| `.is_temperature_line(line)` | Identifies RECORD 3 in the NASA format. |

---

## 7. Constants & Exceptions

**Universal Gas Constant:**
- `R = 8.314462618` J/(mol·K) (CODATA 2018)

**Exception Hierarchy:**
- `ThermoCalcError` (Base)
  - `DatabaseNotConnectedError`
  - `SpeciesNotFoundError`
  - `TemperatureOutOfRangeError`

---

## 8. NASA-7 Polynomial Form

pyglenn uses the **alternate (Gordon–McBride)** NASA-7 form.
The dimensionless properties are computed directly from the coefficients
:math:`a_1` through :math:`a_7` and integration constants :math:`b_1, b_2`:

**Heat Capacity:**

.. math::

   \frac{C_p^\circ}{R} = \frac{a_1}{T^2} + \frac{a_2}{T}
   + a_3 + a_4 T + a_5 T^2 + a_6 T^3 + a_7 T^4

**Enthalpy:**

.. math::

   \frac{H^\circ}{RT} = -\frac{a_1}{T^2} + a_2\frac{\ln T}{T}
   + a_3 + a_4\frac{T}{2} + a_5\frac{T^2}{3}
   + a_6\frac{T^3}{4} + a_7\frac{T^4}{5} + \frac{b_1}{T}

**Entropy:**

.. math::

   \frac{S^\circ}{R} = -\frac{a_1}{2T^2} - \frac{a_2}{T}
   + a_3 \ln T + a_4 T + a_5\frac{T^2}{2}
   + a_6\frac{T^3}{3} + a_7\frac{T^4}{4} + b_2

.. note::

   Dimensionalised units are obtained by multiplying by :math:`R`:
   :math:`C_p^\circ` and :math:`S^\circ` in J/(mol·K),
   :math:`H^\circ` in J/mol.


---

## 9. CLI

Query species directly from the terminal:
```bash
pyglenn query -s O2
```

Build a database from a NASA file:
```bash
pyglenn build -i thermo.inp -o my_database.db -v
```

---

## 10. Database Schema

```sql
CREATE TABLE species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    formula TEXT,
    comments TEXT,
    reference_code TEXT,
    phase TEXT CHECK(phase IN ('gas', 'condensed')),
    molecular_weight REAL,
    heat_of_formation_298K REAL,
    num_intervals INTEGER
);

CREATE TABLE temperature_intervals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    interval_number INTEGER NOT NULL,
    temp_min REAL NOT NULL,
    temp_max REAL NOT NULL,
    h_298_to_0 REAL,
    UNIQUE(species_id, interval_number)
);

CREATE TABLE coefficients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interval_id INTEGER NOT NULL UNIQUE REFERENCES temperature_intervals(id) ON DELETE CASCADE,
    a1 REAL, a2 REAL, a3 REAL, a4 REAL, a5 REAL, a6 REAL, a7 REAL,
    b1 REAL, b2 REAL
);

CREATE TABLE file_metadata (
    id INTEGER PRIMARY KEY,
    temp_min_global REAL,
    temp_500_K REAL,
    temp_1500_K REAL,
    temp_max_global REAL,
    reference_date TEXT,
    total_species INTEGER
);
```

---

## 11. Complete Workflow Examples

### 11.1 Basic Usage
```python
from pyglenn import ThermochemicalCalculator

with ThermochemicalCalculator() as calc:
    species = calc.get_available_species('CH4', exact_match=True)
    sid = species[0]['id']
    
    p = calc.calculate_properties(sid, 298.15)
    print(f"Species: {p['species_name']} | Cp: {p['cp']:.2f} J/molK")
```

### 11.2 Temperature Sweep
```python
with ThermochemicalCalculator() as calc:
    sid = calc.get_available_species('CO2', exact_match=True)[0]['id']
    for T in [300, 500, 1000, 1500]:
        p = calc.calculate_properties(sid, T)
        print(f"T: {T}K | H_rel: {p['h_relative']:.1f} J/mol")
```

### 11.3 Enthalpy Change & Formation
```python
with ThermochemicalCalculator() as calc:
    sid = calc.get_available_species('H2O', exact_match=True)[0]['id']
    dh = calc.calculate_enthalpy_change(sid, 298.15, 1000.0)
    hf = calc.calculate_formation_enthalpy(sid)
    print(f"Sensible H: {dh} J/mol | Hf: {hf} J/mol")
```

### 11.4 Batch Evaluation
```python
with ThermochemicalCalculator() as calc:
    sid = calc.get_available_species('O2', exact_match=True)[0]['id']
    temps = [300.0, 400.0, 500.0]
    results = calc.get_properties_range(sid, temps)
    # results is {300.0: {...}, 400.0: {...}, 500.0: {...}}
```

### 11.5 With Exception Handling
```python
from pyglenn import ThermochemicalCalculator, TemperatureOutOfRangeError

with ThermochemicalCalculator() as calc:
    try:
        sid = calc.get_available_species('N2', exact_match=True)[0]['id']
        p = calc.calculate_properties(sid, 10000.0) # Too high
    except TemperatureOutOfRangeError as e:
        print(f"Error: {e}")
```

---

## 12. Migration Guide: v0.1.9 → v0.1.10+

### 12.1 Species Lookup
**Before (Unsafe):**
```python
# Might return Be3N2(L) if searching for N2
species = calc.get_available_species('N2')
```
**After (Safe):**
```python
# Guaranteed exact match
species = calc.get_available_species('N2', exact_match=True)
```

### 12.2 Exceptions Instead of None
**Before:**
```python
props = calc.calculate_properties(sid, 5000.0)
if props is None:
    print("Out of range")
```
**After:**
```python
try:
    props = calc.calculate_properties(sid, 5000.0)
except TemperatureOutOfRangeError:
    print("Out of range")
```

### 12.3 Simplified Code
**Before:**
```python
# Manual filtering loop to find exact ID
def resolve_id(calc, name):
    for s in calc.get_available_species(name):
        if s['name'] == name: return s['id']
```
**After:**
```python
# Direct access
sid = calc.get_available_species('CH4', exact_match=True)[0]['id']
```

---

## 13. Tips & Best Practices

| Tip | Action |
| :--- | :--- |
| **Lifecycle** | Always use the **context manager** (`with`) to handle DB connections. |
| **Precision** | Use **exact_match=True** to avoid incorrect species identification. |
| **Error Handling** | Catch **ThermoCalcError** to handle all library-specific issues at once. |
| **Sensible Enthalpy** | Use `calculate_enthalpy_change(sid, 298.15, T)` for enthalpy relative to 298.15 K. |
| **Performance** | Use `get_properties_range()` for large temperature sweeps to minimize DB overhead. |
| **Validation** | Check `calculate_formation_enthalpy()` return for `None` as some species lack this data. |

---

## 14. Quick Reference

| | |
|---|---|
| **Install** | `pip install pyglenn` |
| **Version** | 0.1.13 |
| **Docs** | https://profleao.github.io/pyglenn |

**Basic usage:**

```python
with ThermochemicalCalculator() as calc:
    sid = calc.get_available_species('O2', exact_match=True)[0]['id']
    p = calc.calculate_properties(sid, 1000.0)
```

**Returned properties:**

| Key | Unit | Description |
|---|---|---|
| `p['cp']` | J/(mol·K) | Heat capacity |
| `p['h_relative']` | J/mol | Enthalpy relative to 0 K |
| `p['s']` | J/(mol·K) | Absolute entropy |
| `p['phase']` | str | `'gas'` or `'condensed'` |
