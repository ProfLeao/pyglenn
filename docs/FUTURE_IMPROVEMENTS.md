# Melhorias Futuras

Registro de melhorias identificadas durante as auditorias, priorizadas e com
escopo definido. Itens de **baixa prioridade** não bloqueiam a release corrente.

---

## FI-1 — Granularidade de fase (sólido vs líquido) perdida no esquema

**Prioridade:** Baixa
**Origem:** item de auditoria A4
**Estado:** não iniciado

### Contexto

O esquema reduz a fase a dois valores:

```sql
phase TEXT CHECK(phase IN ('gas', 'condensed'))
```

O `thermo.inp` da NASA codifica **mais granularidade** na coluna de fase
(índices 50–51, 0-indexed). Verificado nos dados reais:

| Código bruto | Interpretação | Ocorrências |
|---|---|---|
| `0` | gás | 1266 |
| `1` | sólido | 391 |
| `2` | líquido | 258 |
| `3` / `4` / `5` | granularidade adicional | 170 |

O parser colapsa tudo que não é `0` para `condensed`:

```python
# ThermoDBBuilder.parse_general_info_record
data['phase'] = 'condensed' if phase_code and phase_code != '0' else 'gas'
```

### Impacto

- **Sem impacto em correção numérica** — os polinômios NASA-7 não dependem da fase.
- **Sem perda irreversível** — o sufixo de fase está preservado em `species.name`
  (ex.: `H2O(L)`, `C(gr)`, `Fe(a)`, `PbO(I-y)`, `PbO(II-r)`) e o código bruto
  continua no `thermo.inp`.
- **Impacto real** — 769 espécies (≈38% do dataset) são `condensed` e não podem
  ser filtradas por sólido vs líquido via API pública (`ThermoProperties.phase`,
  `get_available_species`, `list_all_species`). Atinge usuários de fase
  condensada (metalurgia, cerâmica, materiais). O público primário (combustão,
  fase gasosa) não é afetado.

### Por que é baixa prioridade

1. Não é bug de correção — é lacuna de **metadado**.
2. É recuperável por rebuild do `thermo.inp` (não exige migração arriscada).
3. O caso de uso dominante (fase gasosa) já está completo e correto.

### Abordagem correta (quando for implementar)

1. Adicionar `phase_detail TEXT` no **builder**, derivada do código bruto da
   coluna 50–51 (`0` → `gas`, `1` → `solid`, `2` → `liquid`, `3`/`4`/`5` →
   mapear conforme a documentação NASA/CEA).
2. Manter `phase` como agrupamento derivado (`gas` vs `condensed`) para
   retrocompatibilidade.
3. **Reconstruir** o `thermo.db` a partir do `thermo.inp` e rodar
   `validate_database()`.
4. Documentar o domínio de `phase_detail` em `docs/source/database.rst`, na
   dataclass `SpeciesInfo` e no README.

### O que NÃO fazer

- ❌ **Migração sobre a coluna colapsada** — `UPDATE species SET phase_detail =
  CASE WHEN phase='gas' THEN 'gas' ELSE 'condensed' END`. Deriva do dado já
  colapsado e **não recupera** sólido vs líquido (no-op). A granularidade não
  está na coluna `phase`; está no `thermo.inp`.
- ❌ **Derivar `crystal_structure` por heurística de sufixo** (`(L)`, `(cr)`,
  `(gr)`, `(I)`, `(II)`, `(a)`, `(b)`, `(II-r)`, `(I-y)`) sem uma tabela de
  mapeamento explícita — a fronteira entre abreviatura de fase e rótulo
  cristalino é ambígua.
- ❌ **Normalizar/remover o sufixo de fase do nome** — ele é identidade da
  espécie (ver auditoria A3): `Fe(a)` ≠ `Fe(b)` ≠ `Fe(L)`.

### Critérios de aceite (não-vazios)

- `phase_detail` preenchida para 100% das espécies, com o valor correto derivado
  do **código bruto do `thermo.inp`** (não da coluna `phase`).
- Soma de `solid` + `liquid` (+ demais) igual ao total atual de `condensed`
  (769), dentro de tolerância zero.
- Filtro por `phase_detail` disponível em `get_available_species`/
  `list_all_species`/`find_species`.
- Rebuild reproduz as contagens por fase de forma determinística (testado).

### Relacionado

- **A1** (`h_relative`): resolvido na 0.3.0 (`h_sensible_to` + documentação).
- **A2** (`_FORTRAN_D_RE` "morto"): falso — a regex é usada por
  `is_coefficient_line`.
- **A3** (canonicalização de nome): a unificação de sufixo de fase proposta
  colidiria com 319 bases distintas; não implementar.

---

## FI-2 — Depreciar `get_properties_range` em favor de `calculate_properties_range`

**Prioridade:** Baixa
**Origem:** item de auditoria A5
**Estado:** não iniciado

### Contexto

Há dois caminhos públicos para propriedades em várias temperaturas, com
contratos diferentes:

