# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o versionamento segue [SemVer](https://semver.org/).

## [Não publicado]

### Adicionado

- `h_sensible_to(species_id, temperature, t_ref=298.15)` — entalpia sensível.
- `dcp_dt(species_id, temperature)` — derivada analítica de Cp.
- `gamma(species_id, temperature)` — razão Cp/Cv (gás ideal).
- `NOTICE` de atribuição (linhagem Glenn.jl) e `py.typed` para consumidores de
  tipos.

### Alterado

- Docstrings de `h_relative`/`calculate_enthalpy_change` esclarecem a convenção
  NASA-7: `H°(298.15 K) = ΔH°f(298.15 K)` (constante de integração `b1`).

### Descontinuado

- `get_properties_range` — use `calculate_properties_range`. Remoção na 0.4.0.

## [0.2.0] - 2026-08-22

### Adicionado

- API pública tipada (dataclasses: `ThermoProperties`, `SpeciesInfo`,
  `NASACoefficients`, `IntervalData`, `SpeciesData`, `DatabaseStats`).
- Constante de referência do dataset `R_GLENN = 8.314510` (CODATA 1986) e
  tabela `metadata`; migração automática no `connect()`.
- Parser por estados com validação; rebuild do dataset (2.035 espécies,
  3.779 intervalos).
- `validate_database()` e CLI `validate`/`migrate-metadata`.
- Contrato de compatibilidade (`docs/COMPATIBILITY_CONTRACT.md`).

### Corrigido

- Extração de `heat_of_formation_298K` (colunas 65–80 do RECORD 2).
