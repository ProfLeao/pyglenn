#!/usr/bin/env python3
"""
Thermochemical properties calculator.

Computes Cp(T), H°(T), S°(T) from NASA polynomial coefficients
stored in a SQLite database.

All values returned as floats in standard units:
  Cp, S°  → J/(mol·K)
  H°      → J/mol
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from importlib import resources
from typing import Any

from .database import R_UNIVERSAL, ThermoDBQuery
from .models import IntervalData, SpeciesInfo, ThermoProperties

logger = logging.getLogger(__name__)


class ThermoCalcError(Exception):
    """Base exception for thermochemical calculation errors."""

    pass


class DatabaseNotConnectedError(ThermoCalcError):
    """Raised when attempting calculation without a database connection."""

    pass


class SpeciesNotFoundError(ThermoCalcError):
    """Raised when a species ID is not found in the database."""

    def __init__(self, species_id: int) -> None:
        self.species_id = species_id
        super().__init__(f'Species ID {species_id} not found in database')


class TemperatureOutOfRangeError(ThermoCalcError):
    """Raised when the requested temperature is outside valid intervals.

    Carries the requested temperature, the species name, and the overall
    valid temperature bounds (when known).
    """

    def __init__(
        self,
        temperature: float,
        species_name: str | None = None,
        temp_bounds: tuple[float, float] | None = None,
    ) -> None:
        self.temperature = temperature
        self.species_name = species_name
        self.temp_bounds = temp_bounds
        message = f'Temperature {temperature:.1f} K out of valid range'
        if species_name:
            message += f" for species '{species_name}'"
        if temp_bounds is not None:
            message += f' (valid range: {temp_bounds[0]:.1f}-{temp_bounds[1]:.1f} K)'
        super().__init__(message)


class ThermochemicalCalculator:
    """High-level interface for calculating thermochemical properties.

    Uses the bundled ``thermo.db`` by default — no manual build step needed.

    Supports context-manager protocol for automatic connection management::

        with ThermochemicalCalculator() as calc:
            props = calc.calculate_properties(species_id, 1000.0)
    """

    def __init__(self, db_file: str | None = None) -> None:
        if db_file is None:
            # Use the bundled thermo.db shipped with the package
            db_path = resources.files('pyglenn.data') / 'thermo.db'
            db_file = str(db_path)
        self.db: ThermoDBQuery = ThermoDBQuery(db_file)
        self._connected: bool = False
        self.r_ref: float = R_UNIVERSAL

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------
    def __enter__(self) -> ThermochemicalCalculator:
        """Enter context manager — connects to database."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit context manager — closes database connection."""
        self.close()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """Whether the calculator is connected to the database."""
        return self._connected

    def connect(self) -> bool:
        """Connect to the database.

        Returns:
            True if connection succeeded, False otherwise.
        """
        if self.db.connect():
            self.r_ref = self.db.get_gas_constant_ref()
            self._connected = True
            return True
        return False

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()
        self._connected = False
        self.r_ref = R_UNIVERSAL

    # ------------------------------------------------------------------
    # Species lookup
    # ------------------------------------------------------------------
    def get_available_species(
        self, search_pattern: str = '', exact_match: bool = False
    ) -> list[SpeciesInfo]:
        """
        Return a list of available species, optionally filtered by name.

        Args:
            search_pattern: Optional substring to filter species names.
            exact_match: If True, use case-insensitive exact match
                         (e.g. ``'N2'`` returns only N2, not Be3N2).
                         Defaults to False (substring search) for
                         backward compatibility.

        Returns:
            List of SpeciesInfo with id, name, phase, molecular_weight.
        """
        if not self._connected:
            logger.warning('get_available_species called without connection')
            return []

        if search_pattern:
            return self.db.find_species(search_pattern, exact_match=exact_match)

        return self.db.list_all_species()

    # ------------------------------------------------------------------
    # Core calculations
    # ------------------------------------------------------------------
    def calculate_properties(
        self, species_id: int, temperature: float
    ) -> ThermoProperties:
        """
        Calculate thermochemical properties at a given temperature.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            ThermoProperties with temperature, cp, h_relative, s,
            temp_interval, species_name, and phase. ``h_relative`` is the
            absolute H°(T) (NASA-7 convention): H°(298.15 K) equals the
            standard enthalpy of formation.

        Raises:
            DatabaseNotConnectedError: If not connected to database.
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If temperature is outside all
                valid intervals for the species.
        """
        if not self._connected:
            raise DatabaseNotConnectedError(
                'calculate_properties called without database connection'
            )

        species_info = self.db.get_species_info(species_id)
        if species_info is None:
            raise SpeciesNotFoundError(species_id)

        interval_data = self.db.get_species_for_temperature(species_id, temperature)
        if interval_data is None:
            bounds = self.db.get_temperature_bounds(species_id)
            raise TemperatureOutOfRangeError(temperature, species_info.name, bounds)

        coeffs = interval_data.coefficients

        # Dimensionless properties (÷ R)
        cp_r = self.db.calculate_cp(coeffs, temperature)
        h_rt = self.db.calculate_h(coeffs, temperature)
        s_r = self.db.calculate_s(coeffs, temperature)

        # Convert to absolute units
        cp = cp_r * self.r_ref  # J/(mol·K)
        h_relative = h_rt * self.r_ref * temperature  # J/mol
        s = s_r * self.r_ref  # J/(mol·K)

        return ThermoProperties(
            temperature=temperature,
            cp=cp,
            h_relative=h_relative,
            s=s,
            temp_interval=(interval_data.temp_min, interval_data.temp_max),
            species_name=species_info.name,
            phase=species_info.phase,
        )

    def calculate_formation_enthalpy(self, species_id: int) -> float | None:
        """
        Get enthalpy of formation at 298.15 K in J/mol.

        Args:
            species_id: Database ID of the species.

        Returns:
            Enthalpy of formation in J/mol, or None if not available.
        """
        if not self._connected:
            logger.warning('calculate_formation_enthalpy called without connection')
            return None

        species_info = self.db.get_species_info(species_id)
        if species_info is None:
            return None

        return species_info.heat_of_formation_298K

    def calculate_enthalpy_change(
        self, species_id: int, T1: float, T2: float
    ) -> float | None:
        """
        Calculate ΔH°(T₂) − ΔH°(T₁) in J/mol.

        Uses absolute H°(T) values (NASA-7 convention). The NASA-7
        polynomials are continuous across interval boundaries, so T1 and T2
        may lie in different intervals.

        Args:
            species_id: Database ID of the species.
            T1: Initial temperature in Kelvin.
            T2: Final temperature in Kelvin.

        Returns:
            Enthalpy change in J/mol.

        Raises:
            DatabaseNotConnectedError: If not connected to database.
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If either T1 or T2 is outside
                valid intervals.
        """
        if not self._connected:
            logger.warning('calculate_enthalpy_change called without connection')
            return None

        props_t1 = self.calculate_properties(species_id, T1)
        props_t2 = self.calculate_properties(species_id, T2)

        return float(props_t2.h_relative - props_t1.h_relative)

    def h_sensible_to(
        self, species_id: int, temperature: float, t_ref: float = 298.15
    ) -> float | None:
        """Sensible enthalpy H°(T) − H°(t_ref) in J/mol.

        Convenience alias of :meth:`calculate_enthalpy_change` with a readable
        name and a default reference temperature of 298.15 K. Because the
        NASA-7 polynomials are continuous across interval boundaries,
        ``temperature`` and ``t_ref`` may lie in different intervals.

        Args:
            species_id: Database ID of the species.
            temperature: Final temperature in Kelvin.
            t_ref: Reference temperature in Kelvin (default 298.15).

        Returns:
            Sensible enthalpy change in J/mol, or None if not connected.

        Raises:
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If ``temperature`` or ``t_ref`` is
                outside the valid intervals.
        """
        return self.calculate_enthalpy_change(species_id, t_ref, temperature)

    def get_properties_range(
        self, species_id: int, temps: list[float]
    ) -> dict[float, ThermoProperties] | None:
        """
        Calculate properties at multiple temperatures.

        Args:
            species_id: Database ID of the species.
            temps: List of temperatures in Kelvin.

        Returns:
            Dict mapping temperature → ThermoProperties, or None if all fail.
        """
        if not self._connected:
            logger.warning('get_properties_range called without connection')
            return None

        results: dict[float, ThermoProperties] = {}
        for temp in temps:
            try:
                props = self.calculate_properties(species_id, temp)
                results[temp] = props
            except TemperatureOutOfRangeError:
                pass  # skip temperatures outside valid range

        return results if results else None

    def calculate_properties_range(
        self,
        species_id: int,
        temps: Sequence[float],
        *,
        strict: bool = False,
    ) -> list[ThermoProperties]:
        """Calculate properties for many temperatures, loading data once.

        Unlike :meth:`get_properties_range`, this loads the species intervals
        a single time and evaluates all temperatures in memory, preserving
        input order.

        Args:
            species_id: Database ID of the species.
            temps: Sequence of temperatures in Kelvin.
            strict: If True, raise on an out-of-range temperature.
                    If False (default), out-of-range values are skipped.

        Returns:
            Ordered list of ThermoProperties.

        Raises:
            DatabaseNotConnectedError: If not connected to database.
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If ``strict`` and a temperature is
                outside the valid intervals.
        """
        if not self._connected:
            raise DatabaseNotConnectedError(
                'calculate_properties_range called without database connection'
            )

        species_info = self.db.get_species_info(species_id)
        if species_info is None:
            raise SpeciesNotFoundError(species_id)

        species_data = self.db.get_species_data(species_id)
        if species_data is None:
            raise SpeciesNotFoundError(species_id)

        intervals = species_data.intervals
        bounds = ThermochemicalCalculator._overall_bounds(intervals)

        results: list[ThermoProperties] = []
        for temp in temps:
            interval = ThermochemicalCalculator._select_interval(intervals, temp)
            if interval is None:
                if strict:
                    raise TemperatureOutOfRangeError(temp, species_info.name, bounds)
                continue

            coeffs = interval.coefficients
            cp_r = self.db.calculate_cp(coeffs, temp)
            h_rt = self.db.calculate_h(coeffs, temp)
            s_r = self.db.calculate_s(coeffs, temp)

            results.append(
                ThermoProperties(
                    temperature=temp,
                    cp=cp_r * self.r_ref,
                    h_relative=h_rt * self.r_ref * temp,
                    s=s_r * self.r_ref,
                    temp_interval=(interval.temp_min, interval.temp_max),
                    species_name=species_info.name,
                    phase=species_info.phase,
                )
            )
        return results

    def dcp_dt(self, species_id: int, temperature: float) -> float:
        """Derivative of Cp with respect to temperature, in J/(mol·K²).

        Analytical derivative of the NASA-7 Cp polynomial (Equation 1),
        denormalized with the dataset reference gas constant.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            dCp/dT in J/(mol·K²).

        Raises:
            DatabaseNotConnectedError: If not connected to database.
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If temperature is outside all
                valid intervals for the species.
        """
        if not self._connected:
            raise DatabaseNotConnectedError(
                'dcp_dt called without database connection'
            )

        species_info = self.db.get_species_info(species_id)
        if species_info is None:
            raise SpeciesNotFoundError(species_id)

        interval = self.db.get_species_for_temperature(species_id, temperature)
        if interval is None:
            bounds = self.db.get_temperature_bounds(species_id)
            raise TemperatureOutOfRangeError(temperature, species_info.name, bounds)

        a = interval.coefficients
        T = temperature
        dcp_r_dt = (
            -2 * a.a1 / T**3
            - a.a2 / T**2
            + a.a4
            + 2 * a.a5 * T
            + 3 * a.a6 * T**2
            + 4 * a.a7 * T**3
        )
        return dcp_r_dt * self.r_ref

    def gamma(self, species_id: int, temperature: float) -> float:
        """Specific heat ratio Cp/Cv, assuming an ideal gas.

        For an ideal gas Cv = Cp - R, so gamma = Cp / (Cp - r_ref), where
        ``r_ref`` is the dataset reference gas constant.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless ratio Cp/Cv.

        Raises:
            DatabaseNotConnectedError: If not connected to database.
            SpeciesNotFoundError: If species_id is not in the database.
            TemperatureOutOfRangeError: If temperature is outside all
                valid intervals for the species.
        """
        if not self._connected:
            raise DatabaseNotConnectedError(
                'gamma called without database connection'
            )

        species_info = self.db.get_species_info(species_id)
        if species_info is None:
            raise SpeciesNotFoundError(species_id)

        interval = self.db.get_species_for_temperature(species_id, temperature)
        if interval is None:
            bounds = self.db.get_temperature_bounds(species_id)
            raise TemperatureOutOfRangeError(temperature, species_info.name, bounds)

        cp_r = self.db.calculate_cp(interval.coefficients, temperature)
        cp = cp_r * self.r_ref
        return cp / (cp - self.r_ref)

    @staticmethod
    def _select_interval(
        intervals: tuple[IntervalData, ...], temperature: float
    ) -> IntervalData | None:
        """Return the first interval covering ``temperature``, or None."""
        for interval in intervals:
            if interval.temp_min <= temperature <= interval.temp_max + 1e-9:
                return interval
        return None

    @staticmethod
    def _overall_bounds(
        intervals: tuple[IntervalData, ...],
    ) -> tuple[float, float] | None:
        """Return the overall [min, max] temperature covered by intervals."""
        if not intervals:
            return None
        return (
            min(interval.temp_min for interval in intervals),
            max(interval.temp_max for interval in intervals),
        )
