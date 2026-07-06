#!/usr/bin/env python3
# Quick test for O2 species

from thermochemical_calculator import ThermochemicalCalculator

calc = ThermochemicalCalculator()
calc.connect()

# Find O2 specifically
species_list = calc.get_available_species()
o2_species = [s for s in species_list if s['name'].strip() == 'O2']

if o2_species:
    print('Found O2 species:')
    species_id = o2_species[0]['id']
    print(f'ID: {species_id}')
    print()
    
    # Calculate at standard conditions
    temps = [298.15, 500, 1000]
    print('T (K)     Cp (J/mol·K)   H (J/mol)      S (J/mol·K)')
    print('='*60)
    for T in temps:
        props = calc.calculate_properties(species_id, T)
        if props:
            print(f'{T:8.2f}   {props["cp"]:12.3f}   {props["h_relative"]:12.1f}   {props["s"]:12.3f}')
else:
    print('O2 not found. Looking for similar species:')
    species_list = calc.get_available_species('O')
    for i, s in enumerate(species_list[:5]):
        print(f'  {s["name"]} (ID: {s["id"]})')

calc.close()
