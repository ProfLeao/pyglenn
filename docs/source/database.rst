========
Database
========

The SQLite database stores NASA polynomial coefficients for each species
in a **normalised** three-table schema.

Database Schema
===============

The database contains three linked tables:

**species** — chemical species metadata

- ``id`` — primary key (auto-increment)
- ``name`` — species name (e.g., ``'CH4'``, ``'CO2'``)
- ``formula`` — chemical formula
- ``phase`` — ``'gas'`` or ``'condensed'``
- ``molecular_weight`` — in g/mol
- ``heat_of_formation_298K`` — ΔH°f at 298.15 K in J/mol
- ``num_intervals`` — number of temperature intervals
- ``comments`` — free-text notes

**temperature_intervals** — one row per temperature range per species

- ``id`` — primary key
- ``species_id`` — foreign key → ``species.id``
- ``interval_number`` — 1, 2, 3, …
- ``temp_min`` — minimum valid temperature [K]
- ``temp_max`` — maximum valid temperature [K]
- ``h_298_to_0`` — H°(298.15) − H°(0) in J/mol

**coefficients** — NASA-7 polynomial coefficients (one row per interval)

- ``id`` — primary key
- ``interval_id`` — foreign key → ``temperature_intervals.id``
- ``a1`` … ``a7`` — polynomial coefficients
- ``b1``, ``b2`` — integration constants

NASA Polynomial Format
=======================

pyglenn uses the **alternate** NASA-7 form (also known as the "old" or
"Gordon–McBride" form).  The dimensionless properties are:

.. math::

   \frac{C_p^\circ}{R} = \frac{a_1}{T^2} + \frac{a_2}{T}
   + a_3 + a_4 T + a_5 T^2 + a_6 T^3 + a_7 T^4

.. math::

   \frac{H^\circ}{RT} = -\frac{a_1}{T^2} + a_2\frac{\ln T}{T}
   + a_3 + a_4\frac{T}{2} + a_5\frac{T^2}{3}
   + a_6\frac{T^3}{4} + a_7\frac{T^4}{5} + \frac{b_1}{T}

.. math::

   \frac{S^\circ}{R} = -\frac{a_1}{2T^2} - \frac{a_2}{T}
   + a_3 \ln T + a_4 T + a_5\frac{T^2}{2}
   + a_6\frac{T^3}{3} + a_7\frac{T^4}{4} + b_2

These match the implementation in :mod:`pyglenn.database`
(:meth:`~pyglenn.ThermoDBQuery.calculate_cp`,
:meth:`~pyglenn.ThermoDBQuery.calculate_h`,
:meth:`~pyglenn.ThermoDBQuery.calculate_s`).

Querying the Database
=====================

You can query the database directly using :class:`~pyglenn.ThermoDBQuery`:

.. code-block:: python

   from pyglenn import ThermoDBQuery

   query = ThermoDBQuery('thermo.db')
   query.connect()

   # Search species by name
   species = query.find_species('CH4', exact_match=True)
   print(species[0]['name'], species[0]['phase'])

   # Get complete data (metadata + all intervals + coefficients)
   data = query.get_species_data(species[0]['id'])
   for interval in data['intervals']:
       print(f"  {interval['temp_min']}–{interval['temp_max']} K")
       coeffs = interval['coefficients']
       print(f"  a1={coeffs['a1']}, …, a7={coeffs['a7']}")

   query.close()

Universal Gas Constant
======================

The universal gas constant is available as :data:`pyglenn.R`:

.. code-block:: python

   from pyglenn import R

   print(f"R = {R} J/(mol·K)")

