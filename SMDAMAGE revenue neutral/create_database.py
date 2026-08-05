#!/usr/bin/env python3
"""
Create SQLite database for SMDAMAGE CSV data. Produced by Claude with JFR's guidance. 21 July 3036.
"""
# >>> Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. SMDAMAGE: "smdamage_models.py"
# Part IV. Running Hector on SMDAMAGE output. hector_interface.py.
# =============================================================================================
# Source data files. Create these files first. The function create_database() loads these to the SMDAMAGE database.
# ../data/Calibrated_pulses_by_chemical_2025.txt. Create this with Hector.
# Following are all from "Sources of data for SMDAMAGE 2026.xlsx":
# ../data/Forestry_Sequestration.csv, Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
# ../data/Forestry_bid_steps.csv, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
# ../data/MtC_bid_steps.csv,
# ../data/C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv,
# ../data/CH4_bid_steps.csv,
# ../data/N2O_bid_steps.csv,
# ../data/Agriculture_bids.csv,
# ../data/Seaweed_bids.csv.

import csv
import os
import sqlite3
import sys

# sys.path.append("..")  # Add parent directory to find database_interface.py
from database_interface import DB_NAME, database_exists, do_insert, do_query, show_database_info

DATA_DIR = "../Data" # Holds all the CSV files with bidder and warming factor data. Make sure this directory exists and contains the necessary CSV files before running this script.
CHEMICAL_PULSES_FILE = 'Calibrated_pulses_by_chemical_2025.txt' # Make this with Hector.
BUSCH_DB_DEFAULT = r"C:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\Busch2024\Output\Databases\Busch2024_to_SMDAMAGE.sqlite"
BUSCH_DB_ENV_VAR = "BUSCH_SMDAMAGE_SQLITE"

