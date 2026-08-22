#!/usr/bin/env python3
"""
Database builder: converts thermo.inp (NASA FORTRAN format) → SQLite3.

FORTRAN Record Structure (Appendix C):
  RECORD 1 – Species identification
  RECORD 2 – General information
  RECORD 3 – Temperature interval definition
  RECORD 4 – First 5 polynomial coefficients
  RECORD 5 – Last 2 coefficients + integration constants

Records 3–5 repeat for each temperature interval.
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

from .database import (
    GAS_CONSTANT_REF_KEY,
    GAS_CONSTANT_REF_SOURCE_KEY,
    GAS_CONSTANT_REF_VALUE,
    R_GLENN_SOURCE,
)

logger = logging.getLogger(__name__)

# Regex: match FORTRAN double-precision scientific notation (e.g. 1.234567890D+05)
_FORTRAN_D_RE = re.compile(r'\d\.\d{0,9}D[+\-]\d{1,2}', re.IGNORECASE)


class ThermoDBBuilder:
    """Build a SQLite database from a thermo.inp file."""

    def __init__(self, inp_file: str, db_file: str) -> None:
        self.inp_file: Path = Path(inp_file)
        self.db_file: Path = Path(db_file)
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    # ------------------------------------------------------------------
    # Database lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Connect to (or create) the SQLite database."""
        self.conn = sqlite3.connect(str(self.db_file))
        self.cursor = self.conn.cursor()
        self.cursor.execute('PRAGMA foreign_keys = ON')
        self.cursor.execute('PRAGMA journal_mode = WAL')

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None
            self.cursor = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def create_tables(self) -> None:
        """Create the normalised table structure."""
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS species (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                formula TEXT,
                comments TEXT,
                reference_code TEXT,
                phase TEXT CHECK(phase IN ('gas', 'condensed')),
                molecular_weight REAL,
                heat_of_formation_298K REAL,
                num_intervals INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS temperature_intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_id INTEGER NOT NULL,
                interval_number INTEGER NOT NULL,
                temp_min REAL NOT NULL,
                temp_max REAL NOT NULL,
                h_298_to_0 REAL,
                FOREIGN KEY (species_id)
                    REFERENCES species(id) ON DELETE CASCADE,
                UNIQUE(species_id, interval_number)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS coefficients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interval_id INTEGER NOT NULL UNIQUE,
                a1 REAL, a2 REAL, a3 REAL, a4 REAL, a5 REAL,
                a6 REAL, a7 REAL,
                b1 REAL, b2 REAL,
                FOREIGN KEY (interval_id)
                    REFERENCES temperature_intervals(id) ON DELETE CASCADE
            )
        """)

        if self.cursor is None:
            raise RuntimeError('Database not connected')
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                id INTEGER PRIMARY KEY,
                temp_min_global REAL,
                temp_500_K REAL,
                temp_1500_K REAL,
                temp_max_global REAL,
                reference_date TEXT,
                total_species INTEGER
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        assert self.conn is not None
        self.conn.commit()

    def write_metadata(self) -> None:
        """Write canonical dataset metadata using idempotent upserts.

        The method intentionally does not commit; callers can include metadata
        writes in the same transaction as a database build.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
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

    # ------------------------------------------------------------------
    # Low-level parsers
    # ------------------------------------------------------------------
    @staticmethod
    def parse_float(value: str) -> float | None:
        """Parse a FORTRAN-style float ('D' → 'E').

        Args:
            value: String possibly in FORTRAN D notation.

        Returns:
            Float value or None if parsing fails.
        """
        if not value or not value.strip():
            return None
        try:
            return float(value.strip().replace('D', 'E').replace('d', 'e'))
        except ValueError:
            return None

    @staticmethod
    def parse_species_record(line: str) -> tuple[str, str]:
        """Extract species name (cols 1-16) and comments (cols 19-80).

        Args:
            line: RECORD 1 line from thermo.inp.

        Returns:
            Tuple of (species_name, comments).
        """
        name = line[0:16].strip() if len(line) > 16 else line.strip()
        comments = line[18:80].strip() if len(line) > 18 else ''
        return name, comments

    def parse_general_info_record(self, line: str) -> dict[str, Any]:
        """Parse RECORD 2 – general information.

        Args:
            line: RECORD 2 line from thermo.inp.

        Returns:
            Dict with num_intervals, ref_code, phase, molecular_weight,
            heat_of_formation.
        """
        data: dict[str, Any] = {}

        try:
            num_int_str = line[0:2].strip()
            data['num_intervals'] = int(num_int_str) if num_int_str.isdigit() else 0

            data['ref_code'] = line[3:9].strip()

            phase_code = line[50:52].strip()
            data['phase'] = 'condensed' if phase_code and phase_code != '0' else 'gas'

            data['molecular_weight'] = self.parse_float(line[52:65])
            data['heat_of_formation'] = self.parse_float(line[65:80])
        except Exception as e:
            logger.warning('Error parsing RECORD 2: %s', e)

        return data

    @staticmethod
    def parse_temp_interval_record(line: str) -> dict[str, Any]:
        """Parse RECORD 3 – temperature interval.

        Args:
            line: RECORD 3 line from thermo.inp.

        Returns:
            Dict with temp_min, temp_max, h_298_to_0.
        """
        data: dict[str, Any] = {}

        temp_min_str = line[0:11].strip() if len(line) > 11 else ''
        temp_max_str = line[11:22].strip() if len(line) > 22 else ''
        h298_str = line[65:80].strip() if len(line) > 80 else ''

        data['temp_min'] = ThermoDBBuilder.parse_float(temp_min_str)
        data['temp_max'] = ThermoDBBuilder.parse_float(temp_max_str)
        data['h_298_to_0'] = ThermoDBBuilder.parse_float(h298_str)

        return data

    @staticmethod
    def parse_coefficients_record(lines: list[str]) -> dict[str, Any]:
        """Parse RECORDS 4-5 – polynomial coefficients.

        Args:
            lines: Two lines containing a1-a7 and b1-b2.

        Returns:
            Dict with keys a1-a7, b1, b2.
        """
        coeffs: dict[str, Any] = {}

        line4 = lines[0] if len(lines) > 0 else ''
        coeffs['a1'] = ThermoDBBuilder.parse_float(line4[0:16])
        coeffs['a2'] = ThermoDBBuilder.parse_float(line4[16:32])
        coeffs['a3'] = ThermoDBBuilder.parse_float(line4[32:48])
        coeffs['a4'] = ThermoDBBuilder.parse_float(line4[48:64])
        coeffs['a5'] = ThermoDBBuilder.parse_float(line4[64:80])

        line5 = lines[1] if len(lines) > 1 else ''
        coeffs['a6'] = ThermoDBBuilder.parse_float(line5[0:16])
        coeffs['a7'] = ThermoDBBuilder.parse_float(line5[16:32])
        coeffs['b1'] = ThermoDBBuilder.parse_float(line5[48:64])
        coeffs['b2'] = ThermoDBBuilder.parse_float(line5[64:80])

        return coeffs

    # ------------------------------------------------------------------
    # File reading & line-type detection
    # ------------------------------------------------------------------
    def read_thermo_file(self) -> list[str]:
        """Read thermo.inp, stripping comments and blank lines.

        Returns:
            List of non-empty, non-comment lines.
        """
        with open(self.inp_file, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        return [
            line.rstrip('\n\r')
            for line in lines
            if line.strip() and not line.strip().startswith('!')
        ]

    @staticmethod
    def is_temperature_line(line: str) -> bool:
        """Detect RECORD 3 (temperature interval).

        A temperature line has two valid floats in cols 0-11 and 11-22
        where the first is strictly less than the second.

        Args:
            line: A line from thermo.inp.

        Returns:
            True if the line appears to be a temperature interval record.
        """
        if len(line) < 22:
            return False
        try:
            t1 = ThermoDBBuilder.parse_float(line[0:11])
            t2 = ThermoDBBuilder.parse_float(line[11:22])
            return t1 is not None and t2 is not None and t1 < t2
        except Exception:
            return False

    @staticmethod
    def is_coefficient_line(line: str) -> bool:
        """Detect coefficient lines containing FORTRAN D notation.

        Uses regex to match the standard FORTRAN double-precision format
        (e.g. ``1.23456789D+01``), which is more robust than substring
        matching.

        Args:
            line: A line from thermo.inp.

        Returns:
            True if the line contains at least one FORTRAN D-format number.
        """
        return bool(_FORTRAN_D_RE.search(line))

    @staticmethod
    def is_species_header(line: str) -> bool:
        """Return whether a line can be a species-identification record.

        A coefficient line can fit entirely inside the fixed-width species-name
        field.  It must therefore be rejected explicitly, rather than relying
        on whitespace in the apparent name.
        """
        name, _ = ThermoDBBuilder.parse_species_record(line)
        return (
            bool(name)
            and len(name.split()) == 1
            and not ThermoDBBuilder.is_temperature_line(line)
            and not ThermoDBBuilder.is_coefficient_line(line)
        )

    @staticmethod
    def _has_finite_coefficients(coeffs: dict[str, Any]) -> bool:
        """Return whether a parsed NASA-7 coefficient set is complete."""
        return all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in coeffs.values()
        )

    def _parse_intervals(
        self, lines: list[str], start: int, num_intervals: int
    ) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], int] | None:
        """Parse a complete set of interval records without modifying the DB.

        Returning ``None`` leaves the caller free to resynchronise at a later
        verified species header.  This prevents a malformed block from creating
        a partial species or from turning coefficient lines into new species.
        """
        intervals: list[tuple[dict[str, Any], dict[str, Any]]] = []
        index = start

        for _ in range(num_intervals):
            if index + 2 >= len(lines):
                logger.warning('Incomplete interval records at line %d', index + 1)
                return None
            if not self.is_temperature_line(lines[index]):
                logger.warning(
                    'Invalid temperature interval record at line %d', index + 1
                )
                return None

            interval = self.parse_temp_interval_record(lines[index])
            coefficients_lines = lines[index + 1 : index + 3]
            if not all(self.is_coefficient_line(line) for line in coefficients_lines):
                logger.warning('Invalid coefficient records at line %d', index + 2)
                return None

            coefficients = self.parse_coefficients_record(coefficients_lines)
            temp_min = interval['temp_min']
            temp_max = interval['temp_max']
            if (
                not isinstance(temp_min, float)
                or not isinstance(temp_max, float)
                or not math.isfinite(temp_min)
                or not math.isfinite(temp_max)
                or temp_min >= temp_max
                or not self._has_finite_coefficients(coefficients)
            ):
                logger.warning('Invalid interval values at line %d', index + 1)
                return None

            intervals.append((interval, coefficients))
            index += 3

        return intervals, index

    # ------------------------------------------------------------------
    # Main parse & load
    # ------------------------------------------------------------------
    def parse_and_load(self) -> None:
        """Parse the thermo.inp file and populate the database atomically.

        A species is inserted only after every declared interval and its two
        coefficient records have been parsed and validated.  Malformed blocks
        are skipped without leaving partial rows behind.
        """
        if self.cursor is None:
            raise RuntimeError('Database not connected')
        if self.conn is None:
            raise RuntimeError('Database not connected')
        lines = self.read_thermo_file()

        if not lines:
            logger.warning('Empty thermo.inp file!')
            return

        metadata_line = lines[1] if len(lines) > 1 else ''
        metadata_parts = metadata_line.split()
        species_count = 0
        existing_count = 0
        skipped = 0

        try:
            self.conn.execute('BEGIN')
            self.write_metadata()
            if len(metadata_parts) >= 4:
                self.cursor.execute(
                    """
                    INSERT INTO file_metadata
                        (id, temp_min_global, temp_500_K, temp_1500_K,
                         temp_max_global, reference_date)
                    VALUES (1, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        temp_min_global = excluded.temp_min_global,
                        temp_500_K = excluded.temp_500_K,
                        temp_1500_K = excluded.temp_1500_K,
                        temp_max_global = excluded.temp_max_global,
                        reference_date = excluded.reference_date
                    """,
                    (
                        self.parse_float(metadata_parts[0]),
                        self.parse_float(metadata_parts[1]),
                        self.parse_float(metadata_parts[2]),
                        self.parse_float(metadata_parts[3]),
                        metadata_parts[4] if len(metadata_parts) > 4 else None,
                    ),
                )

            index = 2
            while index < len(lines):
                if not self.is_species_header(lines[index]) or index + 1 >= len(lines):
                    index += 1
                    continue

                species_name, comments = self.parse_species_record(lines[index])
                general_info = self.parse_general_info_record(lines[index + 1])
                num_intervals = general_info.get('num_intervals', 0)
                if not isinstance(num_intervals, int) or num_intervals <= 0:
                    index += 1
                    continue

                parsed_intervals = self._parse_intervals(
                    lines, index + 2, num_intervals
                )
                if parsed_intervals is None:
                    logger.warning(
                        'Skipping malformed species block at line %d: %s',
                        index + 1,
                        species_name,
                    )
                    skipped += 1
                    index += 1
                    continue

                intervals, next_index = parsed_intervals
                try:
                    self.cursor.execute(
                        """
                        INSERT INTO species
                            (name, comments, reference_code, phase,
                             molecular_weight, heat_of_formation_298K,
                             num_intervals)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            species_name,
                            comments,
                            general_info.get('ref_code'),
                            general_info.get('phase'),
                            general_info.get('molecular_weight'),
                            general_info.get('heat_of_formation'),
                            num_intervals,
                        ),
                    )
                except sqlite3.IntegrityError:
                    logger.info('Species already exists, skipping: %s', species_name)
                    existing_count += 1
                    index = next_index
                    continue

                species_id = self.cursor.lastrowid
                for interval_number, (interval, coefficients) in enumerate(
                    intervals, 1
                ):
                    self.cursor.execute(
                        """
                        INSERT INTO temperature_intervals
                            (species_id, interval_number, temp_min,
                             temp_max, h_298_to_0)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            species_id,
                            interval_number,
                            interval['temp_min'],
                            interval['temp_max'],
                            interval['h_298_to_0'],
                        ),
                    )
                    interval_id = self.cursor.lastrowid
                    self.cursor.execute(
                        """
                        INSERT INTO coefficients
                            (interval_id, a1, a2, a3, a4, a5,
                             a6, a7, b1, b2)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (interval_id, *coefficients.values()),
                    )

                logger.info('Loaded species: %s', species_name)
                species_count += 1
                index = next_index

            self.cursor.execute(
                'UPDATE file_metadata SET total_species = ? WHERE id = 1',
                (species_count,),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        logger.info('=' * 70)
        logger.info('New species loaded: %d', species_count)
        logger.info('Already existing: %d', existing_count)
        logger.info('Malformed species blocks skipped: %d', skipped)
        logger.info('Database: %s', self.db_file)
