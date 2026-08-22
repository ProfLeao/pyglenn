# Compatibility Contract — pyglenn 0.2.0

**Date:** 2026-08-22
**Basis:** Glenn.jl v0.4.0 → pyglenn audit (`PYGLENN_PARITY_PLAN.md` / `PLANO_PARIDADE_PYGLENN.md`)

This document records the **Stage 0** decisions (compatibility contract). It is
authoritative over the subsequent stages: any implementation that contradicts a
decision here must be treated as a bug.

---

## D1. Typed API — BREAKING (G1)

Public methods now return **dataclasses** (`src/pyglenn/models.py`) instead of
`dict`. There will be no compatibility layer that keeps `dict` as the default
return type.

| Current method | New return type |
|---|---|
| `ThermochemicalCalculator.calculate_properties` | `ThermoProperties` |
| `ThermochemicalCalculator.calculate_properties_range` (new) | `list[ThermoProperties]` |
| `ThermochemicalCalculator.get_properties_range` | `dict[float, ThermoProperties]` |
| `ThermochemicalCalculator.get_available_species` | `list[SpeciesInfo]` |
| `ThermoDBQuery.find_species` | `list[SpeciesInfo]` |
| `ThermoDBQuery.get_species_data` | `SpeciesData` (species + `list[IntervalData]`) |
| `ThermoDBQuery.get_species_info` (new) | `SpeciesInfo | None` |
| `ThermoDBQuery.get_species_for_temperature` | `IntervalData | None` |
| `ThermoDBQuery.list_species_page` | `tuple[list[SpeciesInfo], int]` |
| `ThermoDBQuery.list_all_species` (new) | `list[SpeciesInfo]` |
| `ThermoDBQuery.get_statistics` | `DatabaseStats` |

- Frozen dataclasses with precise optional types for nullable fields (`formula`,
  `molecular_weight`, `heat_of_formation_298K`, `h_298_to_0`).
- Nullable fields remain `None`; they never silently become `0.0`.
- `dataclasses.asdict()` is the documented mechanism for JSON/serialization.
- Coefficient **inputs** (e.g. `calculate_cp/h/s`) keep accepting either
  `dict` **or** `NASACoefficients` — only the **return** type changes.

## D2. Compatibility policy for dict results

- `dict` results are **removed** from public methods; there is no dual-return
  deprecation period.
- Consumers migrate via `CHANGELOG` + a migration guide in the documentation
  (before/after examples with `dict` and with dataclass).
- `dict` continues to exist only as an accepted **input** format (coefficients).

## D3. Metadata migration — AUTOMATIC on connect (G2/G6)

- `ThermoDBQuery.connect()` detects a legacy database (without the `metadata`
  table) and applies the migration **automatically**, writing the canonical keys.
- Write scope: **only** the additive `metadata` table. It never changes
  `species`, `temperature_intervals`, or `coefficients`.
- The fallback to `R_UNIVERSAL` now happens **only** when the `gas_constant_ref`
  value is missing, invalid, or implausible — no longer because the table is
  absent.
- `migrate_metadata()` remains public and idempotent (automation calls it).
- **Impact on existing tests:** `test_reference_gas_constant_legacy_fallback_and_migration`
  must be updated (the legacy fallback for a missing table no longer exists).

## D4. Cross-language numerical tolerances

| Quantity | Tolerance |
|---|---|
| Cp, S (J/(mol·K)) | `rel_tol=1e-9`, `abs_tol=1e-6` |
| H (J/mol) | `rel_tol=1e-9`, `abs_tol=1e-6` |
| ΔH°f of O2 (= 0) | `abs_tol=1.0` J/mol |

- Comparisons use `math.isclose(..., rel_tol=..., abs_tol=...)`; they never
  compare rounded display output.
- `rel_tol=1e-9` is loose enough for evaluation-order differences between Julia
  and Python, and strict enough to detect the ~5.7 ppm bias (5.7e-6).

## D5. Canonical value of the reference constant

- The `gas_constant_ref` key must be written with the literal string **`'8.314510'`**
  (not `str(R_GLENN)`, which would produce `'8.31451'`).
- `gas_constant_ref_source = 'NASA Glenn/CEA thermo.inp (CODATA 1986)'`.
- `R_GLENN = 8.314510` (float) remains the numeric value used in calculations;
  this decision concerns only the **persisted textual representation**.

## Versioning

- Pre-1.0: a return-type change is **breaking** → minor bump: `0.1.13 → 0.2.0`.
- `pyproject.toml` (dynamic via `__init__.__version__`), `conda.recipe/meta.yaml`,
  and generated distributions are bumped together.

## Contract acceptance criteria

1. Public methods return the dataclasses listed in D1.
2. `dataclasses.asdict()` reconstructs the old equivalent `dict` (same keys).
3. `connect()` automatically migrates a legacy database without touching
   thermochemical data.
4. D4 tolerances are applied in cross-language tests.
5. `gas_constant_ref` is persisted as `'8.314510'`.
