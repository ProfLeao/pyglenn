"""Least-squares fitting of NASA-7 polynomials to tabulated Cp(T) data.

This module exposes :func:`fit_nasa7` (single temperature interval) and
:func:`fit_nasa7_multi` (several intervals with continuity of Cp and its
first derivative at each internal breakpoint). Both derive the integration
constants so that the NASA-7 enthalpy convention is satisfied exactly.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .database import R_GLENN
from .models import NASACoefficients

__all__ = ['fit_nasa7', 'fit_nasa7_multi']

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


def _basis_matrix(u: np.ndarray) -> np.ndarray:
    """Scaled NASA-7 Cp basis ``[u^-2, u^-1, 1, u, u², u³, u⁴]`` (M×7)."""
    return np.column_stack([u**-2, u**-1, np.ones_like(u), u, u**2, u**3, u**4])


def _basis_vector(u: float) -> np.ndarray:
    """The scaled Cp basis evaluated at a scalar ``u`` (length 7)."""
    return np.array([u**-2, u**-1, 1.0, u, u**2, u**3, u**4])


def _deriv_vector(u: float) -> np.ndarray:
    """d/du of the scaled Cp basis at a scalar ``u`` (length 7)."""
    return np.array([-2.0 * u**-3, -(u**-2), 0.0, 1.0, 2.0 * u, 3.0 * u**2, 4.0 * u**3])


def _h_poly(a: Sequence[float], T: float) -> float:
    """Polynomial part of H/RT (without ``b1/T``) for a NASA-7 coefficient set."""
    a1, a2, a3, a4, a5, a6, a7 = a
    return float(
        -a1 / T**2
        + a2 * np.log(T) / T
        + a3
        + a4 * T / 2
        + a5 * T**2 / 3
        + a6 * T**3 / 4
        + a7 * T**4 / 5
    )


def _s_poly(a: Sequence[float], T: float) -> float:
    """Polynomial part of S/R (without ``b2``) for a NASA-7 coefficient set."""
    a1, a2, a3, a4, a5, a6, a7 = a
    return float(
        -a1 / (2 * T**2)
        - a2 / T
        + a3 * np.log(T)
        + a4 * T
        + a5 * T**2 / 2
        + a6 * T**3 / 3
        + a7 * T**4 / 4
    )


def fit_nasa7_multi(
    temperatures: Sequence[float],
    cp_values: Sequence[float],
    breakpoints: Sequence[float],
    *,
    t_ref: float = 298.15,
    h_ref: float = 0.0,
    s_ref: float | None = None,
    weights: Sequence[float] | None = None,
    r_ref: float = R_GLENN,
) -> tuple[NASACoefficients, ...]:
    """Fit NASA-7 coefficients across several temperature intervals.

    Fits one set of seven heat-capacity coefficients per interval, requiring
    that both ``Cp/R`` and its first temperature derivative are continuous at
    every internal breakpoint (a linear equality constraint in the
    least-squares problem). The enthalpy constant ``b1`` is anchored in the
    interval containing ``t_ref`` and propagated so that H° is continuous
    across breakpoints; ``b2`` is anchored from ``s_ref`` when provided and
    propagated so that S° is continuous, otherwise set to ``0.0`` everywhere.

    Args:
        temperatures: Temperatures in Kelvin (strictly positive).
        cp_values: Heat capacity at each temperature, in J/(mol·K).
        breakpoints: Internal boundary temperatures, strictly increasing and
            inside the data range. A point with ``T <= breakpoint`` belongs to
            the lower interval (matching pyglenn's interval convention).
        t_ref: Reference temperature for the enthalpy anchor (default 298.15).
        h_ref: Enthalpy H° at ``t_ref`` in J/mol (default 0.0). The interval
            containing ``t_ref`` gets the ``b1`` that makes H°(t_ref) == h_ref.
        s_ref: Optional entropy S° at ``t_ref`` in J/(mol·K).
        weights: Optional per-point weights (same length as ``temperatures``).
        r_ref: Reference gas constant (default :data:`~pyglenn.R_GLENN`).

    Returns:
        Tuple of :class:`~pyglenn.NASACoefficients`, one per interval in
        increasing temperature order.

    Raises:
        ValueError: If the inputs are inconsistent, contain non-positive or
            non-finite values, invalid breakpoints or weights, or an interval
            has fewer than 7 points.

    Notes:
        The continuity constraints concern the fitted Cp polynomial (value and
        first derivative), matching :func:`fit_nasa7`'s NASA-7 convention
        (``b1`` is the enthalpy constant, not ``a6``). The constrained
        least-squares problem is solved with a null-space projection of the
        continuity constraints; each interval is scaled independently to keep
        the problem well-conditioned.
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

    bps = np.asarray(breakpoints, dtype=float)
    if bps.ndim != 1 or bps.size == 0:
        raise ValueError('breakpoints must be a non-empty one-dimensional sequence')
    if not np.all(np.isfinite(bps)):
        raise ValueError('breakpoints must be finite')
    if np.any(bps <= 0.0):
        raise ValueError('breakpoints must be strictly positive')
    if np.any(np.diff(bps) <= 0.0):
        raise ValueError('breakpoints must be strictly increasing')
    if bps[0] <= float(T.min()) or bps[-1] >= float(T.max()):
        raise ValueError('breakpoints must lie strictly inside the temperature range')

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

    n_intervals = int(bps.size) + 1
    # Interval index per point; points at a breakpoint belong to the lower
    # interval (T <= bps[k] -> interval k), matching _select_interval.
    idx = np.searchsorted(bps, T, side='left').astype(int)

    counts = np.bincount(idx, minlength=n_intervals)
    if np.any(counts < _MIN_POINTS):
        raise ValueError(
            f'every interval needs at least {_MIN_POINTS} points '
            f'(got counts {counts.tolist()})'
        )

    y = cp / r_ref
    sqrt_w = np.sqrt(w)

    # Per-interval scaled design matrix, stacked block-diagonally.
    n_unknowns = 7 * n_intervals
    X = np.zeros((T.size, n_unknowns))
    scales = np.empty(n_intervals)
    for k in range(n_intervals):
        mask = idx == k
        Tk = T[mask]
        scales[k] = float(np.exp(np.mean(np.log(Tk))))
        uk = Tk / scales[k]
        X[mask, 7 * k : 7 * k + 7] = _basis_matrix(uk)

    X = X * sqrt_w[:, None]
    y = y * sqrt_w

    # Continuity constraints C c = 0: value and first derivative of Cp/R at
    # each breakpoint (two rows per breakpoint).
    C = np.zeros((2 * int(bps.size), n_unknowns))
    for r in range(int(bps.size)):
        Tb = float(bps[r])
        left = slice(7 * r, 7 * r + 7)
        right = slice(7 * (r + 1), 7 * (r + 1) + 7)
        u_left = Tb / float(scales[r])
        u_right = Tb / float(scales[r + 1])
        C[2 * r, left] = _basis_vector(u_left)
        C[2 * r, right] = -_basis_vector(u_right)
        C[2 * r + 1, left] = _deriv_vector(u_left) / float(scales[r])
        C[2 * r + 1, right] = -_deriv_vector(u_right) / float(scales[r + 1])

    # Solve min ||X c - y|| subject to C c = 0 with a null-space projection:
    # the feasible set is c = N z, where the columns of N span null(C).
    _, s_vals, Vt = np.linalg.svd(C, full_matrices=True)
    tol_c = float(s_vals[0]) * max(C.shape) * np.finfo(float).eps
    rank_c = int(np.sum(s_vals > tol_c))
    null_dim = n_unknowns - rank_c
    if null_dim <= 0:
        raise ValueError('continuity constraints have no feasible solution')
    N = Vt[rank_c:].T

    XN = X @ N
    z, _, rank_z, _ = np.linalg.lstsq(XN, y, rcond=None)
    if rank_z < null_dim:
        raise ValueError(
            'insufficient independent data to fit all intervals '
            '(rank deficiency in the reduced system)'
        )

    c = N @ z  # scaled coefficients, length 7 * n_intervals

    # Map scaled coefficients back to the standard NASA-7 basis per interval.
    a_coeffs: list[list[float]] = []
    for k in range(n_intervals):
        ck = c[7 * k : 7 * k + 7]
        Sk = float(scales[k])
        a_coeffs.append(
            [
                float(ck[0]) * Sk**2,
                float(ck[1]) * Sk,
                float(ck[2]),
                float(ck[3]) / Sk,
                float(ck[4]) / Sk**2,
                float(ck[5]) / Sk**3,
                float(ck[6]) / Sk**4,
            ]
        )

    # Integration constants: anchor at the interval containing t_ref, then
    # propagate so H° (and S°, when s_ref is given) are continuous.
    anchor = int(np.searchsorted(bps, t_ref, side='left'))
    b1 = [0.0] * n_intervals
    b2 = [0.0] * n_intervals

    b1[anchor] = h_ref / r_ref - t_ref * _h_poly(a_coeffs[anchor], t_ref)
    if s_ref is not None:
        b2[anchor] = s_ref / r_ref - _s_poly(a_coeffs[anchor], t_ref)

    for k in range(anchor, n_intervals - 1):
        Tb = float(bps[k])
        b1[k + 1] = b1[k] + Tb * (
            _h_poly(a_coeffs[k], Tb) - _h_poly(a_coeffs[k + 1], Tb)
        )
        if s_ref is not None:
            b2[k + 1] = b2[k] + (
                _s_poly(a_coeffs[k], Tb) - _s_poly(a_coeffs[k + 1], Tb)
            )

    for k in range(anchor, 0, -1):
        Tb = float(bps[k - 1])
        b1[k - 1] = b1[k] + Tb * (
            _h_poly(a_coeffs[k], Tb) - _h_poly(a_coeffs[k - 1], Tb)
        )
        if s_ref is not None:
            b2[k - 1] = b2[k] + (
                _s_poly(a_coeffs[k], Tb) - _s_poly(a_coeffs[k - 1], Tb)
            )

    return tuple(
        NASACoefficients(
            a1=a[0],
            a2=a[1],
            a3=a[2],
            a4=a[3],
            a5=a[4],
            a6=a[5],
            a7=a[6],
            b1=b1[k],
            b2=b2[k],
        )
        for k, a in enumerate(a_coeffs)
    )
