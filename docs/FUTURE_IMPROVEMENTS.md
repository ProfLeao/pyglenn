# Melhorias Futuras

Registro de melhorias identificadas durante as auditorias, priorizadas e com
escopo definido. Itens de **baixa prioridade** não bloqueiam a release corrente.

---

## Metas da próxima versão

- **UQ-1** — Orçamento de erro termoquímico por espécie (envelope de erro em
  Cp/H/S(T) validado contra NIST-JANAF).
- **FI-1** — Granularidade de fase (sólido vs líquido) via `phase_detail`
  derivada do código bruto do `thermo.inp`.
- **DOC-1** — Documentação: revisão e extensão dos notebooks de exemplo e
  criação de um blog de atualizações trilingue (pt/en/es).

---

## DOC-1 — Documentação, notebooks e blog de atualizações

**Prioridade:** Média (meta da próxima versão)
**Origem:** manutenção da documentação de usuário
**Estado:** não iniciado

### Contexto

A documentação de usuário (site Sphinx, em inglês) e os notebooks de exemplo
são a principal porta de entrada do pyglenn. Eles precisam (1) ser revisados
para clareza científica e linguagem natural (com a skill `avoid-ai-writing`),
(2) demonstrar as novas funcionalidades da 0.5.0 e (3) registrar as
atualizações de cada versão em um blog trilingue.

### Abordagem

1. Revisar os notebooks de `examples/` (fonte única da verdade; as cópias sob
   `docs/source/examples/` são geradas no build).
2. Estender os notebooks com `uncertainty` (UQ-1) e `phase_detail` (FI-1)
   quando as funcionalidades estiverem prontas.
3. Criar `docs/source/blog/` com posts por versão em pt/en/es.

### Critérios de aceite

- Notebooks sem marcas de redação automatizada, com clareza científica.
- Notebooks cobrem as novidades da 0.5.0.
- Blog com a entrada da 0.5.0 em pt/en/es publicado no site.

---

## FI-1 — Granularidade de fase (sólido vs líquido) perdida no esquema

**Prioridade:** Baixa (meta da próxima versão)
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
**Estado:** resolvido (depreciação na 0.3.0, remoção na 0.4.0)

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

- Uma documentação legada (removida) recomendava `idx_species_name` e
  `idx_intervals_species`, mas `create_tables` não os cria explicitamente.
  Porém:
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
- Nada a documentar — a doc legada que sugeria os índices foi removida.
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

## B1 — `validate_database --full` com checagem contra dados de referência

**Prioridade:** Baixa
**Origem:** item de auditoria B1
**Estado:** não iniciado

### Contexto

`validate_database()` é **estrutural**: contagens, chaves estrangeiras, limites
finitos/ordenados, continuidade entre intervalos. A auditoria B1 propõe ir além
e validar os **valores** (Cp, H, S) contra uma fonte de referência externa
(NIST-JANAF, CEA, NASA TP-2002).

### Ressalva obrigatória (por que não é trivial)

- O dataset usa `R_GLENN = 8.314510` (CODATA 1986), enquanto fontes modernas
  usam CODATA 2018/2022; isso introduz desvio sistemático da ordem de 1e-6.
- Os polinômios do `thermo.inp` têm precisão finita (7 algarismos nos
  coeficientes), então pontos fora das âncoras acumulam erro de arredondamento.
- A convenção `H°(298.15) = ΔH°f(298.15)` deve ser respeitada ao comparar
  entalpias — nunca comparar `H(0 K)` (não existe neste dataset).

### Abordagem

1. Adicionar `validate_database(full: bool = False)` ou subcomando CLI
   `validate --full`, que amostra N temperaturas por espécie (ex.: 200, 298.15,
   500, 1000, 2000, 4000 K dentro de cada intervalo) e compara contra uma
   tabela de referência **versionada** (arquivo pinado em
   `docs/audit/` ou `data/reference.csv`).
2. Tolerâncias **generosas** e por propriedade (ex.: `rel=1e-4` para Cp/H/S em
   fase gasosa; mais folga para fase condensada), documentadas na saída.
3. Reportar por espécie/intervalo, com resumo agregado (máx. desvio relativo).

### O que NÃO fazer

- ❌ Comparar com constantes de gás diferentes sem corrigir o fator.
- ❌ Tratar desvio < 1e-6 como falha — é ruído de constante/arredondamento.
- ❌ Usar referências sem pino de versão (torna a validação não-reprodutível).

---

## B2 — Ajuste de polinômios NASA-7 a partir de dados brutos (`fit_nasa7`)

**Prioridade:** Média
**Origem:** item de auditoria B2
**Estado:** resolvido na 0.3.0