| Método | Retorno | Fora do intervalo |
|---|---|---|
| `get_properties_range(sid, temps)` | `dict[float, ThermoProperties] \| None` | engole (`except TemperatureOutOfRangeError: pass`) |
| `calculate_properties_range(sid, temps, *, strict=False)` | `list[ThermoProperties]` | engole no default; levanta com `strict=True` |

**Correção ao item A5:** o método novo **também engole** fora-do-intervalo no
default (`strict=False`) — apenas devolve `[]` em vez de `None`. A diferença
real está em três pontos: (1) forma de retorno (dict keyed por T → lista
ordenada pela entrada); (2) `[]` vs `None` quando tudo falha; (3) carregamento
único dos intervalos (performance). Não é verdade que o novo método "não engole
nada".

### Impacto

- Não é bug de correção — é consolidação de API.
- `None` do legado é ambíguo (não-conectado vs tudo-fora-do-range vs entrada
  vazia), mas `calc.connected` desambigua o primeiro caso.
- Dois caminhos sobrepostos confundem novos usuários; o legado já foi marcado
  como retrógrado no contrato D1.

### Abordagem

1. Emitir `DeprecationWarning` em `get_properties_range` com `stacklevel=2`,
   apontando para `calculate_properties_range` **e mencionando a mudança de
   forma de retorno** (dict → lista ordenada).
2. Documentar `calculate_properties_range` como canônico em `api.rst` e
   `usage.rst`, descrevendo os dois estados de `strict`.
3. Atualizar os testes que chamam `get_properties_range`
   (`test_get_properties_range`, `test_calculator_not_connected`) para conviver
   com o warning (`pytest.warns` / `filterwarnings`).
4. Remover o método na **0.4.0**.

### Critérios de aceite

- `pytest.warns(DeprecationWarning)` captura exatamente um aviso contendo
  `calculate_properties_range` ao chamar `get_properties_range`.
- Nenhum método interno chama `get_properties_range` (já verdade hoje; manter).
- A mensagem cita a diferença de retorno (dict → list) e o parâmetro `strict`.

---

## FI-3 — Índices de banco: recomendados na doc mas redundantes

**Prioridade:** Baixa (descartar/documentar)
**Origem:** item de auditoria A6
**Estado:** não fazer

### Veredito

- `docs/README.txt` recomenda `idx_species_name` e `idx_intervals_species`, mas
  `create_tables` não os cria explicitamente. Porém:
  - `species.name` é `UNIQUE` → autoíndice `sqlite_autoindex_species_1`;
  - `temperature_intervals` tem `UNIQUE(species_id, interval_number)` →
    autoíndice `sqlite_autoindex_temperature_intervals_1`.
- `EXPLAIN QUERY PLAN` confirma: a consulta de intervalo usa
  `SEARCH ... USING INDEX sqlite_autoindex_temperature_intervals_1
  (species_id=?)` — **não** SCAN.
- `find_species` (exato e substring) faz SCAN porque `UPPER(name)` e
  `LIKE '%…%'` impedem o uso do índice — um índice simples sobre `name` **não**
  resolveria; só um índice funcional `ON species(UPPER(name))` teria efeito.

### Decisão

- **Não criar** os índices propostos (redundantes com os autoíndices).
- Atualizar `docs/README.txt` para explicar os autoíndices em vez de sugerir
  `CREATE INDEX` redundante.
- Opcional (micro-otimização para 2.035 linhas):
  `CREATE INDEX idx_species_name_upper ON species(UPPER(name));` — baixo valor.

---

## FI-4 — Modo estrito de parsing (`strict_parse`)

**Prioridade:** Baixa
**Origem:** item de auditoria A9
**Estado:** não iniciado (opcional)

### Veredito

- Falso o núcleo da auditoria: `_parse_intervals` **já valida** cada intervalo
  (`is_temperature_line`, `is_coefficient_line`, limites finitos/ordenados e
  nove coeficientes finitos). Blocos malformados são **pulados** (com
  `logging.WARNING`), nunca inseridos — não existe "espécie silenciosamente
  errada".
- Falso o detalhe: o código de fase está nas colunas **50–52** (`line[50:52]`),
  não na coluna 45.
- O `thermo.db` empacotado é construído com **0 blocos malformados pulados**,
  então um modo estrito não mudaria o resultado oficial.

### Decisão

- Se desejado, adicionar `strict_parse: bool = False` como modo **aditivo** de
  diagnóstico (levantar `MalformedRecordError` com o número da linha), mantendo
  o default tolerante. Baixo valor para o dataset atual.

---

## Resolvido na 0.3.0

- **A1** (`h_relative`): `h_sensible_to` + documentação.
- **A7** (licença): copyright corrigido para o autor (2026) + `NOTICE` de
  linhagem Glenn.jl + classifier de licença no `pyproject.toml`.
- **A8** (`py.typed`): `py.typed` criado e incluído em `package-data`
  (`__all__` já existia).

