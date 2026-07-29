#!/usr/bin/env python3
"""
Database interface module for SMDAMAGE. Made by Claude with JFR's guidance.
"""
# >>> Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. SMDAMAGE: "SMDAMAGE revenue neutral.py"
# Part IV. Running Hector on SMDAMAGE output. hector_interface.py.

import sqlite3
import os

# Import hector_interface for getPeriodsPerYear (circular import avoided by late import in getPulse)
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(os.path.dirname(SCRIPT_DIR), "Data", "smdamage_data.db")  # Database in Data directory

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

def get_bids(bidder_name, discount_rate=None):
	if discount_rate is None:
		return do_query("SELECT price_per_unit, quantity_units FROM bids WHERE bidder = ? ORDER BY id", (bidder_name,))
	return do_query("SELECT price_per_unit, quantity_units FROM bids WHERE bidder = ? AND (discount_rate IS NULL OR ABS(discount_rate - ?) < 1e-12) ORDER BY id",
		(bidder_name, discount_rate),)

def get_all_bids(discount_rate=None):
	"""Returns dict {bidder_name: [(price_per_unit, quantity_units), ...]} in one query (suggestion 5)."""
	if discount_rate is None:
		rows = do_query("SELECT bidder, price_per_unit, quantity_units FROM bids ORDER BY bidder, id")
	else:
		rows = do_query("SELECT bidder, price_per_unit, quantity_units FROM bids WHERE (discount_rate IS NULL OR ABS(discount_rate - ?) < 1e-12) ORDER BY bidder, id", (discount_rate,))
	result = {}
	for bidder, price, qty in rows: result.setdefault(bidder, []).append((price, qty))
	return result

def get_forestry_contractdata():
	"""Retrieve metadata for all forestry bidders."""
	rows = do_query("SELECT bidder, rotation_year, cluster_index, available_area_mhectares FROM forestry_bidder_metadata")
	columns = ["bidder", "rotation_year", "cluster_index", "available_area_mhectares"]
	return {row[0]: dict(zip(columns, row)) for row in rows}

def get_forestry_bidder_names():
	results = do_query ("SELECT DISTINCT bidder FROM forestry_removal ORDER BY bidder collate nocase")
	return [row[0] for row in results] # Otherwise you get a list of tuples like [('Loblolly_pine_150',), ('Loblolly_pine_300',), ...]
# print(get_forestry_bidder_names())

def get_forestry_carbon_removal(bidder):
	return do_query ("SELECT year, tons_per_hectare_per_year FROM forestry_removal WHERE bidder = ? ORDER BY year", (bidder,))

def get_all_forestry_carbon_removal():
	"""Returns dict {bidder_name: [(year, tc), ...]} in one query (suggestion 2)."""
	rows = do_query("SELECT bidder, year, tons_per_hectare_per_year FROM forestry_removal ORDER BY bidder, year")
	result = {}
	for bidder, year, tc in rows: result.setdefault(bidder, []).append((year, tc))
	return result
# forestry_seq = get_forestry_carbon_removal('Loblolly_pine_150')
# for row in forestry_seq[:6]: print(row)

def get_hector_names():
	results = do_query ("SELECT DISTINCT hector_name FROM warming_factors order by hector_name collate nocase")
	return [row[0] for row in results]
# print (get_hector_names())

def get_warming_factors(hector_name): # For forestry, you must do the convolution of carbon removal to warming over time.
	results = do_query("SELECT emission_factor, hector_units, * FROM warming_factors WHERE hector_name = ?", (hector_name,))

	result = results[0]
	# Query returns: (emission_factor, hector_units, id, hector_name, emission_factor, hector_units, year_001, year_002, ..., year_296)
	# We want only the year columns starting at index 6
	data_values = list(result[6:])  # All year columns as a list, skipping duplicate metadata
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

def getPulse(): # Retrieves the marginal change in temperature in each year after a pulse emission from the database.
	"""
	Load warming factors from smdamage_data.db and return as a Pulse dictionary.
	Format: Pulse[chemical] = [emission_factor, warming1, warming2, ..., warming_296]
	Each warming value is repeated according to getPeriodsPerYear() for sub-annual periods.
	"""
	from hector_interface import getPeriodsPerYear  # Import here to avoid circular dependency

	Pulse = {}  # [Pulseqty, warming1, warming2, warming3,...]
	hector_names = get_hector_names()

	for hector_name in hector_names:
		warming_data = get_warming_factors(hector_name)
		emission_factor = warming_data['emission_factor']
		data_values = warming_data['data_values']

		# Remove the emission_factor and hector_units from data_values to get just the warming values
		# get_warming_factors returns: {'emission_factor': result[0], 'hector_units': result[1], 'data_values': data_values}
		# where data_values = list(result[2:]) = all year columns

		# Remove 'ffi_emissions' suffix to match the key format of the original Pulse dictionary
		chemical_key = hector_name.replace('_emissions', '')

		# Build the pulse list: [emission_factor] + warming values repeated for each period per year
		pulse_list = [emission_factor] + [float(warming) for warming in data_values for _ in range(getPeriodsPerYear())]
		Pulse[chemical_key] = pulse_list

	return Pulse

