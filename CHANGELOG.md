# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- `h_sensible_to(species_id, temperature, t_ref=298.15)` — sensible enthalpy.
- `dcp_dt(species_id, temperature)` — analytical derivative of Cp.
- `gamma(species_id, temperature)` — Cp/Cv ratio (ideal gas).
- `NOTICE` of attribution (Glenn.jl lineage) and `py.typed` for type
  consumers.

### Changed

- Docstrings of `h_relative`/`calculate_enthalpy_change` clarify the NASA-7
  convention: `H°(298.15 K) = ΔH°f(298.15 K)` (integration constant `b1`).

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
