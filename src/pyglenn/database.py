#!/usr/bin/env python3
"""
Database query interface for thermochemical data.
Provides SQLite access, species lookup, and NASA polynomial calculations.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    DatabaseStats,
    IntervalData,
    NASACoefficients,
    SpeciesData,
    SpeciesInfo,
)

logger = logging.getLogger(__name__)

# Gas constants in J/(mol·K).  The bundled NASA Glenn/CEA polynomials were
# fitted with R_GLENN; R remains a compatibility alias for the universal value.
R_UNIVERSAL: float = 8.31446261815324  # CODATA 2018/2022
R_GLENN: float = 8.314510  # NASA Glenn/CEA thermo.inp, CODATA 1986
R: float = R_UNIVERSAL

GAS_CONSTANT_REF_KEY = 'gas_constant_ref'
GAS_CONSTANT_REF_SOURCE_KEY = 'gas_constant_ref_source'
GAS_CONSTANT_REF_VALUE = '8.314510'  # canonical text form of R_GLENN
R_GLENN_SOURCE = 'NASA Glenn/CEA thermo.inp (CODATA 1986)'


class ThermoDBQuery:
    """Class for querying thermochemical database."""

    def __init__(self, db_file: str = 'thermo.db') -> None:
        self.db_file: Path = Path(db_file)
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def connect(self, *, auto_migrate: bool = True) -> bool:
        """Connect to database.

        Args:
            auto_migrate: If True (default), add canonical dataset metadata
                to legacy databases automatically (see D3).

        Returns:
            True if connection succeeded, False otherwise.
        """
        if not self.db_file.exists():
            logger.error('Database file not found: %s', self.db_file)
            return False

        self.conn = sqlite3.connect(str(self.db_file))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        if auto_migrate:
            self._auto_migrate_metadata()
        return True

    def close(self) -> None:
        """Close connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    # ------------------------------------------------------------------
    # Dataset metadata
    # ------------------------------------------------------------------
    def _metadata_table_exists(self) -> bool:
        """Return whether this database has the additive metadata table."""
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('metadata',),
        )
        return self.cursor.fetchone() is not None

    def _auto_migrate_metadata(self) -> None:
        """Add canonical metadata to legacy databases on connect (D3).

        Only the additive ``metadata`` table is written. Read-only databases
        (or any migration failure) degrade to the documented fallback without
        raising.
        """
        if self.cursor is None or self.conn is None:
            return
        if self._metadata_table_exists():
            return
        try:
            self.migrate_metadata()
            logger.info('migrated legacy database metadata on connect')
        except sqlite3.OperationalError as exc:
            logger.warning('could not auto-migrate metadata: %s', exc)

    def get_gas_constant_ref(self) -> float:
        """Return the dataset gas constant, with a safe legacy fallback.

        Legacy databases without valid metadata retain the historic universal
        constant. Database errors are deliberately allowed to propagate instead
        of being mistaken for a legacy-database condition.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        if not self._metadata_table_exists():
            logger.warning(
                "database has no 'metadata' table; falling back to R_UNIVERSAL"
            )
            return R_UNIVERSAL

        self.cursor.execute(
            'SELECT value FROM metadata WHERE key = ?', (GAS_CONSTANT_REF_KEY,)
        )
        row = self.cursor.fetchone()
        if row is None:
            logger.warning(
                "metadata key 'gas_constant_ref' not found; falling back to R_UNIVERSAL"
            )
            return R_UNIVERSAL

        try:
            r_ref = float(row[0])
        except (TypeError, ValueError):
            logger.warning(
                "metadata key 'gas_constant_ref' is invalid; "
                'falling back to R_UNIVERSAL'
            )
            return R_UNIVERSAL

        if math.isfinite(r_ref) and 8.0 < r_ref < 9.0:
            return r_ref

        logger.warning(
            'metadata gas_constant_ref=%r is implausible; falling back to R_UNIVERSAL',
            r_ref,
        )
        return R_UNIVERSAL

    def migrate_metadata(self) -> None:
        """Add canonical dataset metadata to a connected legacy database.

        This explicit, idempotent operation changes only the additive
        ``metadata`` table. It never rebuilds or alters thermochemical rows.
        """
        if self.cursor is None or self.conn is None:
            raise RuntimeError('Database not connected')

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.cursor.executemany(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            [
                (GAS_CONSTANT_REF_KEY, GAS_CONSTANT_REF_VALUE),
                (GAS_CONSTANT_REF_SOURCE_KEY, R_GLENN_SOURCE),
            ],
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Database validation
    # ------------------------------------------------------------------
    def validate_database(self) -> dict[str, Any]:
        """Run integrity and semantic checks and return a validation report.

        Returns:
            Dict with ``valid`` (bool), ``errors`` (list[str]),
            ``warnings`` (list[str]), and ``counts`` (dict[str, int]).
        """
        if self.cursor is None or self.conn is None:
            raise RuntimeError('Database not connected')

        cur = self.cursor
        errors: list[str] = []
        warnings: list[str] = []
        counts: dict[str, int] = {}

        def _scalar(sql: str, params: tuple = ()) -> int:
            cur.execute(sql, params)
            return int(cur.fetchone()[0])

        missing = []
        for table in ('species', 'temperature_intervals', 'coefficients'):
            cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cur.fetchone() is None:
                missing.append(table)

        if missing:
            errors.append('missing required table(s): ' + ', '.join(missing))
            return {
                'valid': False,
                'errors': errors,
                'warnings': warnings,
                'counts': {},
            }

        counts['total_species'] = _scalar('SELECT COUNT(*) FROM species')
        counts['total_intervals'] = _scalar(
            'SELECT COUNT(*) FROM temperature_intervals'
        )
        counts['total_coeff_sets'] = _scalar('SELECT COUNT(*) FROM coefficients')

        orphans = _scalar(
            'SELECT COUNT(*) FROM coefficients c '
            'LEFT JOIN temperature_intervals ti ON c.interval_id = ti.id '
            'WHERE ti.id IS NULL'
        )
        if orphans:
            errors.append(f'{orphans} coefficient row(s) reference a missing interval')

        orphans = _scalar(
            'SELECT COUNT(*) FROM temperature_intervals ti '
            'LEFT JOIN species s ON ti.species_id = s.id '
            'WHERE s.id IS NULL'
        )
        if orphans:
            errors.append(f'{orphans} interval row(s) reference a missing species')

        dup = _scalar(
            'SELECT COUNT(*) FROM (SELECT interval_id, COUNT(*) AS n '
            'FROM coefficients GROUP BY interval_id) WHERE n != 1'
        )
        if dup:
            errors.append(f'{dup} interval(s) do not have exactly one coefficient row')

        mismatch = _scalar(
            'SELECT COUNT(*) FROM species s WHERE s.num_intervals != '
            '(SELECT COUNT(*) FROM temperature_intervals ti '
            'WHERE ti.species_id = s.id)'
        )
        if mismatch:
            errors.append(
                f'{mismatch} species have num_intervals disagreeing '
                'with actual interval rows'
            )

        bad_bounds = _scalar(
            'SELECT COUNT(*) FROM temperature_intervals '
            'WHERE temp_min IS NULL OR temp_max IS NULL OR temp_min >= temp_max'
        )
        if bad_bounds:
            errors.append(
                f'{bad_bounds} interval(s) have non-finite or unordered bounds'
            )

        bad_coeffs = _scalar(
            'SELECT COUNT(*) FROM coefficients WHERE a1 IS NULL OR a2 IS NULL '
            'OR a3 IS NULL OR a4 IS NULL OR a5 IS NULL OR a6 IS NULL '
            'OR a7 IS NULL OR b1 IS NULL OR b2 IS NULL'
        )
        if bad_coeffs:
            errors.append(f'{bad_coeffs} coefficient set(s) contain NULL values')

        bad_names = _scalar(
            "SELECT COUNT(*) FROM species WHERE name LIKE '%.%D%' OR name LIKE '%.%E%'"
        )
        if bad_names:
            errors.append(
                f'{bad_names} species name(s) look like FORTRAN coefficient tokens'
            )

        bad_mw = _scalar(
            'SELECT COUNT(*) FROM species '
            'WHERE molecular_weight IS NULL OR molecular_weight <= 0'
        )
        if bad_mw:
            warnings.append(
                f'{bad_mw} species have NULL or non-positive molecular weight'
            )

        return {
            'valid': not errors,
            'errors': errors,
            'warnings': warnings,
            'counts': counts,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def get_statistics(self) -> DatabaseStats:
        """Get database statistics.

        Returns:
            DatabaseStats with totals, phase counts, and average
            molecular weight.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')

        self.cursor.execute('SELECT COUNT(*) FROM species')
        total_species = int(self.cursor.fetchone()[0])

        self.cursor.execute('SELECT COUNT(*) FROM temperature_intervals')
        total_intervals = int(self.cursor.fetchone()[0])

        self.cursor.execute('SELECT COUNT(*) FROM coefficients')
        total_coeff_sets = int(self.cursor.fetchone()[0])

        self.cursor.execute('SELECT phase, COUNT(*) FROM species GROUP BY phase')
        species_by_phase = dict(self.cursor.fetchall())

        self.cursor.execute(
            'SELECT AVG(molecular_weight) FROM species '
            'WHERE molecular_weight IS NOT NULL'
        )
        avg_molecular_weight = self.cursor.fetchone()[0]

        return DatabaseStats(
            total_species=total_species,
            total_intervals=total_intervals,
            total_coeff_sets=total_coeff_sets,
            species_by_phase=species_by_phase,
            avg_molecular_weight=avg_molecular_weight,
        )

    # ------------------------------------------------------------------
    # Species lookup
    # ------------------------------------------------------------------
    def find_species(self, name: str, exact_match: bool = False) -> list[SpeciesInfo]:
        """Find species by name.

        Args:
            name: Search pattern.
            exact_match: If True, use case-insensitive exact match.
                         If False (default), use substring match (LIKE).

        Returns:
            List of matching SpeciesInfo (max 20).
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')

        if exact_match:
            # Case-insensitive exact match — returns only the
            # species whose name matches the pattern exactly.
            self.cursor.execute(
                """
                SELECT id, name, formula, phase, molecular_weight,
                       heat_of_formation_298K, num_intervals, comments
                FROM species
                WHERE UPPER(name) = UPPER(?)
                ORDER BY name
                LIMIT 20
                """,
                (name,),
            )
        else:
            # Substring search with exact matches prioritised first,
            # followed by alphabetical ordering of the remainder.
            self.cursor.execute(
                """
                SELECT id, name, formula, phase, molecular_weight,
                       heat_of_formation_298K, num_intervals, comments
                FROM species
                WHERE name LIKE ? OR formula LIKE ?
                ORDER BY
                    CASE WHEN UPPER(name) = UPPER(?) THEN 0 ELSE 1 END,
                    name
                LIMIT 20
                """,
                (f'%{name}%', f'%{name}%', name),
            )

        return [SpeciesInfo.from_mapping(row) for row in self.cursor.fetchall()]

    def get_species_data(self, species_id: int) -> SpeciesData | None:
        """Get complete data for a species with all its intervals.

        Args:
            species_id: Database ID of the species.

        Returns:
            SpeciesData with its ``intervals`` tuple, or None if not found.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute('SELECT * FROM species WHERE id = ?', (species_id,))
        row = self.cursor.fetchone()
        if not row:
            return None

        species_info = SpeciesInfo.from_mapping(row)

        self.cursor.execute(
            """
            SELECT ti.interval_number, ti.temp_min, ti.temp_max,
                   ti.h_298_to_0,
                   c.a1, c.a2, c.a3, c.a4, c.a5, c.a6, c.a7, c.b1, c.b2
            FROM temperature_intervals ti
            LEFT JOIN coefficients c ON ti.id = c.interval_id
            WHERE ti.species_id = ?
            ORDER BY ti.interval_number
            """,
            (species_id,),
        )

        intervals = []
        for row in self.cursor.fetchall():
            intervals.append(
                IntervalData(
                    interval_number=row['interval_number'],
                    temp_min=row['temp_min'],
                    temp_max=row['temp_max'],
                    h_298_to_0=row['h_298_to_0'],
                    coefficients=NASACoefficients(
                        a1=row['a1'],
                        a2=row['a2'],
                        a3=row['a3'],
                        a4=row['a4'],
                        a5=row['a5'],
                        a6=row['a6'],
                        a7=row['a7'],
                        b1=row['b1'],
                        b2=row['b2'],
                    ),
                )
            )

        return SpeciesData(
            id=species_info.id,
            name=species_info.name,
            formula=species_info.formula,
            phase=species_info.phase,
            molecular_weight=species_info.molecular_weight,
            heat_of_formation_298K=species_info.heat_of_formation_298K,
            num_intervals=species_info.num_intervals,
            comments=species_info.comments,
            reference_code=species_info.reference_code,
            intervals=tuple(intervals),
        )

    def get_species_info(self, species_id: int) -> SpeciesInfo | None:
        """Get lightweight species metadata without loading intervals.

        Args:
            species_id: Database ID of the species.

        Returns:
            SpeciesInfo, or None if the species is not found.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute(
            """
            SELECT id, name, formula, phase, molecular_weight,
                   heat_of_formation_298K, num_intervals, comments,
                   reference_code
            FROM species
            WHERE id = ?
            """,
            (species_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        return SpeciesInfo.from_mapping(row)

    def get_temperature_bounds(self, species_id: int) -> tuple[float, float] | None:
        """Return the overall [temp_min, temp_max] covered by a species.

        Args:
            species_id: Database ID of the species.

        Returns:
            Tuple of (min_temp, max_temp), or None if the species has no
            intervals.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute(
            'SELECT MIN(temp_min), MAX(temp_max) FROM temperature_intervals '
            'WHERE species_id = ?',
            (species_id,),
        )
        row = self.cursor.fetchone()
        if row is None or row[0] is None or row[1] is None:
            return None
        return (row[0], row[1])

    def get_species_for_temperature(
        self, species_id: int, temperature: float
    ) -> IntervalData | None:
        """Get the interval and coefficients valid at a specific temperature.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            IntervalData, or None if the temperature is out of range.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        # A small tolerance (1e-9 K) is added to temp_max so that
        # temperatures exactly on an interval boundary are accepted
        # in either adjacent interval.  ORDER BY interval_number
        # guarantees deterministic selection when both intervals
        # cover the same temperature (prefers the lower interval).
        self.cursor.execute(
            """
            SELECT ti.interval_number, ti.temp_min, ti.temp_max,
                   ti.h_298_to_0,
                   c.a1, c.a2, c.a3, c.a4, c.a5, c.a6, c.a7, c.b1, c.b2
            FROM temperature_intervals ti
            LEFT JOIN coefficients c ON ti.id = c.interval_id
            WHERE ti.species_id = ?
              AND ti.temp_min <= ?
              AND ti.temp_max + 1e-9 >= ?
            ORDER BY ti.interval_number
            LIMIT 1
            """,
            (species_id, temperature, temperature),
        )

        row = self.cursor.fetchone()
        if not row:
            return None

        return IntervalData(
            interval_number=row['interval_number'],
            temp_min=row['temp_min'],
            temp_max=row['temp_max'],
            h_298_to_0=row['h_298_to_0'],
            coefficients=NASACoefficients(
                a1=row['a1'],
                a2=row['a2'],
                a3=row['a3'],
                a4=row['a4'],
                a5=row['a5'],
                a6=row['a6'],
                a7=row['a7'],
                b1=row['b1'],
                b2=row['b2'],
            ),
        )

    def list_species_page(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[SpeciesInfo], int]:
        """List species with pagination.

        Args:
            page: Page number (1-based).
            page_size: Number of species per page.

        Returns:
            Tuple of (species_list, total_pages).
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute('SELECT COUNT(*) FROM species')
        total = self.cursor.fetchone()[0]

        offset = (page - 1) * page_size
        self.cursor.execute(
            """
            SELECT id, name, phase, molecular_weight,
                   heat_of_formation_298K, num_intervals
            FROM species
            ORDER BY name
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        )

        species = [SpeciesInfo.from_mapping(row) for row in self.cursor.fetchall()]

        total_pages = (total + page_size - 1) // page_size
        return species, total_pages

    def list_all_species(self) -> list[SpeciesInfo]:
        """List every species in a single ordered query.

        Returns:
            List of all SpeciesInfo ordered by name.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute(
            """
            SELECT id, name, formula, phase, molecular_weight,
                   heat_of_formation_298K, num_intervals, comments
            FROM species
            ORDER BY name
            """
        )
        return [SpeciesInfo.from_mapping(row) for row in self.cursor.fetchall()]

    # ------------------------------------------------------------------
    # NASA polynomial calculations (Cp/R, H/RT, S/R)
    # ------------------------------------------------------------------
    @staticmethod
    def _coeff_dict(
        coeffs: NASACoefficients | dict[str, float],
    ) -> dict[str, float]:
        """Normalise coefficients to a plain dict (accepts NASACoefficients)."""
        if isinstance(coeffs, NASACoefficients):
            return asdict(coeffs)
        return coeffs

    @staticmethod
    def calculate_cp(
        coeffs: NASACoefficients | dict[str, float], temperature: float
    ) -> float:
        """Calculate Cp(T)/R using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless Cp/R.
        """
        T = temperature
        a = ThermoDBQuery._coeff_dict(coeffs)
        return (
            a['a1'] / T**2
            + a['a2'] / T
            + a['a3']
            + a['a4'] * T
            + a['a5'] * T**2
            + a['a6'] * T**3
            + a['a7'] * T**4
        )

    @staticmethod
    def calculate_h(
        coeffs: NASACoefficients | dict[str, float], temperature: float
    ) -> float:
        """Calculate H°(T)/RT using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7, b1.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless H/(RT).
        """
        T = temperature
        a = ThermoDBQuery._coeff_dict(coeffs)
        return (
            -a['a1'] / T**2
            + a['a2'] * math.log(T) / T
            + a['a3']
            + a['a4'] * T / 2
            + a['a5'] * T**2 / 3
            + a['a6'] * T**3 / 4
            + a['a7'] * T**4 / 5
            + a['b1'] / T
        )

    @staticmethod
    def calculate_s(
        coeffs: NASACoefficients | dict[str, float], temperature: float
    ) -> float:
        """Calculate S°(T)/R using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7, b2.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless S/R.
        """
        T = temperature
        a = ThermoDBQuery._coeff_dict(coeffs)
        return (
            -a['a1'] / (2 * T**2)
            - a['a2'] / T
            + a['a3'] * math.log(T)
            + a['a4'] * T
            + a['a5'] * T**2 / 2
            + a['a6'] * T**3 / 3
            + a['a7'] * T**4 / 4
            + a['b2']
        )
