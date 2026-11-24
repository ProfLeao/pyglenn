---
name: avoid-ai-writing
description: >-
  Elimina marcas, vícios de linguagem, estruturas artificiais e assinaturas estilísticas típicas de
  modelos de linguagem (LLMs) em textos acadêmicos, relatórios técnicos, artigos científicos e
  documentações em Markdown e LaTeX. Use esta skill sempre que for solicitado a redigir, revisar,
  refinar ou auditar textos em padrão de escrita humana genuína, garantindo conformidade com normas
  editoriais (ABNT, IEEE, ASME, Elsevier) e aprovação em detectores de IA.
---

# Guia Operacional: Redação Acadêmica Humana e Eliminação de Sinais de IA

Esta skill estabelece o protocolo de escrita, revisão e auditoria estilística para erradicar **sinais de escrita por inteligência artificial** (*Signs of AI writing*). O objetivo é garantir que documentos técnicos e científicos apresentem o ritmo, a densidade analítica e a variabilidade estilística de um pesquisador humano sênior.

---

## 1. As 6 Dimensões das Assinaturas de IA

Textos gerados por LLMs não são identificados por erros gramaticais, mas sim pela **previsibilidade estatística** e **maneirismos estilísticos repetitivos**:

| Dimensão | Vício de IA | Padrão Humano Autêntico |
| :--- | :--- | :--- |
| **1. Pontuação** | Uso compulsivo de travessões (`—`) isolados como muleta explicativa. | Uso sóbrio de vírgulas, parênteses `(...)` ou ponto final com nova oração. |
| **2. Tipografia** | Destaque em negrito (`**termo**`) salpicado em quase todos os parágrafos. | Negrito reservado a títulos e cabeçalhos. Termos técnicos usam itálico apenas na 1ª menção se estrangeiros. |
| **3. Estrutura** | Decomposição obsessiva em tópicos e listas com *bold lead-ins* (`1. **X:** Y`). | Prosa contínua, parágrafos discursivos encadeados com progressão temática lógica. |
| **4. Vocabulário** | Clichês vazios (*crucial*, *pivotal*, *cenário*, *testamento*, *imperativo notar*). | Terminologia técnica precisa, substantivos concretos e verbos operacionais da área. |
| **5. Sintaxe** | Ritmo metronômico, frases com comprimentos uniformes e estruturas em trios (*rule of three*). | Alta variação frasal (*burstiness*): alternância deliberada entre orações curtas e períodos compostos. |
| **6. Elementos Visuais** | Desenhos e fluxogramas em texto puro (*ASCII art* com caixas `+---+`). | Tabelas formais e referências cruzadas a figuras e esquemas gráficos profissionais. |

---

## 2. Léxico Proibido e Substituições Recomendadas

A tabela a seguir cataloga os termos mais comuns que denunciam texto sintético e suas contrapartidas acadêmicas:

| Termo / Expressão de IA | Por que Evitar? | Alternativa Humana Natural |
| :--- | :--- | :--- |
| *"É imperativo observar/notar que..."* | Muleta de ênfase vazia; infla o texto sem adicionar conteúdo. | *"Nota-se que..."*, *"Constata-se que..."* ou omitir e declarar o fato diretamente. |
| *"Nesse cenário / Nesse contexto..."* | Transição genérica e redundante de início de parágrafo. | Conectar o argumento logicamente: *"Sob essa condição..."*, *"Para tal regime..."*, *"Dessa forma..."* |
| *"Crucial / Pivotal / Vital"* | Hiperbólicos superficiais; pesquisadores quantificam relevância. | *"Determinante"*, *"Significativo"*, *"Predominante"* ou explicar o impacto numérico. |
| *"Desempenha um papel fundamental..."* | Clichê passivo e desgastado de introduções de IA. | Verbo direto ativo: *"Governa a resposta..."*, *"Regula o acoplamento..."*, *"Determina o comportamento..."* |
| *"Destaca-se por / Notavelmente..."* | Adjetivação demonstrativa sem suporte em dados. | Apresentar o dado: *"Apresenta rendimento de X%"*, *"Sobressai pela densidade de..."* |
| *"Em suma / Em conclusão / Diante do exposto"* | Fechamentos formulaicos e escolares. | Sintetizar diretamente: *"Os resultados evidenciam que..."*, *"A análise comparativa demonstra..."* |
| *"Mergulhar em..."* (*delve*) | Metáfora coloquial típica de tradução literal de LLMs. | *"Analisar"*, *"Investigar"*, *"Examinar"*, *"Avaliar"*. |
| *"Tapeçaria de... / Mosaico de..."* | Figura poética inadequada para textos técnicos. | *"Conjunto"*, *"Estrutura"*, *"Arranjo"*, *"Configuração"*. |

