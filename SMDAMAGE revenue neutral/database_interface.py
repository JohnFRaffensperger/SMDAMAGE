#!/usr/bin/env python3
"""
Database interface module for SMDAMAGE. Made by Claude with JFR's guidance.
"""
import sqlite3
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(SCRIPT_DIR, "smdamage_data.db")  # Database in same directory as script

def database_exists(): return os.path.exists(DB_NAME)

def do_insert(sql, params=None):
	if not os.path.exists(DB_NAME): raise FileNotFoundError(f"Database '{DB_NAME}' not found. Run create_database.py first.")
	conn = sqlite3.connect(DB_NAME)
	cursor = conn.cursor()
	if params: cursor.execute(sql, params)
	else: cursor.execute(sql)
	conn.commit()
	conn.close()

def do_query(sql, params=None):
	"""Do the SQL query and return results"""
	if not os.path.exists(DB_NAME):
		raise FileNotFoundError(f"Database '{DB_NAME}' not found. Run create_database.py first.")
	conn = sqlite3.connect(DB_NAME)
	cursor = conn.cursor()
	if params: cursor.execute(sql, params)
	else: cursor.execute(sql)
	result = cursor.fetchall()
	conn.close()
	return result

def get_bidders():
	rows = do_query("SELECT id, bidder, class, units, contract_years, hector_name, description FROM bidders ORDER BY bidder collate nocase")
	columns = ["id", "bidder_name", "class", "units", "contract_years", "hector_name", "description"]
	return [dict(zip(columns, row)) for row in rows]
# return do_query("SELECT * FROM bidders ORDER BY bidder collate nocase")
# print(get_bidders())

def get_bids(bidder_name):
	return do_query("SELECT price_per_unit, quantity_units FROM bids WHERE bidder = ? ORDER BY id", (bidder_name,))
# ag_bids = get_bids('Agriculture')
# for i, (price, qty) in enumerate(ag_bids[:3]): print(f"  • Bid {i+1}: ${price:.2f}/MgtonC, {qty:.2f} MgtonC")

def get_forestry_bidder_names():
	results = do_query ("SELECT DISTINCT bidder FROM forestry_removal ORDER BY bidder collate nocase")
	return [row[0] for row in results] # Otherwise you get a list of tuples like [('Loblolly_pine_150',), ('Loblolly_pine_300',), ...]
# print(get_forestry_bidder_names())

def get_forestry_carbon_removal(bidder):
	return do_query ("SELECT year, tons_per_hectare_per_year FROM forestry_removal WHERE bidder = ? ORDER BY year", (bidder,))
# forestry_seq = get_forestry_carbon_removal('Loblolly_pine_150')
# for row in forestry_seq[:6]: print(row)

def get_hector_names():
	results = do_query ("SELECT DISTINCT hector_name FROM warming_factors order by hector_name collate nocase")
	return [row[0] for row in results]
# print (get_hector_names())

def get_warming_factors(hector_name): # For forestry, you must do the convolution of carbon removal to warming over time.
	results = do_query("SELECT emission_factor, hector_units, * FROM warming_factors WHERE hector_name = ?", (hector_name,))

	result = results[0]
	data_values = list(result[2:])  # All year columns as a list
	# You should normalize data_values by emission_factor: data_values = [val / emission_factor for val in data_values].
	return {'emission_factor': result[0], 'hector_units': result[1], 'data_values': data_values}
# print(get_warming_factors('ffi_emissions'))

def show_database_info():
	tables = do_query("SELECT name FROM sqlite_master WHERE type='table'")
	print(f"Database '{DB_NAME}' has {len(tables)} tables:")
	for table in tables:
		result = do_query(f"SELECT COUNT(*) FROM {table[0]}")
		print(f"{table[0]}: {result[0][0]} records")
# show_database_info()
