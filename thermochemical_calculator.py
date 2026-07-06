#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thermochemical properties calculator interface
Computes Cp(T), H°(T), S°(T) from database coefficients
Returns values as floats in standard units: J/(mol·K) for Cp and S°, J/mol for H°
"""

import math
from typing import Dict, Optional, Tuple
from query_thermo_db import ThermoDBQuery

# Physical constant: Gas constant
R = 8.314  # J/(mol·K)

class ThermochemicalCalculator:
    """Interface for calculating thermochemical properties"""
    
    def __init__(self, db_file: str = 'thermo.db'):
        self.db = ThermoDBQuery(db_file)
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to database"""
        if self.db.connect():
            self.connected = True
            return True
        return False
    
    def close(self):
        """Close database connection"""
        self.db.close()
        self.connected = False
    
    def get_available_species(self, search_pattern: str = '') -> list:
        """
        Get list of available species, optionally filtered by name pattern
        
        Args:
            search_pattern: Optional substring to filter species names
        
        Returns:
            List of species dictionaries with id, name, phase, molecular_weight
        """
        if not self.connected:
            return []
        
        if search_pattern:
            return self.db.find_species(search_pattern)
        else:
            # Get all species using pagination
            species_list = []
            page = 1
            while True:
                species_page, total_pages = self.db.list_species_page(page=page, page_size=100)
                if not species_page:
                    break
                species_list.extend(species_page)
                if page >= total_pages:
                    break
                page += 1
            return species_list
    
    def calculate_properties(self, species_id: int, temperature: float) -> Optional[Dict[str, float]]:
        """
        Calculate thermochemical properties at a given temperature
        
        Args:
            species_id: Database ID of the species
            temperature: Temperature in Kelvin
        
        Returns:
            Dictionary with keys:
                - 'temperature': Input temperature (K)
                - 'cp': Heat capacity in J/(mol·K)
                - 'h_relative': Enthalpy relative to 0K in J/mol
                - 's': Absolute entropy in J/(mol·K)
                - 'temp_interval': Temperature interval used [T_min, T_max]
            Or None if calculation fails
        """
        if not self.connected:
            print("Error: Database not connected")
            return None
        
        # Get species data and find appropriate temperature interval
        species_data = self.db.get_species_data(species_id)
        if not species_data or 'intervals' not in species_data:
            print(f"Error: Species ID {species_id} not found")
            return None
        
        # Find the correct interval for the given temperature
        interval_data = self.db.get_species_for_temperature(species_id, temperature)
        if not interval_data:
            print(f"Error: Temperature {temperature}K is out of valid range for species {species_data['name']}")
            print(f"Available intervals: {[(i['temp_min'], i['temp_max']) for i in species_data['intervals']]}")
            return None
        
        coeffs = interval_data['coefficients']
        
        # Calculate properties in relative units (divided by R)
        cp_r = self.db.calculate_cp(coeffs, temperature)
        h_rt = self.db.calculate_h(coeffs, temperature)
        s_r = self.db.calculate_s(coeffs, temperature)
        
        # Convert to absolute units
        cp = cp_r * R  # J/(mol·K)
        h_relative = h_rt * R * temperature  # J/mol
        s = s_r * R  # J/(mol·K)
        
        return {
            'temperature': temperature,
            'cp': cp,  # J/(mol·K)
            'h_relative': h_relative,  # J/mol (relative to 0K)
            's': s,  # J/(mol·K)
            'temp_interval': [interval_data['temp_min'], interval_data['temp_max']],
            'species_name': species_data['name'],
            'phase': species_data['phase']
        }
    
    def calculate_formation_enthalpy(self, species_id: int) -> Optional[float]:
        """
        Get enthalpy of formation at 298.15 K in J/mol
        
        Args:
            species_id: Database ID of the species
        
        Returns:
            Enthalpy of formation in J/mol or None if not available
        """
        if not self.connected:
            print("Error: Database not connected")
            return None
        
        species_data = self.db.get_species_data(species_id)
        if not species_data:
            return None
        
        h_f = species_data.get('heat_of_formation_298K')
        return h_f
    
    def calculate_enthalpy_change(self, species_id: int, T1: float, T2: float) -> Optional[float]:
        """
        Calculate enthalpy change ΔH°(T2) - ΔH°(T1) in J/mol
        Uses calculated H°(T) values relative to 0K
        
        Args:
            species_id: Database ID of the species
            T1: Initial temperature in Kelvin
            T2: Final temperature in Kelvin
        
        Returns:
            Enthalpy change in J/mol or None if calculation fails
        """
        if not self.connected:
            print("Error: Database not connected")
            return None
        
        props_t1 = self.calculate_properties(species_id, T1)
        props_t2 = self.calculate_properties(species_id, T2)
        
        if not props_t1 or not props_t2:
            return None
        
        delta_h = props_t2['h_relative'] - props_t1['h_relative']
        return delta_h
    
    def get_properties_range(self, species_id: int, temps: list) -> Optional[Dict[float, Dict[str, float]]]:
        """
        Calculate properties at multiple temperatures
        
        Args:
            species_id: Database ID of the species
            temps: List of temperatures in Kelvin
        
        Returns:
            Dictionary mapping temperature to property dictionary, or None if fails
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


def main():
    """Example usage"""
    print("="*70)
    print("THERMOCHEMICAL PROPERTIES CALCULATOR")
    print("="*70)
    
    calc = ThermochemicalCalculator()
    
    if not calc.connect():
        print("Error: Could not connect to database")
        return
    
    try:
        # 1. Find a species
        print("\n1. SEARCHING FOR SPECIES:")
        print("-" * 70)
        species_list = calc.get_available_species('O2')
        if not species_list:
            print("No species found")
            return
        
        print(f"Found {len(species_list)} species matching 'O2'")
        for sp in species_list[:3]:
            print(f"  ID: {sp['id']:3d} | Name: {sp['name']:20s} | Phase: {sp['phase']:10s}")
        
        # 2. Calculate properties for O2 at various temperatures
        print("\n2. CALCULATING PROPERTIES FOR O2:")
        print("-" * 70)
        
        species_id = species_list[0]['id']
        species_name = species_list[0]['name']
        
        temperatures = [298.15, 500, 1000, 1500]
        
        print(f"Species: {species_name}")
        print(f"{'Temperature (K)':>15} | {'Cp (J/mol·K)':>15} | {'H° (J/mol)':>15} | {'S° (J/mol·K)':>15}")
        print("-" * 70)
        
        for temp in temperatures:
            props = calc.calculate_properties(species_id, temp)
            if props:
                print(f"{props['temperature']:>15.2f} | {props['cp']:>15.3f} | {props['h_relative']:>15.1f} | {props['s']:>15.3f}")
            else:
                print(f"{temp:>15.2f} | ERROR: Temperature out of range")
        
        # 3. Get enthalpy of formation
        print("\n3. ENTHALPY OF FORMATION:")
        print("-" * 70)
        h_f = calc.calculate_formation_enthalpy(species_id)
        if h_f is not None:
            print(f"Species: {species_name}")
            print(f"H°_f(298.15 K) = {h_f:.1f} J/mol")
        else:
            print(f"No formation enthalpy data available")
        
        # 4. Calculate enthalpy change
        print("\n4. ENTHALPY CHANGE (ΔH° from 298.15K to 1000K):")
        print("-" * 70)
        delta_h = calc.calculate_enthalpy_change(species_id, 298.15, 1000)
        if delta_h is not None:
            print(f"Species: {species_name}")
            print(f"ΔH° = {delta_h:.1f} J/mol")
        else:
            print("Error calculating enthalpy change")
        
        # 5. Properties range
        print("\n5. PROPERTIES ACROSS TEMPERATURE RANGE:")
        print("-" * 70)
        props_range = calc.get_properties_range(species_id, [300, 500, 750, 1000, 1500])
        if props_range:
            print(f"Species: {species_name}")
            print(f"{'T (K)':>8} | {'Cp':>12} | {'H°':>12} | {'S°':>12}")
            for temp in sorted(props_range.keys()):
                props = props_range[temp]
                print(f"{temp:>8.0f} | {props['cp']:>12.2f} | {props['h_relative']:>12.1f} | {props['s']:>12.2f}")
        
        print("\n" + "="*70)
        print("[SUCCESS] Calculations completed successfully!")
        
    finally:
        calc.close()


if __name__ == "__main__":
    main()