# =============================================================================================
# Solutions database accessors (smdamage_solutions.db).
# These functions use a separate DB path passed in, to avoid coupling to defaults_and_utilities.
# =============================================================================================

def save_temperature_series(db_path, scenario_id, source, year_to_value):
	"""Insert rows into temperature_series for one (scenario_id, source) pair."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.executemany(
		"""INSERT INTO temperature_series (scenario_id, source, year, value) VALUES (?,?,?,?)
		ON CONFLICT(scenario_id, source, year) DO UPDATE SET value=excluded.value""",
		[(scenario_id, source, float(year), value) for year, value in year_to_value.items()])
	conn.commit()
	conn.close()

def get_temperature_series_by_scenario_id(db_path, scenario_id, source):
	"""Return {year: value} for one scenario id and source label."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT year, value FROM temperature_series WHERE scenario_id = ? AND source = ? ORDER BY year", (scenario_id, source))
	rows = cursor.fetchall()
	conn.close()
	return {year: value for year, value in rows}

def get_temperature_series(db_path, scenario_name, source):
	"""Return {year: value} for the given scenario name and source label."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute(
		"SELECT ts.year, ts.value FROM temperature_series ts JOIN scenarios s ON s.id = ts.scenario_id WHERE s.name = ? AND ts.source = ? ORDER BY ts.year",
		(scenario_name, source))
	rows = cursor.fetchall()
	conn.close()
	return {year: value for year, value in rows}

def save_fitted_wpt(db_path, calibration_scenario_id, wpt_dict):
	"""Save fitted Wpt values, replacing any existing rows for this calibration scenario."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("DELETE FROM fitted_wpt WHERE calibration_scenario_id = ?", (calibration_scenario_id,))
	cursor.executemany(
		"INSERT INTO fitted_wpt (calibration_scenario_id, pollutant, t, value) VALUES (?,?,?,?)",
		[(calibration_scenario_id, pollutant, int(t), value) for (pollutant, t), value in wpt_dict.items()])
	conn.commit()
	conn.close()

def get_fitted_wpt(db_path, calibration_scenario_id=None):
	"""Return {(pollutant, float(t)): value} from the specified calibration, or the most recently saved one."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	if calibration_scenario_id is not None: cursor.execute("SELECT pollutant, t, value FROM fitted_wpt WHERE calibration_scenario_id = ?", (calibration_scenario_id,))
	else: cursor.execute("SELECT pollutant, t, value FROM fitted_wpt WHERE calibration_scenario_id = (SELECT MAX(calibration_scenario_id) FROM fitted_wpt)")
	rows = cursor.fetchall()
	conn.close()
	return {(pollutant, float(t)): value for pollutant, t, value in rows}

def get_vpt_from_db(db_path, scenario_id):
	"""Return {(bidder, year): summed_value} reconstructed from one scenario id."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute(
		"SELECT v.bidder, v.year, SUM(v.value) FROM variables v WHERE v.scenario_id = ? GROUP BY v.bidder, v.year",
		(scenario_id,))
	rows = cursor.fetchall()
	conn.close()
	return {(bidder, year): value for bidder, year, value in rows}

def get_scenario_id(db_path, scenario_name):
	"""Return the id of the most recently inserted scenario with the given name, or None."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT id FROM scenarios WHERE name = ? ORDER BY id DESC LIMIT 1", (scenario_name,))
	row = cursor.fetchone()
	conn.close()
	return row[0] if row else None

def get_scenario_discount_rate(db_path, scenario_id):
	"""Return discount_rate for the scenario id, or None if not found."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT discount_rate FROM scenarios WHERE id = ?", (scenario_id,))
	row = cursor.fetchone()
	conn.close()
	return row[0] if row else None

def save_calibrated_initial_temp(db_path, scenario_id, calibrated_initial_temp):
	"""Store the calibrated initial temperature on the source scenario row."""
	conn = sqlite3.connect(db_path)
	conn.execute("UPDATE scenarios SET calibrated_initial_temp = ? WHERE id = ?", (calibrated_initial_temp, scenario_id))
	conn.commit()
	conn.close()

