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
import re
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Regex: match FORTRAN double-precision scientific notation (e.g. 1.234D+05)
_FORTRAN_D_RE = re.compile(r'\d\.\d{0,8}D[+\-]\d{1,2}', re.IGNORECASE)


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
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.cursor.execute("PRAGMA journal_mode = WAL")

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
        assert self.cursor is not None, "Database not connected"
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

        self.conn.commit()

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
        comments = line[18:80].strip() if len(line) > 18 else ""
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
            num_int_str = line[0:2].strip() if len(line) > 2 else ""
            data['num_intervals'] = (
                int(num_int_str) if num_int_str.isdigit() else 0
            )

            data['ref_code'] = line[3:9].strip() if len(line) > 9 else ""

            phase_code = line[50:52].strip() if len(line) > 52 else "0"
            data['phase'] = (
                'condensed' if phase_code and phase_code != '0' else 'gas'
            )

            mw_str = line[52:65].strip() if len(line) > 65 else ""
            data['molecular_weight'] = self.parse_float(mw_str)

            hf_str = line[65:80].strip() if len(line) > 80 else ""
            data['heat_of_formation'] = self.parse_float(hf_str)
        except Exception as e:
            logger.warning("Error parsing RECORD 2: %s", e)

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

        temp_min_str = line[0:11].strip() if len(line) > 11 else ""
        temp_max_str = line[11:22].strip() if len(line) > 22 else ""
        h298_str = line[65:80].strip() if len(line) > 80 else ""

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

        line4 = lines[0] if len(lines) > 0 else ""
        coeffs['a1'] = ThermoDBBuilder.parse_float(line4[0:16])
        coeffs['a2'] = ThermoDBBuilder.parse_float(line4[16:32])
        coeffs['a3'] = ThermoDBBuilder.parse_float(line4[32:48])
        coeffs['a4'] = ThermoDBBuilder.parse_float(line4[48:64])
        coeffs['a5'] = ThermoDBBuilder.parse_float(line4[64:80])

        line5 = lines[1] if len(lines) > 1 else ""
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
            return (
                t1 is not None
                and t2 is not None
                and t1 < t2
            )
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

    # ------------------------------------------------------------------
    # Main parse & load
    # ------------------------------------------------------------------
    def parse_and_load(self) -> None:
        """Parse the thermo.inp file and populate the database."""
        assert self.cursor is not None, "Database not connected"
        lines = self.read_thermo_file()

        if not lines:
            logger.warning("Empty thermo.inp file!")
            return

        # --- Global metadata (line index 1) ---
        metadata_line = lines[1] if len(lines) > 1 else ""
        parts = metadata_line.split()
        if len(parts) >= 4:
            self.cursor.execute(
                """
                INSERT INTO file_metadata
                    (id, temp_min_global, temp_500_K, temp_1500_K,
                     temp_max_global, reference_date)
                VALUES (1, ?, ?, ?, ?, ?)
                """,
                (
                    self.parse_float(parts[0]),
                    self.parse_float(parts[1]),
                    self.parse_float(parts[2]),
                    self.parse_float(parts[3]),
                    parts[4] if len(parts) > 4 else None,
                ),
            )

        # --- Species loop ---
        i = 2
        species_count = 0
        skipped = 0

        while i < len(lines):
            try:
                # RECORD 1 – species name
                if i >= len(lines):
                    break

                species_name, comments = self.parse_species_record(lines[i])

                if (
                    not species_name
                    or len(species_name.split()) > 1
                    or self.is_temperature_line(lines[i])
                ):
                    i += 1
                    skipped += 1
                    continue

                logger.info("Processing species: %s", species_name)
                i += 1

                # RECORD 2 – general info
                if i >= len(lines):
                    break
                general_info = self.parse_general_info_record(lines[i])
                i += 1

                if general_info.get('num_intervals', 0) <= 0:
                    skipped += 1
                    continue

                # Insert species
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
                            general_info.get('num_intervals'),
                        ),
                    )
                    species_id = self.cursor.lastrowid
                    species_count += 1
                except sqlite3.IntegrityError:
                    self.cursor.execute(
                        "SELECT id FROM species WHERE name = ?",
                        (species_name,),
                    )
                    result = self.cursor.fetchone()
                    if result:
                        species_id = result[0]
                    else:
                        skipped += 1
                        continue

                # --- Temperature intervals ---
                num_intervals = general_info.get('num_intervals', 0)
                for interval_num in range(num_intervals):
                    if i >= len(lines):
                        break

                    if not self.is_temperature_line(lines[i]):
                        break

                    temp_interval = self.parse_temp_interval_record(lines[i])
                    i += 1

                    if i + 1 >= len(lines):
                        break

                    if not (
                        self.is_coefficient_line(lines[i])
                        and self.is_coefficient_line(lines[i + 1])
                    ):
                        break

                    coeffs = self.parse_coefficients_record(
                        [lines[i], lines[i + 1]]
                    )
                    i += 2

                    if (
                        temp_interval.get('temp_min') is None
                        or temp_interval.get('temp_max') is None
                    ):
                        continue

                    try:
                        self.cursor.execute(
                            """
                            INSERT INTO temperature_intervals
                                (species_id, interval_number, temp_min,
                                 temp_max, h_298_to_0)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                species_id,
                                interval_num + 1,
                                temp_interval.get('temp_min'),
                                temp_interval.get('temp_max'),
                                temp_interval.get('h_298_to_0'),
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
                            (
                                interval_id,
                                coeffs.get('a1'),
                                coeffs.get('a2'),
                                coeffs.get('a3'),
                                coeffs.get('a4'),
                                coeffs.get('a5'),
                                coeffs.get('a6'),
                                coeffs.get('a7'),
                                coeffs.get('b1'),
                                coeffs.get('b2'),
                            ),
                        )

                        logger.debug(
                            "  Interval %d: %sK - %sK",
                            interval_num + 1,
                            temp_interval.get('temp_min'),
                            temp_interval.get('temp_max'),
                        )
                    except Exception as e:
                        logger.warning(
                            "Error inserting interval %d: %s",
                            interval_num + 1, e,
                        )

            except Exception as e:
                logger.warning("Error processing line %d: %s", i, e)
                i += 1

        # Final metadata update
        self.cursor.execute(
            "UPDATE file_metadata SET total_species = ? WHERE id = 1",
            (species_count,),
        )
        self.conn.commit()

        logger.info("=" * 70)
        logger.info("Total species loaded: %d", species_count)
        logger.info("Skipped lines: %d", skipped)
        logger.info("Database: %s", self.db_file)
