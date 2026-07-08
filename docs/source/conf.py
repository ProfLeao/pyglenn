"""Sphinx configuration for pyglenn documentation."""

import os
import sys

# -- Path setup -----------------------------------------------------------
# Add the src directory to sys.path so autodoc can find the package
sys.path.insert(0, os.path.abspath('../../src'))

# -- Project information ---------------------------------------------------
project = 'pyglenn'
copyright = '2025, Dr. Reginaldo G. Leão Jr.'
author = 'Dr. Reginaldo G. Leão Jr.'
release = '1.0.0'

# -- General configuration -------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'myst_parser',
]

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
    '.md': 'markdown',
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

# -- Intersphinx -----------------------------------------------------------
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}
