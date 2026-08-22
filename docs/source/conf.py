"""Sphinx configuration for pyglenn documentation."""

import os
import shutil
import sys

# -- Path setup -----------------------------------------------------------
# Add the src directory to sys.path so autodoc can find the package
sys.path.insert(0, os.path.abspath('../../src'))

# -- Notebook examples -----------------------------------------------------
# The example notebooks live in the top-level ``examples/`` folder (single
# source of truth, runnable standalone and visible on GitHub). Copy them into
# the docs source tree at build time so myst-nb can render them. The copy is
# git-ignored — never edit the notebooks under ``docs/source/examples/``.
_HERE = os.path.dirname(__file__)
_EXAMPLES_SRC = os.path.abspath(os.path.join(_HERE, '../../examples'))
_EXAMPLES_DST = os.path.join(_HERE, 'examples')
if os.path.isdir(_EXAMPLES_SRC):
    shutil.rmtree(_EXAMPLES_DST, ignore_errors=True)
    os.makedirs(_EXAMPLES_DST, exist_ok=True)
    # Copy only the notebooks — auxiliary files (README.md, notes) stay in the
    # repo and are intentionally kept out of the rendered documentation.
    for _name in sorted(os.listdir(_EXAMPLES_SRC)):
        if _name.endswith('.ipynb'):
            shutil.copy2(
                os.path.join(_EXAMPLES_SRC, _name),
                os.path.join(_EXAMPLES_DST, _name),
            )

# -- Audit/validation assets -----------------------------------------------
# Copy audit images and data files so they are accessible to the validation
# RST page.  The originals live in ``docs/audit/`` (outside the Sphinx
# source tree) and are copied into the source directory at build time.
_AUDIT_SRC = os.path.abspath(os.path.join(_HERE, '../audit'))
_AUDIT_DST = os.path.join(_HERE, 'audit')
if os.path.isdir(_AUDIT_SRC):
    shutil.rmtree(_AUDIT_DST, ignore_errors=True)
    os.makedirs(_AUDIT_DST, exist_ok=True)
    for _name in sorted(os.listdir(_AUDIT_SRC)):
        _src = os.path.join(_AUDIT_SRC, _name)
        if os.path.isfile(_src):
            shutil.copy2(_src, os.path.join(_AUDIT_DST, _name))

# -- Project information ---------------------------------------------------
project = 'pyglenn'
copyright = '2025, Dr. Reginaldo G. Leão Jr.'
author = 'Dr. Reginaldo G. Leão Jr.'

# Read version from the package itself (single source of truth)
from pyglenn import __version__ as _pyglenn_version

release = _pyglenn_version
version = '.'.join(release.split('.')[:2])  # e.g. "1.0"

# -- General configuration -------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'myst_nb',
]

# -- myst-nb / MyST configuration ------------------------------------------
# Execute notebooks at build time so their outputs are rendered.
# 'auto' runs a notebook only when it has no stored outputs.
nb_execution_mode = 'auto'
nb_execution_timeout = 120
nb_execution_raise_on_error = True
myst_enable_extensions = ['dollarmath', 'colon_fence']

# Napoleon settings (Google/NumPy docstring style)
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False

# Autodoc settings
autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
autoclass_content = 'both'

templates_path = ['_templates']
exclude_patterns = []

# Support both .rst and .md files
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'myst-nb',
    '.ipynb': 'myst-nb',
}

master_doc = 'index'
language = 'en'

# -- Options for HTML output -----------------------------------------------
html_theme = 'renku'

html_logo = '_static/logo_pyglenn.png'

html_theme_options = {
    'logo_only': False,
    'prev_next_buttons_location': 'bottom',
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 3,
    'includehidden': True,
    'titles_only': False,
}

html_context = {
    'display_github': True,
    'github_user': 'ProfLeao',
    'github_repo': 'pyglenn',
    'github_version': 'main',
    'conf_py_path': '/docs/source/',
    'vcs_pageview_mode': 'blob',
}

html_static_path = ['_static']

# Custom CSS files (loaded after theme CSS, so they take precedence)
html_css_files = [
    'custom.css',
]

# -- Intersphinx -----------------------------------------------------------
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}
