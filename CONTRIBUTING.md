# Contributing to pyglenn

pyglenn computes thermochemical properties from NASA polynomial coefficients.
It ships a bundled SQLite database and a small typed API. This file explains
how to set up a development environment, run the checks, and contribute code,
tests, or documentation.

## Setup

The package uses a src layout and setuptools. Clone the repository and create
a virtual environment:

```bash
git clone https://github.com/ProfLeao/pyglenn.git
cd pyglenn
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
source .venv/bin/activate    # Linux and macOS
pip install -e ".[dev,doc,examples]"
```

`pip install -e .` makes `import pyglenn` resolve to `src/pyglenn` without
touching `sys.path`. The extras install the tooling:

- `dev`: pytest, pytest-cov, ruff, mypy, pre-commit
- `doc`: sphinx, renku-sphinx-theme, myst-nb, matplotlib
- `examples`: jupyterlab, matplotlib

Python 3.10, 3.11, and 3.12 are supported. NumPy is the only runtime
dependency.

## Project layout

| Path | What it holds |
| --- | --- |
| `src/pyglenn/` | the package: API, parser, database layer, CLI |
| `src/pyglenn/data/` | `thermo.inp` source data and the built `thermo.db` |
| `tests/` | pytest suite |
| `docs/source/` | Sphinx documentation |
| `examples/` | Jupyter notebooks, the source of truth for the examples |
| `scripts/` | database rebuild and chart generation helpers |

## Development workflow

1. Create a branch from `main`.
2. Make the change and add or update tests.
3. Run the checks listed below.
4. Commit using conventional commits. Subjects are written in Portuguese,
   matching the rest of the history.

The commit convention observed in this repository:

- `feat:` a new feature
- `fix:` a bug fix
- `docs:` documentation only
- `test:` tests only
- `chore:` tooling, build, or release tasks

A scope in parentheses is optional, for example `feat(calculator): adiciona ...`.

## Checks

Run these before opening a pull request, with the virtual environment active:

```bash
pytest -q
ruff check src tests
ruff format --check src tests
mypy src/pyglenn
sphinx-build -b html -W docs/source docs/build/html
python -m build --no-isolation
```

`pytest` reads its configuration from `pyproject.toml`, which adds `src` to
`sys.path`, so the tests run even without an editable install. The full suite
has 116 tests. The build check needs the `build` package; install it with
`pip install build` if it is missing.

### pre-commit

The repository includes a `.pre-commit-config.yaml`. Install the hooks once:

```bash
pre-commit install
```

The hooks remove trailing whitespace, sort imports with ruff, format with
ruff-format, and run mypy.

## Code style

- Ruff enforces style and a set of lint rules (`E`, `F`, `W`, `I`, `B`, `C4`,
  `UP`, `SIM`, `T20`). Line length is 88.
- Public functions and methods carry type annotations. mypy runs with
  `disallow_untyped_defs`, so unannotated functions fail the check.
- Modules use `from __future__ import annotations`. Modern syntax such as
  `dict[str, Any]` and `X | None` is expected.
- `print` is allowed only in `cli.py` and in the helper scripts, through
  per-file ignores for the `T20` rule.

## Tests

Tests live in `tests/` and use plain fixtures that build a temporary SQLite
database, so they never touch the bundled `thermo.db`. Tests that exercise
the default database call `ThermochemicalCalculator()` without arguments.

Add a test for every bug fix and new behavior. Follow the existing module
split: calculator behavior in `test_calculator.py`, builder and parsing in
`test_builder_merge.py`, uncertainty in `test_uncertainty.py`, and phase
filtering in `test_phase_detail.py`.

## Documentation

Documentation lives in `docs/source/` and builds with Sphinx plus myst-nb.
The notebooks under `examples/` are the source of truth; Sphinx copies them
into the docs tree at build time, so edit the originals in `examples/`, never
the copies under `docs/source/examples/`.

Text written for the documentation follows the guidance in
`.github/skills/avoid-ai-writing/SKILL.md`. In short: no em dashes, no inline
bold, and no alert boxes in prose.

The release blog is in English. Posts are written directly into
`docs/source/blog/index.md`, newest first, each one preceded by an explicit
permalink target, for example `(pyglenn-0.6.0)=`.

## Database and data

`src/pyglenn/data/thermo.inp` is the raw NASA CEA dataset. `thermo.db` is
generated from it and must never be edited by hand.

Rebuilding the database is a two step process:

```bash
python scripts/rebuild_database.py
python scripts/populate_uncertainty.py
```

The first step rebuilds the species and coefficient tables and enforces the
release gates (2,035 species, 3,795 intervals, 3,795 coefficient rows). The
second step restores the `species_uncertainty` table. If you change the
parser, the schema, or the dataset, run both steps and then the full test
suite.

## Releasing

Releases are prepared on a branch named `release/X.Y.Z` and merged into
`main`. A release touches, in order:

1. `src/pyglenn/__init__.py` and `conda.recipe/meta.yaml`: the version.
2. `CHANGELOG.md`: a new section following Keep a Changelog.
3. `docs/FUTURE_IMPROVEMENTS.md`: mark the completed items.
4. The bundled database: run the two rebuild steps above.
5. The full checks above, then `git tag vX.Y.Z`.

Publishing to PyPI happens automatically when a `v*` tag is pushed, through
the trusted publishing workflow in `.github/workflows/publish-pypi.yml`.

## Reporting problems

Open an issue describing what you expected, what happened, and a minimal
example. Include the Python version and the pyglenn version:

```bash
python -c "import pyglenn; print(pyglenn.__version__)"
```
