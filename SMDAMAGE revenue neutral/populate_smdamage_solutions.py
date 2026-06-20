#!/usr/bin/env python3
import os
import sqlite3
import pickle
import re
import sys
from pathlib import Path

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = SCRIPT_DIR
sys.path.append(PROJECT_ROOT)

import database_interface
import defaults_and_utilities

DB_NAME = os.path.join(PROJECT_ROOT, "smdamage_solutions.db")

def create_solutions_db():
	if os.path.exists(DB_NAME):
		os.remove(DB_NAME)

	conn = sqlite3.connect(DB_NAME)
	cursor = conn.cursor()

	cursor.execute("""
		CREATE TABLE scenarios (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT,
			discount_rate REAL,
			initial_temp REAL,
			tau REAL,
			is_revenue_neutral INTEGER,
			is_removal_luc INTEGER,
			use_updated_Wpt INTEGER,
			solver_status TEXT,
			total_revenue REAL
		)
	""")

	cursor.execute("""
		CREATE TABLE accepted_bids (
			scenario_id INTEGER,
			bidder TEXT,
			year REAL,
			max_step_index INTEGER,
			obj_coeff REAL,
			FOREIGN KEY(scenario_id) REFERENCES scenarios(id)
		)
	""")

	cursor.execute("""
		CREATE TABLE binding_constraints (
			scenario_id INTEGER,
			constraint_name TEXT,
			type TEXT,
			bidder TEXT,
			year REAL,
			slack REAL,
			dual_price REAL,
			FOREIGN KEY(scenario_id) REFERENCES scenarios(id)
		)
	""")

	cursor.execute("""
		CREATE TABLE vpt_dual_prices (
			scenario_id INTEGER,
			bidder TEXT,
			year REAL,
			dual_price REAL,
			FOREIGN KEY(scenario_id) REFERENCES scenarios(id)
		)
	""")

	cursor.execute("CREATE INDEX idx_accepted_bids_lookup ON accepted_bids(bidder, year, max_step_index)")
	cursor.execute("CREATE INDEX idx_binding_constraints_name ON binding_constraints(constraint_name)")
	cursor.execute("CREATE INDEX idx_vpt_duals_lookup ON vpt_dual_prices(bidder, year)")

	conn.commit()
	return conn

def parse_scenario_from_filename(filename):
	name_match = re.search(r"SMDAMAGE (.*?)_disc", filename)
	name = name_match.group(1) if name_match else filename
	dr_match = re.search(r"disc_([\d.]+)", filename)
	dr = float(dr_match.group(1)) if dr_match else 0.03
	temp_match = re.search(r"temp0_([\d.]+)", filename)
	temp = float(temp_match.group(1)) if temp_match else 1108.0
	tau_match = re.search(r"tau_([\d.]+)", filename)
	tau = float(tau_match.group(1)) if tau_match else 1.0
	is_rn = 1 if "ffi_removal" not in filename else 0
	is_luc = 1 if "luc_removal" in filename else 0
	use_wpt = 1 if "Wpt_fitted" in filename else 0
	return {
		'name': name, 'discount_rate': dr, 'initial_temp': temp, 'tau': tau,
		'is_revenue_neutral': is_rn, 'is_removal_luc': is_luc, 'use_updated_Wpt': use_wpt
	}

def get_bid_step_data(bidder, year, total_val, bid_curves, discount_rate_base, bidders_info):
	if total_val <= 1e-6: return -1, 0.0
	curve = bid_curves.get(bidder, [])
	if not curve: return -1, 0.0

	acc_qty = 0.0
	for idx, (price, qty) in enumerate(curve):
		acc_qty += qty
		if acc_qty >= total_val - 1e-6:
			start_year = defaults_and_utilities.getStartYear()
			# delta^t where delta = 1/(1+r)
			df = 1.0 / ((1.0 + discount_rate_base)**(year - start_year))
			coeff = price * df
			b_info = bidders_info.get(bidder, {})
			if b_info.get('units') == 'kt': coeff /= 1000.0
			return idx, coeff
	return len(curve) - 1, 0.0

