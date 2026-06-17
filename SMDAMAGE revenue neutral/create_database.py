#!/usr/bin/env python3
"""
Create SQLite database for SMDAMAGE CSV data. Produced by Claude with JFR's guidance.
"""
# >>> Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. SMDAMAGE: "SMDAMAGE revenue neutral.py"
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
	"""Direct forestry import pipeline from Busch SQLite into bidders, bids, and forestry_removal."""
	zero_tolerance = 1e-12
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

		# 1) Insert forestry bidders using bidder-specific area and contract years.
		# Use carbon_removal_schedules first because it is much smaller and avoids long scans on Undiscounted_dta_output.
		print("Forestry import: loading bidder areas from carbon_removal_schedules")
		bidder_rows = source_cur.execute('''SELECT CAST(ROUND(selected_rotation_year) AS INTEGER), cluster_index, MAX(total_area_ha) FROM carbon_removal_schedules
			GROUP BY CAST(ROUND(selected_rotation_year) AS INTEGER), cluster_index ORDER BY CAST(ROUND(selected_rotation_year) AS INTEGER), cluster_index''').fetchall()

		if not bidder_rows:
			print("Forestry import: no area rows in carbon_removal_schedules, falling back to Undiscounted_dta_output")
			bidder_rows = source_cur.execute('''SELECT selected_rotation_year_int, cluster_index, SUM(area_ha) FROM Undiscounted_dta_output
				GROUP BY selected_rotation_year_int, cluster_index ORDER BY selected_rotation_year_int, cluster_index''').fetchall()

		insert_bidders = []
		insert_bidder_metadata = []
		for rotation_year, cluster_index, area_ha_sum in bidder_rows:
			bidder_name = bidder_name_for(rotation_year, cluster_index)
			description = f"Forestry clustered bidder r{int(rotation_year)} c{int(cluster_index)}"
			insert_bidders.append((bidder_name, 'Remover', 'mhectares', int(rotation_year), 'ffi_emissions', description))
			insert_bidder_metadata.append((bidder_name, int(rotation_year), int(cluster_index), float(area_ha_sum)/1_000_000.0))

		target_cur.executemany("INSERT INTO bidders (bidder, class, units, contract_years, hector_name, description) VALUES (?, ?, ?, ?, ?, ?)", insert_bidders,)
		target_cur.executemany("INSERT INTO forestry_bidder_metadata (bidder, rotation_year, cluster_index, available_area_mhectares) VALUES (?, ?, ?, ?)", insert_bidder_metadata,)
		print(f"Forestry import: inserted {len(insert_bidders)} forestry bidders")

		# 2) Insert forestry bid steps from forestry_bid_curves for all discount rates.
		print("Forestry import: loading forestry bid curves for all discount rates")
		curve_rows = source_cur.execute('''SELECT selected_rotation_year_int, cluster_index, bucket_id, npv_max_per_ha, area_ha_sum, discount_rate
			FROM forestry_bid_curves ORDER BY selected_rotation_year_int, cluster_index, discount_rate, bucket_id''').fetchall()

		insert_bids = []
		for rotation_year, cluster_index, bucket_id, npv_max_per_ha, area_ha_sum, discount_rate in curve_rows:
			bidder_name = bidder_name_for(rotation_year, cluster_index)
			price_per_unit = -float(npv_max_per_ha) # SMDAMAGE remover bids are costs (negative values).
			quantity_units = float(area_ha_sum) / 1_000_000.0
			insert_bids.append((bidder_name, price_per_unit, quantity_units, float(discount_rate)))

		target_cur.executemany("INSERT INTO bids (bidder, price_per_unit, quantity_units, discount_rate) VALUES (?, ?, ?, ?)", insert_bids, )
		print(f"Forestry import: inserted {len(insert_bids)} forestry bid rows")

		# 3) Insert forestry carbon removal schedules.
		print("Forestry import: loading carbon removal schedules")
		removal_rows = source_cur.execute('''SELECT selected_rotation_year, cluster_index, year, tC_per_ha_per_year
			FROM carbon_removal_schedules ORDER BY selected_rotation_year, cluster_index, year''').fetchall()

		rows_by_bidder = {}
		for selected_rotation_year, cluster_index, year, tc_per_ha_per_year in removal_rows:
			rotation_year = int(round(selected_rotation_year))
			bidder_name = bidder_name_for(rotation_year, cluster_index)
			if bidder_name not in rows_by_bidder:
				rows_by_bidder[bidder_name] = {'contract_years': rotation_year, 'rows': []}
			rows_by_bidder[bidder_name]['rows'].append((int(year), float(tc_per_ha_per_year)))

		insert_removal = []
		dropped_out_of_contract_rows = 0
		violations = []
		for bidder_name, bidder_data in rows_by_bidder.items():
			contract_years = int(bidder_data['contract_years'])
			bidder_rows = sorted(bidder_data['rows'], key=lambda x: x[0])
			start_year = bidder_rows[0][0]
			last_contract_year = start_year + contract_years - 1

			for year, tc_per_ha_per_year in bidder_rows:
				if year > last_contract_year:
					dropped_out_of_contract_rows += 1
					if abs(tc_per_ha_per_year) > zero_tolerance: violations.append((bidder_name, year, tc_per_ha_per_year, last_contract_year))
					continue
				insert_removal.append((bidder_name, year, tc_per_ha_per_year))

		if violations:
			example_lines = [f"{bidder} year={year} value={value:.6g} last_contract_year={cutoff}" for bidder, year, value, cutoff in violations[:10]]
			raise ValueError("Found non-zero forestry_removal values beyond contract year. " f"violations={len(violations)}. Examples: " + "; ".join(example_lines))

		target_cur.executemany("INSERT INTO forestry_removal (bidder, year, tons_per_hectare_per_year) VALUES (?, ?, ?)", insert_removal,)
		print(f"Forestry import: inserted {len(insert_removal)} forestry removal rows (dropped {dropped_out_of_contract_rows} rows beyond contract years)")

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
