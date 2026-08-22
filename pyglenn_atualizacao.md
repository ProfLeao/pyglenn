# Guia de Atualização para o `pyglenn`

Este documento lista as melhorias implementadas nas versões `0.4.0` e `0.4.1` do **Glenn.jl**, bem como as vantagens arquiteturais e de performance que o pacote Julia possui atualmente sobre o pacote Python (`pyglenn`). O objetivo é servir de roteiro para a atualização e paridade de features no `pyglenn`.

---

## 1. Melhorias Recentes a Serem Portadas (v0.4.0 e v0.4.1)

### 🔴 Correção Crítica: Constante Universal dos Gases (Viés de -5.7 ppm)
A mudança mais importante introduzida na `v0.4.0` corrige um erro silencioso de precisão termodinâmica. 
Os coeficientes NASA-7 do arquivo `thermo.inp` original (NASA CEA) são adimensionais ($C_p/R_0$, $H/R_0T$, $S/R_0$) e foram ajustados utilizando a constante de gás do **CODATA 1986** ($R = 8.314510$ J/mol·K). Desnormalizar esses dados usando o valor moderno (CODATA 2018, $R = 8.314462618$ J/mol·K) introduz um viés sistemático de aproximadamente -5.7 ppm.

**O que fazer no `pyglenn`:**
1. Adicionar uma nova constante `R_GLENN = 8.314510` (CODATA 1986).
2. Adicionar uma tabela `metadata` ao schema do SQLite contendo:
   - `key = 'gas_constant_ref'`
   - `value = '8.314510'`
   - `key = 'gas_constant_ref_source'`
   - `value = 'NASA TP-2002-211556 (CODATA 1986)'`
3. Atualizar as equações polinomiais para usar `R_GLENN` na desnormalização caso o banco possua essa tabela, com fallback para `R_UNIVERSAL` com aviso (`Warning`) caso seja um banco de dados antigo.
4. Implementar funções equivalentes a `get_gas_constant_ref` e `migrate_metadata!` (da v0.4.1) para garantir retrocompatibilidade.

### ✨ Tipagem Forte em Estatísticas
Na versão `v0.4.0`, o retorno de `get_statistics()` deixou de ser um dicionário arbitrário e passou a ser uma estrutura de dados definida (`DatabaseStats`).

**O que fazer no `pyglenn`:**
- Converter o retorno do dicionário genérico de estatísticas do banco de dados em uma `dataclass` (ex: `DatabaseStats` em Python) para melhor suporte a autocompletar e validação estática.

---

## 2. Diferenças Arquiteturais (Que favorecem o Glenn.jl)

As seguintes características foram desenhadas no **Glenn.jl** de forma mais otimizada e robusta do que a implementação original do `pyglenn`. Elas devem ser alvo de refatoração no pacote Python:

### Tipos Fortes e Imutáveis
- **Glenn.jl:** Utiliza `structs` tipados (`ThermoProperties`, `SpeciesInfo`, `NASACoefficients`).
- **pyglenn:** Utiliza dicionários puros (`dict`), que são suscetíveis a erros de digitação de chaves (`KeyError`) e não oferecem boa documentação via Type Hints da IDE.
- **Ação sugerida:** Migrar as respostas de cálculo e lookups do Python para `@dataclass` (ou `pydantic`, `NamedTuple`).

### Cálculo Vetorizado Otimizado
- **Glenn.jl:** Na chamada de cálculo para um vetor de temperaturas (varredura térmica), o pacote busca as informações no banco *apenas uma vez*, guarda na memória e resolve a alocação dos polinômios para todos os `T`.
- **pyglenn:** Realiza um loop ingênuo, fazendo um *round-trip* no banco de dados SQLite para cada temperatura, o que degrada a performance de varreduras longas.
- **Ação sugerida:** Implementar em Python um método vetorizado de varredura térmica no nível da API, agrupando os lookups de DB.

### Exceções com Contexto Rico
- **Glenn.jl:** Exceções customizadas detalhadas, como `SpeciesNotFoundError` e `TemperatureOutOfRangeError`, que carregam dentro da exceção o `species_id`, a temperatura requisitada e o limite do intervalo real.
- **pyglenn:** Lança erros em formato de mensagens simples e genéricas (muitas vezes via um `ValueError` simples).
- **Ação sugerida:** Desenhar uma hierarquia formal de classes `Exception` em Python que armazenem o contexto da falha.

### Builder Transacional de Banco de Dados
- **Glenn.jl:** O parser de arquivos FORTRAN (`thermo.inp`) faz a varredura e todas as milhares de inserções SQL encapsuladas dentro de um único comando de transação explícita (`BEGIN` ... `COMMIT`). Se ocorrer falha no meio da leitura, a transação é cancelada (ROLLBACK).
- **pyglenn:** Opera com o *Autocommit* do módulo sqlite3 nativo, que é extremamente mais lento para inserções em massa e pode deixar o banco corrompido em caso de interrupção (Crash).
- **Ação sugerida:** Envolver a criação do DB Python (`parse_and_load`) em um bloco transacional massivo ou usando executemany com geradores.

### Busca Ampla (`list_all_species`)
- **Glenn.jl:** Possui uma função em nível de usuário que extrai uma query eficiente de listagem com informações consolidadas da tabela de forma imediata.
- **pyglenn:** Estruturado excessivamente ao redor de buscas paginadas e interações indiretas, forçando o usuário a fazer loops repetitivos.
- **Ação sugerida:** Exportar uma função que resgate uma lista em memória das instâncias de espécies disponíveis.
