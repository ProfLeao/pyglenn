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
       # Find methane — exact_match=True avoids confusion with
       # species like CH3CHCH4 or C2H4 that contain 'CH4'
       species = calc.get_available_species('CH4', exact_match=True)
       result = calc.calculate_properties(species[0].id, 500.0)
       print(f"Cp  = {result.cp:.3f} J/(mol·K)")
       print(f"H°  = {result.h_relative:.3f} J/mol")
       print(f"S°  = {result.s:.3f} J/(mol·K)")

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

Migration from dictionaries (v0.1.x)
====================================

As of **v0.2.0**, public methods return typed dataclasses instead of plain
dictionaries. Convert old code by replacing ``result['key']`` with
``result.key``:

.. code-block:: python

   # v0.1.x (dict)
   props = calc.calculate_properties(species_id, 500.0)
   cp = props['cp']
   name = props['species_name']

   # v0.2.0 (dataclass)
   props = calc.calculate_properties(species_id, 500.0)
   cp = props.cp
   name = props.species_name

To recover the previous dictionary shape (for JSON or legacy consumers),
use :func:`dataclasses.asdict` or the ``to_dict()`` method:

.. code-block:: python

   from dataclasses import asdict

   payload = asdict(calc.calculate_properties(species_id, 500.0))

The typed models are :class:`~pyglenn.ThermoProperties`,
:class:`~pyglenn.SpeciesInfo`, :class:`~pyglenn.SpeciesData`,
:class:`~pyglenn.IntervalData`, :class:`~pyglenn.NASACoefficients` and
:class:`~pyglenn.DatabaseStats`.
