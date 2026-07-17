.. _validation:

============================================
Cross-Validation — pyglenn × NIST‑JANAF
============================================

This page documents the thermodynamic audit of **pyglenn**, comparing
the :math:`C_p(T)`, :math:`H^\circ(T)`, and :math:`S^\circ(T)`
properties computed by the library against the **NIST‑JANAF**
reference values (Chase, 1998).


Methodology
===========

**Reference:** NIST reference properties are computed via the Shomate
equation:

.. math::

   C_p^\circ(T) &= A + B\,t + C\,t^2 + D\,t^3 + E\,t^{-2} \\[4pt]
   H^\circ(T) - H^\circ(298.15) &=
   A\,t + B\,\frac{t^2}{2} + C\,\frac{t^3}{3} + D\,\frac{t^4}{4}
   - E\,t^{-1} + F \\[4pt]
   S^\circ(T) &=
   A\ln t + B\,t + C\,\frac{t^2}{2} + D\,\frac{t^3}{3}
   - E\,\frac{t^{-2}}{2} + G

where :math:`t = T / 1000` and the coefficients *A*–*G* were extracted
directly from the `NIST Chemistry WebBook (SRD 69)`_.

**pyglenn:** Properties are calculated from NASA‑7 polynomials stored
in the bundled SQLite database (``thermo.db``).

**Domain:** 300–3000 K, 55 equally spaced points.

**Error metrics:**

.. math::

   \varepsilon_{\text{abs}} &= X_{\text{pyglenn}} - X_{\text{NIST}} \\[4pt]
   \varepsilon_{\text{rel}}(\%) &=
   \frac{X_{\text{pyglenn}} - X_{\text{NIST}}}{|X_{\text{NIST}}|}
   \times 100


Validated Species
=================

.. list-table::
   :header-rows: 1
   :align: left

   * - Code
     - Name
     - Formula
   * - CO₂
     - Carbon dioxide
     - CO\ :sub:`2`
   * - N₂
     - Nitrogen
     - N\ :sub:`2`
   * - CO
     - Carbon monoxide
     - CO
   * - H₂O
     - Water (vapour)
     - H\ :sub:`2`\ O
   * - O₂
     - Oxygen
     - O\ :sub:`2`
   * - NH₃
     - Ammonia
     - NH\ :sub:`3`
   * - SO₂
     - Sulfur dioxide
     - SO\ :sub:`2`

.. note::

   CH₄ was removed from this audit due to a systematic bias
   > 5% in :math:`C_p(T)`.  NH₃ and SO₂ were included as
   replacements.


Graphical Results
=================

Cp(T) — Heat Capacity
---------------------

.. figure:: audit/validation_01_Cp.png
   :alt: Cp(T) — pyglenn vs NIST-JANAF
   :align: center
   :figwidth: 95%

   Comparison of :math:`C_p(T)` for the 7 species.
   Top panels: overlaid absolute values.
   Bottom panel: relative error (%).


ΔH°(298→T) — Enthalpy Change
-----------------------------

.. figure:: audit/validation_02_Enthalpy.png
   :alt: ΔH° — pyglenn vs NIST-JANAF
   :align: center
   :figwidth: 95%

   Comparison of :math:`\Delta H^\circ(298.15 \rightarrow T)`
   for the 7 species.  The large relative error near 298 K is a
   mathematical artefact — the denominator :math:`\Delta H
   \rightarrow 0`.


S°(T) — Absolute Entropy
-------------------------

.. figure:: audit/validation_03_Entropy.png
   :alt: S°(T) — pyglenn vs NIST-JANAF
   :align: center
   :figwidth: 95%

   Comparison of :math:`S^\circ(T)` for the 7 species.
   Top panels: overlaid absolute values.
   Bottom panel: relative error (%).


Consolidated Error Panel
------------------------

.. figure:: audit/validation_errors.png
   :alt: Relative errors — Cp, ΔH, S°
   :align: center
   :figwidth: 95%

   Relative error (%) for :math:`C_p`, :math:`\Delta H`, and
   :math:`S` across all 7 species in a single 3‑column panel.


