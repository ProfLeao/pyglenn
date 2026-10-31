"""
pyglenn — Thermochemical properties calculator.

Computes Cp(T), H°(T), S°(T) from NASA polynomial coefficients
stored in a SQLite database, converted from FORTRAN thermo.inp files.
"""

__version__ = '0.3.0'
__author__ = 'Dr. Reginaldo G. Leão Jr.'

from .builder import ThermoDBBuilder
from .calculator import (
    CompositionError,
    DatabaseNotConnectedError,
    SpeciesNotFoundError,
    TemperatureOutOfRangeError,
    ThermoCalcError,
    ThermochemicalCalculator,
)
from .database import R_GLENN, R_UNIVERSAL, R, ThermoDBQuery
from .fitting import fit_nasa7, fit_nasa7_multi
from .models import (
    DatabaseStats,
    IntervalData,
    MixedProperties,
    Mixture,
    NASACoefficients,
    SpeciesData,
    SpeciesInfo,
    ThermoProperties,
)

__all__ = [
    'CompositionError',
    'DatabaseStats',
    'DatabaseNotConnectedError',
    'IntervalData',
    'Mixture',
    'MixedProperties',
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
    'fit_nasa7',
    'fit_nasa7_multi',
]
