========
Database
========

The SQLite database stores NASA polynomial coefficients for each species.

Database Schema
===============

The database contains a ``species`` table with these columns:

- ``name`` — species name (e.g., ``'CH4'``, ``'CO2'``)
- ``phase`` — phase indicator (G = gas, L = liquid, S = solid)
- ``T_low`` — minimum valid temperature [K]
- ``T_high`` — maximum valid temperature [K]
- ``T_mid`` — midpoint temperature (NASA-7 format)
- ``a1..a7`` — high-temperature polynomial coefficients
- ``a8..a14`` — low-temperature polynomial coefficients (NASA-7)

NASA Polynomial Format
=======================

The coefficients follow the standard NASA polynomial form:

.. math::

   \frac{C_p^\circ}{R} = a_1 + a_2 T + a_3 T^2 + a_4 T^3 + a_5 T^4

.. math::

   \frac{H^\circ}{RT} = a_1 + \frac{a_2}{2}T + \frac{a_3}{3}T^2
   + \frac{a_4}{4}T^3 + \frac{a_5}{5}T^4 + \frac{a_6}{T}

.. math::

   \frac{S^\circ}{R} = a_1 \ln T + a_2 T + \frac{a_3}{2}T^2
   + \frac{a_4}{3}T^3 + \frac{a_5}{4}T^4 + a_7

Querying the Database
=====================

You can query the database directly using :class:`~pyglenn.ThermoDBQuery`:

.. code-block:: python

   from pyglenn import ThermoDBQuery

   query = ThermoDBQuery('thermo.db')

   # List all available species
   species = query.list_species()
   print(species)

   # Get coefficients for a specific species
   coefs = query.get_coefficients('CH4')
   print(coefs)

   query.close()

Universal Gas Constant
======================

The universal gas constant is available as :data:`pyglenn.R`:

.. code-block:: python

   from pyglenn import R

   print(f"R = {R} J/(mol·K)")
