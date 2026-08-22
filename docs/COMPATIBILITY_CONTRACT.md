# Contrato de Compatibilidade — pyglenn 0.2.0

**Data:** 2026-08-22
**Base:** auditoria Glenn.jl v0.4.0 → pyglenn (`PYGLENN_PARITY_PLAN.md` / `PLANO_PARIDADE_PYGLENN.md`)

Este documento registra as decisões da **Etapa 0** (contrato de compatibilidade). Ele
é autoritativo sobre as etapas seguintes: qualquer implementação que contradiga uma
decisão aqui deve ser considerada bug.

---

## D1. API tipada — BREAKING (G1)

Os métodos públicos passam a retornar **dataclasses** (`src/pyglenn/models.py`) em
vez de `dict`. Não haverá camada de compatibilidade que mantenha `dict` como retorno
padrão.

| Método atual | Retorno novo |
|---|---|
| `ThermochemicalCalculator.calculate_properties` | `ThermoProperties` |
| `ThermochemicalCalculator.calculate_properties_range` (novo) | `list[ThermoProperties]` |
| `ThermochemicalCalculator.get_properties_range` | `dict[float, ThermoProperties]` |
| `ThermochemicalCalculator.get_available_species` | `list[SpeciesInfo]` |
| `ThermoDBQuery.find_species` | `list[SpeciesInfo]` |
| `ThermoDBQuery.get_species_data` | `SpeciesData` (espécie + `list[IntervalData]`) |
| `ThermoDBQuery.get_species_info` (novo) | `SpeciesInfo | None` |
| `ThermoDBQuery.get_species_for_temperature` | `IntervalData | None` |
| `ThermoDBQuery.list_species_page` | `tuple[list[SpeciesInfo], int]` |
| `ThermoDBQuery.list_all_species` (novo) | `list[SpeciesInfo]` |
| `ThermoDBQuery.get_statistics` | `DatabaseStats` |

- Dataclasses `frozen` e com `Optional` preciso para campos nulos (`formula`,
  `molecular_weight`, `heat_of_formation_298K`, `h_298_to_0`).
- Campos nulos permanecem `None`; nunca viram `0.0` implicitamente.
- `dataclasses.asdict()` é o mecanismo documentado para JSON/serialização.
- **Entradas** de coeficientes (ex.: `calculate_cp/h/s`) continuam aceitando
  `dict` **ou** `NASACoefficients` — a mudança é só no **retorno**.

## D2. Política de compatibilidade para resultados dict

- Resultados `dict` são **removidos** dos métodos públicos; não há período de
  deprecação por retorno duplo.
- Migração de consumidores via `CHANGELOG` + guia de migração na documentação
  (exemplos "antes/depois" com `dict` e com dataclass).
- `dict` continua existindo apenas como formato de **entrada** aceito (coeficientes).

## D3. Migração de metadados — AUTOMÁTICA no connect (G2/G6)

- `ThermoDBQuery.connect()` detecta banco legado (sem a tabela `metadata`) e aplica
  a migração **automaticamente**, gravando as chaves canônicas.
- Escopo da escrita: **somente** a tabela aditiva `metadata`. Nunca altera
  `species`, `temperature_intervals` ou `coefficients`.
- O fallback para `R_UNIVERSAL` passa a ocorrer **apenas** quando o valor de
  `gas_constant_ref` está ausente, inválido ou implausível — não mais por ausência
  da tabela.
- `migrate_metadata()` permanece público e idempotente (a automação o invoca).
- **Impacto em testes existentes:** `test_reference_gas_constant_legacy_fallback_and_migration`
  deve ser atualizado (o fallback legado por ausência de tabela deixa de existir).

## D4. Tolerâncias numéricas cross-language

| Grandeza | Tolerância |
|---|---|
| Cp, S (J/(mol·K)) | `rel_tol=1e-9`, `abs_tol=1e-6` |
| H (J/mol) | `rel_tol=1e-9`, `abs_tol=1e-6` |
| ΔH°f de O2 (= 0) | `abs_tol=1.0` J/mol |

- Comparações usam `math.isclose(..., rel_tol=..., abs_tol=...)`; nunca comparam
  saída arredondada de display.
- `rel_tol=1e-9` é folgado o bastante para diferenças de ordem de avaliação entre
  Julia e Python, e estrito o bastante para detectar o viés de ~5,7 ppm (5,7e-6).

## D5. Valor canônico da constante de referência

- A chave `gas_constant_ref` deve ser gravada com a string literal **`'8.314510'`**
  (não `str(R_GLENN)`, que produziria `'8.31451'`).
- `gas_constant_ref_source = 'NASA Glenn/CEA thermo.inp (CODATA 1986)'`.
- `R_GLENN = 8.314510` (float) continua sendo o valor numérico usado nos cálculos;
  a decisão aqui é sobre a **representação textual persistida**.

## Versionamento

- Pré-1.0: mudança de retorno é **breaking** → bump de minor: `0.1.13 → 0.2.0`.
- `pyproject.toml` (dynamic via `__init__.__version__`), `conda.recipe/meta.yaml` e
  distribuições geradas sobem juntos.

## Critérios de aceite do contrato

1. Métodos públicos retornam as dataclasses listadas em D1.
2. `dataclasses.asdict()` reconstrói o `dict` equivalente antigo (mesmas chaves).
3. `connect()` migra automaticamente banco legado sem tocar dados termoquímicos.
4. Tolerâncias D4 aplicadas nos testes cross-language.
5. `gas_constant_ref` persistida como `'8.314510'`.
