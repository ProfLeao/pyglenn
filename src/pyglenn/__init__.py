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
from .database import R_GLENN, R_UNIVERSAL, R, ThermoDBQuery
from .models import (
    DatabaseStats,
    IntervalData,
    NASACoefficients,
    SpeciesData,
    SpeciesInfo,
    ThermoProperties,
)

__all__ = [
    'DatabaseStats',
    'DatabaseNotConnectedError',
    'IntervalData',
    'NASACoefficients',
    'R',
    'R_GLENN',
    'R_UNIVERSAL',
    'SpeciesData',
    'SpeciesInfo',
    'SpeciesNotFoundError',
    'TemperatureOutOfRangeError',
    'ThermoCalcError',
    'ThermoDBBuilder',
    'ThermoDBQuery',
    'ThermoProperties',
    'ThermochemicalCalculator',
]
