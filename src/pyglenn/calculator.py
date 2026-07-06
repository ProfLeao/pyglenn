#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thermochemical properties calculator.

Computes Cp(T), H°(T), S°(T) from NASA polynomial coefficients
stored in a SQLite database.

All values returned as floats in standard units:
  Cp, S°  → J/(mol·K)
  H°      → J/mol
"""

from typing import Dict, Optional, Tuple

from .database import ThermoDBQuery, R


class ThermochemicalCalculator:
    """High-level interface for calculating thermochemical properties."""

    def __init__(self, db_file: str = 'thermo.db'):
        self.db = ThermoDBQuery(db_file)
        self.connected = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        """Connect to the database."""
        if self.db.connect():
            self.connected = True
            return True
        return False

    def close(self):
        """Close the database connection."""
        self.db.close()
        self.connected = False

    # ------------------------------------------------------------------
    # Species lookup
    # ------------------------------------------------------------------
    def get_available_species(self, search_pattern: str = '') -> list:
        """
        Return a list of available species, optionally filtered by name.

        Args:
            search_pattern: Optional substring to filter species names.

        Returns:
            List of species dicts with id, name, phase, molecular_weight.
        """
        if not self.connected:
            return []

        if search_pattern:
            return self.db.find_species(search_pattern)

        # Paginate through all species
        species_list = []
        page = 1
        while True:
            species_page, total_pages = self.db.list_species_page(
                page=page, page_size=100
            )
            if not species_page:
                break
            species_list.extend(species_page)
            if page >= total_pages:
                break
            page += 1
        return species_list

    # ------------------------------------------------------------------
    # Core calculations
    # ------------------------------------------------------------------
    def calculate_properties(
        self, species_id: int, temperature: float
    ) -> Optional[Dict[str, float]]:
        """
        Calculate thermochemical properties at a given temperature.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            Dictionary with keys:
              - temperature:   Input temperature (K)
              - cp:            Heat capacity in J/(mol·K)
              - h_relative:    Enthalpy relative to 0 K in J/mol
              - s:             Absolute entropy in J/(mol·K)
              - temp_interval: [T_min, T_max]
              - species_name:  Species name
              - phase:         Phase ('gas' or 'condensed')
            Or None if calculation fails.
        """
        if not self.connected:
            print("Error: Database not connected")
            return None

        species_data = self.db.get_species_data(species_id)
        if not species_data or 'intervals' not in species_data:
            print(f"Error: Species ID {species_id} not found")
            return None

        interval_data = self.db.get_species_for_temperature(
            species_id, temperature
        )
        if not interval_data:
            print(
                f"Error: Temperature {temperature} K is out of valid "
                f"range for species {species_data['name']}"
            )
            print(
                f"Available intervals: "
                f"{[(i['temp_min'], i['temp_max']) for i in species_data['intervals']]}"
            )
            return None

        coeffs = interval_data['coefficients']

        # Dimensionless properties (÷ R)
        cp_r = self.db.calculate_cp(coeffs, temperature)
        h_rt = self.db.calculate_h(coeffs, temperature)
        s_r = self.db.calculate_s(coeffs, temperature)

        # Convert to absolute units
        cp = cp_r * R  # J/(mol·K)
        h_relative = h_rt * R * temperature  # J/mol
        s = s_r * R  # J/(mol·K)

        return {
            'temperature': temperature,
            'cp': cp,
            'h_relative': h_relative,
            's': s,
            'temp_interval': [
                interval_data['temp_min'],
                interval_data['temp_max'],
            ],
            'species_name': species_data['name'],
            'phase': species_data['phase'],
        }

    def calculate_formation_enthalpy(
        self, species_id: int
    ) -> Optional[float]:
        """
        Get enthalpy of formation at 298.15 K in J/mol.

        Args:
            species_id: Database ID of the species.

        Returns:
            Enthalpy of formation in J/mol, or None if not available.
        """
        if not self.connected:
            print("Error: Database not connected")
            return None

        species_data = self.db.get_species_data(species_id)
        if not species_data:
            return None

        return species_data.get('heat_of_formation_298K')

    def calculate_enthalpy_change(
        self, species_id: int, T1: float, T2: float
    ) -> Optional[float]:
        """
        Calculate ΔH°(T₂) − ΔH°(T₁) in J/mol.

        Uses H°(T) values relative to 0 K.

        Args:
            species_id: Database ID of the species.
            T1: Initial temperature in Kelvin.
            T2: Final temperature in Kelvin.

        Returns:
            Enthalpy change in J/mol, or None if calculation fails.
        """
        if not self.connected:
            print("Error: Database not connected")
            return None

        props_t1 = self.calculate_properties(species_id, T1)
        props_t2 = self.calculate_properties(species_id, T2)

        if not props_t1 or not props_t2:
            return None

        return props_t2['h_relative'] - props_t1['h_relative']

    def get_properties_range(
        self, species_id: int, temps: list
    ) -> Optional[Dict[float, Dict[str, float]]]:
        """
        Calculate properties at multiple temperatures.

        Args:
            species_id: Database ID of the species.
            temps: List of temperatures in Kelvin.

        Returns:
            Dict mapping temperature → property dict, or None if all fail.
        """
        if not self.connected:
            print("Error: Database not connected")
            return None

        results = {}
        for temp in temps:
            props = self.calculate_properties(species_id, temp)
            if props:
                results[temp] = props

        return results if results else None
