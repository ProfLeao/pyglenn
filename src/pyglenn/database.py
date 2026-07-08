#!/usr/bin/env python3
"""
Database query interface for thermochemical data.
Provides SQLite access, species lookup, and NASA polynomial calculations.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Physical constant: Universal gas constant
R: float = 8.314462618  # J/(mol·K) — CODATA 2018 value


class ThermoDBQuery:
    """Class for querying thermochemical database."""

    def __init__(self, db_file: str = 'thermo.db') -> None:
        self.db_file: Path = Path(db_file)
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def connect(self) -> bool:
        """Connect to database.

        Returns:
            True if connection succeeded, False otherwise.
        """
        if not self.db_file.exists():
            logger.error("Database file not found: %s", self.db_file)
            return False

        self.conn = sqlite3.connect(str(self.db_file))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return True

    def close(self) -> None:
        """Close connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics.

        Returns:
            Dict with total_species, total_intervals, total_coeff_sets,
            species_by_phase, avg_molecular_weight.
        """
        assert self.cursor is not None, "Database not connected"
        stats: dict[str, Any] = {}

        self.cursor.execute("SELECT COUNT(*) FROM species")
        stats['total_species'] = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM temperature_intervals")
        stats['total_intervals'] = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM coefficients")
        stats['total_coeff_sets'] = self.cursor.fetchone()[0]

        self.cursor.execute(
            "SELECT phase, COUNT(*) FROM species GROUP BY phase"
        )
        stats['species_by_phase'] = dict(self.cursor.fetchall())

        self.cursor.execute(
            "SELECT AVG(molecular_weight) FROM species "
            "WHERE molecular_weight IS NOT NULL"
        )
        stats['avg_molecular_weight'] = self.cursor.fetchone()[0]

        return stats

    # ------------------------------------------------------------------
    # Species lookup
    # ------------------------------------------------------------------
    def find_species(self, name: str) -> list[dict[str, Any]]:
        """Find species by name (supports partial search).

        Args:
            name: Search pattern (substring match).

        Returns:
            List of matching species dicts (max 20).
        """
        assert self.cursor is not None, "Database not connected"
        pattern = f"%{name}%"
        self.cursor.execute(
            """
            SELECT id, name, formula, phase, molecular_weight,
                   heat_of_formation_298K, num_intervals, comments
            FROM species
            WHERE name LIKE ? OR formula LIKE ?
            ORDER BY name
            LIMIT 20
            """,
            (pattern, pattern),
        )

        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_species_data(self, species_id: int) -> dict[str, Any] | None:
        """Get complete data for a species with all its intervals.

        Args:
            species_id: Database ID of the species.

        Returns:
            Species dict with 'intervals' list, or None if not found.
        """
        assert self.cursor is not None, "Database not connected"
        self.cursor.execute(
            "SELECT * FROM species WHERE id = ?", (species_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            return None

        species_data = dict(
            zip([d[0] for d in self.cursor.description], row)
        )

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
            interval = {
                'interval_number': row[0],
                'temp_min': row[1],
                'temp_max': row[2],
                'h_298_to_0': row[3],
                'coefficients': {
                    'a1': row[4], 'a2': row[5], 'a3': row[6], 'a4': row[7],
                    'a5': row[8], 'a6': row[9], 'a7': row[10],
                    'b1': row[11], 'b2': row[12],
                },
            }
            intervals.append(interval)

        species_data['intervals'] = intervals
        return species_data

    def get_species_for_temperature(
        self, species_id: int, temperature: float
    ) -> dict[str, Any] | None:
        """Get valid coefficients for a specific temperature.

        Args:
            species_id: Database ID of the species.
            temperature: Temperature in Kelvin.

        Returns:
            Dict with interval_number, temp_min, temp_max, coefficients,
            or None if temperature is out of range.
        """
        assert self.cursor is not None, "Database not connected"
        self.cursor.execute(
            """
            SELECT ti.interval_number, ti.temp_min, ti.temp_max,
                   c.a1, c.a2, c.a3, c.a4, c.a5, c.a6, c.a7, c.b1, c.b2
            FROM temperature_intervals ti
            LEFT JOIN coefficients c ON ti.id = c.interval_id
            WHERE ti.species_id = ?
              AND ti.temp_min <= ?
              AND ti.temp_max >= ?
            LIMIT 1
            """,
            (species_id, temperature, temperature),
        )

        row = self.cursor.fetchone()
        if not row:
            return None

        return {
            'interval_number': row[0],
            'temp_min': row[1],
            'temp_max': row[2],
            'coefficients': {
                'a1': row[3], 'a2': row[4], 'a3': row[5], 'a4': row[6],
                'a5': row[7], 'a6': row[8], 'a7': row[9],
                'b1': row[10], 'b2': row[11],
            },
        }

    def list_species_page(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """List species with pagination.

        Args:
            page: Page number (1-based).
            page_size: Number of species per page.

        Returns:
            Tuple of (species_list, total_pages).
        """
        assert self.cursor is not None, "Database not connected"
        self.cursor.execute("SELECT COUNT(*) FROM species")
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

        columns = [d[0] for d in self.cursor.description]
        species = [dict(zip(columns, row)) for row in self.cursor.fetchall()]

        total_pages = (total + page_size - 1) // page_size
        return species, total_pages

    # ------------------------------------------------------------------
    # NASA polynomial calculations (Cp/R, H/RT, S/R)
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_cp(coeffs: dict[str, float], temperature: float) -> float:
        """Calculate Cp(T)/R using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless Cp/R.
        """
        T = temperature
        a = coeffs
        return (
            a['a1'] / T ** 2
            + a['a2'] / T
            + a['a3']
            + a['a4'] * T
            + a['a5'] * T ** 2
            + a['a6'] * T ** 3
            + a['a7'] * T ** 4
        )

    @staticmethod
    def calculate_h(coeffs: dict[str, float], temperature: float) -> float:
        """Calculate H°(T)/RT using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7, b1.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless H/(RT).
        """
        T = temperature
        a = coeffs
        return (
            -a['a1'] / T ** 2
            + a['a2'] * math.log(T) / T
            + a['a3']
            + a['a4'] * T / 2
            + a['a5'] * T ** 2 / 3
            + a['a6'] * T ** 3 / 4
            + a['a7'] * T ** 4 / 5
            + a['b1'] / T
        )

    @staticmethod
    def calculate_s(coeffs: dict[str, float], temperature: float) -> float:
        """Calculate S°(T)/R using NASA-7 polynomial coefficients.

        Args:
            coeffs: Dict with keys a1-a7, b2.
            temperature: Temperature in Kelvin.

        Returns:
            Dimensionless S/R.
        """
        T = temperature
        a = coeffs
        return (
            -a['a1'] / (2 * T ** 2)
            - a['a2'] / T
            + a['a3'] * math.log(T)
            + a['a4'] * T
            + a['a5'] * T ** 2 / 2
            + a['a6'] * T ** 3 / 3
            + a['a7'] * T ** 4 / 4
            + a['b2']
        )
