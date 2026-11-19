# Plano de Implementação — pyglenn 0.5.0

**Branch:** `release/0.5.0`
**Data:** 2026-11-19
**Base:** `main` @ `fc87508` (0.4.0)

---

## Visão geral

A 0.5.0 tem **duas metas** registradas em `docs/FUTURE_IMPROVEMENTS.md`:

| Meta | O que é | Prioridade | Natureza |
|---|---|---|---|
| **UQ-1** | Orçamento de erro termoquímico por espécie | Média | Dados + script de auditoria (+ tabela SQLite) |
| **FI-1** | Granularidade de fase (sólido vs líquido) | Baixa | Schema + builder + API + rebuild |

As duas são **independentes** (UQ-1 mexe em auditoria/dados de referência;
FI-1 mexe no parser/schema). Podem ser desenvolvidas em paralelo e
entregues em commits separados.

---

## Meta 1 — UQ-1: Orçamento de erro por espécie

### Objetivo

Produzir um **envelope de erro empírico** em Cp/H/S(T) por espécie, validado
contra NIST-JANAF (Chase 1998, equação de Shomate), aberto e versionado.
**Não** é covariância de coeficientes (isso é UQ-2, longo prazo).

### Etapas

#### U1. Referência versionada (dados)

- Criar `docs/audit/shomate_reference.json` com os coeficientes Shomate
  (A..H) por espécie/fase, extraídos do NIST Chemistry WebBook (SRD 69).
- **Piloto:** ~20 espécies cobrindo a diversidade da base:
  - gases simples: `N2`, `O2`, `CO`, `CO2`, `H2O`;
  - orgânicos: `CH4`, `C2H6`, `C2H5OH`, `C3H8`;
  - inorgânicos: `NH3`, `SO2`, `H2S`, `NO`, `NO2`;
  - condensados: `C(gr)`, `Cr(cr)`, `Fe(a)`, `Ni(cr)`, `SiO2(cr)`, `Al2O3(cr)`.
- **Schema do JSON** (aninhado, pois Shomate tem N faixas × 8 coeffs):

```json
{
  "source": "NIST-JANAF (Chase 1998), NIST Chemistry WebBook SRD 69",
  "extracted": "2026-11-19",
  "species": {
    "CO2": {
      "formula": "CO2",
      "phase": "gas",
      "ranges": [
        {"Tmin": 298, "Tmax": 1200, "A": 24.99735, "B": 55.18696, "C": -33.69137,
         "D": 7.948387, "E": -0.136638, "F": -403.6075, "G": 228.2431, "H": -393.5224},
        {"Tmin": 1200, "Tmax": 6000, "A": 58.16639, "B": 2.720074, "C": -0.492289,
         "D": 0.038844, "E": -6.447293, "F": -425.9186, "G": 263.6125, "H": -393.5224}
      ]
    }
  }
}
```

- Os 7 espécies já hardcoded em `docs/audit/audit_code.py` (`SHOMATE`) servem
  de semente e passam a ler deste JSON (sem duplicação).

#### U2. Casamento de espécies

- Tabela de mapeamento `pyglenn_name ↔ (nist_key, phase)` para resolver
  diferenças de nome/fase (ex.: `H2O` gás ↔ `H2O(g)`; `Cr(cr)` ↔ `Cr(s)`).
- Armazenar o mapeamento no próprio script (dict) ou num arquivo auxiliar
  versionado, com `TODO` explícito para fases ambíguas.

#### U3. Script de comparação

- `docs/audit/error_budget.py` (extensão do `audit_code.py`):
  - lê o JSON de referência e o mapeamento;
  - para cada espécie casada, amostra N temperaturas dentro do range válido
    do pyglenn (ex.: 20 pontos log-espaçados por intervalo);
  - calcula Cp, H, S nos dois lados e registra erro por ponto.

#### U4. Agregação por espécie

- Para cada espécie: viés médio relativo, erro máximo relativo, RMS e o
  perfil erro-vs-T (bordas de intervalo, T alta).
- Saída: `docs/audit/species_error.csv` com colunas:
  `species, phase, T_min, T_max, n_points, cp_rel_bias, cp_rel_max,
  cp_rel_rms, h_rel_bias, h_abs_max, s_abs_bias, s_abs_max`.

#### U5. Modelo de erro + runtime (SQLite)

- Tabela aditiva `species_uncertainty` no `thermo.db` (como `metadata`):

