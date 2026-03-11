#!/usr/bin/env python3
"""
Produced by Claude. Create SQLite database for SMDAMAGE CSV data
Converts all CSV files in the Data directory to organized database tables
"""

import sqlite3
import csv
import os
import sys

# Import functions for bidders data
sys.path.append("./SMDAMAGE revenue neutral")
from defaults_and_utilities import getEmitters, getRemovers, getUnits

# Database file name
DB_NAME = "smdamage_data.db"
DATA_DIR = "Data"

def create_database():
    """Create the SQLite database and populate with CSV data"""
    
    # Connect to database (creates if doesn't exist)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create tables
    create_tables(cursor)
    
    # Load CSV data into tables
    load_csv_data(cursor, conn)
    
    # Create indices for better performance
    create_indices(cursor)
    
    conn.commit()
    conn.close()
    
    print(f"Database '{DB_NAME}' created successfully!")

def create_tables(cursor):
    """Create all database tables"""
    
    # Unified Bids table - replaces all individual *_bids tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder TEXT,
            price_per_unit REAL,
            quantity_units REAL,
            FOREIGN KEY (bidder) REFERENCES bidders(bidder)
        )
    ''')
    
    # Forestry removal table - normalized structure
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forestry_removal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder TEXT NOT NULL,
            year INTEGER NOT NULL,
            tons_per_hectare_per_year REAL NOT NULL
        )
    ''')
    
    # Warming factors table (formerly chemical_pulses) - with individual columns for each data value
    # Create columns for 296 data values (year_001 to year_296)
    data_columns = ', '.join([f'year_{i:03d} REAL' for i in range(1, 297)])
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS warming_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hector_name TEXT,
            emission_factor REAL,
            hector_units TEXT,
            {data_columns}
        )
    ''')
    
    # Bidders table - contains all emitters and removers with their properties
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bidders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bidder TEXT UNIQUE,
            class TEXT,
            units TEXT,
            contract_years INTEGER,
            hector_name TEXT,
            description TEXT
        )
    ''')

