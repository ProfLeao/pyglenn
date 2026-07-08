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

.. code-block:: python

   from pyglenn import ThermochemicalCalculator

   calc = ThermochemicalCalculator()
   calc.connect()

   # Look up methane (CH₄)
   result = calc.calculate('CH4', 298.15)

   print(f"Cp = {result.cp:.3f} J/mol·K")
   print(f"H° = {result.enthalpy:.3f} kJ/mol")
   print(f"S° = {result.entropy:.3f} J/mol·K")

   calc.close()

Features
========

- Compute :math:`C_p(T)`, :math:`H^\circ(T)`, :math:`S^\circ(T)` for any species
- SQLite database built from NASA-7 or NASA-9 polynomial format
- CLI interface for quick lookups
- Temperature range validation

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
