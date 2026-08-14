# >>> Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. SMDAMAGE: "smdamage_models.py"
# Part IV. Running Hector on SMDAMAGE output. hector_interface.py.
# =============================================================================================

import time # for timing the run.
import os # for file system operations
import sqlite3
import hector_interface # Hector pulse generation functions.
import database_interface # for dynamic bidder and tree data.

# Directories and file names.
_HERE = os.path.dirname(os.path.abspath(__file__))
def getOutputDirectory(): return os.path.join(_HERE, "Output", "")
def getSolutionsDBPath(): return os.path.join(_HERE, "Output", "smdamage_solutions.db")
def ensure_solutions_db():
	import sqlite3
	db_path = getSolutionsDBPath()
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.executescript("""CREATE TABLE IF NOT EXISTS scenarios (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, is_land_constraint_implicit INTEGER DEFAULT 0,
			is_revenue_neutral INTEGER, tau REAL, discount_rate REAL, is_removal_luc INTEGER, use_updated_Wpt INTEGER, calibration_scenario INTEGER, initial_temp REAL, solver_status TEXT,
			objective_value REAL, Removal_cost_2025_2125 REAL, net_revenue REAL, Emissions_2025_2125 REAL, Avg_emitter_price_2025_2125 REAL, Avg_remover_price_2025_2125 REAL, solution_datetime TEXT,
			emitters_pay REAL, removers_get REAL);
		CREATE TABLE IF NOT EXISTS variables (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER, bidder TEXT, year REAL, bid_step INTEGER, value REAL,
			FOREIGN KEY (scenario_id) REFERENCES scenarios(id));
		CREATE TABLE IF NOT EXISTS constraint_duals (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER, constraint_name TEXT, pi REAL, FOREIGN KEY (scenario_id) REFERENCES scenarios(id));
		CREATE UNIQUE INDEX IF NOT EXISTS uq_variables_record_key ON variables(scenario_id, bidder, year, bid_step);
		CREATE UNIQUE INDEX IF NOT EXISTS uq_constraint_duals_record_key ON constraint_duals(scenario_id, constraint_name);
		CREATE TABLE IF NOT EXISTS fitted_wpt (id INTEGER PRIMARY KEY AUTOINCREMENT, calibration_scenario_id INTEGER NOT NULL, pollutant TEXT NOT NULL,
			t INTEGER NOT NULL, value REAL NOT NULL, FOREIGN KEY (calibration_scenario_id) REFERENCES scenarios(id));
		CREATE UNIQUE INDEX IF NOT EXISTS uq_fitted_wpt_record_key ON fitted_wpt(calibration_scenario_id, pollutant, t);
		CREATE INDEX IF NOT EXISTS idx_fitted_wpt_scenario ON fitted_wpt(calibration_scenario_id, pollutant);
		CREATE TABLE IF NOT EXISTS scenario_bidder_year (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER NOT NULL,
			bidder TEXT NOT NULL, year REAL NOT NULL, quantity_value REAL, pct_max_bid REAL, dual_price REAL,
			unit_label TEXT, value_source TEXT NOT NULL, FOREIGN KEY (scenario_id) REFERENCES scenarios(id));
		CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_bidder_year ON scenario_bidder_year(scenario_id, bidder, year);
		CREATE INDEX IF NOT EXISTS idx_scenario_bidder_year_bidder ON scenario_bidder_year(scenario_id, bidder);
		CREATE TABLE IF NOT EXISTS scenario_series (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER NOT NULL,
			series_name TEXT NOT NULL, year REAL NOT NULL, value REAL, units TEXT, series_source TEXT NOT NULL DEFAULT 'SMDAMAGE',
			FOREIGN KEY (scenario_id) REFERENCES scenarios(id));
		CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_series ON scenario_series(scenario_id, series_name, year);
		CREATE INDEX IF NOT EXISTS idx_scenario_series_name ON scenario_series(scenario_id, series_name);""")
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN calibrated_initial_temp REAL")
	except Exception: pass # Column already exists.
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN land_rent REAL")
	except Exception: pass # Column already exists.
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN Avg_emitter_price_2025_2125 REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN Avg_remover_price_2025_2125 REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN Emissions_2025_2125 REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN Removal_cost_2025_2125 REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN is_land_constraint_implicit INTEGER DEFAULT 0")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN calibration_scenario INTEGER")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN emitters_pay REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenarios ADD COLUMN removers_get REAL")
	except Exception: pass
	try: cursor.execute("ALTER TABLE scenario_series ADD COLUMN series_source TEXT NOT NULL DEFAULT 'SMDAMAGE'")
	except Exception: pass
	forestry_meta_mig = database_interface.get_forestry_contractdata()
	total_area_mig = sum(meta['available_area_mhectares'] for meta in forestry_meta_mig.values())
	cursor.execute("UPDATE scenarios SET land_rent = (SELECT ? * COALESCE(SUM(cd.pi), 0.0) FROM constraint_duals cd WHERE cd.scenario_id = scenarios.id AND cd.constraint_name LIKE 'Forestry_Land_%') WHERE land_rent IS NULL", (total_area_mig / 1_000_000.0,))
	cursor.execute("""UPDATE scenarios SET
		Avg_emitter_price_2025_2125 = (SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id=scenarios.id AND bidder='Carbon' AND year>=2025 AND year<=2125),
		Avg_remover_price_2025_2125 = (SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id=scenarios.id AND bidder='Agriculture' AND year>=2025 AND year<=2125),
		Emissions_2025_2125 = (SELECT SUM(quantity_value)/1000.0 FROM scenario_bidder_year WHERE scenario_id=scenarios.id AND bidder='Carbon' AND year>=2025 AND year<=2125),
		Removal_cost_2025_2125 = (SELECT COALESCE(SUM(quantity_value*dual_price),0.0)/1000000.0 FROM scenario_bidder_year WHERE scenario_id=scenarios.id
			AND bidder NOT IN ('C2F6','CF4','CH4','Carbon','HFC125','HFC134a','HFC143a','N2O','SF6') AND year>=2025 AND year<=2125)
		WHERE Avg_emitter_price_2025_2125 IS NULL""")
	cursor.execute("""UPDATE scenarios SET
		emitters_pay = (SELECT COALESCE(SUM(quantity_value*dual_price),0.0)/1000000.0 FROM scenario_bidder_year
			WHERE scenario_id=scenarios.id AND bidder IN ('C2F6','CF4','CH4','Carbon','HFC125','HFC134a','HFC143a','N2O','SF6')),
		removers_get = (SELECT COALESCE(SUM(quantity_value*dual_price),0.0)/1000000.0 FROM scenario_bidder_year
			WHERE scenario_id=scenarios.id AND bidder NOT IN ('C2F6','CF4','CH4','Carbon','HFC125','HFC134a','HFC143a','N2O','SF6'))
		WHERE emitters_pay IS NULL""")
	cursor.execute("UPDATE scenarios SET is_land_constraint_implicit = 0 WHERE is_land_constraint_implicit IS NULL")
	cursor.execute("""UPDATE scenarios SET calibration_scenario = (
		SELECT fw.calibration_scenario_id FROM fitted_wpt fw
		JOIN scenarios s2 ON s2.id = fw.calibration_scenario_id
		WHERE s2.is_removal_luc = scenarios.is_removal_luc
		ORDER BY fw.calibration_scenario_id ASC LIMIT 1)
		WHERE calibration_scenario IS NULL AND use_updated_Wpt = 1""")
	conn.commit()
	conn.close()

