#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database query interface for thermochemical data.
Provides SQLite access, species lookup, and NASA polynomial calculations.
"""

import math
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Physical constant: Gas constant
R = 8.314  # J/(mol·K)


class ThermoDBQuery:
    """Class for querying thermochemical database."""

    def __init__(self, db_file: str = 'thermo.db'):
        self.db_file = Path(db_file)
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """Connect to database."""
        if not self.db_file.exists():
            print(f"Error: File {self.db_file} not found")
            return False

        self.conn = sqlite3.connect(str(self.db_file))
        self.cursor = self.conn.cursor()
        return True

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def get_statistics(self) -> Dict:
        """Get database statistics."""
        stats = {}

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
    def find_species(self, name: str) -> List[Dict]:
        """Find species by name (supports partial search)."""
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

    def get_species_data(self, species_id: int) -> Optional[Dict]:
        """Get complete data for a species with all its intervals."""
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
    ) -> Optional[Dict]:
        """Get valid coefficients for a specific temperature."""
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
    ) -> Tuple[List[Dict], int]:
        """List species with pagination."""
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
    def calculate_cp(coeffs: Dict, temperature: float) -> float:
        """Calculate Cp(T)/R using NASA-7 polynomial coefficients."""
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
    def calculate_h(coeffs: Dict, temperature: float) -> float:
        """Calculate H°(T)/RT using NASA-7 polynomial coefficients."""
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
    def calculate_s(coeffs: Dict, temperature: float) -> float:
        """Calculate S°(T)/R using NASA-7 polynomial coefficients."""
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
