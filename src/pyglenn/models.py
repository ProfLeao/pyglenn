"""Typed domain model for pyglenn thermochemical results.

These frozen dataclasses replace plain ``dict`` returns. They are converted at
the SQLite boundary via the ``from_mapping`` constructors and serialised back
with :func:`dataclasses.asdict` (or the ``to_dict`` convenience method).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class NASACoefficients:
    """The nine NASA-7 polynomial coefficients (dimensionless)."""

    a1: float
    a2: float
    a3: float
    a4: float
    a5: float
    a6: float
    a7: float
    b1: float
    b2: float

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> NASACoefficients:
        """Build from a mapping keyed by ``a1``..``a7``, ``b1``, ``b2``."""
        keys = ('a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'b1', 'b2')
        return cls(*(float(mapping[k]) for k in keys))

    def to_dict(self) -> dict[str, float]:
        """Return the coefficients as a plain dict."""
        return asdict(self)


@dataclass(frozen=True)
class SpeciesInfo:
    """Basic metadata for a single species (no interval or coefficient data)."""

    id: int
    name: str
    formula: str | None = None
    phase: str | None = None
    molecular_weight: float | None = None
    heat_of_formation_298K: float | None = None
    num_intervals: int | None = None
    comments: str | None = None
    reference_code: str | None = None

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> SpeciesInfo:
        """Build from a ``dict`` or ``sqlite3.Row``, tolerating missing keys."""

        def _get(key: str) -> Any:
            try:
                return mapping[key]  # type: ignore[index]
            except (KeyError, IndexError):
                return None

        return cls(
            id=_get('id'),
            name=_get('name'),
            formula=_get('formula'),
            phase=_get('phase'),
            molecular_weight=_get('molecular_weight'),
            heat_of_formation_298K=_get('heat_of_formation_298K'),
            num_intervals=_get('num_intervals'),
            comments=_get('comments'),
            reference_code=_get('reference_code'),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the species metadata as a plain dict."""
        return asdict(self)


@dataclass(frozen=True)
class IntervalData:
    """A single temperature interval with its NASA-7 coefficients."""

    interval_number: int
    temp_min: float
    temp_max: float
    h_298_to_0: float | None
    coefficients: NASACoefficients

    def to_dict(self) -> dict[str, Any]:
        """Return the interval as a plain dict (nested coefficients included)."""
        return asdict(self)


@dataclass(frozen=True)
class ThermoProperties:
    """Thermochemical properties at a single temperature.

    ``cp`` and ``s`` are in J/(mol·K); ``h_relative`` is the absolute
    enthalpy H°(T) in J/mol (NASA-7 convention), where
    H°(298.15 K) = ΔH°f(298.15 K).
    """

    temperature: float
    cp: float
    h_relative: float
    s: float
    temp_interval: tuple[float, float]
    species_name: str
    phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the properties as a plain dict (tuple serialised as list)."""
        return {
            'temperature': self.temperature,
            'cp': self.cp,
            'h_relative': self.h_relative,
            's': self.s,
            'temp_interval': list(self.temp_interval),
            'species_name': self.species_name,
            'phase': self.phase,
        }


@dataclass(frozen=True)
class SpeciesData:
    """Complete species record including all intervals and coefficients."""

    id: int
    name: str
    formula: str | None = None
    phase: str | None = None
    molecular_weight: float | None = None
    heat_of_formation_298K: float | None = None
    num_intervals: int | None = None
    comments: str | None = None
    reference_code: str | None = None
    intervals: tuple[IntervalData, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the complete record as a plain dict with an ``intervals`` key."""
        data = asdict(self)
        data['intervals'] = [IntervalData.to_dict(i) for i in self.intervals]
        return data


@dataclass(frozen=True)
class DatabaseStats:
    """Aggregate database statistics."""

    total_species: int
    total_intervals: int
    total_coeff_sets: int
    species_by_phase: Mapping[str, int]
    avg_molecular_weight: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the statistics as a plain dict."""
        return asdict(self)
