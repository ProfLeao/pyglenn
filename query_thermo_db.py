#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example script to query and use data from thermo.db database
Demonstrates common SQL queries and thermochemical calculations
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple

class ThermoDBQuery:
    """Class for querying thermochemical database"""
    
    def __init__(self, db_file: str = 'thermo.db'):
        self.db_file = Path(db_file)
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Connect to database"""
        if not self.db_file.exists():
            print(f"Error: File {self.db_file} not found")
            return False
        
        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        return True
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        stats = {}
        
        self.cursor.execute("SELECT COUNT(*) FROM species")
        stats['total_species'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM temperature_intervals")
        stats['total_intervals'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM coefficients")
        stats['total_coeff_sets'] = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT phase, COUNT(*) FROM species GROUP BY phase")
        stats['species_by_phase'] = dict(self.cursor.fetchall())
        
        self.cursor.execute("SELECT AVG(molecular_weight) FROM species WHERE molecular_weight IS NOT NULL")
        stats['avg_molecular_weight'] = self.cursor.fetchone()[0]
        
        return stats
    
    def find_species(self, name: str) -> List[Dict]:
        """Find species by name (supports partial search)"""
        pattern = f"%{name}%"
        self.cursor.execute("""
            SELECT id, name, formula, phase, molecular_weight, 
                   heat_of_formation_298K, num_intervals, comments
            FROM species
            WHERE name LIKE ? OR formula LIKE ?
            ORDER BY name
            LIMIT 20
        """, (pattern, pattern))
        
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
    
    def get_species_data(self, species_id: int) -> Dict:
        """Get complete data for a species with all its intervals"""
        
        # Species data
        self.cursor.execute("""
            SELECT * FROM species WHERE id = ?
        """, (species_id,))
        
        species_data = dict(zip([d[0] for d in self.cursor.description], 
                                self.cursor.fetchone()))
        
        # Intervals and coefficients
        self.cursor.execute("""
            SELECT ti.interval_number, ti.temp_min, ti.temp_max, ti.h_298_to_0,
                   c.a1, c.a2, c.a3, c.a4, c.a5, c.a6, c.a7, c.b1, c.b2
            FROM temperature_intervals ti
            LEFT JOIN coefficients c ON ti.id = c.interval_id
            WHERE ti.species_id = ?
            ORDER BY ti.interval_number
        """, (species_id,))
        
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
                    'b1': row[11], 'b2': row[12]
                }
            }
            intervals.append(interval)
        
        species_data['intervals'] = intervals
        return species_data
    
    def get_species_for_temperature(self, species_id: int, temperature: float) -> Dict:
        """Get valid coefficients for a specific temperature"""
        
        self.cursor.execute("""
            SELECT ti.interval_number, ti.temp_min, ti.temp_max,
                   c.a1, c.a2, c.a3, c.a4, c.a5, c.a6, c.a7, c.b1, c.b2
            FROM temperature_intervals ti
            LEFT JOIN coefficients c ON ti.id = c.interval_id
            WHERE ti.species_id = ? AND ti.temp_min <= ? AND ti.temp_max >= ?
            LIMIT 1
        """, (species_id, temperature, temperature))
        
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
                'b1': row[10], 'b2': row[11]
            }
        }
    
    def calculate_cp(self, coeffs: Dict, temperature: float) -> float:
        """Calculate Cp(T)/R using the coefficients"""
        T = temperature
        a = coeffs
        
        cp_r = (a['a1']/T**2 + a['a2']/T + a['a3'] + 
                a['a4']*T + a['a5']*T**2 + a['a6']*T**3 + a['a7']*T**4)
        
        return cp_r
    
    def calculate_h(self, coeffs: Dict, temperature: float) -> float:
        """Calculate H°(T)/RT using the coefficients"""
        T = temperature
        a = coeffs
        
        h_rt = (-a['a1']/T**2 + a['a2']*(1/T)**(1) + a['a3'] + 
                a['a4']*T/2 + a['a5']*T**2/3 + a['a6']*T**3/4 + 
                a['a7']*T**4/5 + a['b1']/T)
        
        # Fix ln(T) calculation that was omitted
        import math
        h_rt = (-a['a1']/T**2 + a['a2']*math.log(T) + a['a3'] + 
                a['a4']*T/2 + a['a5']*T**2/3 + a['a6']*T**3/4 + 
                a['a7']*T**4/5 + a['b1']/T)
        
        return h_rt
    
    def calculate_s(self, coeffs: Dict, temperature: float) -> float:
        """Calculate S°(T)/R using the coefficients"""
        T = temperature
        a = coeffs
        import math
        
        s_r = (-a['a1']/(2*T**2) - a['a2']/T + a['a3']*math.log(T) + 
               a['a4']*T + a['a5']*T**2/2 + a['a6']*T**3/3 + 
               a['a7']*T**4/4 + a['b2'])
        
        return s_r
    
    def list_species_page(self, page: int = 1, page_size: int = 20) -> Tuple[List[Dict], int]:
        """List species with pagination"""
        
        # Total species
        self.cursor.execute("SELECT COUNT(*) FROM species")
        total = self.cursor.fetchone()[0]
        
        offset = (page - 1) * page_size
        self.cursor.execute("""
            SELECT id, name, phase, molecular_weight, heat_of_formation_298K, num_intervals
            FROM species
            ORDER BY name
            LIMIT ? OFFSET ?
        """, (page_size, offset))
        
        columns = [d[0] for d in self.cursor.description]
        species = [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        
        total_pages = (total + page_size - 1) // page_size
        
        return species, total_pages

def main():
    """Usage examples"""
    print("="*70)
    print("THERMO.DB QUERY EXAMPLES")
    print("="*70)
    
    db = ThermoDBQuery()
    
    if not db.connect():
        return
    
    try:
        # 1. Statistics
        print("\n1. DATABASE STATISTICS:")
        print("-" * 70)
        stats = db.get_statistics()
        print(f"  Total species: {stats['total_species']}")
        print(f"  Total intervals: {stats['total_intervals']}")
        print(f"  Total coefficient sets: {stats['total_coeff_sets']}")
        print(f"  Species by phase: {stats['species_by_phase']}")
        print(f"  Average molecular weight: {stats['avg_molecular_weight']:.2f} g/mol")
        
        # 2. Search for species
        print("\n2. SPECIES SEARCH (name contains 'O2'):")
        print("-" * 70)
        species_list = db.find_species('O2')
        for sp in species_list[:5]:
            print(f"  ID: {sp['id']}, Name: {sp['name']}, Phase: {sp['phase']}, "
                  f"MW: {sp['molecular_weight']} g/mol")
        
        # 3. Complete species data
        if species_list:
            print("\n3. COMPLETE SPECIES DATA:")
            print("-" * 70)
            first_species = species_list[0]
            data = db.get_species_data(first_species['id'])
            print(f"  Name: {data['name']}")
            print(f"  Phase: {data['phase']}")
            print(f"  Molecular Weight: {data['molecular_weight']} g/mol")
            print(f"  Heat of Formation (298K): {data['heat_of_formation_298K']} J/mol")
            print(f"  Temperature Intervals: {len(data['intervals'])}")
            
            for interval in data['intervals'][:2]:
                print(f"\n  Interval {interval['interval_number']}: "
                      f"{interval['temp_min']}K - {interval['temp_max']}K")
                print(f"    Coefficients: a1={interval['coefficients']['a1']:.3e}, "
                      f"a3={interval['coefficients']['a3']:.6f}")
        
        # 4. Cp calculation
        print("\n4. CALCULATION EXAMPLE (Cp at 1000K):")
        print("-" * 70)
        if species_list:
            data = db.get_species_data(species_list[0]['id'])
            if data['intervals']:
                interval = data['intervals'][0]
                coeffs = interval['coefficients']
                T = 1000
                if T >= interval['temp_min'] and T <= interval['temp_max']:
                    cp_r = db.calculate_cp(coeffs, T)
                    print(f"  Species: {data['name']}")
                    print(f"  Temperature: {T} K")
                    print(f"  Cp(T)/R = {cp_r:.6f}")
                    print(f"  Cp(T) = {cp_r * 8.314:.3f} J/(mol·K)")
        
        # 5. Pagination
        print("\n5. FIRST PAGE OF SPECIES (20 items):")
        print("-" * 70)
        species_page, total_pages = db.list_species_page(page=1, page_size=20)
        for sp in species_page[:5]:
            print(f"  {sp['name']:20s} | Phase: {sp['phase']:10s} | "
                  f"MW: {sp['molecular_weight']:10.4f} g/mol")
        print(f"  ... (page 1 of {total_pages})")
        
        print("\n" + "="*70)
        print("[SUCCESS] Examples executed successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
