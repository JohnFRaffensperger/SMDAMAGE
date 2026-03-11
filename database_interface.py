#!/usr/bin/env python3
"""
Made by Claude with JFR's guidance. Database interface module for SMDAMAGE
Provides functions to query the SQLite database instead of reading CSV files directly
"""

import sqlite3
import os
import csv

# Database file name
DB_NAME = "smdamage_data.db"

def _execute_query(sql, params=None, db_path=None):
    """Execute SQL query and return results"""
    if db_path is None: db_path = DB_NAME
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database '{db_path}' not found. Run create_database.py first.")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if params: cursor.execute(sql, params)
    else: cursor.execute(sql)
    result = cursor.fetchall()
    conn.close()
    return result

def _execute_insert(sql, params=None, db_path=None):
    """Execute SQL insert/update/delete statements"""
    if db_path is None: db_path = DB_NAME
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database '{db_path}' not found. Run create_database.py first.")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if params: cursor.execute(sql, params)
    else: cursor.execute(sql)
    conn.commit()
    conn.close()

def add_bidder(bidder_name, csv_filename, bidder_class='Emitter', units='mtC', contract_years=1, hector_name='ffi_emissions', description=''):
    """Add bidder data from CSV file to database
    
    Args:
        bidder_name: Name of the bidder to add
        csv_filename: Path to CSV file with bid data (price, quantity format)
        bidder_class: Bidder class - 'Emitter' or 'Remover' (default: 'Emitter')
        units: Units for the bidder (default: 'mtC')
        contract_years: Contract duration in years (default: 1)
        hector_name: Associated hector name (default: 'ffi_emissions')
        description: Description of the bidder (default: '')
    """
    if not os.path.exists(csv_filename):
        raise FileNotFoundError(f"CSV file '{csv_filename}' not found")
    
    # First, add bidder to bidders table with all columns if not exists  
    try:
        _execute_insert(
            "INSERT INTO bidders (bidder, class, units, contract_years, hector_name, description) VALUES (?, ?, ?, ?, ?, ?)", 
            (bidder_name, bidder_class, units, contract_years, hector_name, description)
        )
        print(f"Added new bidder: {bidder_name} (class={bidder_class}, units={units}, contract_years={contract_years}, hector_name={hector_name})")
    except sqlite3.IntegrityError:
        print(f"Bidder '{bidder_name}' already exists")
    
    # Read CSV file and insert bid data
    with open(csv_filename, 'r') as file:
        csv_reader = csv.reader(file)
        header = next(csv_reader)  # Skip header row
        
        bid_count = 0
        for row in csv_reader:
            if len(row) >= 2:
                price_per_unit = float(row[0])
                quantity_units = float(row[1])
                
                _execute_insert(
                    "INSERT INTO bids (bidder, price_per_unit, quantity_units) VALUES (?, ?, ?)",
                    (bidder_name, price_per_unit, quantity_units)
                )
                bid_count += 1
        
        print(f"Inserted {bid_count} bid records for {bidder_name}")

# add_bidder('Agriculture', 'Data/Agriculture_bids.csv', bidder_class='Emitter', units='mtC',  description='Agricultural carbon mitigation') 

def get_bids(bidder_name):
    """Get bid data for any bidder from the bids table
    Args: bidder_name: Name of the bidder (must exist in bidders table)
    Returns: List of tuples with bid data (price_per_unit, quantity_units)
    """
    # First, check if bidder exists
    bidder_info = _execute_query("SELECT bidder FROM bidders WHERE bidder = ?", (bidder_name,))
    if not bidder_info: raise ValueError(f"Bidder '{bidder_name}' not found in bidders table")
    return _execute_query("SELECT price_per_unit, quantity_units FROM bids WHERE bidder = ? ORDER BY id", (bidder_name,))

def get_warming_factors(hector_name):
    """Get warming factor data for a specific hector chemical"""
    results = _execute_query("SELECT emission_factor, hector_units, * FROM warming_factors WHERE hector_name = ?", (hector_name,))
    
    if results:
        result = results[0]  # Take first record
        emission_factor = result[0]
        hector_units = result[1]
        data_values = list(result[2:])  # All the year_xxx columns as a list
        
        return {'emission_factor': emission_factor, 'hector_units': hector_units, 'data_values': data_values}
    else: return None

def get_hector_names():
    """Get list of all hector names in warming factor data"""
    results = _execute_query ("SELECT DISTINCT hector_name FROM warming_factors")
    return [row[0] for row in results]

def get_forestry_carbon_removal(bidder):
    """Get forestry removal data for a specific bidder"""
    return _execute_query ("SELECT bidder, year, tons_per_hectare_per_year FROM forestry_removal WHERE bidder = ? ORDER BY year", (bidder,))

def get_forestry_bidder_names():
    """Get list of all forestry bidders in removal data"""
    results = _execute_query ("SELECT DISTINCT bidder FROM forestry_removal ORDER BY bidder")
    return [row[0] for row in results]

# Test and demonstration functions
def test_database_queries():
    """Test all database query functions"""
    print("🧪 Testing SMDAMAGE Database Queries")
    print("=" * 40)
    
    try:
        # Test unified bids function
        print("\n🌾 Agriculture bids (first 3):")
        ag_bids = get_bids('Agriculture')
        for i, (price, qty) in enumerate(ag_bids[:3]):
            print(f"  • Bid {i+1}: ${price:.2f}/MgtonC, {qty:.2f} MgtonC")
        
        print("\n⚫ Carbon bids (first 3):")
        carbon_bids = get_bids('Carbon')
        for i, (price, qty) in enumerate(carbon_bids[:3]):
            print(f"  • Bid {i+1}: ${price:.2f}/ton, {qty:.2f} Mtons")
        
        print("\n🧪 Chemical bids (C2F6 first 3):")
        c2f6_bids = get_bids('C2F6')
        for i, (price, qty) in enumerate(c2f6_bids[:3]):
            print(f"  • Bid {i+1}: ${price:.2f}/kt, {qty:.2f} kt/year")
        
        print("\n🌊 Seaweed bids (first 3):")
        seaweed_bids = get_bids('Seaweed')
        for i, (price, qty) in enumerate(seaweed_bids[:3]):
            print(f"  • Bid {i+1}: ${price:.2f}/mtC, {qty:.2f} mtC/year")
        
        # Test forestry removal function
        print("\n🌲 Forestry removal - Loblolly 150yr (years 0-5):")
        forestry_seq = get_forestry_carbon_removal('Loblolly_pine_150')
        for row in forestry_seq[:6]:
            bidder = row[0]
            year = row[1]
            tons_per_hectare = row[2]
            print(f"  • Year {year}: {tons_per_hectare:.3f} tons/ha/year")
        
        # Test warming factors
        print("\n🌡️ Warming factors (first 3 chemicals):")
        hector_names = get_hector_names()[:3]
        for chemical in hector_names:
            data = get_warming_factors(chemical)
            print(f"  • {chemical}: {data['emission_factor']} {data['hector_units']}")
        
        print("\n✅ All database queries working correctly!")
        
    except Exception as e:
        print(f"❌ Error testing database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database_queries()