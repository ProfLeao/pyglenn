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
from importlib import resources
from typing import Any

from .database import R_UNIVERSAL, ThermoDBQuery
from .models import SpeciesInfo, ThermoProperties

logger = logging.getLogger(__name__)


class ThermoCalcError(Exception):
    """Base exception for thermochemical calculation errors."""

    pass


class DatabaseNotConnectedError(ThermoCalcError):
    """Raised when attempting calculation without a database connection."""

    pass


class SpeciesNotFoundError(ThermoCalcError):
    """Raised when a species ID is not found in the database."""

    pass


class TemperatureOutOfRangeError(ThermoCalcError):
    """Raised when the requested temperature is outside valid intervals."""

    pass


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
            temp_interval, species_name, and phase.

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
            raise SpeciesNotFoundError(
                f'Species ID {species_id} not found in database'
            )

        interval_data = self.db.get_species_for_temperature(
            species_id, temperature
        )
        if interval_data is None:
            raise TemperatureOutOfRangeError(
                f'Temperature {temperature:.1f} K out of valid range '
                f"for species '{species_info.name}'"
            )

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

        Uses H°(T) values relative to 0 K.

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
