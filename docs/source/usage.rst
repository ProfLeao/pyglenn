=====
Usage
=====

Command-Line Interface
=======================

pyglenn provides a CLI for quick thermochemical lookups.

.. code-block:: bash

   pyglenn --help

Building the Database (optional)
================================

The database comes **pre-built and bundled** with the package.
You only need to rebuild if:

- The database file gets corrupted
- You modify the ``thermo.inp`` coefficients manually

.. code-block:: python

   from pyglenn import ThermoDBBuilder

   builder = ThermoDBBuilder('path/to/thermo.inp', 'thermo.db')
   builder.connect()
   builder.create_tables()
   builder.parse_and_load()
   builder.close()

Using the Calculator
====================

Simply instantiate with no arguments — the bundled database is used automatically:

.. code-block:: python

   from pyglenn import ThermochemicalCalculator

   with ThermochemicalCalculator() as calc:
       # Find methane
       species = calc.get_available_species('CH4')
       result = calc.calculate_properties(species[0]['id'], 500.0)
       print(f"Cp  = {result['cp']:.3f} J/(mol·K)")
       print(f"H°  = {result['h_relative']:.3f} J/mol")
       print(f"S°  = {result['s']:.3f} J/(mol·K)")

You can also specify a custom database file:

.. code-block:: python

   with ThermochemicalCalculator('custom.db') as calc:
       ...

Error Handling
==============

The calculator raises specific exceptions for common errors:

- :class:`~pyglenn.DatabaseNotConnectedError` — database not connected
- :class:`~pyglenn.SpeciesNotFoundError` — species not found in database
- :class:`~pyglenn.TemperatureOutOfRangeError` — temperature outside valid range
- :class:`~pyglenn.ThermoCalcError` — base exception for all calculator errors