def Hector_output_file_name(scenario): return getOutputDirectory() + "Hector_output_" + experimentTag_to_file_name(scenario) + ".csv"

# These are the market participants. Emitters face tax tau. Removers do not.
def getEmitters(): return [b['bidder_name'] for b in database_interface.get_bidders() if b['class'].lower() == 'emitter']
def getRemovers(): return [b['bidder_name'] for b in database_interface.get_bidders() if b['class'].lower() == 'remover']
def getChemicals(): return ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6'] # Must be within Emitters.
# TreeTypes must be within Removers.
def getTreeTypes():	return database_interface.get_forestry_bidder_names()

# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
def getUnits(): return {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}

# Part 0. Key parameters. These parameters go to file names and headers. If you change something here, a function may be expecting the wrong filename.
#                                               2125 <<<<<<<<<<<<<< Temperature constrained <<<<<<<<<<<<<<<<< 2306
#           2025 --------- bidding ------------------------------- 2275
# Timeline: StartYear, StartYear+1, ..., FirstConstrainedYear, ..., StartYear + getNumber_of_bid_years(), ..., StartYear + PulseDataLength.
#                             assert (tFirstConstrainedYear <= StartYear + getNumber_of_bid_years()).
def getFirstConstrainedYear(): 		return 2125.0
def getNumber_of_bid_years(): 		return 250 # Run this long to avoid end-of-horizon effects. assert (BeginConstraintYear <= StartYear + getNumber_of_bid_years())
def getStartYear(): 				return 2025.0 # First year of the auction schedule.
def getPulseDataLength(): 			return 296 # Pulse data from Hector goes only 296 years. So raising this would understate later warming.

def getModelPeriods(): return [float(getStartYear()) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*getPulseDataLength())]
def getBidPeriods(): return [float(getStartYear()) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*getNumber_of_bid_years())]
def getLastBidYear(): return getStartYear() + getNumber_of_bid_years() - 1.0  # Typically 100 years after first year, e.g., 2020.