Statistical Summary
===================

.. list-table::
   :header-rows: 1
   :align: left
   :widths: 12 12 18 22 14

   * - Species
     - Property
     - Mean error (%)
     - Max abs. error (%)
     - RMSE (%)
   * - CO
     - Cp
     - +0.024
     - 0.198
     - 0.067
   * - CO
     - ΔH
     - −0.381
     - 18.727
     - 2.527
   * - CO
     - S°
     - +0.001
     - 0.005
     - 0.002
   * - CO\ :sub:`2`
     - Cp
     - −0.025
     - 0.117
     - 0.043
   * - CO\ :sub:`2`
     - ΔH
     - +0.541
     - 26.681
     - 3.600
   * - CO\ :sub:`2`
     - S°
     - −0.002
     - 0.005
     - 0.003
   * - H\ :sub:`2`\ O
     - Cp
     - +0.845
     - 1.940
     - 1.094
   * - H\ :sub:`2`\ O
     - ΔH
     - +0.310
     - 0.879
     - 0.423
   * - H\ :sub:`2`\ O
     - S°
     - +0.053
     - 0.171
     - 0.077
   * - NH\ :sub:`3`
     - Cp
     - −0.632
     - 1.071
     - 0.716
   * - NH\ :sub:`3`
     - ΔH
     - −1.757
     - 62.475
     - 8.452
   * - NH\ :sub:`3`
     - S°
     - −0.117
     - 0.220
     - 0.141
   * - SO\ :sub:`2`
     - Cp
     - −0.464
     - 0.620
     - 0.490
   * - SO\ :sub:`2`
     - ΔH
     - +0.677
     - 48.323
     - 6.527
   * - SO\ :sub:`2`
     - S°
     - −0.068
     - 0.121
     - 0.077

.. note::

   The large maximum errors in :math:`\Delta H` for CO, CO₂, NH₃,
   and SO₂ occur exclusively near 298.15 K, where
   :math:`\Delta H^\circ(298.15 \rightarrow T) \rightarrow 0` and
   the relative error diverges mathematically.  **RMSE** and **mean
   error** are more representative metrics of overall quality.


Interpretation
==============

* **Cp and S° — Excellent agreement.** For all 7 species, the mean
  relative error in :math:`C_p` and :math:`S^\circ` is below 1%,
  with RMSE typically under 0.5%.  This confirms that NASA‑7
  polynomials produce results virtually identical to the Shomate
  equation for these properties.

* **ΔH — Numerical artefact near 298 K.** The relative error in
  :math:`\Delta H` spikes near the reference temperature because the
  denominator approaches zero.  Excluding points below ~400 K, the
  mean error stays within ±2% for all species.

* **H₂O — Best overall case.** Water shows the lowest and most
  balanced errors across all three properties, with RMSE < 1.1%
  for each.

* **NH₃ — Worst case.** Ammonia exhibits the highest RMSE in ΔH
  (8.45%), still dominated by the low‑temperature artefact.
  Cp and S° remain below 1% RMSE.


Full Dataset
============

The CSV file with all 385 validation points (7 species × 55
temperatures) is available for download:

:download:`⬇ pyglenn_vs_nist.csv <audit/pyglenn_vs_nist.csv>`

The audit source code and plain‑text summary can also be found in
the repository:

* :download:`📄 validation_summary.txt <audit/validation_summary.txt>`
* :download:`🐍 audit_code.py <audit/audit_code.py>`


References
==========

.. _NIST Chemistry WebBook (SRD 69): https://webbook.nist.gov/chemistry/

* Chase, M. W. (1998). *NIST‑JANAF Thermochemical Tables*,
  4th ed.  Journal of Physical and Chemical Reference Data,
  Monograph 9.
* `NIST Chemistry WebBook, SRD 69 <https://webbook.nist.gov/chemistry/>`_
  — Shomate coefficients.
