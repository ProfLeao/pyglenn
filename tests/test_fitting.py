"""Tests for NASA-7 polynomial fitting (fit_nasa7)."""

import numpy as np
import pytest

from pyglenn import R_GLENN, NASACoefficients, ThermoDBQuery, fit_nasa7, fit_nasa7_multi

# Real O2 NASA-7 coefficients (low-temperature interval, from the bundled
# thermo.db) used as the "true" polynomial to be recovered.
TRUE = NASACoefficients(
    a1=-34255.6342,
    a2=484.700097,
    a3=1.119010961,
    a4=0.00429388924,
    a5=-6.83630052e-07,
    a6=-2.0233727e-09,
    a7=1.039040018e-12,
    b1=-3391.45487,
    b2=18.4969947,
)


def _cp(coeffs: NASACoefficients, T: float) -> float:
    return ThermoDBQuery.calculate_cp(coeffs, T) * R_GLENN


def _h(coeffs: NASACoefficients, T: float) -> float:
    return ThermoDBQuery.calculate_h(coeffs, T) * R_GLENN * T


def _s(coeffs: NASACoefficients, T: float) -> float:
    return ThermoDBQuery.calculate_s(coeffs, T) * R_GLENN


def test_fit_nasa7_reproduces_synthetic_cp() -> None:
    """A synthetic NASA-7 polynomial is reproduced to < 1e-6 relative."""
    T = np.linspace(200.0, 1000.0, 50)
    cp = np.array([_cp(TRUE, t) for t in T])

    fitted = fit_nasa7(T, cp, t_ref=298.15, h_ref=_h(TRUE, 298.15))

    cp_fit = np.array([_cp(fitted, t) for t in T])
    assert np.allclose(cp_fit, cp, rtol=1e-6, atol=0.0)


def test_fit_nasa7_recovers_coefficients() -> None:
    """On a well-conditioned range the coefficients are recovered closely."""
    T = np.linspace(200.0, 1000.0, 60)
    cp = np.array([_cp(TRUE, t) for t in T])

    fitted = fit_nasa7(T, cp, t_ref=298.15, h_ref=_h(TRUE, 298.15))

    for name in ('a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7'):
        assert getattr(fitted, name) == pytest.approx(
            getattr(TRUE, name), rel=1e-6, abs=1e-12
        )


def test_fit_nasa7_enthalpy_anchor() -> None:
    """H°(t_ref) equals h_ref by construction (b1, not a6)."""
    T = np.linspace(300.0, 3000.0, 100)
    cp = np.array([_cp(TRUE, t) for t in T])
    h_ref = _h(TRUE, 298.15)

    fitted = fit_nasa7(T, cp, t_ref=298.15, h_ref=h_ref)

    assert _h(fitted, 298.15) == pytest.approx(h_ref, rel=1e-9, abs=1e-6)


def test_fit_nasa7_entropy_anchor() -> None:
    """S°(t_ref) equals s_ref when provided; b2 = 0.0 otherwise."""
    T = np.linspace(300.0, 3000.0, 100)
    cp = np.array([_cp(TRUE, t) for t in T])
    h_ref = _h(TRUE, 298.15)
    s_ref = _s(TRUE, 298.15)

    fitted = fit_nasa7(T, cp, t_ref=298.15, h_ref=h_ref, s_ref=s_ref)
    assert _s(fitted, 298.15) == pytest.approx(s_ref, rel=1e-9, abs=1e-6)

    fitted_no_s = fit_nasa7(T, cp, t_ref=298.15, h_ref=h_ref)
    assert fitted_no_s.b2 == 0.0