### Contexto

Não existe caminho para gerar um conjunto NASA-7 a partir de dados tabulados
(T, Cp/H/S) — só leitura do `thermo.inp`. A auditoria B2 propõe expor um
ajustador.

### Escopo proposto

- API: `fit_nasa7(temperatures, cp_values, t_ref=298.15, h_ref=0.0, ...) ->
  NASACoefficients`, com pesos opcionais por ponto.
- Ajuste por mínimos quadrados nas 7 potências `a1..a7`, impondo por construção
  `H°(t_ref) = h_ref` (isto é, `b1` derivado do polinômio de H avaliado em
  `t_ref`, coerente com a convenção do dataset).
- Para múltiplos intervalos: continuidade de **valor e primeira derivada** no
  ponto de emenda (restrição linear no problema de mínimos quadrados).

### Critérios de aceite

- Reproduz um polinômio NASA-7 sintético com erro relativo < 1e-6 nos pontos
  amostrados.
- `H°(t_ref)` do resultado igual a `h_ref` dentro de tolerância numérica.
- Documentação da convenção (constante `b1`, não `a6`) no docstring.

---

## B3 — Exportação Chemkin / Cantera (com ressalvas)

**Prioridade:** Baixa
**Origem:** item de auditoria B3
**Estado:** não iniciado

### Contexto

Interoperabilidade com Chemkin (`thermo.dat`) e Cantera (YAML). A auditoria B3
sugere exportar as espécies do dataset.

### Ressalva crítica (impede "dump direto")

O formato NASA-7 do **Chemkin** difere do **NASA-CEA** (origem do `thermo.inp`):

| Item | NASA-CEA (nosso) | Chemkin |
|---|---|---|
| Constante de entalpia | `b1` (colunas 73–78) | `a6` |
| Constante de entropia | `b2` (colunas 79–84) | `a7` |
| `a6`, `a7` | zero | carregam as constantes |

Ou seja: `a6`/`a7` têm **significados diferentes** nos dois formatos. Exportar
exige **transformação de base** — mover `b1 → a6` e `b2 → a7` — e revalidação
numérica contra o arquivo de origem.

### Abordagem

1. Implementar `export_chemkin(path)` e/ou `export_cantera(path)` que façam a
   transformação `b1/b2 → a6/a7` e escrevam o cabeçalho Chemkin apropriado
   (divisão de faixa 200–1000 / 1000–6000 K, quando aplicável).
2. Validar round-trip: importar o arquivo exportado em Cantera e comparar
   Cp/H/S contra `calculate_properties` em N temperaturas.
3. Documentar a transformação de base explicitamente (não esconder em
   comentário).

### O que NÃO fazer

- ❌ Copiar `a1..a7, b1, b2` direto para as colunas Chemkin — inverte o
  significado de `a6`/`a7` e corrompe H/S.
- ❌ Anunciar "exportação Chemkin" sem teste de round-trip.

---

## UQ-1 — Orçamento de erro termoquímico por espécie (curto prazo)

**Prioridade:** Média (meta da próxima versão)
**Origem:** comentário externo de revisão (nov/2026)
**Estado:** não iniciado

### Contexto

Os coeficientes NASA-7 do `thermo.inp` são publicados **sem incerteza**. Um
revisor apontou que ninguém propaga esse erro até composição de equilíbrio ou
temperatura de chama adiabática de forma sistemática e aberta, e que um
"orçamento de erro validado sobre a base inteira seria excelente".

Este item cobre a parte **factível no curto prazo**: um **envelope de erro
empírico por espécie** em Cp/H/S(T), derivado de comparação com referência
independente — **não** a covariância dos coeficientes (ver UQ-2).

### Abordagem (método)

1. **Referência fixada:** NIST-JANAF (Chase 1998), equação de Shomate,
   versionada em `docs/audit/` como JSON (Shomate é aninhado: N faixas × 8
   coeficientes — CSV não representa bem).
2. **Casamento de espécies:** mapear `pyglenn: H2O (gas)` ↔ `NIST: H₂O(g)`,
   com cuidado especial com fases condensadas (`Cr(cr)`, `Fe(a)`, …).
3. **Amostragem e comparação:** N temperaturas por espécie, dentro do range
   válido, calculando Cp/H/S nos dois lados.
4. **Agregação por espécie:** viés médio, erro máximo, RMS e perfil erro-vs-T
   (bordas de intervalo, T alta).
5. **Modelo de erro:** tabela por espécie + classificação em tiers por
   fase/classe, calibrada no subconjunto validado.
6. **Validação e publicação:** orçamento validado e versionado abertamente,
   com metodologia documentada.

