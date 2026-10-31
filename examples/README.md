# pyglenn usage examples

This folder contains Jupyter *notebooks* demonstrating how to use the
**pyglenn** library for thermochemical property calculations
($C_p(T)$, $H^\circ(T)$, $S^\circ(T)$) from NASA polynomial coefficients.

The notebooks are the **source of truth** for the examples: they run both
standalone and are rendered in the
[Sphinx documentation](https://profleao.github.io/pyglenn) during the build.

## How to run

From the repository root:

```bash
# 1. Activate the virtual environment
#    Windows (PowerShell)
.venv\Scripts\Activate.ps1
#    Linux/macOS
source .venv/bin/activate

# 2. Install the package in editable mode + example dependencies
#    (Jupyter + matplotlib)
pip install -e ".[examples]"

# 3. Open the notebooks
jupyter lab examples/
```

Since `pyglenn` uses a *src-layout*, `pip install -e .` is what makes
`import pyglenn` available inside the notebooks — no need to touch
`sys.path`.

## Notebooks

### Core examples

| Notebook | Description |
|----------|-------------|
| [`01_basic_usage.ipynb`](01_basic_usage.ipynb) | First steps: look up species and compute $C_p$, $H^\circ$, $S^\circ$. |
| [`02_fuel_comparison.ipynb`](02_fuel_comparison.ipynb) | Compares CH4, ethanol, and propane with plots of $C_p(T)$, $S^\circ(T)$ and sensible enthalpy (requires matplotlib). |
| [`03_mixture_properties.ipynb`](03_mixture_properties.ipynb) | Mixtures (air, combustion products): `Mixture`, `mixture_properties`, molar vs mass basis. |
| [`04_fitting.ipynb`](04_fitting.ipynb) | Generate NASA-7 coefficients from Cp(T) data: `fit_nasa7` (single interval) and `fit_nasa7_multi` (multi-interval with continuity). |