# Set this if Agriculture is expressed in mtC but should also consume land in land-balance constraints.
# Units: mtC per million hectares. Keep 0.0 to ignore agriculture in hectare constraints.
def getAgricultureMtCPerMhectare(): return 0.0

def inflate_2020_to_2025(): 		return 1.23 # Inflate prices from 2020 to 2025. From https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexhistorical_us_table.htm, I will multiply bids by $316/$257 = 1.23.
def dateTimeString(): return time.strftime("%Y%m%d%H%M", time.localtime())

class Scenario(object):
	def __init__(self, comment, discount_rate, initial_temperature, is_revenue_neutral, tau, is_removal_luc, use_updated_Wpt, calibration_scenario_id):
		self.comment = comment
		self.discount_rate_base = discount_rate
		self.initial_temperature = initial_temperature
		self.is_revenue_neutral = is_revenue_neutral
		self.tau = tau
		self.is_removal_luc = is_removal_luc
		self.use_updated_Wpt = use_updated_Wpt
		self.calibration_scenario_id = calibration_scenario_id
	def discount_rate(self, periods): return 1.0/(1.0 + self.discount_rate_base)**(periods)
# your_sample_scenario = Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = 971.24975, is_revenue_neutral = True, tau = 2.6, is_removal_luc = True, use_updated_Wpt = False, calibration_scenario_id = None)

def append_temperatures_to_db(scenario_id, source, year_to_value):
	database_interface.save_scenario_series(getSolutionsDBPath(), scenario_id, source, year_to_value)

def delete_scenario_solution(scenario_id_list):
	"""Delete all solution rows for each scenario id in scenario_id_list."""
	ensure_solutions_db()
	db_path = getSolutionsDBPath()
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	for scenario_id in scenario_id_list:
		cursor.execute("DELETE FROM fitted_wpt WHERE calibration_scenario_id = ?", (scenario_id,))
		cursor.execute("DELETE FROM scenario_series WHERE scenario_id = ?", (scenario_id,))
		cursor.execute("DELETE FROM scenario_bidder_year WHERE scenario_id = ?", (scenario_id,))
		cursor.execute("DELETE FROM variables WHERE scenario_id = ?", (scenario_id,))
		cursor.execute("DELETE FROM constraint_duals WHERE scenario_id = ?", (scenario_id,))
		cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
	conn.commit()
	conn.close()

def experimentTag_to_file_name(scenario):
	tag = getExperimentTag(scenario)
	tag = tag.replace(" ", "_")
	tag = tag.replace(",", "_")
	tag = tag.replace("__", "_")
	return tag

def getExperimentTag(scenario): # Used in file names and headers. discount_rate, initial_temperature, is_revenue_neutral, tau, is_removal_luc, use_updated_Wpt, comment
	if len(scenario.comment) >= 1: experiment_tag = scenario.comment + ", "
	experiment_tag += "disc " + str(round(scenario.discount_rate_base, 4)) + ", "
	experiment_tag += "temp0 " + str(round(scenario.initial_temperature, 3)) + ", "
	if scenario.is_revenue_neutral: experiment_tag += "tau " + str(scenario.tau) + ", "
	else: experiment_tag += "3rd payer, " # Auction manager has to find 3rd party funds.
	if scenario.is_removal_luc: experiment_tag += "luc removal, "
	else: experiment_tag += "ffi removal, "
	if scenario.use_updated_Wpt: experiment_tag += "Wpt fitted, "
	else: experiment_tag += "Wpt default, "
	experiment_tag += str(int(getStartYear())) + "-" + str(int(getFirstConstrainedYear()))
	return experiment_tag
# print(getExperimentTag(your_sample_scenario))

# Forestry, carbon removed in the optimal auction schedule.
def get_tree_schedule_carbon_removal(vpt): # vpt is {(bidder, year): value} with plain float values.
	Treetypes = getTreeTypes()
	mtC_removed = {t: 0.0 for t in getModelPeriods()}

	for tree in Treetypes:
		removal_data = database_interface.get_forestry_carbon_removal(tree)
		tc_dict = {int(year): tc for year, tc in removal_data}

		for u in getBidPeriods():
			if (tree, u) in vpt:
				vpt_val = vpt[tree, u]
				if vpt_val is not None and vpt_val != 0:
					for growth_year, tc in tc_dict.items():
						t = u + float(growth_year)
						if t in mtC_removed: mtC_removed[t] += vpt_val * tc
	return mtC_removed

