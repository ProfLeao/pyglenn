=====
Usage
=====

Command-Line Interface
=======================

pyglenn provides a CLI for quick thermochemical lookups.

.. code-block:: bash

   pyglenn --help

Building the Database
=====================

Before using the calculator, you need to build the SQLite database
from a NASA polynomial ``thermo.inp`` file:

.. code-block:: python

   from pyglenn import ThermoDBBuilder

   builder = ThermoDBBuilder('thermo.inp')
   builder.build('thermo.db')

Using the Calculator
====================

.. code-block:: python

   from pyglenn import ThermochemicalCalculator

   calc = ThermochemicalCalculator('thermo.db')
   calc.connect()

   # Compute properties for methane at 500 K
   result = calc.calculate('CH4', 500.0)

   print(f"Cp  = {result.cp:.3f} J/(mol·K)")
   print(f"H°  = {result.enthalpy:.3f} kJ/mol")
   print(f"S°  = {result.entropy:.3f} J/(mol·K)")

   calc.close()

Context Manager
---------------

Use the calculator as a context manager for automatic cleanup:

.. code-block:: python

   with ThermochemicalCalculator('thermo.db') as calc:
       result = calc.calculate('CO2', 1000.0)
       print(f"Cp = {result.cp:.3f} J/(mol·K)")

Error Handling
==============

The calculator raises specific exceptions for common errors:

- :class:`~pyglenn.DatabaseNotConnectedError` — database not connected
- :class:`~pyglenn.SpeciesNotFoundError` — species not found in database
- :class:`~pyglenn.TemperatureOutOfRangeError` — temperature outside valid range
- :class:`~pyglenn.ThermoCalcError` — base exception for all calculator errors
