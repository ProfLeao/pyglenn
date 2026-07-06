LOGIC SUMMARY - TABLE C1: FORTRAN FORMAT USED FOR DATA IN APPENDIX D
================================================================================

OVERVIEW:
This table defines the structured format for storing thermodynamic data
in a data file (thermo.inp). The data is organized in "records", where
each record occupies specific columns with pre-defined FORTRAN formats.

================================================================================

RECORD STRUCTURE:

RECORD 1 - Species Identification
──────────────────────────────────
Purpose: Identify the substance/species and its data sources
  • Columns 1-16:   Species name or chemical formula (format A16)
  • Columns 19-80:  Comments and data sources (format A62)

RECORD 2 - General Information
──────────────────────────────────
Purpose: Define general data parameters
  • Columns 1-2:    Number of temperature intervals (I2)
  • Columns 4-9:    Reference date code (A6)
  • Columns 11-50:  Chemical formula in uppercase symbols and numbers (5(A2, F6.2))
  • Columns 51-52:  Phase indicator (0=gas; ≠0=condensed) (I2)
  • Columns 53-65:  Molecular weight (F13.7)
  • Columns 66-80:  Heat of formation at 298.15 K in J/mol (F15.5)

RECORD 3 - Temperature Interval Definition
────────────────────────────────────────────
Purpose: Specify the valid temperature range and coefficients
  • Columns 1-22:   Temperature range (2F11.3) - minimum and maximum temperature
  • Column 23:      Number of coefficients for Cp(T)/R = always 7 (I1)
  • Columns 24-63:  T exponents in empirical equation (always -2, -1, 0, 1, 2, 3, 4) (8F5.1)
  • Columns 66-80:  Ho(298.15) - Ho(0) in J/mol, if available (F15.3)

RECORD 4 - First Five Coefficients
───────────────────────────────────
Purpose: Store the first 5 coefficients a1, a2, a3, a4, a5
  • Columns 1-80:   Five coefficients in scientific notation (5D16.9)

RECORD 5 - Last Two Coefficients and Integration Constants
───────────────────────────────────────────────────────────
Purpose: Store a6, a7 and integration constants b1, b2
  • Columns 1-32:   Last two coefficients (a6, a7) (2D16.9)
  • Columns 49-80:  Integration constants b1 and b2 from equations (2) and (3) (2D16.9)

REPETITION PATTERN:
───────────────────
RECORDS 3, 4, and 5 are REPEATED for each temperature interval
specified in RECORD 2.

================================================================================

LOGICAL FLOW FOR READING DATA:

1. READ RECORD 1: Get species name and identification
2. READ RECORD 2: Get N = number of temperature intervals
3. FOR EACH of the N intervals:
   a) READ RECORD 3: Define temperature interval and exponents
   b) READ RECORD 4: Get coefficients a1 through a5
   c) READ RECORD 5: Get coefficients a6, a7 and constants b1, b2
4. REPEAT for next species (return to RECORD 1)

================================================================================

DATA STRUCTURE PER RECORD (Example - TiN):

Record 1: "TiN(cr)        " and "Chase,1998 pp1612−4."
Record 2: 2 intervals | Date | Ti 1.00 N 1.00 | 0 (solid) | 61.87374 | -337648.800
Record 3a: 200.000 to 800.000 K | 7 coefficients | Exponents -2,-1,0,1,2,3,4 | 5487.000
Record 4a: 5 coefficients in format 5D16.9
Record 5a: 2 coefficients + 2 integration constants
Record 3b: 800.000 to 3220.000 K | (similar for second interval)
Record 4b: next 5 coefficients
Record 5b: next 2 coefficients + constants

================================================================================

IMPORTANT NOTES:
────────────────
• Heat Capacity Equations (Cp):
  Cp(T)/R = a1·T⁻² + a2·T⁻¹ + a3 + a4·T + a5·T² + a6·T³ + a7·T⁴

• Relative Enthalpy: H°(T)/RT = -a1·T⁻² + a2·ln(T) + a3 + a4·T/2 + ... + b1/T

• Relative Entropy: S°(T)/R = -a1·T⁻²/2 - a2·T⁻¹ + a3·ln(T) + ... + b2

• Condensed phases are numbered in increasing order by temperature
• All numeric values use double precision scientific notation (D)
• Unfilled columns follow strict FORTRAN spacing rules

================================================================================