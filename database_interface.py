#!/usr/bin/env python3
"""
Made by Claude with JFR's guidance. Database interface module for SMDAMAGE
Provides functions to query the SQLite database instead of reading CSV files directly
"""

import sqlite3
import os

# Database file name
DB_NAME = "smdamage_data.db"

class SmdamageDataDB:
    """Class to handle database connections and queries for SMDAMAGE data"""
    
    def __init__(self, db_path=None):
        """Initialize database connection"""
        if db_path is None:
            db_path = DB_NAME
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database '{db_path}' not found. Run create_database.py first.")
        
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_bids(self, bidder_name):
        """Get bid data for any bidder from the unified bids table
        
        Args:
            bidder_name: Name of the bidder (must exist in bidders table)
            
        Returns:
            List of tuples with bid data (price_per_unit, quantity_units)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # First, check if bidder exists
        cursor.execute("SELECT bidder FROM bidders WHERE bidder = ?", (bidder_name,))
        bidder_info = cursor.fetchone()
        
        if not bidder_info:
            conn.close()
            raise ValueError(f"Bidder '{bidder_name}' not found in bidders table")
        
        # Get bid data from unified bids table
        cursor.execute('''
            SELECT price_per_unit, quantity_units 
            FROM bids 
            WHERE bidder = ? 
            ORDER BY id
        ''', (bidder_name,))
        
        data = cursor.fetchall()
        conn.close()
        return data
    
    def get_warming_factors(self, hector_name):
        """Get warming factor data for a specific hector chemical"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query to select all year columns
        year_columns = ', '.join([f'year_{i:03d}' for i in range(1, 297)])
        
        cursor.execute(f"""
            SELECT emission_factor, hector_units, {year_columns}
            FROM warming_factors 
            WHERE hector_name = ?
        """, (hector_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            emission_factor = result[0]
            hector_units = result[1]
            data_values = list(result[2:])  # All the year_xxx columns as a list
            
            return {
                'emission_factor': emission_factor,
                'hector_units': hector_units,
                'data_values': data_values
            }
        else:
            return None
    
    def get_hector_names(self):
        """Get list of all hector names in warming factor data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT hector_name FROM warming_factors")
        names = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return names
    
    def get_forestry_removal(self, bidder, year=None):
        """Get forestry removal data for a specific bidder, optionally filtered by year"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT bidder, year, tons_per_hectare_per_year FROM forestry_removal"
        params = [bidder]
        conditions = ["bidder = ?"]
        
        if year:
            conditions.append("year = ?") 
            params.append(year)
            
        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY year"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_all_forestry_bidders(self):
        """Get list of all forestry bidders in removal data"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT bidder FROM forestry_removal ORDER BY bidder")
        bidders = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return bidders
    
    def query_custom(self, sql_query, params=None):
        """Execute a custom SQL query"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(sql_query, params)
        else:
            cursor.execute(sql_query)
        
        data = cursor.fetchall()
        conn.close()
        
        return data
    
    def get_database_info(self):
        """Get information about database tables and record counts"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        info = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            info[table_name] = count
        
        conn.close()
        return info

# Global database instance (singleton pattern)
_db_instance = None

def get_db():
    """Get the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = SmdamageDataDB()
    return _db_instance

# Test and demonstration functions
def test_database_queries():
    """Test all database query functions"""
    print("🧪 Testing SMDAMAGE Database Queries")
    print("=" * 40)
    
    try:
        db = get_db()
        
        # Test database info
        print("📊 Database Info:")
        info = db.get_database_info()
        for table, count in info.items():
            print(f"  • {table}: {count} records")
        
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
        forestry_seq = get_forestry_removal_data('Loblolly_pine_150')
        for row in forestry_seq[:6]:
            bidder = row[0]
            year = row[1]
            tons_per_hectare = row[2]
            print(f"  • Year {year}: {tons_per_hectare:.3f} tons/ha/year")
        
        # Test warming factors
        print("\n🌡️ Warming factors (first 3 chemicals):")
        hector_names = get_all_hector_names()[:3]
        for chemical in hector_names:
            data = get_warming_factor_data(chemical)
            print(f"  • {chemical}: {data['emission_factor']} {data['hector_units']}")
        
        print("\n✅ All database queries working correctly!")
        
    except Exception as e:
        print(f"❌ Error testing database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database_queries()