# Simple bidders can be loaded directly with add_bidder
SIMPLE_BIDDERS = [
	{'bidder_name': 'Agriculture', 'csv_filename': 'Agriculture_bids.csv', 'bidder_class': 'Remover', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Agricultural carbon mitigation'},
	{'bidder_name': 'Seaweed', 'csv_filename': 'Seaweed_bids.csv', 'bidder_class': 'Remover', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Seaweed carbon removal'},
	{'bidder_name': 'Carbon', 'csv_filename': 'MtC_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Carbon emissions'},
	{'bidder_name': 'CH4', 'csv_filename': 'CH4_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mt', 'contract_years': 1, 'hector_name': 'CH4_emissions', 'description': 'Methane emissions'},
	{'bidder_name': 'N2O', 'csv_filename': 'N2O_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mt', 'contract_years': 1, 'hector_name': 'N2O_emissions', 'description': 'Nitrous oxide emissions'}
]

# Multi-column CSV files. The multi-column CSV is convenient but requires special handling to split into individual bidders with their own price and quantity columns.
MULTI_COLUMN_BIDDERS = {'chemicals': {
		'csv_filename': 'C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv',
		'shared_quantity_col': None,  # Each bidder has its own quantity column
		'bidders': [
			{'name': 'C2F6', 'price_col': 0, 'qty_col': 1, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'C2F6_emissions'},
			{'name': 'CF4', 'price_col': 2, 'qty_col': 3, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'CF4_emissions'},
			{'name': 'HFC125', 'price_col': 4, 'qty_col': 5, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'HFC125_emissions'},
			{'name': 'HFC134a', 'price_col': 6, 'qty_col': 7, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'HFC134a_emissions'},
			{'name': 'HFC143a', 'price_col': 8, 'qty_col': 9, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'HFC143a_emissions'},
			{'name': 'SF6', 'price_col': 10, 'qty_col': 11, 'bidder_class': 'Emitter', 'units': 'kt', 'contract_years': 1, 'hector_name': 'SF6_emissions'}
		]
	}
}

def create_database():
	"""Create the SQLite database and populate with CSV data"""
	# Check if database already exists
	if database_exists():
		print(f"❌ Database already exists. Delete it first or use a different name.")
		sys.exit(1)

	# Bootstrap an empty SQLite file so database_interface.do_query can run CREATE statements.
	sqlite3.connect(DB_NAME).close()

	# Warming data
	data_columns = ', '.join([f'year_{i:03d} REAL' for i in range(1, 297)]) # Warming factors table, 296 data values (year_001 to year_296).
	do_query(f'''CREATE TABLE IF NOT EXISTS warming_factors (id INTEGER PRIMARY KEY AUTOINCREMENT, hector_name TEXT, emission_factor REAL, hector_units TEXT, {data_columns})''')
	do_query('CREATE INDEX IF NOT EXISTS idx_warming_factors_hector_name ON warming_factors(hector_name)')
	load_chemical_pulses() # originally from Hector.

	# Bidders
	do_query('''CREATE TABLE IF NOT EXISTS bidders (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT UNIQUE, class TEXT, units TEXT, contract_years INTEGER, hector_name TEXT, description TEXT)''')
	do_query('CREATE INDEX IF NOT EXISTS idx_bidders_name ON bidders(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bidders_class ON bidders(class)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bidders_contract_years ON bidders(contract_years)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bidders_hector_name ON bidders(hector_name)')

	# Bids
	do_query('''CREATE TABLE IF NOT EXISTS bids (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT, price_per_unit REAL, quantity_units REAL, discount_rate REAL, FOREIGN KEY (bidder) REFERENCES bidders(bidder))''')
	do_query('CREATE INDEX IF NOT EXISTS idx_bids_bidder ON bids(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bids_price ON bids(price_per_unit)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bids_discount_rate ON bids(discount_rate)')

	load_simple_bidders()
	load_multi_column_bidders('chemicals')

	# Forestry carbon removal.
	do_query('''CREATE TABLE IF NOT EXISTS forestry_removal (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT NOT NULL, year INTEGER NOT NULL, tons_per_hectare_per_year REAL NOT NULL)''')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder ON forestry_removal(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_year ON forestry_removal(year)')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder_year ON forestry_removal(bidder, year)')

	# Forestry bidder metadata: explicit max area and cluster mapping.
	do_query('''CREATE TABLE IF NOT EXISTS forestry_bidder_metadata (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT UNIQUE NOT NULL, rotation_year INTEGER NOT NULL, cluster_index INTEGER NOT NULL, available_area_mhectares REAL NOT NULL, FOREIGN KEY (bidder) REFERENCES bidders(bidder))''')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_meta_bidder ON forestry_bidder_metadata(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_meta_rotation_cluster ON forestry_bidder_metadata(rotation_year, cluster_index)')
	load_forestry_from_busch_sqlite()

	# Create indexes for faster queries
	print(f"Database created and populated with data.")

def add_bidder_and_bids(bidder_name, csv_filename, bidder_class='Emitter', units='mtC', contract_years=1, hector_name='ffi_emissions', description=''):
	"""Add bidder data from CSV file to database

	Args:
		bidder_name: Name of the bidder to add.
		csv_filename: Path to CSV file with bid data (price, quantity format).
		bidder_class: Bidder class - 'Emitter' or 'Remover' (default: 'Emitter').
		units: Units for the bidder (default: 'mtC').
		contract_years: Contract duration in years (default: 1).
		hector_name: Associated hector name (default: 'ffi_emissions').
		description: Description of the bidder (default: '').
	"""
	if not os.path.exists(csv_filename): raise FileNotFoundError(f"CSV file '{csv_filename}' not found.")

	do_insert("INSERT INTO bidders (bidder, class, units, contract_years, hector_name, description) VALUES (?, ?, ?, ?, ?, ?)",
		(bidder_name, bidder_class, units, contract_years, hector_name, description))

	# Add the bids
	with open(csv_filename, 'r') as file:
		csv_reader = csv.reader(file)
		header = next(csv_reader)  # Skip header row

		bid_count = 0
		total_price = 0.0 # Check that removers have negative prices and emitters have positive prices.
		for row in csv_reader:
			if len(row) >= 2:
				price_per_unit = float(row[0])
				quantity_units = float(row[1])
				do_insert("INSERT INTO bids (bidder, price_per_unit, quantity_units, discount_rate) VALUES (?, ?, ?, ?)", (bidder_name, price_per_unit, quantity_units, None))
				total_price += price_per_unit
				bid_count += 1
		if total_price > 0 and bidder_class.lower() == 'remover': print(f"Warning: you classified Bidder '{bidder_name}' as a 'Remover' but their prices are positive, total {total_price:.2f}. Check the CSV data.")
		elif total_price < 0 and bidder_class.lower() == 'emitter': print(f"Warning: you classified Bidder '{bidder_name}' as an 'Emitter' but their prices are negative, total {total_price:.2f}. Check the CSV data.")
		print(f"Inserted {bid_count} bid records for {bidder_name}")

def load_simple_bidders():
	"""Load simple bidders (agriculture, seaweed, carbon, CH4, N2O) using add_bidder function"""
	for bidder_config in SIMPLE_BIDDERS:
		try: add_bidder_and_bids (bidder_name=bidder_config['bidder_name'],
				csv_filename=os.path.join(DATA_DIR, bidder_config['csv_filename']),
				bidder_class=bidder_config['bidder_class'],
				units=bidder_config['units'],
				contract_years=bidder_config['contract_years'],
				hector_name=bidder_config['hector_name'],
				description=bidder_config['description'])
		except FileNotFoundError: print(f"⚠ {bidder_config['csv_filename']} not found")
		except Exception as e: print(f"⚠ Error loading {bidder_config['bidder_name']} bids: {e}")

def load_multi_column_bidders(config_key):
	"""Load bidders from multi-column CSV files using configuration"""
	config = MULTI_COLUMN_BIDDERS[config_key]
	csv_filename = config['csv_filename']
	shared_quantity_col = config['shared_quantity_col']
	bidders = config['bidders']

	try: # First read the multi-column CSV file
		with open(os.path.join(DATA_DIR, csv_filename), 'r') as f:
			reader = csv.reader(f)
			header = next(reader)  # Skip header
			rows = list(reader)  # Read all data rows

		for bidder in bidders: # Process each bidder in the configuration
			bidder_data = []
			for row in rows:
				price_col = bidder['price_col']
				qty_col = bidder['qty_col'] if bidder['qty_col'] is not None else shared_quantity_col

				if len(row) > max(price_col, qty_col):
					price = float(row[price_col])
					quantity = float(row[qty_col])
					bidder_data.append([price, quantity])

			if bidder_data: # Create temporary CSV file for this bidder
				temp_csv_path = os.path.join(DATA_DIR, f"temp_{bidder['name']}_bids.csv")
				with open(temp_csv_path, 'w', newline='') as temp_f:
					writer = csv.writer(temp_f)
					writer.writerow(['price_per_unit', 'quantity_units'])  # Header
					writer.writerows(bidder_data)

				try: add_bidder_and_bids(bidder_name=bidder['name'], csv_filename=temp_csv_path,
						bidder_class=bidder['bidder_class'], units=bidder['units'],
						contract_years=bidder['contract_years'], hector_name=bidder['hector_name'],
						description=f"{bidder['name'].replace('_', ' ')} {bidder['bidder_class'].lower()}")
				finally: # Clean up temporary file
					if os.path.exists(temp_csv_path): os.remove(temp_csv_path)

		print(f"Loaded {csv_filename} decomposed into individual bidders.")
	except FileNotFoundError: print(f"⚠ {csv_filename} not found")
	except Exception as e: print(f"⚠ Error loading {config_key} bids: {e}")

def load_chemical_pulses():
	"""Load chemical pulses into warming factors table"""
	try:
		with open(os.path.join(DATA_DIR, CHEMICAL_PULSES_FILE), 'r') as f:
			for line in f:
				if line.strip():  # Skip empty lines
					parts = line.strip().split(',')
					if len(parts) > 3:  # Ensure we have enough parts
						chemical_name = parts[0]
						emission_factor = float(parts[1])
						units = parts[2]
						data_values = [float(val) for val in parts[3:]]  # Convert to individual float values
						while len(data_values) < 296: data_values.append(0.0) # Pad with zeros if we have fewer than 296 values

						year_columns = ', '.join([f'year_{i:03d}' for i in range(1, 297)])
						placeholders = ', '.join(['?' for _ in range(296)])
						do_insert(f'''INSERT INTO warming_factors (hector_name, emission_factor, hector_units, {year_columns}) VALUES (?, ?, ?, {placeholders})''', (chemical_name, emission_factor, units, *data_values))
		print(f"Loaded {CHEMICAL_PULSES_FILE} (decomposed into individual columns)")
	except FileNotFoundError: print(f"⚠ {CHEMICAL_PULSES_FILE} not found")

def bidder_name_for(rotation_year, cluster_index): return f"Forestry_r{int(rotation_year):02d}_c{int(cluster_index):02d}"

def get_busch_db_path(): return os.getenv(BUSCH_DB_ENV_VAR, BUSCH_DB_DEFAULT)

def load_forestry_from_busch_sqlite():
	"""Direct forestry import pipeline from Busch SQLite into bidders, bids, and forestry_removal.
	Reads the new schema: Pixel_bids, cluster_carbon_schedules_{years}, cluster_forestry_bid_curves_{years}.
	"""
	busch_db_path = get_busch_db_path()
	if not os.path.exists(busch_db_path):
		print(f"⚠ Busch SQLite not found: {busch_db_path}")
		print(f"   Set {BUSCH_DB_ENV_VAR} to the correct .sqlite path to load forestry data.")
		return

	script_dir = os.path.dirname(os.path.abspath(__file__))
	target_db_path = os.path.normpath(os.path.join(script_dir, '..', 'Data', 'smdamage_data.db'))

	source_conn = sqlite3.connect(busch_db_path)
	source_cur = source_conn.cursor()
	target_conn = sqlite3.connect(target_db_path)
	target_cur = target_conn.cursor()
	try:
		target_cur.execute('BEGIN')
		print("Forestry import: transaction started")

		# 1) Discover contract years.
		contract_years_list = [r[0] for r in source_cur.execute(
			'SELECT DISTINCT contract_years FROM Pixel_bids ORDER BY contract_years')]
		if not contract_years_list:
			print("⚠ Forestry import: no contract_years found in Pixel_bids")
			return

		# 2) Insert forestry bidders: one per (contract_years, cluster_id).
		print("Forestry import: loading bidder areas from Pixel_bids")
		insert_bidders = []
		insert_bidder_metadata = []
		for years in contract_years_list:
			area_rows = source_cur.execute(
				'SELECT cluster_id, SUM(area_ha) FROM Pixel_bids WHERE contract_years = ? GROUP BY cluster_id ORDER BY cluster_id',
				(years,)).fetchall()
			for cluster_id, area_ha_sum in area_rows:
				bidder_name = bidder_name_for(years, cluster_id)
				description = f"Forestry clustered bidder r{years} c{cluster_id}"
				insert_bidders.append((bidder_name, 'Remover', 'mhectares', int(years), 'ffi_emissions', description))
				insert_bidder_metadata.append((bidder_name, int(years), int(cluster_id), float(area_ha_sum) / 1_000_000.0)) # Units conversion from hectares to millions of hectares.

		target_cur.executemany("INSERT INTO bidders (bidder, class, units, contract_years, hector_name, description) VALUES (?, ?, ?, ?, ?, ?)", insert_bidders)
		target_cur.executemany("INSERT INTO forestry_bidder_metadata (bidder, rotation_year, cluster_index, available_area_mhectares) VALUES (?, ?, ?, ?)", insert_bidder_metadata)
		print(f"Forestry import: inserted {len(insert_bidders)} forestry bidders")

		# 3) Insert forestry bid steps from cluster_forestry_bid_curves_{years} for all discount rates.
		# discount_rate_00 is stored as integer (e.g. 30 means 3.0%); convert to decimal for bids table.
		print("Forestry import: loading forestry bid curves for all discount rates")
		insert_bids = []
		for years in contract_years_list:
			curve_table = f"cluster_forestry_bid_curves_{years}"
			curve_rows = source_cur.execute(f'SELECT cluster_id, discount_rate_00, bid_step, npv_max_per_ha, step_area_ha FROM {curve_table} ORDER BY cluster_id, discount_rate_00, bid_step').fetchall()
			for cluster_id, discount_rate_00, bid_step, npv_max_per_ha, step_area_ha in curve_rows:
				bidder_name = bidder_name_for(years, cluster_id)
				price_per_unit = -float(npv_max_per_ha) # SMDAMAGE remover bids are costs (negative values).
				quantity_units = float(step_area_ha) / 1_000_000.0
				discount_rate = discount_rate_00 / 1000.0
				insert_bids.append((bidder_name, price_per_unit, quantity_units, discount_rate))

		target_cur.executemany("INSERT INTO bids (bidder, price_per_unit, quantity_units, discount_rate) VALUES (?, ?, ?, ?)", insert_bids)
		print(f"Forestry import: inserted {len(insert_bids)} forestry bid rows")

		# 4) Insert forestry carbon removal schedules from cluster_carbon_schedules_{years}.
		print("Forestry import: loading carbon removal schedules")
		insert_removal = []
		for years in contract_years_list:
			carbon_table = f"cluster_carbon_schedules_{years}"
			removal_rows = source_cur.execute(
				f'SELECT cluster_id, growth_year, tC_per_ha_per_year FROM {carbon_table} ORDER BY cluster_id, growth_year'
			).fetchall()
			for cluster_id, growth_year, tc_per_ha_per_year in removal_rows:
				bidder_name = bidder_name_for(years, cluster_id)
				insert_removal.append((bidder_name, int(growth_year), float(tc_per_ha_per_year)))

		target_cur.executemany("INSERT INTO forestry_removal (bidder, year, tons_per_hectare_per_year) VALUES (?, ?, ?)", insert_removal)
		print(f"Forestry import: inserted {len(insert_removal)} forestry removal rows")

		target_conn.commit()
		print(f"Loaded forestry from Busch SQLite: {len(insert_bidders)} bidders, {len(insert_bids)} bids (all discount rates), {len(insert_removal)} removal rows")
	except Exception as e:
		target_conn.rollback()
		print(f"⚠ Error loading forestry from Busch SQLite: {e}")
		raise
	finally:
		source_conn.close()
		target_conn.close()

if __name__ == "__main__":
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir) # Change to the script directory

	if not os.path.exists(DATA_DIR):
		print(f"❌ Error: '{DATA_DIR}' directory not found. Make sure this script is in the same directory as the '{DATA_DIR}' folder.")
		sys.exit(1)

	create_database()
	show_database_info()