---

## 3. Diretrizes Estruturais Obrigatórias

Ao produzir ou revisar documentos Markdown ou LaTeX:

### 3.1 Proibição de Caixas e Desenhos em ASCII Art
- **NUNCA** gere fluxogramas ou diagramas formados por caracteres de texto (`+---+`, `| v |`, `-->`). Em relatórios científicos, isso é a marca registrada de respostas de chatbot.
- **Substituição:** Utilize tabelas no padrão Markdown/LaTeX ou elabore a descrição textual encadeada com etapas numeradas de procedimento.

### 3.2 Eliminação de Negritos no Corpo dos Parágrafos
- O usuário humano acadêmico não destaca palavras-chave em negrito dentro de frases normais (hábito herdado de assistentes de busca e resumos de IA).
- Remova `**termo**` de dentro dos parágrafos de texto corrido. Reserve o negrito exclusivamente para:
  - Cabeçalhos de tabela;
  - Títulos de figuras;
  - Rótulos de autores em referências bibliográficas.

### 3.3 Extinção de Travessões (`—`) como Parênteses
- Empregue vírgulas quando a oração for adjetiva explicativa.
- Empregue parênteses `(...)` para siglas, acrônimos ou breves esclarecimentos:
  - *Incorreto:* `o modelo de parâmetros concentrados — SDOF — foi descartado...`
  - *Correto:* `o modelo de parâmetros concentrados (SDOF) foi descartado...`

### 3.4 Conversão de Listas com "Bold Lead-ins" em Prosa Contínua
- LLMs tendem a formatar todo argumento sob a forma:
  ```markdown
  - **Eficiência:** A eficiência atinge 90%...
  - **Estabilidade:** A estabilidade é garantida por...
  - **Custo:** O custo é reduzido porque...
  ```
- **Reescreva em prosa acadêmica articulada:**
  *"A eficiência alcança patamares de 90%, enquanto a estabilidade decorre do critério de Routh-Hurwitz. Paralelamente, os custos associados decrescem devido à simplificação topológica."*

### 3.5 Supressão de Alertas de Plataforma
- Remova caixas como `> [!WARNING]` ou `> [!IMPORTANT]`, que são extensões do GitHub Flavored Markdown típicas de documentação de repositório, não de artigos científicos ou relatórios de engenharia.

---

## 4. Script Auxiliar de Auditoria Automatizada

A pasta da skill contém o utilitário em Python [`check_ai_patterns.py`](./scripts/check_ai_patterns.py), que executa análise estática de texto detectando:
- Ocorrências de palavras e expressões do léxico de IA;
- Contagem e localização de travessões (`—`);
- Densidade de termos em negrito inline (`**`);
- Presença de blocos ASCII art;
- Presença de alertas do tipo `> [!`;
- Cálculo do **Índice de Contaminação por IA** com linha e coluna de cada ocorrência.

### Como Executar:
```bash
python .github/skills/avoid-ai-writing/scripts/check_ai_patterns.py documento.md
```

---

## 5. Checklist de Verificação Antes da Publicação

Antes de finalizar qualquer documento Markdown ou compilar para PDF:
- [ ] O texto contém algum travessão `—` usado como parêntese? Se sim, substituir por vírgulas ou parênteses.
- [ ] Há negrito dentro do corpo dos parágrafos? Se sim, desmarcar e deixar o texto plano.
- [ ] Existem desenhos de caixas em ASCII? Se sim, converter em tabela ou prosa.
- [ ] Foram removidas expressões clichê (*crucial*, *cenário*, *imperativo notar*, *em suma*)?
- [ ] As ideias estão desenvolvidas em parágrafos encadeados e não em listas intermináveis de tópicos?
- [ ] O ritmo das frases varia entre períodos concisos e reflexões analíticas compostas?
- [ ] Títulos evitam perguntas retóricas (*"Por que o modelo X falha?"* -> *"Limitações Teóricas do Modelo X"*).

