"""
pythermo — Thermochemical properties calculator.

Computes Cp(T), H°(T), S°(T) from NASA polynomial coefficients
stored in a SQLite database, converted from FORTRAN thermo.inp files.
"""

__version__ = "1.0.0"
__author__ = "Glenn"

from .calculator import ThermochemicalCalculator
from .database import ThermoDBQuery, R
from .builder import ThermoDBBuilder

__all__ = [
    "ThermochemicalCalculator",
    "ThermoDBQuery",
    "ThermoDBBuilder",
    "R",
]