def get_calibrated_initial_temp(scenario):
	"""Return calibrated_initial_temp from the most recently saved scenario matching the given scenario tag.
	Always queries the uncalibrated (Wpt default) row, where save_calibrated_initial_temp stores the value."""
	import defaults_and_utilities # Late import to avoid circular dependency.
	db_path = defaults_and_utilities.getSolutionsDBPath()
	was_updated = scenario.use_updated_Wpt
	scenario.use_updated_Wpt = False
	name = defaults_and_utilities.getExperimentTag(scenario)
	scenario.use_updated_Wpt = was_updated
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT calibrated_initial_temp FROM scenarios WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
	row = cursor.fetchone()
	conn.close()
	if row is None or row[0] is None: raise ValueError(f"No calibrated_initial_temp found for '{name}'. Run run_SMDAMAGE_fit_W first.")
	return row[0]

def get_scenario_tau(db_path, scenario_id):
	"""Return tau for the scenario id, or None if not found."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT tau FROM scenarios WHERE id = ?", (scenario_id,))
	row = cursor.fetchone()
	conn.close()
	return row[0] if row else None

def save_scenario_series(db_path, scenario_id, series_name, year_to_value, units=None, series_source="temperature_output_csv"):
	"""Insert rows into scenario_series for one (scenario_id, series_name) pair."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.executemany(
		"""INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?)
		ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source""",
		[(scenario_id, series_name, float(year), value, units, series_source) for year, value in year_to_value.items()])
	conn.commit()
	conn.close()

def upsert_scenario_bidder_year_rows(db_path, rows):
	"""Upsert scenario_bidder_year rows.
	Each row: (scenario_id, bidder, year, quantity_value, pct_max_bid, dual_price, unit_label, value_source)
	"""
	if not rows: return
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.executemany(
		"""INSERT INTO scenario_bidder_year
		(scenario_id, bidder, year, quantity_value, pct_max_bid, dual_price, unit_label, value_source)
		VALUES (?,?,?,?,?,?,?,?)
		ON CONFLICT(scenario_id, bidder, year) DO UPDATE SET
		quantity_value=excluded.quantity_value,
		pct_max_bid=excluded.pct_max_bid,
		dual_price=excluded.dual_price,
		unit_label=excluded.unit_label,
		value_source=excluded.value_source""",
		rows)
	conn.commit()
	conn.close()

def insert_scenario_artifact(db_path, scenario_id, artifact_type, artifact_path=None, header_text=None, created_at=None, content_hash=None):
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute(
		"INSERT INTO scenario_artifacts (scenario_id, artifact_type, artifact_path, header_text, created_at, content_hash) VALUES (?,?,?,?,?,?)",
		(scenario_id, artifact_type, artifact_path, header_text, created_at, content_hash))
	conn.commit()
	conn.close()

def get_scenario_bidder_year(db_path, scenario_id):
	"""Return {(bidder, year): {'quantity_value': q, 'pct_max_bid': p, 'dual_price': d, 'unit_label': u}}."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute(
		"SELECT bidder, year, quantity_value, pct_max_bid, dual_price, unit_label FROM scenario_bidder_year WHERE scenario_id = ?",
		(scenario_id,))
	rows = cursor.fetchall()
	conn.close()
	return {(bidder, year): {'quantity_value': q, 'pct_max_bid': p, 'dual_price': d, 'unit_label': u} for bidder, year, q, p, d, u in rows}

def get_scenario_series(db_path, scenario_id, series_name):
	"""Return {year: value} from scenario_series for one scenario and series name."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT year, value FROM scenario_series WHERE scenario_id = ? AND series_name = ? ORDER BY year", (scenario_id, series_name))
	rows = cursor.fetchall()
	conn.close()
	return {year: value for year, value in rows}

def get_vpt_dual_series_by_scenario_id(db_path, scenario_id, bidder='Carbon'):
	"""Return {year: pi} for Vpt(bidder,year) duals from constraint_duals for one scenario."""
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("SELECT constraint_name, pi FROM constraint_duals WHERE scenario_id = ? AND constraint_name LIKE ?", (scenario_id, f"Vpt({bidder},%"))
	rows = cursor.fetchall()
	conn.close()
	series = {}
	for constraint_name, pi in rows:
		inner = constraint_name[4:-1]
		last_comma = inner.rfind(',')
		series[float(inner[last_comma + 1:])] = pi
	return series