def load_csv_data(cursor, conn):
    """Load data from CSV files into unified bids table"""
    
    # Load Agriculture bids
    try:
        with open(os.path.join(DATA_DIR, 'Agriculture_bids.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                cursor.execute('''
                    INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                    VALUES (?, ?, ?)
                ''', ('Agriculture', float(row[0]), float(row[1])))
        print("✓ Loaded Agriculture_bids.csv")
    except FileNotFoundError:
        print("⚠ Agriculture_bids.csv not found")
    
    # Load Carbon bids
    try:
        with open(os.path.join(DATA_DIR, 'MtC_bid_steps.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                cursor.execute('''
                    INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                    VALUES (?, ?, ?)
                ''', ('Carbon', float(row[0]), float(row[1])))
        print("✓ Loaded MtC_bid_steps.csv")
    except FileNotFoundError:
        print("⚠ MtC_bid_steps.csv not found")
    
    # Load Seaweed bids
    try:
        with open(os.path.join(DATA_DIR, 'Seaweed_bids.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                cursor.execute('''
                    INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                    VALUES (?, ?, ?)
                ''', ('Seaweed', float(row[0]), float(row[1])))
        print("✓ Loaded Seaweed_bids.csv")
    except FileNotFoundError:
        print("⚠ Seaweed_bids.csv not found")
    
    # Load Chemical bids (decomposed into individual chemical bidders)
    try:
        with open(os.path.join(DATA_DIR, 'C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            
            # Chemical names and their column positions (price, quantity pairs)
            chemicals_info = [
                ('C2F6', 0, 1),
                ('CF4', 2, 3),
                ('HFC125', 4, 5),
                ('HFC134a', 6, 7),
                ('HFC143a', 8, 9),
                ('SF6', 10, 11)
            ]
            
            for row in reader:
                for chemical_name, price_col, qty_col in chemicals_info:
                    cursor.execute('''
                        INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                        VALUES (?, ?, ?)
                    ''', (chemical_name, float(row[price_col]), float(row[qty_col])))
        
        print("✓ Loaded C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv (decomposed)")
    except FileNotFoundError:
        print("⚠ C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv not found")
    
    # Load CH4 bids
    try:
        with open(os.path.join(DATA_DIR, 'CH4_bid_steps.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                cursor.execute('''
                    INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                    VALUES (?, ?, ?)
                ''', ('CH4', float(row[0]), float(row[1])))
        print("✓ Loaded CH4_bid_steps.csv")
    except FileNotFoundError:
        print("⚠ CH4_bid_steps.csv not found")
    
    # Load N2O bids
    try:
        with open(os.path.join(DATA_DIR, 'N2O_bid_steps.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                cursor.execute('''
                    INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                    VALUES (?, ?, ?)
                ''', ('N2O', float(row[0]), float(row[1])))
        print("✓ Loaded N2O_bid_steps.csv")
    except FileNotFoundError:
        print("⚠ N2O_bid_steps.csv not found")
    
    # Load Forestry bids - create separate bid entries for each tree type/contract combination
    try:
        with open(os.path.join(DATA_DIR, 'Forestry_bid_steps.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                # Extract values for each tree type and contract duration
                plantable_mhectares = float(row[0])
                loblolly_150 = float(row[1])
                ponderosa_150 = float(row[2])
                black_walnut_150 = float(row[3])
                loblolly_10 = float(row[4])
                ponderosa_10 = float(row[5])
                black_walnut_10 = float(row[6])
                loblolly_24 = float(row[7])
                ponderosa_103 = float(row[8])
                black_walnut_55 = float(row[9])
                
                # Create bid entries for each forestry option
                forestry_bids = [
                    ('Loblolly_pine_150', loblolly_150),
                    ('Ponderosa_pine_150', ponderosa_150),
                    ('Black_walnut_150', black_walnut_150),
                    ('Loblolly_pine_10', loblolly_10),
                    ('Ponderosa_pine_10', ponderosa_10),
                    ('Black_walnut_10', black_walnut_10),
                    ('Loblolly_pine_24', loblolly_24),
                    ('Ponderosa_pine_103', ponderosa_103),
                    ('Black_walnut_55', black_walnut_55)
                ]
                
                for bidder_name, price_per_hectare in forestry_bids:
                    cursor.execute('''
                        INSERT INTO bids (bidder, price_per_unit, quantity_units) 
                        VALUES (?, ?, ?)
                    ''', (bidder_name, price_per_hectare, plantable_mhectares))
                    
        print("✓ Loaded Forestry_bid_steps.csv (decomposed into individual bidders)")
    except FileNotFoundError:
        print("⚠ Forestry_bid_steps.csv not found")
    
    # Load Forestry removal (unchanged)
    try:
        with open(os.path.join(DATA_DIR, 'Forestry_sequestration.csv'), 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            
            # Column mapping: CSV column index -> (bidder_name, description)
            column_mappings = [
                (1, 'Loblolly_pine_150', 'Loblolly pine 150yr'),
                (2, 'Ponderosa_pine_150', 'Ponderosa pine 150yr'), 
                (3, 'Black_walnut_150', 'Black walnut 150yr'),
                (4, 'Loblolly_pine_10', 'Loblolly pine 10yr'),
                (5, 'Ponderosa_pine_10', 'Ponderosa pine 10yr'),
                (6, 'Black_walnut_10', 'Black walnut 10yr'),
                (7, 'Loblolly_pine_24', 'Loblolly pine 24yr'),
                (8, 'Ponderosa_pine_103', 'Ponderosa pine 103yr'),
                (9, 'Black_walnut_55', 'Black walnut 55yr')
            ]
            
            for row in reader:
                year = int(row[0])
                # Transform wide format to long format - one row per bidder per year
                for col_idx, bidder_name, description in column_mappings:
                    tons_per_hectare = float(row[col_idx])
                    cursor.execute('''
                        INSERT INTO forestry_removal 
                        (bidder, year, tons_per_hectare_per_year) 
                        VALUES (?, ?, ?)
                    ''', (bidder_name, year, tons_per_hectare))
        print("✓ Loaded Forestry_sequestration.csv (normalized to long format into forestry_removal table)")
    except FileNotFoundError:
        print("⚠ Forestry_sequestration.csv not found")
    
    # Load Chemical pulses (unchanged) - split data values into individual columns
    try:
        with open(os.path.join(DATA_DIR, 'Calibrated_pulses_by_chemical_2025.txt'), 'r') as f:
            for line in f:
                if line.strip():  # Skip empty lines
                    parts = line.strip().split(',')
                    if len(parts) > 3:  # Ensure we have enough parts
                        chemical_name = parts[0]
                        emission_factor = float(parts[1])
                        units = parts[2]
                        data_values = [float(val) for val in parts[3:]]  # Convert to individual float values
                        
                        # Pad with zeros if we have fewer than 296 values
                        while len(data_values) < 296:
                            data_values.append(0.0)
                        
                        # Create column names and values for insertion
                        year_columns = ', '.join([f'year_{i:03d}' for i in range(1, 297)])
                        placeholders = ', '.join(['?' for _ in range(296)])
                        
                        cursor.execute(f'''
                            INSERT INTO warming_factors 
                            (hector_name, emission_factor, hector_units, {year_columns}) 
                            VALUES (?, ?, ?, {placeholders})
                        ''', (chemical_name, emission_factor, units, *data_values))
        print("✓ Loaded Calibrated_pulses_by_chemical_2025.txt (decomposed into individual columns)")
    except FileNotFoundError:
        print("⚠ Calibrated_pulses_by_chemical_2025.txt not found")

    # Load Bidders data from defaults_and_utilities functions (unchanged)
    try:
        units_dict = getUnits()
        
        def get_hector_name(bidder_name, is_emitter):
            """Map bidder names to Hector chemical names"""
            # Mapping based on hector_interface.py lines 95-98
            hector_mapping = {
                # Emitters - match to specific chemical emissions
                'Carbon': 'ffi_emissions',
                'CH4': 'CH4_emissions',
                'N2O': 'N2O_emissions',
                'C2F6': 'C2F6_emissions',
                'CF4': 'CF4_emissions', 
                'HFC125': 'HFC125_emissions',
                'HFC134a': 'HFC134a_emissions',
                'HFC143a': 'HFC143a_emissions',
                'SF6': 'SF6_emissions'
            }
            
            if bidder_name in hector_mapping:
                return hector_mapping[bidder_name]
            elif not is_emitter:
                # All removers (agriculture, seaweed, forestry) map to ffi_emissions
                return 'ffi_emissions'
            else:
                return None  # Unknown emitter
        
        # Add all emitters (all have 1-year contracts)
        for emitter in getEmitters():
            units = units_dict.get(emitter, 'unknown')
            hector_name = get_hector_name(emitter, True)
            cursor.execute('''
                INSERT OR IGNORE INTO bidders (bidder, class, units, contract_years, hector_name, description) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (emitter, 'Emitter', units, 1, hector_name, ''))
        
        # Add all removers with appropriate contract years
        for remover in getRemovers():
            units = units_dict.get(remover, 'unknown')
            hector_name = get_hector_name(remover, False)
            
            # Extract contract years from name for forestry items
            contract_years = 1  # Default for Agriculture and Seaweed
            if remover not in ['Agriculture', 'Seaweed']:
                # Extract number from names like "Loblolly_pine_150", "Black_walnut_55", etc.
                parts = remover.split('_')
                for part in reversed(parts):  # Check from end to find the number
                    if part.isdigit():
                        contract_years = int(part)  
                        break
            
            cursor.execute('''
                INSERT OR IGNORE INTO bidders (bidder, class, units, contract_years, hector_name, description) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (remover, 'Remover', units, contract_years, hector_name, ''))
        
        print("✓ Loaded bidders data from defaults_and_utilities functions")
    except Exception as e:
        print(f"⚠ Error loading bidders data: {e}")

def create_indices(cursor):
    """Create database indices for better performance"""
    
    # Create indices on frequently queried columns
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bids_bidder ON bids(bidder)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bids_price ON bids(price_per_unit)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_warming_factors_hector_name ON warming_factors(hector_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder ON forestry_removal(bidder)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_forestry_seq_year ON forestry_removal(year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder_year ON forestry_removal(bidder, year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bidders_name ON bidders(bidder)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bidders_class ON bidders(class)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bidders_contract_years ON bidders(contract_years)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bidders_hector_name ON bidders(hector_name)')
    
    print("✓ Created database indices")

def show_database_info():
    """Display information about the created database"""
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n📊 Database '{DB_NAME}' contains {len(tables)} tables:")
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  • {table_name}: {count} records")
    
    conn.close()

if __name__ == "__main__":
    print("🗄️  Creating SMDAMAGE SQLite Database")
    print("=" * 40)
    
    # Change to the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check if Data directory exists
    if not os.path.exists(DATA_DIR):
        print(f"❌ Error: '{DATA_DIR}' directory not found!")
        print(f"   Make sure this script is in the same directory as the '{DATA_DIR}' folder.")
        sys.exit(1)
    
    # Create the database
    create_database()
    
    # Show database information
    show_database_info()
    
    print("\n✅ Database creation complete!")
    print(f"\n💡 You can now query the database using:")
    print(f"   conn = sqlite3.connect('{DB_NAME}')")
    print("   cursor = conn.cursor()")
    print("   cursor.execute('SELECT * FROM agriculture_bids LIMIT 5')")