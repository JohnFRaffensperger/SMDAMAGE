#!/usr/bin/env python3
"""
Create SQLite database for SMDAMAGE CSV data. Produced by Claude with JFR's guidance.
"""
import csv
import os
import sys

sys.path.append("./SMDAMAGE revenue neutral")
from database_interface import database_exists, do_insert, do_query, show_database_info

DATA_DIR = "Data" # Holds all the CSV files with bidder and warming factor data. Make sure this directory exists and contains the necessary CSV files before running this script.

# Simple bidders can be loaded directly with add_bidder
SIMPLE_BIDDERS = [
	{'bidder_name': 'Agriculture', 'csv_filename': 'Agriculture_bids.csv', 'bidder_class': 'Remover', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Agricultural carbon mitigation'},
	{'bidder_name': 'Seaweed', 'csv_filename': 'Seaweed_bids.csv', 'bidder_class': 'Remover', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Seaweed carbon removal'},
	{'bidder_name': 'Carbon', 'csv_filename': 'MtC_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mtC', 'contract_years': 1, 'hector_name': 'ffi_emissions', 'description': 'Carbon emissions'},
	{'bidder_name': 'CH4', 'csv_filename': 'CH4_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mt', 'contract_years': 1, 'hector_name': 'CH4_emissions', 'description': 'Methane emissions'},
	{'bidder_name': 'N2O', 'csv_filename': 'N2O_bid_steps.csv', 'bidder_class': 'Emitter', 'units': 'mt', 'contract_years': 1, 'hector_name': 'N2O_emissions', 'description': 'Nitrous oxide emissions'}
]

# Multi-column CSV files. Easy to make but require special handling to split into individual bidders with their own price and quantity columns.
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
	},
	'forestry': {
		'csv_filename': 'Forestry_bid_steps.csv',
		'shared_quantity_col': 0,  # All forestry bidders share quantity from column 0
		'bidders': [
			{'name': 'Loblolly_pine_150', 'price_col': 1, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 150, 'hector_name': 'ffi_emissions'},
			{'name': 'Ponderosa_pine_150', 'price_col': 2, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 150, 'hector_name': 'ffi_emissions'},
			{'name': 'Black_walnut_150', 'price_col': 3, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 150, 'hector_name': 'ffi_emissions'},
			{'name': 'Loblolly_pine_10', 'price_col': 4, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 10, 'hector_name': 'ffi_emissions'},
			{'name': 'Ponderosa_pine_10', 'price_col': 5, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 10, 'hector_name': 'ffi_emissions'},
			{'name': 'Black_walnut_10', 'price_col': 6, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 10, 'hector_name': 'ffi_emissions'},
			{'name': 'Loblolly_pine_24', 'price_col': 7, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 24, 'hector_name': 'ffi_emissions'},
			{'name': 'Ponderosa_pine_103', 'price_col': 8, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 103, 'hector_name': 'ffi_emissions'},
			{'name': 'Black_walnut_55', 'price_col': 9, 'qty_col': None, 'bidder_class': 'Remover', 'units': 'mhectares', 'contract_years': 55, 'hector_name': 'ffi_emissions'}
		]
	}
}

# Other data file configurations
CHEMICAL_PULSES_FILE = 'Calibrated_pulses_by_chemical_2025.txt'
FORESTRY_SEQUESTRATION_FILE = 'Forestry_sequestration.csv'

def create_database():
	"""Create the SQLite database and populate with CSV data"""
	# Check if database already exists
	if database_exists():
		print(f"❌ Database already exists. Delete it first or use a different name.")
		sys.exit(1)

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
	do_query('''CREATE TABLE IF NOT EXISTS bids (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT, price_per_unit REAL, quantity_units REAL, FOREIGN KEY (bidder) REFERENCES bidders(bidder))''')
	do_query('CREATE INDEX IF NOT EXISTS idx_bids_bidder ON bids(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_bids_price ON bids(price_per_unit)')

	load_simple_bidders()
	load_multi_column_bidders('chemicals')
	load_multi_column_bidders('forestry')

	# Forestry carbon removal.
	do_query('''CREATE TABLE IF NOT EXISTS forestry_removal (id INTEGER PRIMARY KEY AUTOINCREMENT, bidder TEXT NOT NULL, year INTEGER NOT NULL, tons_per_hectare_per_year REAL NOT NULL)''')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder ON forestry_removal(bidder)')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_year ON forestry_removal(year)')
	do_query('CREATE INDEX IF NOT EXISTS idx_forestry_seq_bidder_year ON forestry_removal(bidder, year)')
	load_forestry_removal()

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
				do_insert("INSERT INTO bids (bidder, price_per_unit, quantity_units) VALUES (?, ?, ?)", (bidder_name, price_per_unit, quantity_units))
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
	except FileNotFoundError:
		print(f"⚠ {CHEMICAL_PULSES_FILE} not found")

def load_forestry_removal():
	"""Load forestry removal data from Forestry_sequestration.csv"""
	try:
		# Build column mappings from existing forestry configuration
		forestry_bidders = MULTI_COLUMN_BIDDERS['forestry']['bidders']
		column_mappings = []
		for bidder in forestry_bidders:
			# Map price_col to the sequestration data column (same column index)
			col_idx = bidder['price_col']
			bidder_name = bidder['name']
			description = f"{bidder_name.replace('_', ' ')} {bidder['contract_years']}yr"
			column_mappings.append((col_idx, bidder_name, description))

		with open(os.path.join(DATA_DIR, FORESTRY_SEQUESTRATION_FILE), 'r') as f:
			reader = csv.reader(f)
			next(reader)  # Skip header

			for row in reader:
				year = int(row[0])
				# Transform wide format to long format - one row per bidder per year
				for col_idx, bidder_name, description in column_mappings:
					tons_per_hectare = float(row[col_idx])
					do_insert('''INSERT INTO forestry_removal (bidder, year, tons_per_hectare_per_year) VALUES (?, ?, ?)''', (bidder_name, year, tons_per_hectare))
		print(f"Loaded {FORESTRY_SEQUESTRATION_FILE} (normalized to long format into forestry_removal table)")
	except FileNotFoundError:
		print(f"⚠ {FORESTRY_SEQUESTRATION_FILE} not found")

if __name__ == "__main__":
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir) # Change to the script directory

	if not os.path.exists(DATA_DIR):
		print(f"❌ Error: '{DATA_DIR}' directory not found. Make sure this script is in the same directory as the '{DATA_DIR}' folder.")
		sys.exit(1)

	create_database()
	show_database_info()
