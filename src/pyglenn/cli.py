#!/usr/bin/env python3
"""
Command-line interface for pyglenn.

Usage:
    pyglenn build  – Convert thermo.inp → thermo.db
    pyglenn query  – Run example queries
"""

from __future__ import annotations

import argparse
import logging
import sys

from .builder import ThermoDBBuilder
from .calculator import ThermoCalcError, ThermochemicalCalculator
from .database import ThermoDBQuery


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI output.

    Args:
        verbose: If True, enable DEBUG level logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(levelname)-8s %(message)s',
        stream=sys.stderr,
    )


def cmd_build(args: argparse.Namespace) -> None:
    """Build the SQLite database from thermo.inp."""
    print('=' * 70)
    print('CONVERTING thermo.inp → SQLite3')
    print('=' * 70)

    builder = ThermoDBBuilder(args.input, args.output)
    try:
        builder.connect()
        builder.create_tables()
        builder.parse_and_load()

        assert builder.cursor is not None
        builder.cursor.execute('SELECT COUNT(*) FROM species')
        num_species = builder.cursor.fetchone()[0]
        builder.cursor.execute('SELECT COUNT(*) FROM temperature_intervals')
        num_intervals = builder.cursor.fetchone()[0]
        builder.cursor.execute('SELECT COUNT(*) FROM coefficients')
        num_coeffs = builder.cursor.fetchone()[0]

        print('\nDatabase Statistics:')
        print(f'  Species: {num_species}')
        print(f'  Temperature Intervals: {num_intervals}')
        print(f'  Coefficient Sets: {num_coeffs}')
        print('\n[SUCCESS] Conversion completed!')
    finally:
        builder.close()


def cmd_query(args: argparse.Namespace) -> None:
    """Run example queries against the database."""
    print('=' * 70)
    print('THERMO.DB QUERY EXAMPLES')
    print('=' * 70)

    calc = ThermochemicalCalculator(args.database)
    if not calc.connect():
        print('Error: Could not connect to database')
        return

    try:
        # Statistics
        print('\n1. DATABASE STATISTICS:')
        print('-' * 70)
        stats = calc.db.get_statistics()
        print(f'  Total species: {stats.total_species}')
        print(f'  Total intervals: {stats.total_intervals}')
        print(f'  Total coefficient sets: {stats.total_coeff_sets}')
        print(f'  Species by phase: {stats.species_by_phase}')
        print(f'  Average molecular weight: {stats.avg_molecular_weight:.2f} g/mol')

        # Search
        pattern = args.species or 'O2'
        print(f"\n2. SPECIES SEARCH ('{pattern}'):")
        print('-' * 70)
        species_list = calc.get_available_species(pattern)
        for sp in species_list[:5]:
            print(
                f'  ID: {sp.id:4d} | Name: {sp.name:20s} | '
                f'Phase: {sp.phase:10s} | MW: {sp.molecular_weight}'
            )

        # Properties
        if species_list:
            species_id = species_list[0].id
            species_name = species_list[0].name
            print(f'\n3. PROPERTIES FOR {species_name}:')
            print('-' * 70)
            print(
                f'{"T (K)":>8} | {"Cp (J/mol·K)":>14} | '
                f'{"H° (J/mol)":>14} | {"S° (J/mol·K)":>14}'
            )
            print('-' * 70)
            for T in [298.15, 500, 1000, 1500]:
                try:
                    props = calc.calculate_properties(species_id, T)
                except ThermoCalcError:
                    continue
                print(
                    f'{props.temperature:>8.2f} | '
                    f'{props.cp:>14.3f} | '
                    f'{props.h_relative:>14.1f} | '
                    f'{props.s:>14.3f}'
                )

            h_f = calc.calculate_formation_enthalpy(species_id)
            if h_f is not None:
                print(f'\n  H°_f(298.15 K) = {h_f:.1f} J/mol')

        print('\n' + '=' * 70)
        print('[SUCCESS] Queries completed!')
    finally:
        calc.close()


def cmd_migrate_metadata(args: argparse.Namespace) -> None:
    """Ensure a database carries the canonical dataset metadata."""
    query = ThermoDBQuery(args.database)
    if not query.connect():
        print('Error: Could not connect to database')
        return
    try:
        r_ref = query.get_gas_constant_ref()
        print('=' * 70)
        print('METADATA MIGRATION')
        print('=' * 70)
        print(f'  Database: {args.database}')
        print(f'  gas_constant_ref: {r_ref}')
        print('  gas_constant_ref_source: NASA Glenn/CEA thermo.inp (CODATA 1986)')
        print('\n[SUCCESS] Metadata is present and canonical.')
    finally:
        query.close()


def cmd_validate(args: argparse.Namespace) -> None:
    """Run read-only integrity checks against a database."""
    query = ThermoDBQuery(args.database)
    if not query.connect(auto_migrate=False):
        print('Error: Could not connect to database')
        return
    try:
        report = query.validate_database()
        print('=' * 70)
        print('DATABASE VALIDATION')
        print('=' * 70)
        print(f'  Valid: {report["valid"]}')
        if report['errors']:
            print('  Errors:')
            for err in report['errors']:
                print(f'    - {err}')
        if report['warnings']:
            print('  Warnings:')
            for warn in report['warnings']:
                print(f'    - {warn}')
        print('  Counts:', report['counts'])
        if report['valid']:
            print('\n[SUCCESS] Validation completed.')
        else:
            print('\n[FAIL] Validation failed.')
    finally:
        query.close()


def main() -> None:
    """Entry point for the pyglenn CLI."""
    parser = argparse.ArgumentParser(
        prog='pyglenn',
        description='Thermochemical properties calculator',
    )
    sub = parser.add_subparsers(dest='command', help='Available commands')

    # build
    p_build = sub.add_parser('build', help='Build database from thermo.inp')
    p_build.add_argument(
        '-v', '--verbose', action='store_true', help='Enable verbose (DEBUG) logging'
    )
    p_build.add_argument(
        '-i',
        '--input',
        default='thermo.inp',
        help='Input FORTRAN file (default: thermo.inp)',
    )
    p_build.add_argument(
        '-o',
        '--output',
        default='thermo.db',
        help='Output SQLite database (default: thermo.db)',
    )
    p_build.set_defaults(func=cmd_build)

    # query
    p_query = sub.add_parser('query', help='Run example queries')
    p_query.add_argument(
        '-v', '--verbose', action='store_true', help='Enable verbose (DEBUG) logging'
    )
    p_query.add_argument(
        '-d',
        '--database',
        default='thermo.db',
        help='SQLite database file (default: thermo.db)',
    )
    p_query.add_argument(
        '-s',
        '--species',
        default='O2',
        help='Species name pattern to search (default: O2)',
    )
    p_query.set_defaults(func=cmd_query)

    # migrate-metadata
    p_migrate = sub.add_parser(
        'migrate-metadata', help='Add canonical dataset metadata to a database'
    )
    p_migrate.add_argument(
        '-d',
        '--database',
        default='thermo.db',
        help='SQLite database file (default: thermo.db)',
    )
    p_migrate.set_defaults(func=cmd_migrate_metadata)

    # validate
    p_validate = sub.add_parser(
        'validate', help='Run read-only database integrity checks'
    )
    p_validate.add_argument(
        '-d',
        '--database',
        default='thermo.db',
        help='SQLite database file (default: thermo.db)',
    )
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        _setup_logging(verbose=getattr(args, 'verbose', False))
        args.func(args)


if __name__ == '__main__':
    main()
