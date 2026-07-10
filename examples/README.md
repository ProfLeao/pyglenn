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

### Additional examples

Extra notebooks live in [`extra/`](extra/) — drop new `.ipynb` files there
and they will appear in the documentation on the next build.
