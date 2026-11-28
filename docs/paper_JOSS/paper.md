---
title: 'pyglenn: A lightweight Python library for NASA Glenn thermochemical properties'
tags:
  - Python
  - thermochemistry
  - thermodynamics
  - NASA polynomials
  - combustion
  - SQLite
authors:
  - name: Reginaldo G. Leão Jr.
    orcid: 0000-0002-3596-2256
    corresponding: true
    affiliation: 1
affiliations:
  - name: Instituto Federal de Educação, Ciência e Tecnologia de Minas Gerais (IFMG), Arcos, Brazil
    index: 1
    ror: 0553w5c95
date: 27 November 2026
bibliography: paper.bib
---

# Summary

`pyglenn` (version 0.5.1) is an open-source Python package, distributed under the MIT license, for computing constant-pressure heat capacity ($C_p$), enthalpy ($H^\circ$), and entropy ($S^\circ$) from 7-term NASA polynomial coefficients (NASA-7). It converts legacy fixed-column FORTRAN `thermo.inp` files into a normalized SQLite3 relational database, exposes a statically typed Python API, and provides a command-line interface (`pyglenn`).

Unlike libraries that require compiling C/C++ extensions or configuring full reaction mechanisms, `pyglenn` depends only on NumPy (`numpy>=1.21`) at runtime and ships with a pre-built, validated database (`thermo.db`) containing **2,035 chemical species** (1,266 gas, 296 liquid, and 473 solid) across **3,795 temperature intervals**. Beyond scalar and batch property evaluation, the package computes sensible enthalpy, the analytical derivative $\mathrm{d}C_p/\mathrm{d}T$, the heat capacity ratio $\gamma = C_p/C_v$, fixed-composition mixture properties (on both molar and mass bases), and per-species uncertainty estimates audited against NIST-JANAF tables. It also includes least-squares fitting of NASA-7 coefficients with continuity constraints.

# Statement of need

Reliable thermochemical data are required for modeling reactive flows, combustion, aerospace propulsion, and chemical equilibrium. The NASA polynomial format, popularized by the Chemical Equilibrium with Applications (CEA) code from the NASA Glenn Research Center [@Gordon1994; @McBride2002], has become a standard representation for temperature-dependent thermodynamic properties over wide thermal ranges.

Working directly with `thermo.inp` files in Python poses two practical difficulties:

1. **Fragile parsing and lack of indexing:** `thermo.inp` files use a rigid fixed-column FORTRAN layout with `D` exponential notation instead of `E` and repeated records for phase transitions. Ad-hoc parsers break easily or silently accept corrupted values when columns shift or records are truncated.
2. **Systematic bias in the gas constant:** NASA Glenn/CEA polynomials store dimensionless quantities ($C_p^\circ/R$, $H^\circ/RT$, and $S^\circ/R$) originally fitted with the CODATA 1986 gas constant ($R_{\text{GLENN}} = 8.314510\ \text{J/(mol}\cdot\text{K)}$). Denormalizing these coefficients with the modern CODATA 2018/2022 value ($R_{\text{UNIVERSAL}} = 8.31446261815324\ \text{J/(mol}\cdot\text{K)}$) introduces a systematic bias of approximately $-5.7\ \text{ppm}$ in all dimensional outputs.

`pyglenn` is built for researchers, engineers, and educators in thermochemistry, chemical engineering, and combustion who need reproducible, typed access to NASA-7 catalogs from Python scripts or the command line without installing heavy chemical-kinetics suites.

# State of the field

Several established libraries address thermodynamic and thermochemical calculations in Python, each with a different scope:

- **NASA CEA (FORTRAN):** The original CEA program [@Gordon1994] remains a standard reference for complex chemical equilibrium, but it operates through FORTRAN text input and output files without a native Python API or relational querying.
- **Cantera:** Used primarily for chemical kinetics, flames, and reacting flows [@Goodwin2025], supporting NASA-7 and NASA-9 polynomials through YAML and CHEMKIN files. Because it is a large C++ suite aimed at full reaction mechanisms, it adds unnecessary complexity when the goal is simply to query species properties, compute non-reacting mixtures, or fit NASA-7 coefficients.
- **CoolProp:** A standard library for pure fluids, refrigerants, and real-fluid mixtures using Helmholtz-energy equations of state (such as Span-Wagner formulations) and vapor-liquid equilibrium [@Bell2014]. Its scope does not target the catalog of more than 2,000 high-temperature gas and condensed species typical of NASA-7 files.
- **PYroMat:** Aimed at thermodynamics education and cycle analysis (Rankine, Brayton), implementing ideal gases via Shomate and NASA-7 polynomials (`ig2`) alongside multiphase fluids (`mp1`), with a focus on state-pair inversions such as $(P, h)$ [@Martin2022]. It does not provide transactional state-machine ingestion of `thermo.inp`, metadata tracking of $R_{\text{ref}}$, or multi-interval fitting with derivative continuity.
- **Thermo (Caleb Bell ecosystem):** Oriented toward chemical process engineering, physical property estimation, group-contribution methods, and phase equilibria (VLE/LLE) [@Bell2016thermo], backed by a broader dependency tree (`chemicals`, `fluids`, `scipy`).