```sql
CREATE TABLE IF NOT EXISTS species_uncertainty (
    species_id INTEGER PRIMARY KEY REFERENCES species(id) ON DELETE CASCADE,
    cp_rel_bias REAL, cp_rel_2sigma REAL,
    h_rel_bias REAL, h_rel_2sigma REAL,
    s_abs_2sigma REAL,
    n_ref_points INTEGER,
    source TEXT CHECK(source IN ('nist-janaf', 'extrapolated')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- `source='nist-janaf'` para espécies validadas; `source='extrapolated'` para
  as demais (calibradas por fase/classe no subconjunto validado).
- API opcional (só se o dado estiver populado):
  `ThermochemicalCalculator.uncertainty(species_id, T) -> dict`.

#### U6. Validação e publicação

- `docs/audit/error_budget_summary.txt`: método, limitações, tiers, pino de
  versão da referência e do dataset.
- Testes de regressão: reprodução do orçamento para as espécies-piloto dentro
  de tolerância; `validate_database()` confere integridade de
  `species_uncertainty`.

### Critérios de aceite (UQ-1)

- Piloto (~20 espécies) validado e versionado, com CSV + summary.
- `species_uncertainty` presente e consistente (FK, `source` válido).
- Documentação da extrapolação (fase/classe) explícita — sem números sem
  pino de versão.

### Riscos / limitações

- NIST-JANAF **não cobre as 2 035 espécies**: orçamento será parcialmente
  validado e parcialmente extrapolado (documentado).
- Extração de Shomate é manual/propensa a erro → double-check por par
  (revisão) antes de versionar.

---

## Meta 2 — FI-1: Granularidade de fase (sólido vs líquido)

### Objetivo

Adicionar `phase_detail` (sólido vs líquido, além do `gas`/`condensed`
atual), derivada do **código bruto de fase** do `thermo.inp` — não da coluna
`phase` já colapsada.

### Etapas

#### F1. Levantar o domínio dos códigos

- Extrair todos os valores da coluna de fase (índices 50–52) do `thermo.inp`
  e suas contagens (auditoria A4/FI-4 já indicou: `0`=1266, `1`=391, `2`=258,
  `3/4/5`=170).
- **Investigar o significado de `3/4/5`** na documentação NASA/CEA antes de
  mapear (não adivinhar). Definir a tabela de mapeamento em código/constante.

#### F2. Schema + builder

- Adicionar `phase_detail TEXT` à tabela `species` (coluna aditiva).
- Estender `parse_general_info_record` para extrair `phase_detail` do código
  bruto e `INSERT INTO species` para gravá-la.
- Manter `phase` como agrupamento derivado (`gas` | `condensed`) para
  retrocompatibilidade.

#### F3. Modelo + API

- Adicionar `phase_detail` às dataclasses `SpeciesInfo` e `SpeciesData`
  (`from_mapping` incluído).
- Expor filtro `phase_detail` em `get_available_species`, `list_all_species`
  e `find_species` (parâmetro opcional, sem quebrar assinaturas).

#### F4. Rebuild + validação

- Rebuild do `thermo.db` (gate de intervalos continua 3 795).
- `validate_database()` ganha checagens: `phase_detail` preenchida para 100%,
  soma `solid`+`liquid`+… = total de `condensed` (769), e consistência
  `phase` ↔ `phase_detail`.

#### F5. Documentação + testes

- Documentar o domínio de `phase_detail` em `docs/source/database.rst`, na
  docstring de `SpeciesInfo` e no README/cheat sheet.
- Testes: contagens por fase determinísticas, filtro por `phase_detail`,
  rebuild reproduzível.

### Critérios de aceite (FI-1)

- `phase_detail` preenchida para 100% das espécies (valor derivado do código
  bruto).
- `solid` + `liquid` (+ demais) == 769, tolerância zero.
- Filtro por `phase_detail` disponível nas três funções de busca.
- Rebuild determinístico (testado).

### Riscos / limitações

- **Códigos `3/4/5`** sem documentação clara podem exigir decisão conservadora
  (ex.: manter como `condensed` + sub-rotular como `other`).
- NÃO derivar de heurística de sufixo de nome (`(L)`, `(gr)`, …) — a fronteira
  fase/cristal é ambígua (auditoria A3).

---

## Sequenciamento e milestones

| # | Marco | Conteúdo | Depende de |
|---|---|---|---|
| M1 | UQ-1 piloto | U1–U4 (JSON + script + CSV) | — |
| M2 | UQ-1 runtime | U5–U6 (tabela SQLite + summary + testes) | M1 |
| M3 | FI-1 parser | F1–F2 (mapeamento + builder) | — |
| M4 | FI-1 API | F3 (dataclasses + filtros) | M3 |
| M5 | FI-1 rebuild | F4–F5 (rebuild + validate + testes) | M4 |
| M6 | Release 0.5.0 | bump versão + CHANGELOG + rebuild final + tag | M2, M5 |

M1/M2 (UQ-1) e M3–M5 (FI-1) são **paralelizáveis**; só o M6 é serial.

---

## Definição de pronto (0.5.0)

- [ ] UQ-1: piloto validado + `species_uncertainty` + summary + testes.
- [ ] FI-1: `phase_detail` + filtros + rebuild + validação + testes.
- [ ] `__version__` → `0.5.0`; `conda.recipe/meta.yaml` idem.
- [ ] `CHANGELOG.md` com seção `[0.5.0]`.
- [ ] `docs/FUTURE_IMPROVEMENTS.md`: UQ-1 e FI-1 marcados como resolvidos.
- [ ] Pipeline verde: `pytest`, `ruff check`, `ruff format`, `mypy`,
      `sphinx -b html -W`, e `python -m build`.
- [ ] Rebuild final do `thermo.db` via `scripts/rebuild_database.py`
      (gates 2 035 / 3 795 / 3 795).

---

## Comandos de validação (resumo)

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m ruff format --check src tests
.venv\Scripts\python.exe -m mypy src/pyglenn
.venv\Scripts\python.exe -m sphinx -b html -W docs/source docs/build/html
.venv\Scripts\python.exe -m build --no-isolation
.venv\Scripts\python.exe scripts/rebuild_database.py
```
