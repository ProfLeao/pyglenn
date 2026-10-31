# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- `h_sensible_to(species_id, temperature, t_ref=298.15)` — sensible enthalpy.
- `dcp_dt(species_id, temperature)` — analytical derivative of Cp.
- `gamma(species_id, temperature)` — Cp/Cv ratio (ideal gas).
- `Mixture` and `MixedProperties` dataclasses plus
  `ThermochemicalCalculator.mixture_properties(...)` — mole-fraction-weighted
  mixture properties (molar and mass basis) for a fixed composition.
- `CompositionError` (subclass of `ThermoCalcError`) for invalid mixture
  compositions.
- `fit_nasa7(temperatures, cp_values, ...)` — least-squares fitting of NASA-7
  coefficients to tabulated Cp(T) data, honoring the
  `H°(t_ref) = h_ref` convention (`b1`, not `a6`).
- `fit_nasa7_multi(temperatures, cp_values, breakpoints, ...)` — multi-interval
  NASA-7 fit with continuity of Cp and its first derivative at each breakpoint.
- `NOTICE` of attribution (Glenn.jl lineage) and `py.typed` for type
  consumers.

### Changed

- Docstrings of `h_relative`/`calculate_enthalpy_change` clarify the NASA-7
  convention: `H°(298.15 K) = ΔH°f(298.15 K)` (integration constant `b1`).
- NumPy (`numpy>=1.21`) added as the first runtime dependency (used by
  `fit_nasa7`).

### Deprecated

- `get_properties_range` — use `calculate_properties_range`. Removal in 0.4.0.

## [0.2.0] - 2026-08-22

### Added

- Typed public API (dataclasses: `ThermoProperties`, `SpeciesInfo`,
  `NASACoefficients`, `IntervalData`, `SpeciesData`, `DatabaseStats`).
- Dataset reference constant `R_GLENN = 8.314510` (CODATA 1986) and the
  `metadata` table; automatic migration in `connect()`.
- State-based parser with validation; dataset rebuild (2,035 species,
  3,779 intervals).
- `validate_database()` and the `validate`/`migrate-metadata` CLI commands.
- Compatibility contract (`docs/COMPATIBILITY_CONTRACT.md`).

### Fixed

- `heat_of_formation_298K` extraction (columns 65–80 of RECORD 2).
