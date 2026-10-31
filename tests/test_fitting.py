"""Tests for NASA-7 polynomial fitting (fit_nasa7)."""

import numpy as np
import pytest

from pyglenn import R_GLENN, NASACoefficients, ThermoDBQuery, fit_nasa7

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
