# Exemplos de uso do pyglenn

Esta pasta contém *notebooks* Jupyter demonstrando o uso da biblioteca
**pyglenn** para cálculo de propriedades termoquímicas
($C_p(T)$, $H^\circ(T)$, $S^\circ(T)$) a partir de polinômios NASA.

Os notebooks são a **fonte da verdade** dos exemplos: eles são executados
tanto isoladamente quanto renderizados na
[documentação Sphinx](https://profleao.github.io/pyglenn) durante o build.

## Como executar

A partir da raiz do repositório:

```bash
# 1. Ative o ambiente virtual
#    Windows (PowerShell)
.venv\Scripts\Activate.ps1
#    Linux/macOS
source .venv/bin/activate

# 2. Instale o pacote em modo editável + dependências dos exemplos
#    (Jupyter + matplotlib)
pip install -e ".[examples]"

# 3. Abra os notebooks
jupyter lab examples/
```

Como o `pyglenn` usa *src-layout*, o `pip install -e .` é o que torna
`import pyglenn` disponível dentro dos notebooks — não é necessário mexer
em `sys.path`.

## Notebooks

| Notebook | Descrição |
|----------|-----------|
| [`01_basic_usage.ipynb`](01_basic_usage.ipynb) | First steps: look up species and compute $C_p$, $H^\circ$, $S^\circ$. |
| [`02_fuel_comparison.ipynb`](02_fuel_comparison.ipynb) | Compares CH4, ethanol, and propane with plots of $C_p(T)$, $S^\circ(T)$ and sensible enthalpy (requires matplotlib). |
