==============================================
pyglenn — Thermochemical Properties Calculator
==============================================

**pyglenn** computes :math:`C_p(T)`, :math:`H^\circ(T)`, and :math:`S^\circ(T)`
from NASA polynomial coefficients stored in a SQLite database, converted from
FORTRAN ``thermo.inp`` files.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   usage
   examples
   api
   database

----------------
Quick Start
----------------

Installation
============

.. code-block:: bash

   pip install pyglenn

Basic Usage
===========

The database is **bundled** — no manual setup required:

.. code-block:: python

   from pyglenn import ThermochemicalCalculator

   with ThermochemicalCalculator() as calc:
       result = calc.calculate_properties(
           calc.get_available_species('CH4')[0]['id'], 298.15
       )
       print(f"Cp = {result['cp']:.3f} J/mol·K")
       print(f"H° = {result['h_relative']:.3f} J/mol")
       print(f"S° = {result['s']:.3f} J/mol·K")

Features
========

- Compute :math:`C_p(T)`, :math:`H^\circ(T)`, :math:`S^\circ(T)` for any species
- SQLite database bundled with **~2030 species, 3772 temperature intervals** — no setup needed
- CLI interface for quick lookups
- Temperature range validation

----

:Author: **Dr. Reginaldo G. Leão Jr.** — `prof.reginaldo.leao@gmail.com <mailto:prof.reginaldo.leao@gmail.com>`_
:GitHub: `github.com/ProfLeao/pyglenn <https://github.com/ProfLeao/pyglenn>`_
:Documentation: `profleao.github.io/pyglenn <https://profleao.github.io/pyglenn>`_

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
