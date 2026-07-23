# Changelog — pyglenn

---

## v0.1.11 (2026-07-22)

**Base:** v0.1.10
**Commits:** `aa6138c`, `0648e12`, `129b2a4`, `8991afb`

### Correções

| # | Descrição | Gravidade |
|---|-----------|-----------|
| 🔴 | `thermo.db` removido do tracking git na raiz (duplicata de `src/pyglenn/data/`) | Alta |
| 🟡 | 11 `assert` substituídos por `if ... is None: raise RuntimeError(...)` em `builder.py` e `database.py` — seguro com `python -O` | Média |
| 🟢 | `docs/` removido do `MANIFEST.in` — reduz tamanho do sdist | Baixa |
| 💡 | `cli.py` incluído na cobertura de testes (`pyproject.toml`) | Sugestão |

### Arquivos alterados

| Arquivo | Mudança |
|---------|---------|
| `thermo.db` | Removido do tracking (`.gitignore` já o ignorava) |
| `src/pyglenn/builder.py` | 6 asserts → `RuntimeError` |
| `src/pyglenn/database.py` | 5 asserts → `RuntimeError` |
| `MANIFEST.in` | `recursive-include docs` comentado |
| `pyproject.toml` | `omit = ["src/pyglenn/cli.py"]` removido |

---

## v0.1.10 (2026-07-22)

**Data:** 2026-07-22
**Base:** v0.1.5 (source) / v0.1.9 (pip)
**Commits:** `860a995`, `dc9af42`, `d6eb054`

---

## Inconsistências Corrigidas

As 4 inconsistências relatadas em `relatorio_inconsistencias_pyglenn_v0_1_9.txt`
foram todas corrigidas.

### ✅ Inconsistência 1 — `get_available_species()` retornava espécie errada (CRÍTICA)

**Problema:** `LIKE '%name%'` com `LIMIT 20` fazia `get_available_species('N2')`
retornar `Be3N2(L)` em vez de `N2` molecular. 5 de 9 consultas falhavam (56%).

**Solução:**
- `find_species()` (database.py) ganhou parâmetro `exact_match=False`
- `get_available_species()` (calculator.py) expõe `exact_match`
- Quando `exact_match=True`, usa `WHERE UPPER(name) = UPPER(?)` — case-insensitive
- Default mantém `LIKE` para compatibilidade reversa

**Exemplo:**
```python
# Antes (quebrado)
calc.get_available_species('N2')[0]  # → Be3N2(L) ❌

# Depois (corrigido)
calc.get_available_species('N2', exact_match=True)[0]  # → N2 ✅
```

---

### ✅ Inconsistência 2 — `calculate_properties()` retornava None em fronteiras (ALTA)

**Problema:** `calculate_properties(sid, 1000.0)` retornava `None` quando a
temperatura estava exatamente no limite entre dois intervalos (ex: 1000 K
é max do intervalo 1 e min do intervalo 2).

**Causa raiz:** query SQL sem `ORDER BY` + possível erro de ponto flutuante
no builder (FORTRAN `D` → float).

**Solução:**
- `get_species_for_temperature()` (database.py):
  - Adicionado `ORDER BY ti.interval_number` — determinístico
  - Adicionada tolerância de 1e-9: `temp_max + 1e-9 >= ?`
- `calculate_properties()` (calculator.py): **agora lança exceções** em vez
  de retornar `None`:
  - `DatabaseNotConnectedError` — sem conexão
  - `SpeciesNotFoundError` — ID inválido
  - `TemperatureOutOfRangeError` — T fora dos intervalos

**⚠️ Breaking change:** código que usa `if props is None` precisa migrar
para `try/except ThermoCalcError`.

---

### ✅ Inconsistência 3 — Ordenação imprevisível dos resultados (MÉDIA)

**Problema:** `ORDER BY name` (alfabético) não priorizava correspondências
exatas. `'N2'` retornava Be3N2 antes de N2.

**Solução:** `find_species()` agora ordena com `CASE WHEN UPPER(name) = UPPER(?) THEN 0 ELSE 1 END` — matches exatos no topo, depois ordem alfabética.

---

### ✅ Inconsistência 4 — Comportamento não determinístico (BAIXA)

**Problema:** `get_species_for_temperature()` sem `ORDER BY` permitia que o
SQLite retornasse qualquer intervalo quando dois cobriam a mesma temperatura.

**Solução:** `ORDER BY ti.interval_number` garante seleção determinística
do intervalo inferior.

---

## Outras Alterações

### Documentação atualizada

| Arquivo | Mudança |
|---------|---------|
| `README.md` | Exemplos usam `exact_match=True` |
| `docs/paper_zenodo/paper.md` | Idem |
| `docs/source/index.rst` | Idem |
| `docs/source/usage.rst` | Idem + nota sobre uso de `exact_match` |
| `examples/01_basic_usage.ipynb` | 3 células atualizadas |
| `examples/02_fuel_comparison.ipynb` | `resolve_id()` removido — substituído por `exact_match=True` |
| `docs/audit/audit_code.py` | `if props is None` → `try/except ThermoCalcError`; match exato |

### Código

| Arquivo | Mudança |
|---------|---------|
| `src/pyglenn/cli.py` | `if props:` → `try/except ThermoCalcError` |
| `src/pyglenn/calculator.py` | Docstring de `calculate_enthalpy_change` corrigida |
| `tests/test_calculator.py` | +6 testes (fronteiras 200/1000/6000 K, exact_match); fixture com 2 intervalos |

### Versão

- `src/pyglenn/__init__.py`: `__version__ = '0.1.10'`
- `conda.recipe/meta.yaml`: `version = "0.1.10"`

---

## Migração da v0.1.9 para v0.1.10

### get_available_species()

```python
# Antes — risco de espécie errada
species = calc.get_available_species('N2')
n2_id = species[0]['id']  # podia ser Be3N2(L)!

# Depois — seguro
species = calc.get_available_species('N2', exact_match=True)
n2_id = species[0]['id']  # garantido: N2 molecular
```

### calculate_properties()

```python
# Antes — None silencioso
props = calc.calculate_properties(sid, 1000.0)
if props is None:  # ← acontecia na fronteira
    ...

# Depois — exceção explícita
from pyglenn import ThermoCalcError

try:
    props = calc.calculate_properties(sid, 1000.0)
except ThermoCalcError:
    ...
```

### 02_fuel_comparison.ipynb

```python
# Antes — 10 linhas
def resolve_id(calc, name, phase='gas'):
    for s in calc.get_available_species(name):
        if s['name'] == name and s['phase'] == phase:
            return s['id']
    raise ValueError(...)

# Depois — 1 linha
calc.get_available_species(name, exact_match=True)[0]['id']
```

---

## Testes

```
44 passed in 0.45s ✅
```

Novos testes:
- `test_calculate_properties_lower_boundary` — T = 200.0 K
- `test_calculate_properties_shared_boundary` — T = 1000.0 K
- `test_calculate_properties_upper_boundary` — T = 6000.0 K
- `test_get_available_species_exact_match` — case-insensitive, sem match
- `test_thermodbquery_find_species_exact_match` — API de baixo nível
