"""Least-squares fitting of NASA-7 polynomials to tabulated Cp(T) data.

This module exposes :func:`fit_nasa7`, which fits the seven heat-capacity
coefficients (``a1..a7``) to tabulated data and derives the integration
constants so that the NASA-7 enthalpy convention is satisfied exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .database import R_GLENN
from .models import NASACoefficients

__all__ = ['fit_nasa7']

# Minimum number of data points required to determine the seven a-coefficients.
_MIN_POINTS = 7


def fit_nasa7(
    temperatures: Sequence[float],
    cp_values: Sequence[float],
    *,
    t_ref: float = 298.15,
    h_ref: float = 0.0,
    s_ref: float | None = None,
    weights: Sequence[float] | None = None,
    r_ref: float = R_GLENN,
) -> NASACoefficients:
    """Fit NASA-7 coefficients ``a1..a7`` to tabulated Cp(T) data.

    Fits the seven heat-capacity coefficients by (weighted) least squares in
    the dimensionless form::

        Cp/R = a1/T² + a2/T + a3 + a4·T + a5·T² + a6·T³ + a7·T⁴

    The enthalpy integration constant ``b1`` is **not** fitted: it is derived
    so that the NASA-7 convention ``H°(t_ref) = h_ref`` holds exactly. The
    entropy constant ``b2`` is derived from ``s_ref`` when provided, and set
    to ``0.0`` otherwise.

    Args:
        temperatures: Temperatures in Kelvin (must be strictly positive).
        cp_values: Heat capacity at each temperature, in J/(mol·K).
        t_ref: Reference temperature in Kelvin for the enthalpy anchor
            (default 298.15).
        h_ref: Enthalpy H° at ``t_ref`` in J/mol (default 0.0). The returned
            ``b1`` guarantees H°(t_ref) == h_ref.
        s_ref: Optional entropy S° at ``t_ref`` in J/(mol·K). When given, the
            returned ``b2`` guarantees S°(t_ref) == s_ref.
        weights: Optional per-point weights (same length as ``temperatures``).
            Defaults to uniform weights.
        r_ref: Reference gas constant used to denormalize ``cp_values`` and
            ``h_ref``. Defaults to :data:`~pyglenn.R_GLENN`, the value used by
            the bundled database.

    Returns:
        :class:`~pyglenn.NASACoefficients` with ``a1..a7``, ``b1`` and ``b2``.

    Raises:
        ValueError: If the inputs are inconsistent, too short, or contain
            non-positive temperatures, non-finite values, or invalid weights.

    Notes:
        **NASA-7 convention.** The enthalpy integration constant is ``b1``;
        ``a6`` and ``a7`` multiply T³ and T⁴ in the Cp polynomial and are
        **not** integration constants. The fitted coefficients follow the same
        convention as the rest of pyglenn, so they can be evaluated directly
        with :meth:`pyglenn.ThermoDBQuery.calculate_cp`.

        **Conditioning.** The fit is performed in the scaled variable
        ``u = T / T_scale`` (with ``T_scale`` the geometric mean temperature)
        to keep the design matrix well-conditioned. Very wide temperature
        ranges remain inherently ill-conditioned; NASA datasets split each
        species into several intervals, so prefer fitting one interval at a
        time.
    """
    T = np.asarray(temperatures, dtype=float)
    cp = np.asarray(cp_values, dtype=float)

    if T.ndim != 1 or cp.ndim != 1:
        raise ValueError('temperatures and cp_values must be one-dimensional')
    if T.size != cp.size:
        raise ValueError(
            f'temperatures and cp_values must have the same length '
            f'(got {T.size} and {cp.size})'
        )
    if T.size < _MIN_POINTS:
        raise ValueError(
            f'at least {_MIN_POINTS} data points are required to fit seven '
            f'coefficients (got {T.size})'
        )
    if not np.all(np.isfinite(T)):
        raise ValueError('temperatures must be finite')
    if np.any(T <= 0.0):
        raise ValueError('temperatures must be strictly positive')
    if not np.all(np.isfinite(cp)):
        raise ValueError('cp_values must be finite')

    t_ref = float(t_ref)
    h_ref = float(h_ref)
    r_ref = float(r_ref)
    if not np.isfinite(t_ref) or t_ref <= 0.0:
        raise ValueError('t_ref must be finite and strictly positive')
    if not np.isfinite(h_ref):
        raise ValueError('h_ref must be finite')
    if not np.isfinite(r_ref) or r_ref <= 0.0:
        raise ValueError('r_ref must be finite and strictly positive')

    if s_ref is not None:
        s_ref = float(s_ref)
        if not np.isfinite(s_ref):
            raise ValueError('s_ref must be finite')

    if weights is None:
        w = np.ones(T.size, dtype=float)
    else:
        w = np.asarray(weights, dtype=float)
        if w.ndim != 1 or w.size != T.size:
            raise ValueError('weights must be one-dimensional and match temperatures')
        if not np.all(np.isfinite(w)):
            raise ValueError('weights must be finite')
        if np.any(w < 0.0):
            raise ValueError('weights must be non-negative')
        if np.all(w == 0.0):
            raise ValueError('at least one weight must be positive')

    # Denormalize Cp with the chosen reference gas constant.
    y = cp / r_ref

    # Fit in the scaled variable u = T / T_scale (u is O(1)).
    T_scale = float(np.exp(np.mean(np.log(T))))
    u = T / T_scale

    sqrt_w = np.sqrt(w)
    X = np.column_stack([u**-2, u**-1, np.ones_like(u), u, u**2, u**3, u**4])
    X = X * sqrt_w[:, None]
    y = y * sqrt_w

    c, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < _MIN_POINTS:
        raise ValueError(
            f'design matrix is rank-deficient (rank {rank} < {_MIN_POINTS}); '
            'provide at least 7 distinct temperatures'
        )

    # Map the scaled coefficients back to the standard NASA-7 basis.
    a1 = float(c[0]) * T_scale**2
    a2 = float(c[1]) * T_scale
    a3 = float(c[2])
    a4 = float(c[3]) / T_scale
    a5 = float(c[4]) / T_scale**2
    a6 = float(c[5]) / T_scale**3
    a7 = float(c[6]) / T_scale**4

    # Enthalpy integration constant: enforce H°(t_ref) = h_ref exactly.
    log_t_ref = float(np.log(t_ref))
    p_ref = (
        -a1 / t_ref**2
        + a2 * log_t_ref / t_ref
        + a3
        + a4 * t_ref / 2
        + a5 * t_ref**2 / 3
        + a6 * t_ref**3 / 4
        + a7 * t_ref**4 / 5
    )
    b1 = h_ref / r_ref - t_ref * p_ref

    # Entropy integration constant: optional anchor, otherwise 0.0.
    if s_ref is None:
        b2 = 0.0
    else:
        q_ref = (
            -a1 / (2 * t_ref**2)
            - a2 / t_ref
            + a3 * log_t_ref
            + a4 * t_ref
            + a5 * t_ref**2 / 2
            + a6 * t_ref**3 / 3
            + a7 * t_ref**4 / 4
        )
        b2 = s_ref / r_ref - q_ref

    return NASACoefficients(
        a1=a1,
        a2=a2,
        a3=a3,
        a4=a4,
        a5=a5,
        a6=a6,
        a7=a7,
        b1=b1,
        b2=b2,
    )
