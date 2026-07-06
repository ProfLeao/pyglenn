================================================================================
README - THERMOCHEMICAL CONVERSION PROJECT (thermo.inp → SQLite3)
================================================================================

OVERVIEW:
This project converts thermochemical data from FORTRAN format (thermo.inp)
into a normalized SQLite3 database, facilitating queries and analysis
of thermodynamic properties of chemical species.

================================================================================

PROJECT FILES:

1. referencia.pdf / referencia.txt
   - Documentation of Table C1 (original FORTRAN format)
   - Describes the logic of FORTRAN records for thermochemical data

2. logicofthermo.txt / logicofthermo.md
   - Summary in Portuguese/English of FORTRAN record logic
   - Explains structure: Records 1-5 and their meaning

3. thermo.inp
   - Original file with thermochemical data (FORTRAN format)
   - Contains ~2030 species and their polynomial coefficients

4. thermo_to_sqlite.py
   - Python script that converts thermo.inp to SQLite3
   - Uses robust parser to handle format variations
   - Creates normalized structure with 4 main tables

5. thermo.db
   - Generated SQLite3 database
   - 2030 species, 3772 temperature intervals
   - 3772 polynomial coefficient sets

6. query_thermo_db.py
   - Example script with queries and calculations
   - Demonstrates how to use the database for thermochemical analyses

7. DATABASE_DOCUMENTATION.txt
   - Complete SQLite3 schema documentation
   - Includes SQL query examples

8. conversion_log.txt
   - Conversion execution log

================================================================================

DATABASE STRUCTURE:

   ┌─────────────────┐
   │ file_metadata   │ (file metadata)
   └─────────────────┘
           ↓
   ┌─────────────────┐
   │    species      │ (2030 chemical species)
   │  (id, name...)  │
   └─────────────────┘
           ↓
   ┌────────────────────────────┐
   │ temperature_intervals      │ (3772 intervals)
   │ (species_id, temp_min/max) │
   └────────────────────────────┘
           ↓
   ┌──────────────────────────────┐
   │    coefficients              │ (3772 sets)
   │ (a1-a7, b1, b2 coefficients) │
   └──────────────────────────────┘

================================================================================

HOW TO USE:

1. CONVERT FILE (if necessary):
   $ python thermo_to_sqlite.py
   
   Result:
   - Creates/updates thermo.db file
   - Log: conversion_log.txt

2. QUERY DATABASE:
   $ python query_thermo_db.py
   
   Examples executed:
   - General statistics
   - Species search
   - Thermochemical calculations (Cp, H°, S°)
   - Data pagination

3. DIRECT SQL QUERIES:
   $ sqlite3 thermo.db
   
   Examples:
   .mode column
   SELECT * FROM species LIMIT 5;
   SELECT s.name, ti.temp_min, ti.temp_max 
     FROM species s JOIN temperature_intervals ti ON s.id=ti.species_id 
     WHERE s.name='O2';

================================================================================

DATA LOADED:

✓ Species: 2030
  - Gaseous: 1264
  - Condensed: 766
  
✓ Temperature Intervals: 3772
  - Global range: 200 K to 20000 K
  - Multiple intervals per species for better accuracy
  
✓ Polynomial Coefficients: 3772 sets
  - 7 coefficients (a1-a7) for Cp
  - 2 integration constants (b1, b2)

✓ Molecular Weight: ~3100 available data points
  - Range: 0.0005 to ~500 g/mol

================================================================================

AVAILABLE FEATURES:

1. Direct SQL queries to the database
2. Calculation of thermodynamic properties:
   - Cp(T)/R - Reduced heat capacity
   - H°(T)/RT - Reduced relative enthalpy
   - S°(T)/R - Reduced relative entropy
3. Species search by:
   - Exact or partial name
   - Chemical formula
   - Temperature range
   - Phase (gas/condensed)
4. Data analysis:
   - General statistics
   - Distribution by phase
   - Molecular weights

================================================================================

POLYNOMIAL EQUATIONS:

Data is stored as coefficients (a1-a7, b1-b2) that reproduce
the following equations in specific temperature intervals:

Cp(T)/R = a1·T⁻² + a2·T⁻¹ + a3 + a4·T + a5·T² + a6·T³ + a7·T⁴

H°(T)/RT = -a1·T⁻² + a2·ln(T) + a3 + a4·T/2 + a5·T²/3 + 
           a6·T³/4 + a7·T⁴/5 + b1/T

S°(T)/R = -a1·T⁻²/2 - a2·T⁻¹ + a3·ln(T) + a4·T + a5·T²/2 + 
          a6·T³/3 + a7·T⁴/4 + b2

================================================================================

EXAMPLE PROGRAMMATIC USE (Python):

from query_thermo_db import ThermoDBQuery

# Connect to database
db = ThermoDBQuery('thermo.db')
db.connect()

# Search for species
species = db.find_species('O2')
print(species[0]['name'])  # O2

# Get species data
data = db.get_species_data(species[0]['id'])

# Calculate Cp at 1000 K
coeffs = data['intervals'][0]['coefficients']
cp_r = db.calculate_cp(coeffs, 1000)
print(f"Cp(1000K)/R = {cp_r}")

db.close()

================================================================================

ORIGINAL REFERENCES:

Source: NASA Polynomial Database
- Chase, M.W., et al. (1998). NIST-JANAF Thermochemical Tables
- Publication: NASA/TP—2002-211556
- Format: FORTRAN with structured records (Appendix C)

Data reference codes:
- g: Glenn Research Center
- j: NIST-JANAF Thermochemical Tables
- tpis: Thermodynamic Properties of Individual Substances
- n: TRC Thermodynamic Tables (NIST)
- bar: Barin Thermochemical Data
- coda: CODATA Key Values
- srd: Standard Reference Data

================================================================================

TECHNICAL NOTES:

1. Adapted FORTRAN Parser:
   - Recognizes D notation (e.g., 1.5D+03)
   - Identifies records by patterns (temperatures, coefficients)
   - Handles formatting variations

2. Data Normalization:
   - Separation of concerns (species, intervals, coefficients)
   - Referential integrity with FOREIGN KEY and CASCADE DELETE
   - Implicit indexes on PRIMARY KEYs

3. Validation:
   - Duplicate species avoided
   - Malformed data recorded but not loaded
   - Loading statistics available

================================================================================

SUGGESTED NEXT STEPS:

1. Create additional indexes for better performance:
   CREATE INDEX idx_species_name ON species(name);
   CREATE INDEX idx_intervals_species ON temperature_intervals(species_id);

2. Export data in other formats (JSON, CSV, HDF5)

3. Develop web interface for interactive queries

4. Implement more complex thermodynamic calculations:
   - Chemical reactions
   - Thermodynamic equilibrium
   - Phase diagrams

5. Add support for other thermochemical databases

================================================================================

SUPPORT AND DOCUMENTATION:

- DATABASE_DOCUMENTATION.txt: Complete schema and SQL examples
- logicofthermo.txt: Detailed explanation of original format
- query_thermo_db.py: Practical usage examples
- conversion_log.txt: History of last conversion

================================================================================

CREATION DATE: 2026-07-04
VERSION: 1.0
AUTHOR: Automated Thermochemical Data Conversion System

================================================================================