### Formatos

| Dado | Formato | Onde |
|---|---|---|
| Shomate de referência (entrada) | JSON | `docs/audit/` (versionado) |
| Estatísticas de erro (publicação) | CSV | `docs/audit/` (convenção atual) |
| Incerteza em runtime (futuro) | tabela `species_uncertainty` no `thermo.db` | SQLite (additiva, como `metadata`) |

A tabela `species_uncertainty` deve ter colunas de proveniência (`source` ∈
`nist-janaf` | `extrapolated`, `n_ref_points`) para separar valores validados
de extrapolados.

### Limitação explícita

O NIST-JANAF **não cobre as 2 035 espécies** do `thermo.inp`. O orçamento será
**validado** para o subconjunto com referência e **extrapolado** para o resto
via modelo por fase/classe, com a extrapolação documentada (não inventada).

### O que NÃO fazer

- ❌ Apresentar covariância de coeficientes como se existisse (ver UQ-2).
- ❌ Extrapolar sem documentar o modelo e sua calibração.
- ❌ Publicar números sem pino de versão da referência e do dataset.

---

## UQ-2 — Covariância e propagação até equilíbrio/chama (longo prazo)

**Prioridade:** Baixa (indefinida)
**Origem:** comentário externo de revisão (nov/2026)
**Estado:** não iniciado (indefinido)

### Contexto

A parte de longo prazo do mesmo comentário: propagar a incerteza termoquímica
até **composição de equilíbrio** e **temperatura de chama adiabática**.

### Por que é longo prazo

1. **O dado não existe:** não há matriz de covariância publicada para os
   coeficientes NASA-7 (`a1..a7, b1, b2`). Estimá-la é um problema de pesquisa,
   não de código.
2. **O pyglenn não resolve equilíbrio:** a API de misturas trata a composição
   como **entrada**. Propagar até equilíbrio exige antes um solver de equilíbrio
   (trabalho futuro já citado no paper).

### Pré-requisitos

- UQ-1 concluído (envelope de erro por espécie como ponto de partida).
- Solver de equilíbrio químico.

### O que NÃO fazer

- ❌ Anunciar propagação de incerteza sem o orçamento UQ-1 validado.
- ❌ Tratar covariância como "soma de variâncias independentes" sem justificativa.

---

## Resolvido na 0.3.0

- **A1** (`h_relative`): `h_sensible_to` + documentação.
- **A7** (licença): copyright corrigido para o autor (2026) + `NOTICE` de
  linhagem Glenn.jl + classifier de licença no `pyproject.toml`.
- **A8** (`py.typed`): `py.typed` criado e incluído em `package-data`
  (`__all__` já existia).
- **B4** (consistência `H°(298.15) = ΔH°f` + exemplo de reação): teste de
  consistência sobre o dataset e teste de entalpia de reação
  (CH₄ + 2 O₂ → CO₂ + 2 H₂O vs NIST-JANAF) adicionados em
  `tests/test_calculator.py`.
- **B5** (CHANGELOG + depreciação): `CHANGELOG.md` criado (Keep a Changelog) e
  `get_properties_range` marcado com `DeprecationWarning` (ver FI-2).
- **B6** (`dcp_dt` e `gamma`): métodos analíticos adicionados a
  `ThermochemicalCalculator`, com testes de diferença finita e gás monoatômico.
- **Bloco C** (misturas): `Mixture`, `MixedProperties`, `mixture_properties`
  e `CompositionError` implementados; massa molar por média aritmética
  ponderada pelas frações molares (correção da média harmônica da spec).
- **B2** (`fit_nasa7`): ajuste por mínimos quadrados implementado em
  `src/pyglenn/fitting.py` (dependência `numpy`), com ancoragem
  `H°(t_ref) = h_ref` via `b1`, escala interna para condicionamento e
  `fit_nasa7_multi` para múltiplos intervalos com continuidade de valor e
  primeira derivada no ponto de emenda.

---

## Resolvido na 0.4.0

- **FI-2** (remoção de `get_properties_range`): método removido;
  `calculate_properties_range` é o único caminho para varreduras de
  temperatura.
- **Dataset mesclado** (Fix 4 do guia de porting): `parse_and_load` ganhou
  `merge_duplicates=True` (opt-in na 0.3.1), e o banco empacotado foi
  rebuildado com merge, indo de 3 779 para **3 795 intervalos** — as faixas de
  alta temperatura das espécies com transição de fase (ex.: `Cr(cr)`,
  `200–2130 K`) foram recuperadas e validadas contra NIST-JANAF em nível
  sub-percentual.

