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

Enthalpy Semantics
==================

``calculate_properties`` returns ``h_relative`` as the **absolute** enthalpy
$H^\circ(T)$ following the NASA-7 convention, in which
$H^\circ(298.15\,\mathrm{K})$ equals the standard enthalpy of formation
$\Delta H_f^\circ(298.15)$. The sensible enthalpy relative to 298.15 K is
therefore:

.. code-block:: python

   from pyglenn import ThermochemicalCalculator

   with ThermochemicalCalculator() as calc:
       sid = calc.get_available_species('CH4', exact_match=True)[0].id

       h_total    = calc.calculate_properties(sid, 1000.0).h_relative
       h_sensible = calc.h_sensible_to(sid, 1000.0)          # H(1000) − H(298.15)
       h_formation = calc.calculate_formation_enthalpy(sid)  # ΔH°f(298.15)

       # h_total = h_formation + h_sensible

The NASA-7 polynomials are continuous across interval boundaries, so the two
temperatures may lie in different intervals.

Analytical Derivatives
======================

.. code-block:: python

   with ThermochemicalCalculator() as calc:
       sid = calc.get_available_species('O2', exact_match=True)[0].id

       dcp_dt = calc.dcp_dt(sid, 1000.0)   # dCp/dT in J/(mol·K²)
       gamma  = calc.gamma(sid, 1000.0)    # Cp/Cv (ideal gas)

Mixtures
========

For a mixture with a **known** composition (air, combustion products, reference
mixtures), compose per-species properties with :class:`~pyglenn.Mixture`:

.. code-block:: python

   from pyglenn import Mixture, ThermochemicalCalculator

   with ThermochemicalCalculator() as calc:
       n2 = calc.get_available_species('N2', exact_match=True)[0]
       o2 = calc.get_available_species('O2', exact_match=True)[0]

       air = Mixture(((n2.id, 0.79), (o2.id, 0.21)))  # mole fractions
       air.validate()                                  # raises CompositionError

       mix = calc.mixture_properties(air, 1000.0)      # MixedProperties

       print(mix.cp_mass)      # J/(kg·K)
       print(mix.molar_mass)   # kg/mol (mole-fraction weighted mean)

``mixture_properties`` returns :class:`~pyglenn.MixedProperties` with both
molar and mass values. The mean molar mass is the mole-fraction-weighted
**arithmetic** mean ``M = Σ xᵢ Mᵢ``. No chemical equilibrium is solved — the
composition is an input. Out-of-range components raise
:class:`~pyglenn.TemperatureOutOfRangeError` with ``strict=True`` (default)
or are skipped and renormalized (with a warning) when ``strict=False``.

Fitting NASA-7 Coefficients
===========================

:func:`~pyglenn.fit_nasa7` fits the seven heat-capacity coefficients
(``a1..a7``) to tabulated Cp(T) data and derives the integration constants so
that ``H°(t_ref) = h_ref`` holds exactly (NASA-7 convention, constant ``b1``):

.. code-block:: python

   import numpy as np
   from pyglenn import fit_nasa7

   T = np.linspace(200.0, 1000.0, 50)          # Kelvin
   cp = ...                                    # J/(mol·K), measured or computed

   coeffs = fit_nasa7(
       T, cp, t_ref=298.15, h_ref=0.0, s_ref=None
   )                                           # -> NASACoefficients

``s_ref`` optionally anchors the entropy constant ``b2``; otherwise it is
``0.0``. The fit is performed in a scaled variable to keep the design matrix
well-conditioned — prefer fitting one temperature interval at a time, as NASA
datasets do.

Error Handling
==============

The calculator raises specific exceptions for common errors:

- :class:`~pyglenn.CompositionError` — invalid mixture composition (mole fractions)
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
:class:`~pyglenn.IntervalData`, :class:`~pyglenn.NASACoefficients`,
:class:`~pyglenn.Mixture`, :class:`~pyglenn.MixedProperties` and
:class:`~pyglenn.DatabaseStats`.

Deprecated API
==============

:meth:`pyglenn.ThermochemicalCalculator.get_properties_range` is deprecated and
will be removed in 0.4.0. Use
:meth:`~pyglenn.ThermochemicalCalculator.calculate_properties_range` instead —
it returns an ordered list of ``ThermoProperties`` rather than a
temperature-keyed dictionary, and accepts ``strict=True`` to raise on
out-of-range temperatures.