def compute_scenario_summary_stats(bidder_year_rows):
	"""Return (avg_emitter_price, avg_remover_price, emissions_gtc, removal_cost_trillions, emitters_pay_trillions, removers_get_trillions)."""
	removers = set(getRemovers())
	emitters_set = set(getEmitters())
	carbon = [(qty, dp) for b, yr, qty, pct, dp, ul, vs in bidder_year_rows if b == 'Carbon' and 2025.0 <= yr <= 2125.0 and dp is not None]
	ag = [dp for b, yr, qty, pct, dp, ul, vs in bidder_year_rows if b == 'Agriculture' and 2025.0 <= yr <= 2125.0 and dp is not None]
	removal = sum(qty * dp for b, yr, qty, pct, dp, ul, vs in bidder_year_rows if b in removers and 2025.0 <= yr <= 2125.0 and dp is not None)
	emitters_pay = sum(qty * dp for b, yr, qty, pct, dp, ul, vs in bidder_year_rows if b in emitters_set and dp is not None)
	removers_get = sum(qty * dp for b, yr, qty, pct, dp, ul, vs in bidder_year_rows if b in removers and dp is not None)
	return (sum(dp for _, dp in carbon) / len(carbon) if carbon else None,
		sum(ag) / len(ag) if ag else None,
		sum(qty for qty, _ in carbon) / 1000.0 if carbon else None,
		removal / 1_000_000.0,
		emitters_pay / 1_000_000.0,
		removers_get / 1_000_000.0)

def get_land_rent(scenario_id):
	"""Return total_area * sum_t(pi(Forestry_Land_t)) in trillions for the given scenario.
	This is the rent earned by forestry bidders from the land constraint —
	a term missing from the Vpt-dual-based netrevenue calculation."""
	forestry_meta = database_interface.get_forestry_contractdata()
	total_area = sum(meta['available_area_mhectares'] for meta in forestry_meta.values())
	conn = sqlite3.connect(getSolutionsDBPath())
	cursor = conn.cursor()
	cursor.execute("SELECT COALESCE(SUM(pi), 0.0) FROM constraint_duals WHERE scenario_id = ? AND constraint_name LIKE 'Forestry_Land_%'", (scenario_id,))
	sum_pi = cursor.fetchone()[0]
	conn.close()
	return total_area * sum_pi / 1_000_000.0

def print_results_text(scenario_id):
	conn = sqlite3.connect(getSolutionsDBPath())
	cursor = conn.cursor()
	cursor.execute("""SELECT id, name, discount_rate, tau, is_revenue_neutral, emitters_pay, removers_get, net_revenue, Avg_emitter_price_2025_2125,
		Avg_remover_price_2025_2125, Emissions_2025_2125, is_land_constraint_implicit FROM scenarios WHERE id = ?""", (scenario_id,))
	id, name, disc, tau, is_rev_neutral, emitters_pay, removers_get, net_revenue, emitter_price_C, remover_price_C, total_emissions, is_implicit = cursor.fetchone()
	source_id = scenario_id
	if is_implicit:
		source_id = int(name.split(',')[0].split()[-1])
		cursor.execute("SELECT name FROM scenarios WHERE id = ?", (source_id,))
		source_name = cursor.fetchone()[0]
	conn.close()
	emitter_price_CO2 = round(emitter_price_C * 12.0/44.0, 2)
	remover_price_CO2 = round(remover_price_C * 12.0/44.0, 2)
	emitter_price_C, remover_price_C = round(emitter_price_C, 2), round(remover_price_C, 2)

	final_text = f"{id}, {name}: For this case, with a {disc * 100:.4g}% discount rate, emitters pay about ${-emitters_pay:.2f} trillion over 100 years to carbon removers"
	if is_implicit: final_text = f"Based on scenario {source_id}." + final_text
	if is_rev_neutral:
		final_text += f" with no third party payments. Emitters are carbon negative. Because emitters pay the surcharge τ = {tau} for drawdown,"
		final_text += f" emitters face an average price of about ${-emitter_price_C:.2f}/tC (${-emitter_price_CO2:.2f}/tCO2)."
		final_text += f" Removers face a price of ${remover_price_C:.2f}/tC (${remover_price_CO2:.2f}/tCO2)."
		final_text += f" From 2025 to 2125, total carbon emissions are {total_emissions:.1f} GtC."
	else:
		final_text += f". Emitters are carbon neutral. The auction manager must find a third party to pay an additional ${net_revenue:.2f} trillion for drawdown."
		final_text += f" Total drawdown therefore costs about ${removers_get:.2f} trillion."
		final_text += f" Emitters and removers face an average price of about ${emitter_price_C:.2f}/tC (${emitter_price_CO2:.2f}/tCO2)."
		final_text += f" From 2025 to 2125, total carbon emissions are {total_emissions:.1f} GtC."
	with open(getOutputDirectory() + "Summary_of_estimates_to_end_global_warming.txt", "a", encoding="utf-8") as f:
		f.write(final_text + "\n\n")
	return final_text
# if __name__ == '__main__': print (print_results_text(11))