def test_fit_nasa7_uniform_weights_equal_unweighted() -> None:
    """Explicit uniform weights match the default unweighted fit."""
    T = np.linspace(200.0, 1000.0, 40)
    cp = np.array([_cp(TRUE, t) for t in T])

    unweighted = fit_nasa7(T, cp, t_ref=298.15, h_ref=_h(TRUE, 298.15))
    weighted = fit_nasa7(
        T,
        cp,
        t_ref=298.15,
        h_ref=_h(TRUE, 298.15),
        weights=np.ones_like(T),
    )

    for name in ('a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'b1', 'b2'):
        assert getattr(weighted, name) == pytest.approx(
            getattr(unweighted, name), rel=1e-9, abs=1e-12
        )


def test_fit_nasa7_too_few_points() -> None:
    """Fewer than 7 points raise ValueError."""
    with pytest.raises(ValueError, match='at least 7'):
        fit_nasa7([200.0, 400.0, 600.0], [1.0, 2.0, 3.0])


def test_fit_nasa7_length_mismatch() -> None:
    """Temperatures and cp_values of different lengths raise ValueError."""
    T = np.linspace(200.0, 1000.0, 8)
    cp = np.ones(9)
    with pytest.raises(ValueError, match='same length'):
        fit_nasa7(T, cp)


def test_fit_nasa7_nonpositive_temperature() -> None:
    """Non-positive temperatures raise ValueError."""
    T = [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0]
    cp = np.ones(8)
    with pytest.raises(ValueError, match='strictly positive'):
        fit_nasa7(T, cp)


def test_fit_nasa7_invalid_weights() -> None:
    """Negative or all-zero weights raise ValueError."""
    T = np.linspace(200.0, 1000.0, 8)
    cp = np.ones(8)

    with pytest.raises(ValueError, match='non-negative'):
        fit_nasa7(T, cp, weights=[1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 1.0, 1.0])

    with pytest.raises(ValueError, match='positive'):
        fit_nasa7(T, cp, weights=[0.0] * 8)


def test_fit_nasa7_duplicate_temperatures_rank_deficient() -> None:
    """Seven points but only two distinct temperatures raise ValueError."""
    T = [200.0] * 4 + [1000.0] * 3
    cp = np.ones(7)
    with pytest.raises(ValueError, match='rank-deficient'):
        fit_nasa7(T, cp)


def _dcp_dt(coeffs: NASACoefficients, T: float) -> float:
    """Analytical dCp/dT in J/(mol·K²)."""
    a = coeffs
    d = (
        -2 * a.a1 / T**3
        - a.a2 / T**2
        + a.a4
        + 2 * a.a5 * T
        + 3 * a.a6 * T**2
        + 4 * a.a7 * T**3
    )
    return d * R_GLENN


def test_fit_nasa7_multi_reproduces_single_polynomial() -> None:
    """Two intervals recover a single global polynomial over 200-6000 K."""
    T = np.linspace(200.0, 6000.0, 200)
    cp = np.array([_cp(TRUE, t) for t in T])

    coeffs = fit_nasa7_multi(T, cp, [1000.0], t_ref=298.15, h_ref=_h(TRUE, 298.15))
    assert len(coeffs) == 2

    cp_fit = np.array(
        [_cp(coeffs[0], t) if t <= 1000.0 else _cp(coeffs[1], t) for t in T]
    )
    assert np.allclose(cp_fit, cp, rtol=1e-6, atol=0.0)


def test_fit_nasa7_multi_cp_continuity() -> None:
    """Cp/R and d(Cp/R)/dT are continuous at the breakpoint."""
    T = np.linspace(200.0, 6000.0, 200)
    cp = np.array([_cp(TRUE, t) for t in T])

    c0, c1 = fit_nasa7_multi(T, cp, [1000.0], t_ref=298.15, h_ref=0.0)
    Tb = 1000.0
    assert _cp(c0, Tb) == pytest.approx(_cp(c1, Tb), rel=1e-9)
    assert _dcp_dt(c0, Tb) == pytest.approx(_dcp_dt(c1, Tb), rel=1e-9)


def test_fit_nasa7_multi_enthalpy_continuity_and_anchor() -> None:
    """H° is anchored at t_ref and continuous across the breakpoint."""
    T = np.linspace(200.0, 6000.0, 200)
    cp = np.array([_cp(TRUE, t) for t in T])
    h_ref = _h(TRUE, 298.15)

    c0, c1 = fit_nasa7_multi(T, cp, [1000.0], t_ref=298.15, h_ref=h_ref)

    # t_ref = 298.15 belongs to interval 0
    assert _h(c0, 298.15) == pytest.approx(h_ref, rel=1e-9, abs=1e-6)
    assert _h(c0, 1000.0) == pytest.approx(_h(c1, 1000.0), rel=1e-9, abs=1e-3)


def test_fit_nasa7_multi_entropy_anchor_and_continuity() -> None:
    """With s_ref, S° is anchored and continuous across the breakpoint."""
    T = np.linspace(200.0, 6000.0, 200)
    cp = np.array([_cp(TRUE, t) for t in T])
    h_ref = _h(TRUE, 298.15)
    s_ref = _s(TRUE, 298.15)

    c0, c1 = fit_nasa7_multi(T, cp, [1000.0], t_ref=298.15, h_ref=h_ref, s_ref=s_ref)

    assert _s(c0, 298.15) == pytest.approx(s_ref, rel=1e-9, abs=1e-6)
    assert _s(c0, 1000.0) == pytest.approx(_s(c1, 1000.0), rel=1e-9, abs=1e-6)


def test_fit_nasa7_multi_three_intervals() -> None:
    """Three intervals reproduce data with continuity at both breakpoints."""
    T = np.linspace(200.0, 6000.0, 300)
    cp = np.array([_cp(TRUE, t) for t in T])

    coeffs = fit_nasa7_multi(T, cp, [1000.0, 3000.0], t_ref=298.15, h_ref=0.0)
    assert len(coeffs) == 3
    for Tb in (1000.0, 3000.0):
        i = 0 if Tb <= 1000.0 else 1
        assert _cp(coeffs[i], Tb) == pytest.approx(_cp(coeffs[i + 1], Tb), rel=1e-9)


def test_fit_nasa7_multi_validation() -> None:
    """Invalid breakpoints or too few points per interval raise ValueError."""
    T = np.linspace(200.0, 6000.0, 200)
    cp = np.array([_cp(TRUE, t) for t in T])

    with pytest.raises(ValueError, match='inside'):
        fit_nasa7_multi(T, cp, [50.0])
    with pytest.raises(ValueError, match='increasing'):
        fit_nasa7_multi(T, cp, [3000.0, 1000.0])
    with pytest.raises(ValueError, match='at least 7'):
        fit_nasa7_multi(T[:10], cp[:10], [400.0])
