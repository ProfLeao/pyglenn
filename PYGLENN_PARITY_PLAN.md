# Glenn.jl -> pyglenn: functional parity and implementation plan

**Audit date:** 2026-08-19  
**Source repositories:** [Glenn.jl](https://github.com/ProfLeao/Glenn.jl) and [pyglenn](https://github.com/ProfLeao/pyglenn)  
**Audited Julia version:** `0.4.0` (release merged into `main` on 2026-08-19)  
**Audited Python version:** `0.1.13`

## 1. Purpose and scope

This document records the functionality implemented in Glenn.jl, compares it with the current pyglenn implementation, and defines a detailed plan for porting Glenn-only capabilities to pyglenn.

The two projects share the NASA-7 data model and the SQLite database generated from NASA FORTRAN `thermo.inp`. The comparison therefore distinguishes:

1. **Glenn-only functionality:** behavior or public API present in Glenn.jl and not currently present in pyglenn.
2. **Equivalent functionality:** present in both projects, although names, return types, or lifecycle differ.
3. **pyglenn-only or parity gaps:** behavior present in pyglenn that should be considered for Glenn.jl as well, but is not part of the Glenn-to-pyglenn port.
4. **Non-runtime project features:** documentation, CI, notebooks, and quality tooling. These are tracked separately from the scientific API.

The goal is not to make Python look like Julia. The goal is to expose the same scientific capabilities while preserving Python conventions, backward compatibility, and the existing SQLite format.

## 0. Version 0.2.0 remediation plan

This release first corrects the integrity and scientific-consistency issues in the bundled dataset. It must precede the broader typed-model and performance work, because those changes would otherwise formalize incorrect data or numerical output.

### 0.1 Evidence and scope

The bundled database reports the expected row counts (2,030 species and 3,772 intervals), but its molecular-weight average is implausible. Inspection found three records whose `name` values are FORTRAN coefficient tokens (for example, `-1.302004763D+06`) and whose molecular weights reach `5.6168201e12 g/mol`. This is a parser recovery failure: after an incomplete or malformed interval block, a later coefficient line can be reconsidered as a new species header. The release must rebuild and validate the data; filtering bad rows from an existing database is not an acceptable correction.

The reference implementation is Glenn.jl v0.4.0, merged on 2026-08-19. Its commit `77ff931` (`fix: use dataset reference gas constant (R_GLENN) for denormalization`) establishes the G2 behavior. The changelog documents that NASA Glenn/CEA data are normalized with the CODATA 1986 reference constant `8.314510`; use of the universal CODATA value caused an approximately -5.7 ppm systematic bias.

### 0.2 Workstream A — safe parser and rebuild

1. Replace the implicit, best-effort index recovery in `ThermoDBBuilder.parse_and_load()` with an explicit record-state parser: `species header -> general information -> N complete interval triplets`. A state may only consume its expected record type; coefficient lines must never be eligible as a species header.
2. Validate each complete block before insertion: non-empty species name, positive interval count, finite ordered temperature bounds, and all nine finite coefficient values. Record a source line number and reason for every rejected block.
3. Treat a declared-but-incomplete interval sequence as a rejected species block, then resynchronize only at a verified species-header boundary. Do not insert partial species, intervals, or coefficients.
4. Build into a temporary SQLite file in one transaction. Run post-load validation there and replace the bundled `thermo.db` only after all release gates pass. A failed rebuild must leave the previous database untouched.
5. Add parser fixtures for valid multi-interval data, malformed interval headers, missing coefficient lines, FORTRAN `D`/`d` notation, and the exact desynchronization shape that previously turned a coefficient into a species.

### 0.3 Workstream B — database integrity

1. Add a reusable `validate_database()` report (and a read-only CLI command if useful) that checks foreign keys, one coefficient row per interval, no orphan rows, finite values, ordered bounds, and `num_intervals` agreement with actual interval rows.
2. Add semantic checks that reject coefficient-like species names, require positive finite molecular weights, and flag values outside a documented domain range. The threshold is a diagnostic guard, not a substitute for correct parsing.
3. Require the rebuilt canonical data to match the validated source baseline (currently 2,035 valid species, 3,779 intervals, and 3,779 coefficient sets); verify the gas/condensed split and compare representative O2, CO2, H2O, NH3, and SO2 values with the NIST audit. Update legacy 2,030/3,772 documentation only after this validation is made reproducible in CI.
4. Recompute and assert plausible aggregate statistics after the rebuild. In particular, average molecular weight must be derived from corrected source data, never hidden by excluding corrupt rows in `get_statistics()`.
5. Store the validation report with release artifacts and make CI build a fresh temporary database from `thermo.inp` before integrity tests.

### 0.4 Workstream C — G2 implementation specification

Implement G2 before regenerating the bundled database, following Glenn.jl commit `77ff931` and its subsequent `da0d833` API-documentation commit:

1. In `database.py`, expose `R_UNIVERSAL = 8.31446261815324` and `R_GLENN = 8.314510`. Keep `R` as a documented compatibility alias for `R_UNIVERSAL` for the 0.2.x line; do not silently change its meaning.
2. Create additive schema `metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)` in `ThermoDBBuilder.create_tables()`. Implement an idempotent, parameterized `write_metadata()` that persists exactly `gas_constant_ref = "8.314510"` and `gas_constant_ref_source = "NASA Glenn/CEA thermo.inp (CODATA 1986)"`.
3. Add `get_gas_constant_ref()` to `ThermoDBQuery`. Explicitly check for the table, read the key with a parameterized query, parse the value, and accept only a finite value in `(8.0, 9.0)`. Missing table/key, invalid text, and implausible values must warn and return `R_UNIVERSAL`; connection/query errors must not be swallowed as fallback.
4. Add an explicit, idempotent `migrate_metadata()` for legacy databases. It creates the table and writes the two canonical keys without rebuilding or altering species, intervals, or coefficients. Connecting to a user database remains read-only; migration is opt-in.
5. Add `r_ref` to `ThermochemicalCalculator`, populate it only after a successful connection, and use it for every dimensional conversion: `cp_r * r_ref`, `h_rt * r_ref * T`, and `s_r * r_ref`. This includes scalar and multi-temperature paths.
6. Regenerate the bundled database with metadata and verify it selects `R_GLENN`. A pre-metadata database must continue to open using the universal-constant fallback until migrated.
7. Add tests for constants, new-builder metadata, idempotent writes and migration, missing/invalid/implausible metadata, legacy fallback, and the exact scaling ratio `R_GLENN / R_UNIVERSAL`. Add cross-language regression values for Cp, H, and S of O2 at 298.15 K and 1000 K plus one nonzero-formation-enthalpy species.
8. Update the README, Sphinx database reference, changelog, API exports, and release notes to identify the dataset constant and quantify the intentional ~5.7 ppm correction.

### 0.5 Release gates and ordering

1. Write parser and integrity tests before modifying the canonical data.
2. Implement and test G2 on a minimal fixture, including legacy fallback.
3. Rebuild the bundled database in a temporary location, validate it, then replace the package asset and regenerate the NIST audit.
4. Build both wheel and sdist from a clean environment and assert that each includes `pyglenn/data/thermo.db` and `pyglenn/data/thermo.inp`.
5. Run the full Python support matrix (3.9–3.12), Ruff, mypy, docs with warnings-as-errors, and cross-language comparisons against Glenn.jl v0.4.0.
6. Only after these gates pass, continue with G1/G3/G4/G5. Bump the package, Conda recipe, generated distributions, and release documentation together to `0.2.0`.

## 2. Glenn.jl functionality inventory

### 2.1 Package and lifecycle

- Zero-configuration `Calculator()` using the bundled `data/thermo.db`.
- `Calculator(path)` for a custom SQLite database.
- `Calculator(f::Function, path)` do-block context manager that always closes the calculator in `finally`.
- `Base.close(calc)` and `Base.show` representations for calculator and database handles.
- `default_db_path()` and `default_inp_path()` for resolving packaged data files.
- Public package metadata: `Glenn.__version__` and `Glenn.__author__`.

### 2.2 Typed domain model

Glenn.jl exposes immutable Julia structs instead of untyped dictionaries:

- `ThermoProperties`: temperature, Cp, relative enthalpy, entropy, interval bounds, species name, and phase.
- `SpeciesInfo`: ID, name, formula, phase, molecular weight, formation enthalpy, and interval count.
- `NASACoefficients`: the nine NASA-7 values `a1`-`a7`, `b1`, and `b2`, all as `Float64`.
- `IntervalData`: interval identity, bounds, reference enthalpy, and typed coefficients.
- `DatabaseStats`: total species, intervals, coefficient sets, phase counts, and average molecular weight.

`NASACoefficients(::Dict)` is retained as a compatibility constructor. The old `Dict` calculation methods are deprecated in favor of typed coefficients.

### 2.3 Database API

The low-level `ThermoDatabase` API exports:

- `ThermoDB(path)` and `close(tdb)`.
- `get_statistics(tdb) -> DatabaseStats`.
- `find_species(tdb, name; exact_match=false)` with case-insensitive exact-name matching when requested.
- Substring search by species name or formula, with exact-name results prioritized.
- `list_species_page(tdb; page=1, page_size=20)`.
- `list_all_species(tdb)` as a single-query full listing.
- `get_species_info(tdb, species_id)` as a lightweight metadata-only lookup.
- `get_species_data(tdb, species_id)` with all intervals and coefficients.
- `get_species_for_temperature(tdb, species_id, temperature)`.
- Standalone NASA-7 evaluators: `calculate_cp`, `calculate_h`, and `calculate_s`.
- Domain exception types: `ThermoCalcError`, `DatabaseNotConnectedError`, `SpeciesNotFoundError`, and `TemperatureOutOfRangeError`.

### 2.4 Calculator API

The high-level API exports:

- `get_available_species(calc, pattern; exact_match=false)`.
- `calculate_properties(calc, species_id, T) -> ThermoProperties`.
- `calculate_properties(calc, species_id, T_range) -> Vector{ThermoProperties}`.
- `calculate_formation_enthalpy(calc, species_id)`.
- `calculate_enthalpy_change(calc, species_id, T1, T2)`.
- `get_properties_range(calc, species_id, T_range)`.

The scalar and range APIs denormalize dimensionless NASA quantities into SI units. The range overload loads species intervals once and evaluates all valid temperatures in memory.

### 2.5 Gas-constant and dataset metadata

Glenn.jl has a dataset-specific reference-constant system:

- `R_UNIVERSAL = 8.31446261815324` for the universal CODATA value.
- `R_GLENN = 8.314510` for the NASA Glenn/CEA polynomial reference value.
- `metadata(key TEXT PRIMARY KEY, value TEXT)` table.
- `write_metadata(builder)` when building a database.
- `get_gas_constant_ref(db)` when opening a database.
- `migrate_metadata!(db)` for legacy databases without the metadata table.
- `Calculator` stores `R_ref` and uses it for Cp, H, and S denormalization.

### 2.6 Database builder

`ThermoDBBuilder` implements:

- SQLite connection lifecycle with foreign keys and WAL mode.
- Creation of `species`, `temperature_intervals`, `coefficients`, `file_metadata`, and `metadata` tables.
- Parsing of NASA FORTRAN fixed-width records.
- FORTRAN `D`/`d` notation conversion.
- Species, general-information, temperature-interval, and coefficient parsing helpers.
- Temperature and coefficient line detection.
- Transactional loading with rollback on failure.
- Idempotent handling of species already present in the database.
- Distinct reporting of new species, existing species, and skipped lines.
- Dataset gas-constant metadata persistence.

### 2.7 CLI and project assets

- `cli_main()` with `build` and `query` commands.
- `bin/glenn.jl` convenience entry point.
- Query output containing statistics, species search results, sample properties, and formation enthalpy.
- Documenter.jl documentation and API pages.
- Executable examples and Pluto-compatible notebooks.
- NIST-JANAF/Shomate cross-validation audit for CO2, N2, CO, H2O, O2, NH3, and SO2.
- Aqua.jl and JuliaFormatter.jl test/development integration.
- CI, documentation, TagBot, and CompatHelper workflows.

## 3. Comparison with pyglenn

### 3.1 Functionality already equivalent

These capabilities are already available in both projects:

| Capability | Glenn.jl | pyglenn | Notes |
|---|---|---|---|
| Bundled SQLite dataset | `Calculator()` | `ThermochemicalCalculator()` plus `connect()` | Lifecycle differs. |
| Custom database path | `Calculator(path)` | `ThermochemicalCalculator(path)` | Both support external databases. |
| NASA FORTRAN builder | `ThermoDBBuilder` | `ThermoDBBuilder` | Same normalized core schema. |
| NASA-7 Cp/H/S equations | `calculate_cp/h/s` | `ThermoDBQuery.calculate_cp/h/s` | Julia uses typed coefficients; Python uses dicts. |
| Species substring search | `find_species` / `get_available_species` | Same | Both search name and formula. |
| Case-insensitive exact match | `exact_match=true` | `exact_match=True` | Same intended behavior. |
| Paginated species listing | `list_species_page` | `list_species_page` | Same page/total-pages model. |
| Complete species data | `get_species_data` | `get_species_data` | Return representation differs. |
| Temperature-specific interval lookup | `get_species_for_temperature` | Same | Boundary behavior is not identical; see Section 3.3. |
| Formation enthalpy | `calculate_formation_enthalpy` | Same | Return conventions differ for disconnected/missing data. |
| Enthalpy change | `calculate_enthalpy_change` | Same | Both evaluate two endpoint properties. |
| Multiple-temperature properties | `get_properties_range` | Same name | Julia returns a vector; Python returns a temperature-keyed dict. |
| Database statistics | `get_statistics` | Same name | Julia returns `DatabaseStats`; Python returns a dict. |
| Context manager | Julia do-block | Python `with` | Both guarantee cleanup. |
| CLI build/query | `cli_main`, `bin/glenn.jl` | installed `pyglenn` command | Both expose the same two primary commands. |
| Domain errors | exported in Julia | raised in Python | Julia currently does not consistently throw the specialized subtypes; see Section 3.3. |

### 3.2 Glenn-only capabilities to implement in pyglenn

These are the primary differences requested by this audit.

#### G1. Typed domain result model

**Current Glenn.jl behavior:**

- Public calculations return `ThermoProperties`.
- Species queries return `SpeciesInfo`.
- Interval queries return `IntervalData` containing `NASACoefficients`.
- Statistics return `DatabaseStats`.

**Current pyglenn behavior:**

- Calculations and queries return `dict[str, Any]`.
- Coefficients are ordinary dictionaries.
- Statistics return a dictionary.

**Implementation plan:**

1. Add frozen dataclasses in `src/pyglenn/models.py`:
   - `NASACoefficients`.
   - `SpeciesInfo`.
   - `IntervalData`.
   - `ThermoProperties`.
   - `DatabaseStats`.
2. Use precise optional types for nullable SQLite values.
3. Add `from_mapping` or explicit conversion helpers only at the SQLite boundary.
4. Change public methods to return dataclasses while retaining mapping compatibility for one deprecation cycle, or add an opt-in typed API first if v0.2 compatibility risk is unacceptable.
5. Export the models from `pyglenn.__init__` and document field names and units.
6. Add equality and representation tests; dataclass equality should make scientific regression tests easier to read.

**Acceptance criteria:**

- Public typed results expose attributes equivalent to the Julia fields.
- `asdict()` or an equivalent documented conversion is available for JSON/legacy callers.
- Nullable `formula`, molecular weight, formation enthalpy, and interval reference values remain nullable rather than silently becoming zero.
- Existing dictionary consumers either continue to work through a documented compatibility layer or receive a planned, documented deprecation warning.

#### G2. Dataset reference gas constant and metadata

**Current Glenn.jl behavior:**

- Distinguishes `R_UNIVERSAL` from `R_GLENN`.
- Stores `gas_constant_ref` and its source in the `metadata` table.
- Reads the value when a calculator opens a database.
- Migrates old databases explicitly.

**Current pyglenn behavior:**

- Uses one module constant, `R = 8.314462618`.
- The builder creates no `metadata` table and writes no dataset reference constant.
- Calculations therefore denormalize NASA coefficients with the universal constant, not the bundled dataset's original `R_GLENN` reference.

**Implementation plan:**

1. Add `R_UNIVERSAL = 8.31446261815324` and `R_GLENN = 8.314510` in `database.py`.
2. Add the `metadata` table creation to `ThermoDBBuilder.create_tables()`.
3. Add `write_metadata()` using parameterized SQL and idempotent upserts.
4. Add `migrate_metadata(connection)` for existing databases.
5. Add `get_gas_constant_ref()` with explicit fallback behavior for legacy databases.
6. Make `ThermochemicalCalculator` store `R_ref` after connecting/opening the database.
7. Use `R_ref` consistently for Cp, H, S, and range calculations.
8. Add a source metadata key such as `gas_constant_ref_source`.
9. Update the database-structure documentation and release notes.
10. Decide whether legacy databases should be migrated automatically on connect or only through an explicit API. The recommended default is explicit migration to avoid silently modifying user files.

**Acceptance criteria:**

- A newly built database contains the metadata table and `gas_constant_ref = 8.314510`.
- A legacy database without the table still opens and has a documented fallback.
- The bundled database produces the same denormalized values as Glenn.jl within a documented tolerance.
- Metadata writes are idempotent and do not duplicate rows.

#### G3. Single-query complete species listing

**Current Glenn.jl behavior:**

- `list_all_species(tdb)` loads all species with one ordered query.
- `get_available_species(calc)` uses it when no pattern is provided.

**Current pyglenn behavior:**

- `get_available_species()` walks through pages of 100 records.
- `list_species_page()` is available, but there is no equivalent single-query `list_all_species()` method.

**Implementation plan:**

1. Add `ThermoDBQuery.list_all_species() -> list[SpeciesInfo]`.
2. Select the same fields as `find_species`, order by name, and convert rows at the database boundary.
3. Change `ThermochemicalCalculator.get_available_species()` with an empty pattern to call the new method.
4. Keep pagination for large datasets and expose it for callers that need bounded memory.
5. Add a test proving the no-pattern path does not make repeated page queries; use a small query spy or a dedicated method-level test.

**Acceptance criteria:**

- Empty-pattern lookup returns all records in alphabetical order.
- The result type and fields are documented.
- Paginated and full-list APIs remain separately available.

#### G4. Lightweight species metadata lookup

**Current Glenn.jl behavior:**

- `get_species_info(tdb, species_id)` returns basic metadata without loading intervals or coefficients.
- The high-level calculator uses this for scalar property calculations.

**Current pyglenn behavior:**

- `calculate_properties()` calls `get_species_data()` first, loading all intervals before selecting one.
- There is no equivalent public lightweight lookup.

**Implementation plan:**

1. Add `ThermoDBQuery.get_species_info(species_id) -> SpeciesInfo | None`.
2. Select only species columns needed for identity and output metadata.
3. Use it in scalar `calculate_properties()` and `calculate_formation_enthalpy()`.
4. Preserve `get_species_data()` for callers explicitly requesting all intervals.
5. Add tests that distinguish not-found from a species with no coefficient rows.

**Acceptance criteria:**

- Scalar calculations do not load every interval unnecessarily.
- Formation-enthalpy lookup remains correct when interval data is absent.
- The complete-data API remains unchanged for existing callers.

#### G5. Vectorized range result model

**Current Glenn.jl behavior:**

- `calculate_properties(calc, species_id, T_range)` is a dedicated overload.
- `get_properties_range()` returns an ordered `Vector{ThermoProperties}`.
- Interval data is loaded once and reused.

**Current pyglenn behavior:**

- `get_properties_range()` loops through temperatures and returns `dict[float, dict]`.
- It skips out-of-range temperatures and returns `None` if every temperature fails.

**Implementation plan:**

1. Keep the existing Python dictionary API for backward compatibility.
2. Add a typed `calculate_properties_range()` or `get_properties_range_typed()` returning an ordered list of `ThermoProperties`.
3. Load species intervals once per call and select intervals in memory.
4. Define duplicate-temperature behavior explicitly; recommended behavior is to preserve input order in the typed list and retain dictionary deduplication for the legacy method.
5. Define out-of-range behavior explicitly; recommended behavior is to skip invalid values in the legacy method and offer `strict=True` for raising an error.
6. Add benchmark coverage comparing one bulk query with repeated scalar calls.

**Acceptance criteria:**

- Ordered range results are available without breaking existing dictionary callers.
- All valid temperatures use the correct interval.
- The reference gas constant is applied consistently to every result.
- Performance is measurably better than repeated complete-data lookups.

#### G6. Explicit dataset metadata migration API

This is separated from G2 because it is an operational capability.

**Current Glenn.jl behavior:** `migrate_metadata!(db)` can upgrade an old shared database without rebuilding all species.

**Implementation plan:**

1. Provide `migrate_metadata(connection_or_query) -> None` in pyglenn.
2. Make it safe to run repeatedly.
3. Do not rebuild species or coefficient rows.
4. Return a small migration report or document that the function returns `None`.
5. Add a CLI option, for example `pyglenn migrate-metadata -d thermo.db`, only if users need a command-line migration path.

## 4. pyglenn behavior that should also be considered for Glenn.jl

These are not Glenn-only features, but the audit found them while comparing the implementations.

### P1. Explicit connection state

pyglenn exposes `connect() -> bool` and `connected -> bool`, and supports a calculator object that can exist before connection. Glenn.jl opens the database in `Calculator(path)` and has no public connected property.

Recommended Julia decision: keep eager construction for idiomatic Julia resource handling, but add `isopen(calc)` and `isopen(tdb)` methods. Avoid introducing a disconnected calculator unless there is a concrete use case.

### P2. Interval-boundary tolerance and deterministic selection

pyglenn uses `temp_max + 1e-9` and orders by interval number, making shared boundaries deterministic. Glenn.jl currently uses direct inclusive comparisons without an explicit `ORDER BY` in `get_species_for_temperature`.

Recommended Julia change:

- Add `ORDER BY ti.interval_number LIMIT 1`.
- Use a documented tolerance, preferably a named constant.
- Add tests at the lower boundary, shared boundary, upper boundary, and values within one tolerance of a boundary.

This is a correctness and cross-language reproducibility item.

### P3. Specialized exception behavior

Both projects define specialized error concepts, but Glenn.jl high-level calculations currently throw `ThermoCalcError` directly for invalid species and out-of-range temperatures. pyglenn raises `SpeciesNotFoundError` and `TemperatureOutOfRangeError` in those cases.

Recommended Julia change:

- Throw `SpeciesNotFoundError(species_id)` for missing IDs.
- Throw `TemperatureOutOfRangeError(T, info.name)` for invalid temperatures.
- Reserve `ThermoCalcError` for errors without a more specific domain type.
- Update tests and documentation.

### P4. Public CLI installation contract

pyglenn installs a `pyglenn` executable through `pyproject.toml`. Glenn.jl has `cli_main()` and `bin/glenn.jl`, but no Julia package executable declaration equivalent to Python console scripts.

Recommended Julia decision: retain the script because Julia package executables are commonly project scripts, and document a stable invocation. If a global command is required, provide a Julia application wrapper rather than changing the library API.

### P5. Builder default-path behavior

The two CLIs use different defaults: Glenn.jl resolves bundled paths in its lightweight parser, while pyglenn's CLI defaults to relative `thermo.inp` and `thermo.db` for the build command. The implementation plan should define whether a future pyglenn metadata migration/build command operates on the bundled file or the current working directory.

## 5. Proposed pyglenn implementation phases

### Phase 0 - Compatibility contract

- Publish the API comparison and decide whether typed dataclasses are additive or a breaking return-type change.
- Add a compatibility policy for dictionary results.
- Decide automatic versus explicit metadata migration.
- Define numerical tolerances for cross-language comparisons.

### Phase 1 - Models and conversion boundary

- Add `models.py` dataclasses.
- Add row-to-model conversion helpers.
- Add unit and nullable-field documentation.
- Add tests without changing existing public return types yet.

### Phase 2 - Metadata and gas constant

- Add constants and metadata schema.
- Add builder writes and migration.
- Add calculator `R_ref` handling.
- Regenerate or migrate the bundled database.
- Add cross-language regression values for O2 at 298.15 K, 1000 K, and a second species.

### Phase 3 - Database query parity

- Add `list_all_species()`.
- Add `get_species_info()`.
- Switch empty-pattern lookup and scalar calculations to the lightweight paths.
- Add query-count and not-found tests.

### Phase 4 - Typed range API

- Add an additive typed range method.
- Preserve the existing temperature-keyed dictionary method.
- Document ordering, duplicate temperatures, skipped values, and strict mode.
- Add performance and numerical tests.

### Phase 5 - Public exports and documentation

- Export constants, models, metadata helpers, and new query methods from `pyglenn.__init__`.
- Update README, Sphinx pages, examples, and the CLI help.
- Add a migration guide with old dictionary examples and new dataclass examples.

### Phase 6 - Release and interoperability verification

- Run pyglenn tests, Ruff, mypy, and coverage.
- Run Glenn.jl tests against the migrated database.
- Compare SQLite schemas and row counts.
- Compare Cp, H, and S at shared species/temperature points.
- Release under a minor version if compatibility adapters remain; use a major/minor policy appropriate to pyglenn's pre-1.0 status if return types change.

## 6. Cross-language acceptance matrix

The implementation is complete only when the following checks pass:

| Area | Required check |
|---|---|
| Schema | Both builders create the same core tables; metadata is additive and understood by both libraries. |
| Constants | Bundled NASA data is denormalized with `8.314510` in both implementations. |
| Exact lookup | `O2`, `o2`, and partial `O` produce the same match semantics. |
| Formula lookup | Name/formula substring behavior is equivalent. |
| Boundaries | 200 K, 1000 K, and 6000 K select the same intervals for O2. |
| Missing species | Both libraries expose a clear, documented not-found result/error. |
| Out-of-range T | Both libraries expose a clear, documented range error/result policy. |
| Scalar values | Cp, H, and S agree within an explicit tolerance at shared points. |
| Range values | Valid temperatures, ordering, skipped values, and duplicate handling are documented and tested. |
| Formation enthalpy | O2 reference value and a nonzero formation-enthalpy species agree. |
| Builder | A minimal `thermo.inp` builds successfully and writes metadata. |
| Legacy DB | A pre-metadata database remains readable and can be migrated without rebuilding. |
| CLI | Build/query commands report useful errors and complete successfully. |

## 7. Suggested test fixtures

Use one shared small SQLite fixture and one minimal FORTRAN input fixture:

- Species `O2`, with intervals `[200, 1000]` and `[1000, 6000]`.
- At least one species with nonzero formation enthalpy, such as `CO2`.
- A formula-search case where the formula differs from the display name.
- A database without `metadata` for migration/fallback tests.
- A database with `metadata` containing an invalid or implausible value for fallback tests.
- Temperatures `200.0`, `1000.0`, `6000.0`, `100.0`, and `7000.0`.
- A range containing valid, invalid, duplicate, and integer-valued temperatures.

Numerical comparison tests should use absolute and relative tolerances appropriate to the polynomial evaluation and the selected gas constant. Do not compare rounded display output.

## 8. Risks and decisions

- **Return-type compatibility:** replacing dictionaries outright can break downstream Python users. Prefer additive typed APIs or a deprecation period.
- **SQLite metadata typing:** keep `metadata.value` as `TEXT` because it is a generic key/value table; parse the gas constant at read time and validate its range.
- **Automatic migration:** silently changing a user's database is surprising. Prefer an explicit migration API, with a clear warning or CLI command.
- **Shared database correctness:** the gas constant is scientific data, not merely configuration. The metadata source and fallback policy must be documented and tested.
- **Boundary behavior:** a tolerance can accept values slightly outside the declared interval. Keep it small, name it, and test it explicitly.
- **Performance:** typed conversion at the database boundary should not cause one query per temperature. Range calculations must reuse loaded intervals.
- **Versioning:** pyglenn is pre-1.0, but its users still need a migration note when return shapes or constants change.

## 9. Short-term recommendation

Implement G2 first, because it affects every denormalized thermodynamic result. Then implement G1 and G4, which establish a stable typed/query boundary. Implement G3 and G5 afterward as performance and API improvements. In parallel, apply P2 and P3 to Glenn.jl so both libraries agree on interval boundaries and exception semantics before numerical cross-validation is used as a release gate.