**Build vs. contribute rationale:** Extending Cantera or CoolProp would not satisfy the need for a minimal library (NumPy as the only runtime dependency, paired with Python's standard-library SQLite3) that parses `thermo.inp` under strict validation, tracks $R_{\text{GLENN}}$ in database metadata, returns immutable dataclasses, and includes constrained NASA-7 fitting. `pyglenn` fills this gap alongside existing tools.

# Software design

`pyglenn` is organized into six modules (`models.py`, `builder.py`, `database.py`, `calculator.py`, `fitting.py`, and `cli.py`), shaped by five design choices:

1. **State-machine parser and transactional loading (`builder.py`):** Rather than permissive regular expressions, `ThermoDBBuilder` uses dedicated line classifiers and loads each dataset inside a single SQLite transaction (`BEGIN`/`COMMIT`/`ROLLBACK`). Malformed species blocks are rejected without silent recovery, and `merge_duplicates=True` optionally merges repeated phase-transition records (recovering, for example, the extended 200–2,130 K range for `Cr(cr)`).
2. **Normalized SQLite schema and $R_{\text{ref}}$ tracking (`database.py`):** The database stores `species`, `temperature_intervals`, `coefficients`, `file_metadata`, `metadata`, and `species_uncertainty` tables. The reference gas constant (`R_GLENN` or `R_UNIVERSAL`) is recorded in `metadata` and selected automatically upon connection, with non-destructive automatic migration (`auto_migrate=True`) for older databases. `validate_database()` checks foreign-key integrity, 1:1 interval-to-coefficient mapping, ordered temperature bounds, and data consistency.
3. **Typed API with immutable dataclasses and explicit exceptions (`models.py`, `calculator.py`):** Public methods on `ThermochemicalCalculator` return frozen dataclasses (`ThermoProperties`, `SpeciesInfo`, `SpeciesData`, `NASACoefficients`, `DatabaseStats`, `Mixture`, and `MixedProperties`) and ship with a `py.typed` marker (PEP 561). Errors raise specific subclasses of `ThermoCalcError` (`DatabaseNotConnectedError`, `SpeciesNotFoundError`, `TemperatureOutOfRangeError`, and `CompositionError`). This supports static checking (`mypy`) and IDE autocompletion while preserving `to_dict()` for serialization.
4. **Batch evaluation, mixtures, and continuity-constrained fitting (`calculator.py`, `fitting.py`):**
   - `calculate_properties_range` loads a species' intervals into memory once, avoiding repeated SQL queries across temperature sweeps.
   - Alongside `calculate_properties`, the calculator provides `h_sensible_to`, `dcp_dt`, `gamma`, and `mixture_properties` (mole-fraction weighting with conversion to a mass basis via mean molar mass).
   - `fitting.py` provides `fit_nasa7` (single interval, enforcing $H^\circ(t_{\text{ref}}) = h_{\text{ref}}$ through $b_1$) and `fit_nasa7_multi` (simultaneous least-squares fitting across multiple intervals with continuity of both $C_p$ and $\mathrm{d}C_p/\mathrm{d}T$ at breakpoints).
5. **CLI (`cli.py`) and NIST-JANAF audit:** The command-line tool exposes `pyglenn build`, `query`, `migrate-metadata`, and `validate`. Cross-validation against NIST-JANAF tables [@Chase1998] from 300 to 3,000 K (CO, CO$_2$, H$_2$O, N$_2$, NH$_3$, O$_2$, and SO$_2$) shows sub-percent agreement for $C_p$ and $S^\circ$, populating the `species_uncertainty` table queried by `calc.uncertainty(species_id, temperature)`. The codebase is verified by 116 automated tests (`pytest`), `ruff`, and `mypy`.

Because `thermo.db` is bundled with the package, evaluating species properties requires no external files or manual database setup:

```python
from pyglenn import ThermochemicalCalculator

with ThermochemicalCalculator() as calc:
    co2 = calc.get_available_species("CO2", exact_match=True)[0]
    props = calc.calculate_properties(co2.id, 1000.0)
```

# Research impact statement

`pyglenn` has been developed iteratively across public releases from `v0.1.0` to `v0.5.1`, introducing the typed dataclass API and `R_GLENN` metadata tracking (`v0.2.0`), mixture calculations and `fit_nasa7` (`v0.3.0`), merged phase-transition intervals (`v0.4.0`), and NIST-JANAF per-species uncertainty budgets with `phase_detail` filtering (`v0.5.0`–`v0.5.1`). The package is published on PyPI (`pip install pyglenn`), includes a `conda` recipe, Sphinx documentation with four example notebooks (basic usage, fuel comparison, mixture properties, and coefficient fitting), the companion [pyglenn Labbook — Thermochemical Worked Examples](https://profleao.github.io/pyglenn-notebooks/), and an archival Zenodo release [@goncalves_leao_junior_2026_23917294].

Outside the project, `pyglenn` is integrated as an optional dependency (`difflow[pyglenn]`) in the **Differentiable Flowsheets** (`difflow`) framework developed by the Kitchin Research Group at Carnegie Mellon University [@KitchinDifflow]. Through `difflow.pyglenn_import`, `difflow` imports molar masses, enthalpies of formation, and $C_p(T)$ samples from the NASA Glenn/CEA database into JAX-differentiable `SpeciesData` structures for chemical process flowsheet simulation and optimization.

# AI usage disclosure

Generative artificial intelligence tools assisted with documentation review, test organization, and initial manuscript drafting. All architectural decisions, scientific implementations, numerical validations against NIST-JANAF data, and the final review of the code and manuscript were performed by the author.

# Acknowledgements

The author thanks the open-source scientific software community and the maintainers of the NASA Glenn/CEA and NIST-JANAF reference databases for making these thermochemical datasets publicly available.

# References
