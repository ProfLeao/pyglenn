# Glenn.jl -> pyglenn: paridade funcional e plano de implementacao

**Data da auditoria:** 2026-08-19  
**Repositorios analisados:** [Glenn.jl](https://github.com/ProfLeao/Glenn.jl) e [pyglenn](https://github.com/ProfLeao/pyglenn)  
**Versao Julia auditada:** `0.4.0` (release integrada ao `main` em 2026-08-19)  
**Versao Python auditada:** `0.1.13`

## 1. Objetivo e escopo

Este documento registra as funcionalidades implementadas no Glenn.jl, compara-as com a implementacao atual do pyglenn e define um plano tecnico detalhado para portar ao pyglenn as capacidades existentes apenas no Glenn.jl.

Os dois projetos compartilham o modelo de dados NASA-7 e o banco SQLite gerado a partir de `thermo.inp` no formato FORTRAN da NASA. A comparacao separa:

1. **Funcionalidades exclusivas do Glenn.jl:** comportamento ou API publica presente no Julia e ausente atualmente no pyglenn.
2. **Funcionalidades equivalentes:** presentes nos dois projetos, embora com nomes, tipos de retorno ou ciclo de vida diferentes.
3. **Lacunas de paridade:** comportamentos presentes no pyglenn que tambem devem ser considerados no Glenn.jl.
4. **Recursos nao-runtime:** documentacao, CI, notebooks e ferramentas de qualidade, acompanhados separadamente da API cientifica.

O objetivo nao e fazer Python parecer Julia. O objetivo e oferecer as mesmas capacidades cientificas, preservando as convencoes do Python, a compatibilidade com usuarios existentes e o formato SQLite compartilhado.

## 0. Plano de saneamento da versao 0.2.0

Esta release corrige primeiro os problemas de integridade e consistencia cientifica do dataset incluido. Esse trabalho deve preceder os modelos tipados e as melhorias de desempenho, que de outro modo formalizariam dados ou resultados numericos incorretos.

### 0.1 Evidencias e escopo

O banco incluido apresenta as contagens esperadas (2.030 especies e 3.772 intervalos), mas sua massa molar media e implausivel. A inspecao encontrou tres registros cujo campo `name` e um token de coeficiente FORTRAN (por exemplo, `-1.302004763D+06`) e cujas massas molares chegam a `5.6168201e12 g/mol`. Trata-se de uma falha de recuperacao do parser: apos um bloco de intervalos incompleto ou malformado, uma linha posterior de coeficientes pode ser reinterpretada como cabecalho de especie. A correcao exige reconstruir e validar os dados; filtrar linhas ruins do banco atual nao e aceitavel.

A implementacao de referencia e o Glenn.jl v0.4.0, integrado em 2026-08-19. O commit `77ff931` (`fix: use dataset reference gas constant (R_GLENN) for denormalization`) estabelece o comportamento de G2. O changelog registra que os dados NASA Glenn/CEA foram normalizados com a constante de referencia CODATA 1986 `8.314510`; usar o valor universal CODATA introduziu vies sistematico de aproximadamente -5,7 ppm.

### 0.2 Frente A — parser e reconstrucao seguros

1. Substituir a recuperacao implicita e tolerante de indice em `ThermoDBBuilder.parse_and_load()` por um parser com estados explicitos: `cabecalho da especie -> informacoes gerais -> N triplas completas de intervalo`. Cada estado deve consumir somente o tipo de registro esperado; uma linha de coeficientes nunca pode ser candidata a cabecalho de especie.
2. Validar cada bloco completo antes da insercao: nome de especie nao vazio, numero de intervalos positivo, limites de temperatura finitos e ordenados e nove coeficientes finitos. Registrar linha de origem e motivo de cada bloco rejeitado.
3. Tratar uma sequencia declarada, mas incompleta, de intervalos como bloco de especie rejeitado e resincronizar somente em um limite de cabecalho de especie confirmado. Nao inserir especies, intervalos ou coeficientes parciais.
4. Construir em um arquivo SQLite temporario, dentro de uma unica transacao. Executar a validacao pos-carga nele e substituir o `thermo.db` incluido somente depois que todos os gates da release passarem. Uma reconstrucao com falha deve preservar o banco anterior.
5. Adicionar fixtures para dados validos com multiplos intervalos, cabecalhos de intervalo malformados, linhas de coeficientes ausentes, notacao FORTRAN `D`/`d` e a forma exata da dessincronizacao que antes convertia um coeficiente em especie.

### 0.3 Frente B — integridade do banco

1. Adicionar um relatorio reutilizavel `validate_database()` (e um comando CLI somente de leitura, se util) que verifique chaves estrangeiras, uma linha de coeficientes por intervalo, ausencia de orfaos, valores finitos, limites ordenados e concordancia entre `num_intervals` e as linhas de intervalo reais.
2. Adicionar verificacoes semanticas que rejeitem nomes de especie com formato de coeficiente, exijam massas molares finitas e positivas e sinalizem valores fora de uma faixa de dominio documentada. O limite e apenas guarda diagnostica, nao substitui um parser correto.
3. Exigir que os dados canonicos reconstruidos coincidam com o baseline validado do arquivo-fonte (atualmente 2.035 especies validas, 3.779 intervalos e 3.779 conjuntos de coeficientes); verificar a divisao gas/condensed e comparar valores de O2, CO2, H2O, NH3 e SO2 com a auditoria NIST. Atualizar a documentacao legada de 2.030/3.772 somente depois que essa validacao for reproduzivel na CI.
4. Recalcular e testar estatisticas agregadas plausiveis apos a reconstrucao. Em particular, a massa molar media deve vir dos dados-fonte corrigidos, nunca de esconder linhas corrompidas em `get_statistics()`.
5. Armazenar o relatorio de validacao com os artefatos de release e fazer a CI construir um banco temporario novo a partir de `thermo.inp` antes dos testes de integridade.

### 0.4 Frente C — especificacao de implementacao de G2

Implementar G2 antes de regenerar o banco incluido, seguindo o commit `77ff931` do Glenn.jl e o commit posterior `da0d833`, de documentacao da API:

1. Em `database.py`, expor `R_UNIVERSAL = 8.31446261815324` e `R_GLENN = 8.314510`. Manter `R` como alias de compatibilidade documentado para `R_UNIVERSAL` na linha 0.2.x; nao alterar seu significado silenciosamente.
2. Criar o schema aditivo `metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)` em `ThermoDBBuilder.create_tables()`. Implementar `write_metadata()` parametrizado e idempotente, persistindo exatamente `gas_constant_ref = "8.314510"` e `gas_constant_ref_source = "NASA Glenn/CEA thermo.inp (CODATA 1986)"`.
3. Adicionar `get_gas_constant_ref()` a `ThermoDBQuery`. Verificar explicitamente a existencia da tabela, ler a chave com consulta parametrizada, converter o valor e aceitar somente numeros finitos no intervalo `(8.0, 9.0)`. Tabela/chave ausente, texto invalido e valor implausivel devem emitir aviso e retornar `R_UNIVERSAL`; erros de conexao ou consulta nao podem ser ocultados por esse fallback.
4. Adicionar `migrate_metadata()` explicito e idempotente para bancos legados. Ele cria a tabela e grava as duas chaves canonicas sem reconstruir nem alterar especies, intervalos ou coeficientes. Conectar a um banco de usuario permanece uma operacao de leitura; a migracao e opt-in.
5. Adicionar `r_ref` a `ThermochemicalCalculator`, preenchendo-o somente apos conexao bem-sucedida, e usa-lo em todas as conversoes dimensionais: `cp_r * r_ref`, `h_rt * r_ref * T` e `s_r * r_ref`. Isso inclui caminhos escalares e de varias temperaturas.
6. Regenerar o banco incluido com metadados e verificar que ele seleciona `R_GLENN`. Um banco sem metadados deve continuar abrindo com o fallback da constante universal ate ser migrado.
7. Adicionar testes para constantes, metadados de um banco novo, escritas e migracoes idempotentes, metadados ausentes/invalidos/implausiveis, fallback legado e a razao exata de escala `R_GLENN / R_UNIVERSAL`. Adicionar valores de regressao entre linguagens para Cp, H e S de O2 em 298,15 K e 1000 K, mais uma especie com entalpia de formacao nao nula.
8. Atualizar README, referencia de banco do Sphinx, changelog, exportacoes publicas da API e notas de release para identificar a constante do dataset e quantificar a correcao intencional de ~5,7 ppm.

### 0.5 Ordem e gates de release

1. Escrever os testes de parser e integridade antes de alterar os dados canonicos.
2. Implementar e testar G2 em fixture minimo, incluindo o fallback legado.
3. Reconstruir o banco incluido em local temporario, valida-lo, substituir o asset do pacote e regenerar a auditoria NIST.
4. Construir wheel e sdist em ambiente limpo e verificar que ambos incluem `pyglenn/data/thermo.db` e `pyglenn/data/thermo.inp`.
5. Executar a matriz completa de Python (3.9–3.12), Ruff, mypy, documentacao com avisos como erro e comparacoes entre linguagens contra Glenn.jl v0.4.0.
6. Somente apos esses gates, continuar com G1/G3/G4/G5. Atualizar juntos para `0.2.0` o pacote, a receita Conda, as distribuicoes geradas e a documentacao de release.

## 2. Inventario de funcionalidades do Glenn.jl

### 2.1 Pacote e ciclo de vida

- `Calculator()` sem configuracao, usando o `data/thermo.db` incluido no pacote.
- `Calculator(path)` para um banco SQLite personalizado.
- Gerenciador de contexto `Calculator(f::Function, path)`, com sintaxe do-block e fechamento garantido em `finally`.
- `Base.close(calc)` e representacoes `Base.show` para calculadoras e conexoes de banco.
- `default_db_path()` e `default_inp_path()` para localizar os arquivos de dados incluidos.
- Metadados publicos do pacote: `Glenn.__version__` e `Glenn.__author__`.

### 2.2 Modelo de dominio tipado

O Glenn.jl expoe structs Julia imutaveis em vez de dicionarios sem tipo:

- `ThermoProperties`: temperatura, Cp, entalpia relativa, entropia, limites do intervalo, nome da especie e fase.
- `SpeciesInfo`: ID, nome, formula, fase, massa molecular, entalpia de formacao e quantidade de intervalos.
- `NASACoefficients`: os nove valores NASA-7 `a1`-`a7`, `b1` e `b2`, todos como `Float64`.
- `IntervalData`: identidade, limites, entalpia de referencia e coeficientes tipados.
- `DatabaseStats`: total de especies, intervalos, conjuntos de coeficientes, contagem por fase e massa molecular media.

`NASACoefficients(::Dict)` e mantido como construtor de compatibilidade. Os metodos antigos de calculo que recebem `Dict` estao deprecated em favor dos coeficientes tipados.

### 2.3 API de banco de dados

A API de baixo nivel `ThermoDatabase` exporta:

- `ThermoDB(path)` e `close(tdb)`.
- `get_statistics(tdb) -> DatabaseStats`.
- `find_species(tdb, name; exact_match=false)`.
- Busca por substring no nome ou formula da especie, priorizando correspondencias exatas de nome.
- Correspondencia exata sem diferenciar maiusculas e minusculas quando `exact_match=true`.
- `list_species_page(tdb; page=1, page_size=20)`.
- `list_all_species(tdb)` como listagem completa em uma unica consulta.
- `get_species_info(tdb, species_id)` como consulta leve apenas dos metadados.
- `get_species_data(tdb, species_id)` com todos os intervalos e coeficientes.
- `get_species_for_temperature(tdb, species_id, temperature)`.
- Avaliadores NASA-7 independentes: `calculate_cp`, `calculate_h` e `calculate_s`.
- Tipos de excecao de dominio: `ThermoCalcError`, `DatabaseNotConnectedError`, `SpeciesNotFoundError` e `TemperatureOutOfRangeError`.

### 2.4 API da calculadora

A API de alto nivel exporta:

- `get_available_species(calc, pattern; exact_match=false)`.
- `calculate_properties(calc, species_id, T) -> ThermoProperties`.
- `calculate_properties(calc, species_id, T_range) -> Vector{ThermoProperties}`.
- `calculate_formation_enthalpy(calc, species_id)`.
- `calculate_enthalpy_change(calc, species_id, T1, T2)`.
- `get_properties_range(calc, species_id, T_range)`.

As APIs escalar e de intervalo convertem as grandezas NASA adimensionais para unidades SI. A sobrecarga de intervalo carrega os intervalos uma vez e avalia, em memoria, todas as temperaturas validas.

### 2.5 Constante do gas e metadados do dataset

O Glenn.jl possui um sistema de constante de referencia especifico do dataset:

- `R_UNIVERSAL = 8.31446261815324` para o valor universal CODATA.
- `R_GLENN = 8.314510` para a constante de referencia dos polinomios NASA Glenn/CEA.
- Tabela `metadata(key TEXT PRIMARY KEY, value TEXT)`.
- `write_metadata(builder)` durante a construcao do banco.
- `get_gas_constant_ref(db)` ao abrir o banco.
- `migrate_metadata!(db)` para bancos legados sem a tabela de metadados.
- `Calculator` armazena `R_ref` e usa essa constante para desnormalizar Cp, H e S.

### 2.6 Construtor do banco

`ThermoDBBuilder` implementa:

- Ciclo de vida da conexao SQLite com foreign keys e modo WAL.
- Criacao das tabelas `species`, `temperature_intervals`, `coefficients`, `file_metadata` e `metadata`.
- Leitura de registros NASA FORTRAN em largura fixa.
- Conversao da notacao FORTRAN `D`/`d`.
- Parsers para especie, informacoes gerais, intervalos de temperatura e coeficientes.
- Deteccao de linhas de temperatura e coeficientes.
- Carga transacional com rollback em caso de falha.
- Tratamento idempotente de especies que ja existem no banco.
- Relatorio separado para especies novas, existentes e linhas ignoradas.
- Persistencia dos metadados da constante de gas do dataset.

### 2.7 CLI e recursos do projeto

- `cli_main()` com os comandos `build` e `query`.
- Script de conveniencia `bin/glenn.jl`.
- Saida de consulta com estatisticas, busca de especies, propriedades de exemplo e entalpia de formacao.
- Documentacao Documenter.jl e paginas de referencia da API.
- Exemplos executaveis e notebooks compativeis com Pluto.
- Auditoria de validacao cruzada NIST-JANAF/Shomate para CO2, N2, CO, H2O, O2, NH3 e SO2.
- Integracao de Aqua.jl e JuliaFormatter.jl para testes e desenvolvimento.
- Workflows de CI, documentacao, TagBot e CompatHelper.

## 3. Comparacao com o pyglenn

### 3.1 Funcionalidades ja equivalentes

| Capacidade | Glenn.jl | pyglenn | Observacoes |
|---|---|---|---|
| Dataset SQLite incluido | `Calculator()` | `ThermochemicalCalculator()` mais `connect()` | O ciclo de vida e diferente. |
| Banco personalizado | `Calculator(path)` | `ThermochemicalCalculator(path)` | Ambos aceitam bancos externos. |
| Construtor NASA FORTRAN | `ThermoDBBuilder` | `ThermoDBBuilder` | Mesmo schema normalizado principal. |
| Equacoes NASA-7 Cp/H/S | `calculate_cp/h/s` | `ThermoDBQuery.calculate_cp/h/s` | Julia usa coeficientes tipados; Python usa dicionarios. |
| Busca por substring | `find_species` / `get_available_species` | Equivalente | Ambos pesquisam nome e formula. |
| Busca exata sem diferenciar caixa | `exact_match=true` | `exact_match=True` | Mesmo comportamento pretendido. |
| Listagem paginada | `list_species_page` | `list_species_page` | Mesmo modelo de pagina e total de paginas. |
| Dados completos de especie | `get_species_data` | `get_species_data` | A representacao do retorno e diferente. |
| Busca do intervalo por temperatura | `get_species_for_temperature` | Equivalente | O comportamento nos limites nao e identico. |
| Entalpia de formacao | `calculate_formation_enthalpy` | Equivalente | As convencoes de retorno sao diferentes. |
| Variacao de entalpia | `calculate_enthalpy_change` | Equivalente | Ambos avaliam as duas temperaturas. |
| Propriedades em varias temperaturas | `get_properties_range` | Mesmo nome | Julia retorna vetor; Python retorna dicionario indexado por temperatura. |
| Estatisticas do banco | Mesmo nome | Mesmo nome | Julia retorna `DatabaseStats`; Python retorna dicionario. |
| Gerenciador de contexto | do-block Julia | `with` Python | Ambos garantem limpeza. |
| CLI build/query | `cli_main`, `bin/glenn.jl` | comando instalado `pyglenn` | Ambos expoem os dois comandos principais. |
| Erros de dominio | Tipos exportados em Julia | Excecoes lancadas em Python | O Julia ainda nao usa consistentemente os subtipos especializados. |

### 3.2 Funcionalidades do Glenn.jl a implementar no pyglenn

Estas sao as diferencas principais identificadas pela auditoria.

#### G1. Modelo tipado de resultados

**Comportamento atual do Glenn.jl:**

- Calculos retornam `ThermoProperties`.
- Consultas de especies retornam `SpeciesInfo`.
- Consultas de intervalos retornam `IntervalData` contendo `NASACoefficients`.
- Estatisticas retornam `DatabaseStats`.

**Comportamento atual do pyglenn:**

- Calculos e consultas retornam `dict[str, Any]`.
- Coeficientes sao dicionarios comuns.
- Estatisticas retornam um dicionario.

**Plano de implementacao:**

1. Adicionar dataclasses imutaveis em `src/pyglenn/models.py`:
   - `NASACoefficients`.
   - `SpeciesInfo`.
   - `IntervalData`.
   - `ThermoProperties`.
   - `DatabaseStats`.
2. Usar tipos opcionais precisos para valores nulos vindos do SQLite.
3. Adicionar conversores `from_mapping` ou helpers explicitos na fronteira SQLite.
4. Alterar os metodos publicos para retornarem dataclasses, mantendo compatibilidade com mapeamentos por um ciclo de deprecacao, ou introduzir primeiro uma API tipada opt-in.
5. Exportar os modelos por `pyglenn.__init__` e documentar campos e unidades.
6. Adicionar testes de igualdade e representacao.

**Criterios de aceitacao:**

- Os resultados tipados expoem atributos equivalentes aos campos do Julia.
- `asdict()` ou conversor equivalente e documentado para JSON e usuarios legados.
- `formula`, massa molecular, entalpia de formacao e valores de referencia continuam podendo ser nulos.
- Usuarios existentes de dicionarios continuam funcionando por uma camada de compatibilidade documentada ou recebem um aviso de deprecacao planejado.

#### G2. Constante de referencia do dataset e metadados

**Comportamento atual do Glenn.jl:**

- Diferencia `R_UNIVERSAL` de `R_GLENN`.
- Armazena `gas_constant_ref` e sua fonte na tabela `metadata`.
- Le o valor ao abrir a calculadora.
- Migra explicitamente bancos antigos.

**Comportamento atual do pyglenn:**

- Usa uma unica constante de modulo, `R = 8.314462618`.
- O construtor nao cria a tabela `metadata` nem grava a constante de referencia do dataset.
- Os coeficientes NASA sao portanto desnormalizados com a constante universal, e nao com a constante original `R_GLENN` do dataset incluido.

**Plano de implementacao:**

1. Adicionar `R_UNIVERSAL = 8.31446261815324` e `R_GLENN = 8.314510` em `database.py`.
2. Adicionar a criacao da tabela `metadata` em `ThermoDBBuilder.create_tables()`.
3. Adicionar `write_metadata()` usando SQL parametrizado e upsert idempotente.
4. Adicionar `migrate_metadata(connection)` para bancos existentes.
5. Adicionar `get_gas_constant_ref()` com fallback explicito para bancos legados.
6. Fazer `ThermochemicalCalculator` armazenar `R_ref` apos abrir a conexao.
7. Usar `R_ref` consistentemente nos calculos escalares e em intervalos.
8. Adicionar uma chave de fonte, como `gas_constant_ref_source`.
9. Atualizar a documentacao do schema e as notas da release.
10. Decidir se a migracao ocorre automaticamente ou somente por API explicita. A recomendacao e usar migracao explicita para evitar alterar arquivos do usuario silenciosamente.

**Criterios de aceitacao:**

- Um banco novo contem a tabela de metadados e `gas_constant_ref = 8.314510`.
- Um banco legado sem a tabela continua abrindo e possui fallback documentado.
- O banco incluido produz os mesmos valores desnormalizados do Glenn.jl dentro da tolerancia definida.
- As escritas de metadados sao idempotentes.

#### G3. Listagem completa em uma unica consulta

**Comportamento atual do Glenn.jl:**

- `list_all_species(tdb)` carrega todas as especies com uma consulta ordenada.
- `get_available_species(calc)` usa esse caminho sem padrao de busca.

**Comportamento atual do pyglenn:**

- `get_available_species()` percorre paginas de 100 registros.
- `list_species_page()` existe, mas nao ha equivalente publico a `list_all_species()`.

**Plano de implementacao:**

1. Adicionar `ThermoDBQuery.list_all_species() -> list[SpeciesInfo]`.
2. Selecionar os mesmos campos de `find_species`, ordenar por nome e converter as linhas na fronteira do banco.
3. Fazer `get_available_species()` chamar o novo metodo quando o padrao estiver vazio.
4. Manter a paginacao para datasets grandes e para consumidores que precisam limitar memoria.
5. Adicionar teste garantindo que a busca sem padrao nao executa repetidas consultas de pagina.

**Criterios de aceitacao:**

- A busca sem padrao retorna todos os registros em ordem alfabetica.
- O tipo e os campos do retorno estao documentados.
- As APIs de lista completa e paginada continuam disponiveis separadamente.

#### G4. Consulta leve de metadados de especie

**Comportamento atual do Glenn.jl:**

- `get_species_info(tdb, species_id)` retorna metadados basicos sem carregar intervalos ou coeficientes.
- O calculo escalar usa essa consulta leve.

**Comportamento atual do pyglenn:**

- `calculate_properties()` chama primeiro `get_species_data()`, carregando todos os intervalos.
- Nao ha consulta publica equivalente.

**Plano de implementacao:**

1. Adicionar `ThermoDBQuery.get_species_info(species_id) -> SpeciesInfo | None`.
2. Selecionar somente as colunas necessarias para identidade e metadados de saida.
3. Usar o metodo em `calculate_properties()` e `calculate_formation_enthalpy()`.
4. Manter `get_species_data()` para consumidores que realmente precisam dos intervalos completos.
5. Testar a diferenca entre especie inexistente e especie sem linhas de coeficientes.

**Criterios de aceitacao:**

- Calculos escalares nao carregam todos os intervalos sem necessidade.
- A busca de entalpia continua correta sem dados de intervalos.
- A API de dados completos permanece disponivel.

#### G5. Modelo tipado para resultados em intervalo

**Comportamento atual do Glenn.jl:**

- `calculate_properties(calc, species_id, T_range)` e uma sobrecarga dedicada.
- `get_properties_range()` retorna um `Vector{ThermoProperties}` ordenado.
- Os intervalos sao carregados uma vez e reutilizados.

**Comportamento atual do pyglenn:**

- `get_properties_range()` percorre as temperaturas e retorna `dict[float, dict]`.
- Temperaturas fora do intervalo sao ignoradas; retorna `None` quando todas falham.

**Plano de implementacao:**

1. Manter a API Python baseada em dicionario por compatibilidade.
2. Adicionar `calculate_properties_range()` ou `get_properties_range_typed()` retornando uma lista ordenada de `ThermoProperties`.
3. Carregar os intervalos uma vez por chamada e selecionar em memoria.
4. Definir o comportamento de temperaturas duplicadas; a recomendacao e preservar a ordem de entrada na lista tipada e manter a deduplicacao na API legada.
5. Definir o comportamento de valores fora do intervalo; a recomendacao e manter o skip na API legada e oferecer `strict=True` para lancar erro.
6. Adicionar benchmark comparando uma chamada em lote com chamadas escalares repetidas.

**Criterios de aceitacao:**

- Resultados ordenados estao disponiveis sem quebrar consumidores do dicionario.
- Cada temperatura valida usa o intervalo correto.
- A constante de referencia e aplicada consistentemente.
- A performance melhora em relacao a chamadas repetidas que carregam todos os dados.

#### G6. API de migracao dos metadados do dataset

Este item e separado de G2 por ser uma capacidade operacional.

**Comportamento atual do Glenn.jl:** `migrate_metadata!(db)` atualiza um banco compartilhado antigo sem reconstruir todas as especies.

**Plano de implementacao:**

1. Disponibilizar `migrate_metadata(connection_or_query) -> None` no pyglenn.
2. Tornar a operacao segura para execucao repetida.
3. Nao reconstruir especies nem linhas de coeficientes.
4. Retornar um pequeno relatorio ou documentar o retorno `None`.
5. Adicionar uma opcao CLI, como `pyglenn migrate-metadata -d thermo.db`, somente se houver necessidade operacional.

## 4. Comportamentos do pyglenn a considerar no Glenn.jl

Estas nao sao funcionalidades exclusivas do Glenn.jl, mas apareceram na comparacao e devem ser consideradas para paridade.

### P1. Estado explicito da conexao

O pyglenn expoe `connect() -> bool` e `connected`, permitindo criar uma calculadora antes de conectar. O Glenn.jl abre o banco em `Calculator(path)` e nao possui propriedade publica de conexao.

Decisao recomendada para Julia: manter a construcao imediata, idiomatica para gerenciamento de recursos, mas adicionar `isopen(calc)` e `isopen(tdb)`. Evitar uma calculadora desconectada sem caso de uso concreto.

### P2. Tolerancia nos limites dos intervalos

O pyglenn usa `temp_max + 1e-9` e ordena por numero do intervalo, tornando deterministica uma fronteira compartilhada. O Glenn.jl usa comparacoes inclusivas diretas e atualmente nao possui `ORDER BY` explicito nessa consulta.

Mudanca recomendada no Julia:

- Adicionar `ORDER BY ti.interval_number LIMIT 1`.
- Usar uma tolerancia documentada, de preferencia uma constante nomeada.
- Testar limite inferior, fronteira compartilhada, limite superior e valores dentro da tolerancia.

Este item e importante para correcao e reproducibilidade entre linguagens.

### P3. Comportamento das excecoes especializadas

Os dois projetos definem conceitos de erro especializados, mas os calculos de alto nivel do Glenn.jl atualmente lancam `ThermoCalcError` diretamente para especie invalida e temperatura fora do intervalo. O pyglenn usa `SpeciesNotFoundError` e `TemperatureOutOfRangeError` nesses casos.

Mudanca recomendada no Julia:

- Lancar `SpeciesNotFoundError(species_id)` para IDs inexistentes.
- Lancar `TemperatureOutOfRangeError(T, info.name)` para temperaturas invalidas.
- Reservar `ThermoCalcError` para erros sem tipo de dominio mais especifico.
- Atualizar testes e documentacao.

### P4. Contrato de instalacao da CLI

O pyglenn instala um executavel `pyglenn` por `pyproject.toml`. O Glenn.jl possui `cli_main()` e `bin/glenn.jl`, mas nao possui declaracao equivalente de executavel global.

Decisao recomendada no Julia: manter o script, comum em projetos Julia, e documentar uma invocacao estavel. Se for necessario um comando global, fornecer um wrapper de aplicacao Julia sem alterar a API da biblioteca.

### P5. Caminhos padrao do builder

As CLIs usam padroes diferentes: o Glenn.jl resolve caminhos incluidos no pacote no parser leve, enquanto a CLI do pyglenn usa `thermo.inp` e `thermo.db` relativos ao diretorio atual no comando de build. Uma futura migracao de metadados deve definir se opera sobre os arquivos incluidos ou sobre o diretorio atual.

## 5. Fases propostas para implementar no pyglenn

### Fase 0 - Contrato de compatibilidade

- Publicar esta comparacao e decidir se dataclasses tipadas serao aditivas ou implicarao mudanca de retorno.
- Definir politica de compatibilidade para dicionarios.
- Decidir migracao automatica ou explicita de metadados.
- Definir tolerancias numericas para comparacoes entre linguagens.

### Fase 1 - Modelos e fronteira de conversao

- Adicionar as dataclasses em `models.py`.
- Adicionar conversores de linhas para modelos.
- Documentar unidades e campos opcionais.
- Adicionar testes sem alterar inicialmente os retornos publicos existentes.

### Fase 2 - Metadados e constante do gas

- Adicionar constantes e schema de metadados.
- Gravar metadados no builder e implementar migracao.
- Adicionar `R_ref` na calculadora.
- Regenerar ou migrar o banco incluido.
- Adicionar valores de regressao para O2 em 298.15 K, 1000 K e uma segunda especie.

### Fase 3 - Paridade das consultas

- Adicionar `list_all_species()`.
- Adicionar `get_species_info()`.
- Usar os caminhos de lista completa e consulta leve.
- Adicionar testes de quantidade de consultas e especie inexistente.

### Fase 4 - API tipada de intervalos

- Adicionar metodo tipado de intervalo de forma aditiva.
- Preservar o metodo atual baseado em dicionario indexado por temperatura.
- Documentar ordem, temperaturas duplicadas, valores ignorados e modo estrito.
- Adicionar testes de performance e numericos.

### Fase 5 - Exports e documentacao

- Exportar constantes, modelos, helpers de metadados e novas consultas em `pyglenn.__init__`.
- Atualizar README, paginas Sphinx, exemplos e ajuda da CLI.
- Adicionar guia de migracao com exemplos antigos e novos usando dataclasses.

### Fase 6 - Release e interoperabilidade

- Executar testes, Ruff, mypy e cobertura do pyglenn.
- Executar os testes do Glenn.jl contra o banco migrado.
- Comparar schemas SQLite e quantidades de registros.
- Comparar Cp, H e S em especies e temperaturas compartilhadas.
- Publicar uma release menor se os adaptadores de compatibilidade permanecerem; definir a politica adequada ao estado pre-1.0 caso os tipos de retorno mudem.

## 6. Matriz de aceitacao entre linguagens

A implementacao somente estara concluida quando estas verificacoes passarem:

| Area | Verificacao obrigatoria |
|---|---|
| Schema | Os dois builders criam as mesmas tabelas principais; metadados sao aditivos e compreendidos pelas duas bibliotecas. |
| Constantes | O dataset NASA incluido e desnormalizado com `8.314510` nas duas implementacoes. |
| Busca exata | `O2`, `o2` e o parcial `O` produzem a mesma semantica de busca. |
| Formula | O comportamento de busca por nome/formula e equivalente. |
| Limites | 200 K, 1000 K e 6000 K selecionam os mesmos intervalos para O2. |
| Especie ausente | As duas bibliotecas expoem um resultado/erro claro e documentado. |
| Temperatura invalida | As duas bibliotecas expoem uma politica clara para temperatura fora do intervalo. |
| Valores escalares | Cp, H e S concordam dentro de tolerancia explicita. |
| Valores em intervalo | Temperaturas validas, ordem, valores ignorados e duplicatas sao documentados e testados. |
| Entalpia de formacao | O valor de referencia de O2 e uma especie com valor nao nulo concordam. |
| Builder | Um `thermo.inp` minimo e carregado com sucesso e grava metadados. |
| Banco legado | Um banco anterior aos metadados continua legivel e pode ser migrado sem rebuild. |
| CLI | Os comandos build/query reportam erros uteis e terminam com sucesso. |

## 7. Fixtures de teste sugeridas

Use um fixture SQLite pequeno e um fixture FORTRAN minimo:

- Especie `O2`, com intervalos `[200, 1000]` e `[1000, 6000]`.
- Pelo menos uma especie com entalpia de formacao nao nula, como `CO2`.
- Um caso de busca por formula diferente do nome exibido.
- Um banco sem `metadata` para testes de migracao/fallback.
- Um banco com `metadata` contendo valor invalido ou implausivel.
- Temperaturas `200.0`, `1000.0`, `6000.0`, `100.0` e `7000.0`.
- Um intervalo de entrada com temperaturas validas, invalidas, duplicadas e inteiras.

Os testes numericos devem usar tolerancias absoluta e relativa adequadas a avaliacao dos polinomios e a constante de gas selecionada. Nao compare a saida arredondada exibida no terminal.

## 8. Riscos e decisoes

- **Compatibilidade de retorno:** substituir dicionarios diretamente pode quebrar usuarios Python. Prefira APIs tipadas aditivas ou um periodo de deprecacao.
- **Tipagem do SQLite:** mantenha `metadata.value` como `TEXT`, pois a tabela e chave/valor generica; converta a constante na leitura e valide seu intervalo.
- **Migracao automatica:** alterar o banco do usuario silenciosamente e surpreendente. Prefira uma API explicita com aviso ou comando CLI.
- **Correcao cientifica:** a constante de gas e dado cientifico, nao apenas configuracao. A fonte e o fallback devem ser documentados e testados.
- **Limites de intervalo:** uma tolerancia pode aceitar valores ligeiramente fora do intervalo declarado. Use tolerancia pequena, nomeada e testada.
- **Performance:** a conversao tipada nao deve causar uma consulta por temperatura. Calculos em lote devem reutilizar os intervalos carregados.
- **Versionamento:** embora o pyglenn seja pre-1.0, usuarios precisam de nota de migracao quando tipos de retorno ou constantes mudarem.

## 9. Recomendacao de curto prazo

Implemente G2 primeiro, pois ele afeta todos os resultados termodinamicos desnormalizados. Em seguida implemente G1 e G4, que estabelecem uma fronteira tipada e estavel para modelos e consultas. Depois implemente G3 e G5 como melhorias de performance e API. Em paralelo, aplique P2 e P3 no Glenn.jl para que as duas bibliotecas concordem nos limites de intervalo e na semantica das excecoes antes de usar a validacao numerica como gate de release.
