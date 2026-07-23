"""
pyglenn — Thermochemical properties calculator.

Computes Cp(T), H°(T), S°(T) from NASA polynomial coefficients
stored in a SQLite database, converted from FORTRAN thermo.inp files.
"""

__version__ = '0.1.13'
__author__ = 'Dr. Reginaldo G. Leão Jr.'

from .builder import ThermoDBBuilder
from .calculator import (
    DatabaseNotConnectedError,
    SpeciesNotFoundError,
    TemperatureOutOfRangeError,
    ThermoCalcError,
    ThermochemicalCalculator,
)
from .database import R, ThermoDBQuery

__all__ = [
    'ThermochemicalCalculator',
    'ThermoDBQuery',
    'ThermoDBBuilder',
    'R',
    'ThermoCalcError',
    'DatabaseNotConnectedError',
    'SpeciesNotFoundError',
    'TemperatureOutOfRangeError',
]