def populate():
	print("Starting initial population...")
	conn = create_solutions_db()
	cursor = conn.cursor()
	output_dir = os.path.join(PROJECT_ROOT, "Output")
	pkl_files = [f for f in os.listdir(output_dir) if f.endswith(".pkl") and not f.endswith("_taxed_temps.pkl") and f.startswith("SMDAMAGE ")]

	all_bidders_list = database_interface.get_bidders()
	bidders_info = {b['bidder_name']: b for b in all_bidders_list}
	bid_curves = {b['bidder_name']: database_interface.get_bids(b['bidder_name']) for b in all_bidders_list}
	forestry_meta = database_interface.get_forestry_metadata()

	for pkl_file in pkl_files:
		print(f"Processing {pkl_file}...")
		meta = parse_scenario_from_filename(pkl_file)
		with open(os.path.join(output_dir, pkl_file), "rb") as f:
			vpt = pickle.load(f)

		cursor.execute("""
			INSERT INTO scenarios (name, discount_rate, initial_temp, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, solver_status)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		""", (meta['name'], meta['discount_rate'], meta['initial_temp'], meta['tau'], meta['is_revenue_neutral'], meta['is_removal_luc'], meta['use_updated_Wpt'], "Optimal"))
		scenario_id = cursor.lastrowid

		# Process variables (vpt)
		accepted_bids_data = []
		for (bidder, t), var in vpt.items():
			val = var.varValue if var.varValue is not None else 0.0
			if val > 1e-6:
				step_idx, obj_coeff = get_bid_step_data(bidder, t, val, bid_curves, meta['discount_rate'], bidders_info)
				if step_idx >= 0:
					accepted_bids_data.append((scenario_id, bidder, t, step_idx, obj_coeff))
		if accepted_bids_data:
			cursor.executemany("INSERT INTO accepted_bids (scenario_id, bidder, year, max_step_index, obj_coeff) VALUES (?, ?, ?, ?, ?)", accepted_bids_data)

		# Process vpt_dual_prices from CSV
		csv_filename = pkl_file.replace(".pkl", ".csv").replace("SMDAMAGE ", "SMDAMAGE_soln_")
		csv_path = os.path.join(output_dir, csv_filename)
		if os.path.exists(csv_path):
			print(f"  Populating vpt_dual_prices from {csv_filename}...")
			with open(csv_path, "r") as csv_f:
				lines = csv_f.readlines()
				if len(lines) > 2:
					header = lines[1].strip().split(',')
					price_cols = {}
					for i, col in enumerate(header):
						if " $M/" in col:
							bidder_name = col.split(" $M/")[0].strip()
							price_cols[bidder_name] = i

					vpt_duals = []
					for line in lines[2:]:
						parts = line.strip().split(',')
						if len(parts) > max(price_cols.values(), default=-1):
							try:
								year = float(parts[0])
								for bidder, col_idx in price_cols.items():
									val_str = parts[col_idx]
									if val_str and val_str != '.':
										dual_val = float(val_str)
										if abs(dual_val) > 1e-9:
											vpt_duals.append((scenario_id, bidder, year, dual_val))
							except ValueError:
								continue
					if vpt_duals:
						cursor.executemany("INSERT INTO vpt_dual_prices (scenario_id, bidder, year, dual_price) VALUES (?, ?, ?, ?)", vpt_duals)

		# Process land constraints
		binding_constraints = []
		for bidder, f_meta in forestry_meta.items():
			rotation = f_meta['rotation_year']
			limit = f_meta['available_area_mhectares']
			for t in defaults_and_utilities.getBidPeriods():
				land_use = 0.0
				for u in defaults_and_utilities.getBidPeriods():
					if u <= t <= u + rotation - 1:
						var = vpt.get((bidder, u))
						if var and (var.varValue if var.varValue is not None else 0.0) > 1e-6:
							land_use += var.varValue
				if land_use >= limit - 1e-4:
					binding_constraints.append((scenario_id, f"Forestry_Land_{bidder}_{t}", "Land", bidder, t, 0.0, None))
		if binding_constraints:
			cursor.executemany("INSERT INTO binding_constraints (scenario_id, constraint_name, type, bidder, year, slack, dual_price) VALUES (?, ?, ?, ?, ?, ?, ?)", binding_constraints)

	conn.commit()
	conn.close()
	print("Population complete.")

if __name__ == "__main__":
	populate()
