# Simulation of SMDAMAGE, by John F Raffensperger. 10 Aug 2019, 5 Aug 2026. I've been at it a while!
# SMDAMAGE_0 is the long-run revenue-negative model from my 2021 paper.
# SMDAMAGE_1 is the long-run revenue-neutral model.
# SMDAMAGE_2 is the short-run (e.g., 8-year auctions) revenue-neutral model. This model could be implemented in an emission trading system.

# Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
# Critical values: discount rate in discount_rate(), StartYear (e.g., 2025), BeginConstraintYear (warming deadline, e.g., 2125), revenue neutrality as REVENUE_NEUTRAL, and InitialTemperature.

# =============================================================================================
# Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# >>> Part III. KEY PROGRAM smdamage_models.py.
# Part IV. Running Hector on SMDAMAGE output: hector_interface.py. Called from the experiments.py.
# Parts V, VI, and VII: experiments in experiments.py.
# =============================================================================================

import database_interface # reads the SMDAMAGE database.
import defaults_and_utilities # Default parameters and utility functions
import hector_interface # Hector pulse generation functions.
from pulp import * #pulp.pulpTestAll() # to solve the linear programs.
import time # for timing the run.
import datetime
import sqlite3
import numpy as np

SOLVE_RESTRICTED = True # use column generation for faster solutions in run_SMDAMAGE and run_SMDAMAGE_for_tau.

# Retrieve warming parameters from the database and collect them into the Wpt dictionary for all bidders.
def get_warming_effects(scenario): # Get warming effects in degrees Celsius in each period, based on the solution vpt.
	Pulse = database_interface.getPulse() # Reads the Pulse input file from database.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = defaults_and_utilities.getRemovers() # ['luc', 'Agriculture', 'Seaweed', ...]

	# Fetch all bidders dynamically to ensure Wpt_dict is initialized for everything in PT_set
	AllBidders = [b['bidder_name'] for b in database_interface.get_bidders()]

	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	# Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	Wpt_dict = {(p, float(t0)): 0.0 for p in set(AllBidders + Emitters + Removers + ['luc']) for t0 in range(defaults_and_utilities.getPulseDataLength())} # >= 0.
	scaleCelsius = 1000.0 # Thousandths of a degree.

	if scenario.use_updated_Wpt: Wpt_pkl = database_interface.get_fitted_wpt(defaults_and_utilities.getSolutionsDBPath(), scenario.calibration_scenario_id) # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
	for t0 in range(defaults_and_utilities.getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		if scenario.use_updated_Wpt: # If not variable in SMDAMAGE_Fit_W, then it will be the same as in the original pulse file.
			Wpt_dict [('luc', float(t0))] = Wpt_pkl[('luc', float(t0))]
			Wpt_dict [('Carbon', float(t0))] = Wpt_pkl[('Carbon', float(t0))]
		else:
			# Looks dumb to have 1000 in the numerator and denominator, but this is for clarity. Denominator 1000 converts degrees C/gigaton to degrees C/megaton. Numerator 1000 converts degrees to thousandths of a degree.
			Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
			Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0

		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('luc', float(t0))]
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]

		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]

	# A hectare of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	ForestryBidders = database_interface.get_forestry_bidder_names()
	all_removal_data = database_interface.get_all_forestry_carbon_removal() # Batch DB call: one query for all forestry bidders.
	pulse_len = defaults_and_utilities.getPulseDataLength()
	ag_wpt_arr = np.array([Wpt_dict[('Agriculture', float(lag))] for lag in range(pulse_len)])
	for tree in ForestryBidders:
		removal_data = all_removal_data.get(tree, [])
		tree_wpt_arr = np.zeros(pulse_len)
		for year, tc in removal_data:
			length = pulse_len - year
			if length > 0: tree_wpt_arr[year:] += tc * ag_wpt_arr[:length] * scaleCelsius / 1000.0
		for t0 in range(pulse_len): Wpt_dict[(tree, float(t0))] = float(tree_wpt_arr[t0])

	# 	Units: C2F6: kt/yr, CF4: kt/yr, CH4: MtCH4/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, N2O: MtN2O-N/yr
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(defaults_and_utilities.getPulseDataLength()): Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]
	return Wpt_dict

# Read all current bids from the database.
def read_bids(scenario):
	AllBidPeriods = defaults_and_utilities.getBidPeriods()
	StartYear = defaults_and_utilities.getStartYear()

	Bapt = {} # Bid price for agent a, pollutant p, time period t.
	Uapt = {} # Upper bid quantity, kg, for agent a, pollutant p, time period t.
	APT_set = set() # [(a, p, t),...]
	PT_set = set()
	Bidders = database_interface.get_bidders()
	forestry_bidder_names = set(database_interface.get_forestry_bidder_names()) # Cache: avoid one DB call per bidder.
	all_bids_data = database_interface.get_all_bids(scenario.discount_rate_base) # Batch: one DB call for all bidders.
	for bidder in Bidders:
		bidder_name = bidder['bidder_name']
		bids = all_bids_data.get(bidder_name, [])

		# Check for forestry bidders (units == 'mhectares' and discount_rate (in db) not NULL)
		# NOTE: database_interface.get_bids filters out other forestry rates but includes non-forestry (NULL discount rate).
		is_forestry = bidder['units'] == 'mhectares' and bidder_name in forestry_bidder_names
		if is_forestry and not bids: raise ValueError(f"No bids found for forestry bidder '{bidder_name}' at discount rate {scenario.discount_rate_base}. Check the database.")

		for t in AllBidPeriods:
			PT_set.add((bidder_name, t))
			for bidstep, (price, quantity) in enumerate(bids):
				APT_set.add((bidstep, bidder_name, t))
				if bidder['units'] == 'kt':
					# For ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6'], data is given in $/ton and quantities are kilotons, but decision variables should be $million/kiloton.
					# Thus, $500/ton --> $0.5 million per kiloton, so we need to divide by 1000.
					Bapt[bidstep, bidder_name, t] = price * scenario.discount_rate(t - StartYear)/1000
				else: Bapt[bidstep, bidder_name, t] = price * scenario.discount_rate(t - StartYear)
				Uapt[bidstep, bidder_name, t] = quantity / hector_interface.getPeriodsPerYear()
	return Bapt, Uapt, APT_set, PT_set

def Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants, tau_override=None, tau_mode="standard", restrict_columns=True, forestry_fixed_ub=None):
	"""
	Called by run_SMDAMAGE and run_SMDAMAGE_for_tau. If not scenario.is_revenue_neutral, this function solves SMDAMAGE_0, else this function solves SMDAMAGE_1.
	The function runs a simplified column generation algorithm, starting with a restricted set of columns if available in the database.
	tau_mode: if "standard", then tau is a scalar used for all years; elsif "dynamic", tau[t] can be a different value for every period.
	restrict_columns: if False, all (a,p,t) columns are active (no warm-starting from DB). With an empty solutions database, you're stuck with a big first solve.
	"""
	# 1. Get general parameters.
	restrict_columns = SOLVE_RESTRICTED

	Emitters = defaults_and_utilities.getEmitters()
	local_tau = tau_override if tau_override is not None else scenario.tau
	BeginConstraintYear = int(defaults_and_utilities.getFirstConstrainedYear())
	ModelPeriods = defaults_and_utilities.getModelPeriods()
	ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))]

	# 2. Fetch bidder metadata to determine direction (Emitter/Remover)
	# use_scenario_id = 6 # If you want to start from a specific scenario for speed. Otherwise, the code loads nonzero columns from all previous solutions.
	# previous_acceptedbids, previous_bindingrows, _ = get_previous_acceptedbidsteps_bindingrows_and_prices (scenario_id = use_scenario_id)
	previous_acceptedbids, _, _ = database_interface.get_previous_acceptedbidsteps(defaults_and_utilities.getSolutionsDBPath())
	bidder_metadata = {b['bidder_name']: b for b in database_interface.get_bidders()}
	# If smdamage_solutions.db is empty, run the first model with all variables. It'll be slow, but later models will run much faster.
	if not previous_acceptedbids: print ("The solutions database smdamage_solutions.db is empty, so the first model run will be slow. Later models should solve much faster.")
	restricted_APT_set = set(APT_set) if (not restrict_columns or not previous_acceptedbids) else {(a, p, t) for (a, p, t) in APT_set if (a, p, t) in previous_acceptedbids}
	restricted_PT_set = {(p, t) for (a, p, t) in restricted_APT_set}
	forestry_bidder_names_set = set(database_interface.get_forestry_bidder_names()) if forestry_fixed_ub is not None else set()
	if forestry_fixed_ub is not None:
		restricted_APT_set = {(a, p, t) for (a, p, t) in restricted_APT_set if p not in forestry_bidder_names_set}
		restricted_APT_set |= set(forestry_fixed_ub.keys())

	bid_periods = defaults_and_utilities.getBidPeriods()
	inflate2020_to_2025 = defaults_and_utilities.inflate_2020_to_2025()
	StartYear = defaults_and_utilities.getStartYear()
	_all_bids_data = database_interface.get_all_bids(scenario.discount_rate_base) # Batch: one DB call for all bidders.
	all_bids = {p: _all_bids_data.get(p, []) for p in set(p for p, t in PT_set)}

	# Pre-build variables and constraint expressions outside the loop (items 1, 2, 5), because these do not depend on restricted_APT_set.
	vpt = {(p, t): LpVariable(f"vpt({p},{t})", None, None) for (p, t) in PT_set}
	temperatureChange = {t: LpVariable(f"tempChange({t})", None, None) for t in ModelPeriods}
	if scenario.is_revenue_neutral: taxedTemperatureChange = {t: LpVariable(f"taxedTempChange({t})", None, None) for t in ModelPeriods}
	sparse_Wpt = {k: v for k, v in Wpt_dict.items() if v != 0.0}

	# Total area, used below in 3.2 land constraint.
	forestry_contract_data = database_interface.get_forestry_contractdata()
	total_area = sum(meta['available_area_mhectares'] for meta in forestry_contract_data.values())

	temp_exprs = {t: lpSum(sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if u <= t and (p, float(t - u)) in sparse_Wpt) - temperatureChange[t] for t in ModelPeriods}
	if scenario.is_revenue_neutral:
		if tau_mode == "dynamic" and isinstance(local_tau, dict): # tau is a time indexed dictionary.
			taxed_exprs = {t: (local_tau[t] * lpSum(sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if p in Emitters and u <= t and (p, float(t - u)) in sparse_Wpt)
				+ lpSum(sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if p not in Emitters and u <= t and (p, float(t - u)) in sparse_Wpt) - taxedTemperatureChange[t]) for t in ModelPeriods}
		else: # tau is a scalar.
			taxed_exprs = {t: (lpSum(local_tau * sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if p in Emitters and u <= t and u <= BeginConstraintYear - 1.0 and (p, float(t - u)) in sparse_Wpt)
				+ lpSum(sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if p in Emitters and u <= t and u >= BeginConstraintYear and (p, float(t - u)) in sparse_Wpt)
				+ lpSum(sparse_Wpt[(p, float(t - u))] * vpt[p, u] for (p, u) in PT_set if p not in Emitters and u <= t and (p, float(t - u)) in sparse_Wpt) - taxedTemperatureChange[t]) for t in ModelPeriods}

	iterations = 0
	while True: # Column/row generation loop.
		# 3. Define the model and variables.
		iterations += 1
		start_solve_time = time.time()
		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
		qapt = {(a, p, t): LpVariable(f"qapt({a},{p},{t})", 0.0, forestry_fixed_ub[(a, p, t)] if (forestry_fixed_ub is not None and (a, p, t) in forestry_fixed_ub) else Uapt[a, p, t]) for (a, p, t) in APT_set if (a, p, t) in restricted_APT_set}

		# 3.1 Objective
		SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025() * lpSum(Bapt[a, p, t] * qapt[a, p, t] for (a, p, t) in qapt), "Total_value"

		# 3.2. Forestry land constraint: one per bid period, summed over all bidders (always all rows).
		if forestry_fixed_ub is None:
			for t in bid_periods: SMDAMAGE += lpSum(vpt[bidder_name, u]
							for bidder_name, bidder_contract in forestry_contract_data.items()
							for u in bid_periods if (bidder_name, u) in vpt and u <= t <= u + bidder_contract['rotation_year'] - 1) \
								<= total_area, f"Forestry_Land_{t}"

		# 3.3. Vpt rows
		Vname = {}
		for (p, t) in PT_set:
			Vname[(p, t)] = f"Vpt({p},{t})"
			valid_steps = [a for a in BidStepSet[p, t] if (a, p, t) in qapt]
			SMDAMAGE += vpt[p, t] == lpSum([qapt[a, p, t] for a in valid_steps]), Vname[(p, t)]

		# 3.4. Temperature constraints (expressions pre-built before the loop).
		# 3.4.1. Right hand side zero. This allows revenue neutrality.
		for t in ModelPeriods: SMDAMAGE += temp_exprs[t] == 0.0, f"Temp_t({t})"

		# 3.4.2. Taxed temperature constraints.
		if scenario.is_revenue_neutral:
			for t in ModelPeriods: SMDAMAGE += taxed_exprs[t] == 0, f"TaxedTemp_t({t})"
			for t in ConstraintPeriods: SMDAMAGE += taxedTemperatureChange[t] <= 0.0, f"Capt({t})"
		else:
			Capt = {t: -1.0*scenario.initial_temperature for t in ConstraintPeriods}
			for t in ConstraintPeriods: SMDAMAGE += temperatureChange[t] <= Capt[t], f"Capt({t})"

		# 4. Solve. Write a debugging model if you like.
		# SMDAMAGE.writeLP(defaults_and_utilities.getOutputDirectory() + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".lpt")
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0, options=['-threads', '8']))]
		end_solve_time = time.time()
		dual_pi = {(p, t): (SMDAMAGE.constraints[Vname[(p, t)]].pi or 0.0) for (p, t) in Vname} # item 4.

		# 5. Decide whether the linear program needs more columns.
		expanded = False
		added_cols = 0

		# 5.1. Get the current highest accepted bid step number.
		current_front_max = {(p, t): -1 for (p, t) in PT_set}
		for (a, p, t) in restricted_APT_set:
			if a > current_front_max[(p, t)]: current_front_max[(p, t)] = a

		# 5.2. Decide whether to add the next bid steps.
		for (p, t) in PT_set:
			if forestry_fixed_ub is not None and p in forestry_bidder_names_set: continue
			meta = bidder_metadata[p]
			if meta['class'] == 'Emitter': continue
			max_a = current_front_max[(p, t)]
			bids_p = all_bids[p]
			dual = dual_pi.get((p, t), 0.0)
			discount = inflate2020_to_2025 * scenario.discount_rate(t - StartYear)
			kt_divisor = 1000.0 if meta['units'] == 'kt' else 1.0

			# For an emitter, if their (positive) objective coefficient + vpt.pi > 0.0, their bid should enter. The emitter is willing to pay more than that for the right to emit. obj_emitter + pi >= 0.
			# For a remover, if their (negative) objective coefficient + vpt.pi < 0.0, their bid should enter. The remover is willing to remove carbon for less than a stated price. pi - obj_remover >= 0.
			for a in range(max_a + 1, len(bids_p)):
				if (a, p, t) in restricted_APT_set: continue
				next_coeff, _ = bids_p[a]
				next_reduced_cost = next_coeff * discount / kt_divisor + dual
				if next_reduced_cost > -0.01: # Take columns with near zero reduced cost to kill off degeneracy.
					restricted_APT_set.add((a, p, t))
					expanded = True
					added_cols += 1
				else: # Bring the next two bids into the optimization. Just trying to be clever.
					# for extra_a in range(a, min(a + 2, len(bids_p))):
					# 	restricted_APT_set.add((extra_a, p, t))
					# 	added_cols += 1
					break

		obj_val = value(SMDAMAGE.objective) if solve_status == "Optimal" else 0.0
		print(f"  Iteration {iterations}. Solve Time: {end_solve_time - start_solve_time:.2f}s. status: {solve_status}. Obj: {obj_val:,.2f}. Added {added_cols} cols.")

		if not expanded:
			# Final solution reached, one last check on objective coefficients
			scenario.solution_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			return SMDAMAGE, qapt, vpt, temperatureChange, (taxedTemperatureChange if scenario.is_revenue_neutral else None), Vname, solve_status

# We've solved the optimization, now store it in the database and wherever else you want to put it.
# Called from run_SMDAMAGE and run_SMDAMAGE_for_tau.
def save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data=None, scenario_series_entries=None, bidder_year_rows=None, is_land_constraint_implicit=0):
	db_path = defaults_and_utilities.getSolutionsDBPath()
	defaults_and_utilities.ensure_solutions_db()

	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()

	sol_datetime = getattr(scenario, 'solution_datetime', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
	net_revenue = -sum(vpt[p, t].varValue * SMDAMAGE.constraints[Vname[(p, t)]].pi for (p, t) in Vname if Vname[(p, t)] in SMDAMAGE.constraints) / 1_000_000.0 # trillions
	forestry_meta = database_interface.get_forestry_contractdata()
	land_rent = sum(meta['available_area_mhectares'] for meta in forestry_meta.values()) * sum((c.pi or 0.0) for name, c in SMDAMAGE.constraints.items() if name.startswith('Forestry_Land_')) / 1_000_000.0 # trillions
	cursor.execute("INSERT INTO scenarios (name, discount_rate, initial_temp, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, solver_status, net_revenue, land_rent, objective_value, solution_datetime, calibration_scenario, is_land_constraint_implicit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		(defaults_and_utilities.getExperimentTag(scenario), scenario.discount_rate_base, scenario.initial_temperature, scenario.tau, 1 if scenario.is_revenue_neutral else 0,
		1 if scenario.is_removal_luc else 0, 1 if scenario.use_updated_Wpt else 0, LpStatus[SMDAMAGE.status], net_revenue, land_rent, value(SMDAMAGE.objective) / 1_000_000.0, sol_datetime,
		scenario.calibration_scenario_id, is_land_constraint_implicit))
	scenario_id = cursor.lastrowid

	# Save the nonzero solution.
	variables = [(scenario_id, p, t, a, var.varValue) for (a, p, t), var in qapt.items() if var.varValue != 0.0]
	if variables: cursor.executemany("""INSERT INTO variables (scenario_id, bidder, year, bid_step, value) VALUES (?,?,?,?,?) ON CONFLICT(scenario_id, bidder, year, bid_step) DO UPDATE SET value=excluded.value""", variables)
	duals = [(scenario_id, c_name, c.pi) for c_name, c in SMDAMAGE.constraints.items() if c.pi != 0.0]
	if duals: cursor.executemany("""INSERT INTO constraint_duals (scenario_id, constraint_name, pi) VALUES (?,?,?) ON CONFLICT(scenario_id, constraint_name) DO UPDATE SET pi=excluded.pi""", duals)

	if temp_data:
		for source, year_to_value in temp_data.items():
			cursor.executemany("""INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?) ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source""",
				[(scenario_id, source, float(year), value, None, 'SMDAMAGE') for year, value in year_to_value.items()])

	if scenario_series_entries:
		for series_name, year_to_value, units in scenario_series_entries:
			cursor.executemany("""INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?) ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source""",
				[(scenario_id, series_name, float(year), value, units, 'SMDAMAGE') for year, value in year_to_value.items()])

	if bidder_year_rows:
		cursor.executemany("""INSERT INTO scenario_bidder_year (scenario_id, bidder, year, quantity_value, pct_max_bid, dual_price, unit_label, value_source)
			VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(scenario_id, bidder, year) DO UPDATE SET quantity_value=excluded.quantity_value,
			pct_max_bid=excluded.pct_max_bid, dual_price=excluded.dual_price, unit_label=excluded.unit_label, value_source=excluded.value_source""",
			[(scenario_id,) + row for row in bidder_year_rows])
	avg_ep, avg_rp, emis, removal, emitters_pay, removers_get = defaults_and_utilities.compute_scenario_summary_stats(bidder_year_rows or [])
	cursor.execute("UPDATE scenarios SET Avg_emitter_price_2025_2125=?, Avg_remover_price_2025_2125=?, Emissions_2025_2125=?, Removal_cost_2025_2125=?, emitters_pay=?, removers_get=? WHERE id=?",
		(avg_ep, avg_rp, emis, removal, emitters_pay, removers_get, scenario_id))

	conn.commit()
	conn.close()
	return scenario_id

# Main function. With solve_SMDAMAGE above, solve the SMDAMAGE model to find the best schedule of emissions and carbon removal.
def run_SMDAMAGE(scenario):
	start_time = time.time()
	defaults_and_utilities.ensure_solutions_db()
	if scenario.is_revenue_neutral: print ("\nSMDAMAGE_1. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	else: print ("\nSMDAMAGE_0. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")

	BeginConstraintYear = int(defaults_and_utilities.getFirstConstrainedYear())
	ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))]
	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.

	# Bids. All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)
	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t]
		BidStepSet[p,t].append(a)

	# Only emitters face tax tau. Removers do not. Reminder, Carbon is 'ffi' in pulsefile.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']
	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.

	# Solve the model with a simple column and row generation algorithm.
	SMDAMAGE, qapt, vpt, temperatureChange, taxedTemperatureChange, Vname, solve_status = Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants)

	netrevenue = 0.0 # Show net revenue with marginal cost pricing.
	yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
	for (p,t) in PT_set:
		netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi

	# print ("Saving solution to CSV.")
	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}
	bidder_year_rows = []
	for t in defaults_and_utilities.getBidPeriods():
		for p in Pollutants:
			qty = vpt[p,t].varValue
			pct = qty/TotalU[p,t] if TotalU[p,t] != 0.0 else None
			dual = SMDAMAGE.constraints[Vname[(p,t)]].pi if Vname[(p,t)] in SMDAMAGE.constraints else None
			bidder_year_rows.append((p, t, qty, pct, dual, Units[p], "derived"))

	# SMDAMAGE_fit_W uses vpt reconstructed from the solutions database.
	temp_data = {"SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated": {t: vpt['Carbon',t].varValue for t in defaults_and_utilities.getBidPeriods()},
		"SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated": yearlyrevenue,
		"SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated": {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()},}
	if scenario.is_revenue_neutral: temp_data["SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"] = {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()}

	actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
	scenario_series_entries = [(actual_source, {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C")]
	if scenario.is_revenue_neutral:
		taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
		scenario_series_entries.append((taxed_source, {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C"))
	scenario_series_entries.append(("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal({k: v.varValue for k, v in vpt.items()}), "mtC"))
	scenario_id = save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data, scenario_series_entries, bidder_year_rows)
	land_rent = defaults_and_utilities.get_land_rent(scenario_id)
	print (f"Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue / 1_000_000.0:.4f} trillion. Land rent {land_rent:.4f} trillion. Tau {local_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + f" thousandths C. Total time {time.time() - start_time:.1f}s.")

	return scenario_id
# END run_SMDAMAGE().

def solve_smdamage_with_implicit_land_constraints(scenario_id):
	"""Rebuild the model for scenario_id with no land constraints; forestry qapt upper bounds fixed to DB optimal values."""
	db_path = defaults_and_utilities.getSolutionsDBPath()
	defaults_and_utilities.ensure_solutions_db()
	start_time = time.time()
	params = database_interface.get_scenario_full_params(db_path, scenario_id)
	scenario = defaults_and_utilities.Scenario(
		comment=f"Implicit land {scenario_id}",
		discount_rate=params['discount_rate'],
		initial_temperature=params['initial_temp'],
		is_revenue_neutral=bool(params['is_revenue_neutral']),
		tau=params['tau'],
		is_removal_luc=bool(params['is_removal_luc']),
		use_updated_Wpt=bool(params['use_updated_Wpt']),
		calibration_scenario_id=params['calibration_scenario'])
	print(f"\nSMDAMAGE implicit land constraints, source scenario {scenario_id}. {time.asctime(time.localtime(time.time()))}.")

	forestry_bidder_names = set(database_interface.get_forestry_bidder_names())
	all_qapt = database_interface.get_qapt_values_from_db(db_path, scenario_id)
	forestry_fixed_ub = {(a, p, t): v for (a, p, t), v in all_qapt.items() if p in forestry_bidder_names}

	Wpt_dict = get_warming_effects(scenario)
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)
	Pollutants = sorted(list(set([p for p, t in PT_set])))
	BidStepSet = {}
	for (p, t) in PT_set: BidStepSet[p, t] = []
	TotalU = {(p, t): 0.0 for (p, t) in PT_set}
	for (a, p, t) in APT_set:
		TotalU[p, t] += Uapt[a, p, t]
		BidStepSet[p, t].append(a)

	SMDAMAGE, qapt, vpt, temperatureChange, taxedTemperatureChange, Vname, solve_status = Solve_SMDAMAGE(
		scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants, forestry_fixed_ub=forestry_fixed_ub)

	yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
	for (p, t) in PT_set: yearlyrevenue[t] -= vpt[p, t].varValue * SMDAMAGE.constraints[Vname[(p, t)]].pi

	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}
	bidder_year_rows = []
	for t in defaults_and_utilities.getBidPeriods():
		for p in Pollutants:
			qty = vpt[p, t].varValue
			pct = qty / TotalU[p, t] if TotalU[p, t] != 0.0 else None
			dual = SMDAMAGE.constraints[Vname[(p, t)]].pi if Vname[(p, t)] in SMDAMAGE.constraints else None
			bidder_year_rows.append((p, t, qty, pct, dual, Units[p], "derived"))

	temp_data = {"SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated": {t: vpt['Carbon', t].varValue for t in defaults_and_utilities.getBidPeriods()},
		"SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated": yearlyrevenue,
		"SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated": {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()}}
	if scenario.is_revenue_neutral: temp_data["SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"] = {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()}

	actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
	scenario_series_entries = [(actual_source, {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C")]
	if scenario.is_revenue_neutral:
		taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
		scenario_series_entries.append((taxed_source, {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C"))
	scenario_series_entries.append(("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal({k: v.varValue for k, v in vpt.items()}), "mtC"))

	new_scenario_id = save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data, scenario_series_entries, bidder_year_rows, is_land_constraint_implicit=1)
	print(f"Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. 2125 temp {round(scenario.initial_temperature + temperatureChange[2125].varValue, 3)} thousandths C. Total time {time.time() - start_time:.1f}s.")
	return new_scenario_id

# Here's how the subgradient optimization works.
def update_tau (old_temp, current_temp, old_tau, current_tau, step_size):
	total_change = 0.0
	new_tau = {t: 1.0 for t in old_tau}
	for t in old_tau:
		if t >= defaults_and_utilities.getFirstConstrainedYear():
			# new_tau[t] = linear_interpolation(0.0, [old_temp[t], current_temp[t]], [old_tau[t], current_tau[t]])
			# Keep in mind that tau[t] is the tax on the effect year, not the emission year. I doubt anyone will ever read this, but it's a big f'g deal.
			# If the current_temp[t] == 0, keep tau as is. If current_temp[t] > 0, tau should rise. If current_temp[t] < 0, tau can fall.
			new_tau[t] = max(1.0, current_tau[t] + step_size*current_temp[t]/1000.0)
			total_change += abs(new_tau[t] - old_tau[t])
	return total_change, new_tau
# Examples:
# old_tau = {2125: 1.5, 2126: 1.4, 2127: 2.0}
# old_temp = {2125: 100.0, 2126: 120.0, 2127: -80.0}
# current_tau = {2125: 1.7, 2126: 1.5, 2127: 1.8}
# current_temp = {2125: -100.0, 2126: 12.0, 2127: 80.0}
# print("\n\n", update_tau(old_temp, current_temp, old_tau, current_tau, 1.0))

# Use subgradient optimization on SMDAMAGE_1 to find the best tau by year.
# Warning! Very slow, e.g., 8 hours to run this.
def run_SMDAMAGE_for_tau(scenario):
	defaults_and_utilities.ensure_solutions_db()
	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)

	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t]
		BidStepSet[p,t].append(a)

	# Decision variables
	qapt = {(a,p,t): LpVariable("qapt(" + str(a) + "," + p + "," + str(t) + ")", 0.0, Uapt[a,p,t]) for (a, p, t) in APT_set}
	vpt = {(p,t): LpVariable("vpt(" + p + "," + str(t) + ")", None, None) for (p, t) in PT_set} # Must be a free variable.

	Emitters = defaults_and_utilities.getEmitters() # Emitters face tax tau. Others do not.

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}

	# You might want to solve the model for multiple BeginConstraintYears. Currently this does a single loop.
	for BeginConstraintYear in range(int(defaults_and_utilities.getFirstConstrainedYear()), int(defaults_and_utilities.getFirstConstrainedYear()) + 1, 1):
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= defaults_and_utilities.getStartYear() + defaults_and_utilities.getNumber_of_bid_years())

		# Initialize tau.
		old_tau = {t: 1.0 for t in defaults_and_utilities.getModelPeriods()} # When tau = 1, the market is net zero, which gets you only the current temperature into the future. But I want base zero.
		old_temp = {t: scenario.initial_temperature for t in ConstraintPeriods}
		current_tau = {t: scenario.tau if t in ConstraintPeriods else 1.0 for t in defaults_and_utilities.getModelPeriods()} # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.
		current_temp = {t: 0.0 for t in ConstraintPeriods}

		# Loop over tau[t] =================
		step_size = 2.0 # For subgradient optimization.
		for run in range(200): # At most 200 iterations, but see total_change stopping criteria below.
			# Use the restricted solver
			SMDAMAGE, qapt, vpt, temperatureChange, taxedTemperatureChange, Vname, solve_status = Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants,
					tau_override=current_tau, tau_mode="dynamic")

			# Calculate tau based on emissions and removals.
			for t in ConstraintPeriods: current_temp[t] = scenario.initial_temperature + temperatureChange[t].varValue

			# Subgradient optimization. Update temperature and tau for the next run.
			total_change, next_tau = update_tau(old_temp, current_temp, old_tau, current_tau, step_size)
			step_size = 0.9*step_size

			 # Stopping criteria.
			if total_change < 0.5: break # Sum of tau over 100 years, e.g., 1.7*100, this is a small percent.

			sum_of_under_shoot = 0.0 # error metric
			for t in ConstraintPeriods:
				sum_of_under_shoot += scenario.initial_temperature - temperatureChange[t].varValue
				old_temp[t] = scenario.initial_temperature + taxedTemperatureChange[t].varValue
				old_tau[t] = current_tau[t]
				current_tau[t] = next_tau[t]
			print (f"Run {run}. Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths C. Undershoot " + str(round(sum_of_under_shoot,0)) + ".")

		# Save temperature series for parity with run_SMDAMAGE().
		yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
		for (p, t) in PT_set:
			if (p, t) in Vname and Vname[(p, t)] in SMDAMAGE.constraints: yearlyrevenue[t] -= vpt[p, t].varValue * SMDAMAGE.constraints[Vname[(p, t)]].pi

		temp_data = {"SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated": {t: vpt['Carbon', t].varValue for t in defaults_and_utilities.getBidPeriods()},
			"SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated": yearlyrevenue,
			"SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated": {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()},}
		if scenario.is_revenue_neutral and taxedTemperatureChange is not None:
			temp_data["SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"] = {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()}
		temp_data["SMDAMAGE tau calibrated" if scenario.use_updated_Wpt else "SMDAMAGE tau uncalibrated"] = current_tau

		actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
		scenario_series_entries = [(actual_source, {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C")]
		if scenario.is_revenue_neutral and taxedTemperatureChange is not None:
			taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
			scenario_series_entries.append((taxed_source, {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C"))
		scenario_series_entries.append(("SMDAMAGE tau calibrated" if scenario.use_updated_Wpt else "SMDAMAGE tau uncalibrated", current_tau, "ratio"))
		scenario_series_entries.append(("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal({k: v.varValue for k, v in vpt.items()}), "mtC"))

		Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}
		bidder_year_rows = []
		for t in defaults_and_utilities.getBidPeriods():
			for p in Pollutants:
				qty = vpt[p, t].varValue
				pct = qty/TotalU[p,t] if TotalU[p,t] != 0.0 else None
				dual = SMDAMAGE.constraints[Vname[(p,t)]].pi if (p,t) in Vname and Vname[(p,t)] in SMDAMAGE.constraints else None
				bidder_year_rows.append((p, t, qty, pct, dual, Units[p], "derived"))

		scenario_id = save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data, scenario_series_entries, bidder_year_rows)
	return scenario_id

# SMDAMAGE_2. This modified version of run_SMDAMAGE() runs 2-year auctions, each of which must be revenue neutral. The auctions should use the calibrated Wpt values.
# This is the version that could actually be implemented. The auction manager (and policymakers I guess) would have to choose tau[t] in advance.
# We could end global warming with this.
def run_SMDAMAGE_short_auctions(years_in_auction, land_scale_factor, scenario):
	print ("\nSMDAMAGE_2, short auctions. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	AllBidPeriods = defaults_and_utilities.getBidPeriods()

	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)
	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t] # Used to calculate fraction of bid accepted in output.
		BidStepSet[p,t].append(a)

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}

	FixedPeriods = []
	Fixed_Vpt = {(p,t): 0.0 for (p,t) in PT_set}

	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Emitters face tax tau. Others do not. Reminder, Carbon is 'ffi' in pulsefile.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']

	forestry_meta = database_interface.get_forestry_contractdata()
	total_area = land_scale_factor * sum(meta['available_area_mhectares'] for meta in forestry_meta.values())
	all_qapt_rows = []
	all_duals = {}
	total_objective = 0.0
	all_vpt_values = {}
	all_Vname = {}
	all_yearlyrevenue = {}
	total_land_rent = 0.0
	last_solve_status = "Not solved"
	solution_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	# Run short auctions. Running this out to 2300 seems dumb, but we need it for a valid comparison with the other experiments.
	for startyear in range(int(min(AllBidPeriods)), int(max(AllBidPeriods)) - years_in_auction, years_in_auction):
	# for startyear in range(2025, 2133, years_in_auction):
		BidPeriods = [float(startyear + i) for i in range(years_in_auction)]

		# Decision variables
		qapt = {(a,p,t): LpVariable("qapt(" + str(a) + "," + p + "," + str(t) + ")", 0.0, Uapt[a,p,t]) for (a, p, t) in APT_set if t in BidPeriods}
		vpt = {(p,t): LpVariable("vpt(" + p + "," + str(t) + ")", None, None) for (p, t) in PT_set if t in BidPeriods} # Must be a free variable.

		BeginConstraintYear = int(defaults_and_utilities.getFirstConstrainedYear())
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= defaults_and_utilities.getStartYear() + defaults_and_utilities.getNumber_of_bid_years())

		# Create model & objective.
		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
		SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set if t in BidPeriods), "Total value" # Objective.

		# Land constraint. Subtract previously-committed land still in rotation.
		for t in AllBidPeriods:
			c_name = f"Forestry_Land_{t}"
			fixed_land = sum(Fixed_Vpt[bidder_name, u] for bidder_name, meta in forestry_meta.items() for u in FixedPeriods if u <= t <= u + meta['rotation_year'] - 1)
			SMDAMAGE += lpSum(vpt[bidder_name, u] for bidder_name, meta in forestry_meta.items()
				# rhs coming up slightly negative sometimes, resulting in infeasible models, hence max(0.0, ...).
				for u in BidPeriods if (bidder_name, u) in vpt and u <= t <= u + meta['rotation_year'] - 1) <= max(0.0, total_area - fixed_land), c_name

		# Vpt rows.
		Vname = {}
		for (p, t) in PT_set:
			if t in BidPeriods:
				Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
				SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]

		# Measuring (but not constraining) actual temperature change. If REVENUE_NEUTRAL, Temp_t equations should not constrain the model.
		temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]}
		for t in defaults_and_utilities.getModelPeriods() [len(FixedPeriods):]:
			SMDAMAGE += lpSum (sum([Wpt_dict[(p, float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if u <= t and u in FixedPeriods]
				+ [Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t and u in BidPeriods]) - temperatureChange[t]) == 0, "Temp_t(" + str(t) + ")"

		# Measuring taxed temperature change: includes Fixed_Vpt from past auctions so constraint is cumulative, not per-auction.
		# tau applies only to emitters with u < BeginConstraintYear; post-constraint-year emissions bear no surcharge.
		# This matches Solve_SMDAMAGE's taxed_exprs split so both models enforce revenue neutrality identically.
		taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]}
		FixedPeriods_set = set(FixedPeriods)
		for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]:
			SMDAMAGE += lpSum(
				[scenario.tau*Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in BidPeriods and u <= 1 + BeginConstraintYear]
				+ [Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in BidPeriods and u >= BeginConstraintYear]
				+ [Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t and u in BidPeriods]) \
				- taxedTemperatureChange[t] \
				+ sum([scenario.tau*Wpt_dict[(p,float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in FixedPeriods_set and u <= 1 + BeginConstraintYear]) \
				+ sum([Wpt_dict[(p,float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in FixedPeriods_set and u >= BeginConstraintYear]) \
				+ sum([Wpt_dict[(p,float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t and u in FixedPeriods_set]) \
				== 0, "TaxedTemp_t(" + str(t) + ")"
		for t in ConstraintPeriods:
			if t not in FixedPeriods: SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"

		# print ("5. Solving the model...")
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(threads=8, msg=0))]
		# solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD('HiGHS', msg=0))]
		print (f"SMDAMAGE_2, short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear) + ", tau=" + str(scenario.tau) + ", " + str(round(scenario.initial_temperature + temperatureChange [float(startyear + years_in_auction - 1)].varValue,3)) + " 000C.")

		# Save a debug model. Easy to open with Notepad or LP_SolveIDE, if your computer has the RAM for the big models. For example, I found the land constraint rhs could be slightly negative, resulting in infeasible models.
		if solve_status == "Infeasible": SMDAMAGE.writeLP(defaults_and_utilities.getOutputDirectory() + defaults_and_utilities.getExperimentTag(scenario) + "_" + str(startyear) + ".lpt")

		FixedPeriods = FixedPeriods + BidPeriods # Variables in BidPeriods are now fixed for next auction.

		netrevenue = 0.0 # Show net revenue with marginal cost pricing.
		yearlyrevenue = {t: 0.0 for t in BidPeriods}
		for (p,t) in PT_set:
			if t in BidPeriods:
				Fixed_Vpt[(p,t)] = vpt[p,t].varValue # Will be fixed in the next auction.
				netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
				yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi

		all_qapt_rows.extend([(p, t, a, var.varValue) for (a, p, t), var in qapt.items() if var.varValue != 0.0])
		all_duals.update({c_name: c.pi for c_name, c in SMDAMAGE.constraints.items() if c.pi != 0.0})
		total_objective += value(SMDAMAGE.objective)
		all_vpt_values.update({(p, t): vpt[p, t].varValue for (p, t) in vpt})
		all_Vname.update(Vname)
		last_solve_status = solve_status
		all_yearlyrevenue.update(yearlyrevenue)
		c_land = SMDAMAGE.constraints[f"Forestry_Land_{float(startyear)}"]
		if c_land: total_land_rent -= c_land.pi*c_land.constant  # dual Ã— (total_area - fixed_land[startyear])

	# Compute full temperature trajectories from Fixed_Vpt (all bid-period quantities accumulated above).
	# full_temp: actual temperature; full_taxed_temp: emitter warming multiplied by tau (for the revenue-neutrality constraint).
	Emitters_set = set(Emitters)
	full_temp = {t: scenario.initial_temperature + sum(Wpt_dict.get((p, float(t - u)), 0.0) * Fixed_Vpt[(p, u)] for (p, u) in PT_set if u <= t) for t in defaults_and_utilities.getModelPeriods()}
	if scenario.is_revenue_neutral:
		full_taxed_temp = {t: scenario.initial_temperature + sum((scenario.tau if p in Emitters_set else 1.0) * Wpt_dict.get((p, float(t - u)), 0.0) * Fixed_Vpt[(p, u)] for (p, u) in PT_set if u <= t) for t in defaults_and_utilities.getModelPeriods()}
	bidder_year_rows = [(p, t, all_vpt_values.get((p, t), 0.0),
		all_vpt_values.get((p, t), 0.0)/TotalU[p, t] if TotalU[p, t] != 0.0 else None,
		all_duals.get(all_Vname[(p, t)], 0.0) if (p, t) in all_Vname else None, Units[p], "derived")
		for t in defaults_and_utilities.getBidPeriods() for p in Pollutants]

	# Save solution to database.
	defaults_and_utilities.ensure_solutions_db()
	db_path = defaults_and_utilities.getSolutionsDBPath()
	net_revenue = -sum(all_vpt_values[(p, t)] * all_duals.get(all_Vname[(p, t)], 0.0) for (p, t) in all_Vname) / 1_000_000.0 # trillions
	land_rent = total_land_rent / 1_000_000.0 # trillions
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	cursor.execute("INSERT INTO scenarios (name, discount_rate, initial_temp, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, solver_status, net_revenue, land_rent, objective_value, solution_datetime, calibration_scenario, is_land_constraint_implicit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
		(defaults_and_utilities.getExperimentTag(scenario), scenario.discount_rate_base, scenario.initial_temperature, scenario.tau,
		 1 if scenario.is_revenue_neutral else 0, 1 if scenario.is_removal_luc else 0,
		 1 if scenario.use_updated_Wpt else 0, last_solve_status, net_revenue, land_rent, total_objective / 1_000_000.0, solution_datetime,
		 scenario.calibration_scenario_id, 0))
	scenario_id = cursor.lastrowid
	assert scenario_id, "Failed to insert short-auctions scenario into smdamage_solutions.db."
	if all_qapt_rows: cursor.executemany("INSERT INTO variables (scenario_id, bidder, year, bid_step, value) VALUES (?,?,?,?,?) ON CONFLICT(scenario_id, bidder, year, bid_step) DO UPDATE SET value=excluded.value",
		[(scenario_id, p, t, a, val) for p, t, a, val in all_qapt_rows])
	if all_duals: cursor.executemany("INSERT INTO constraint_duals (scenario_id, constraint_name, pi) VALUES (?,?,?) ON CONFLICT(scenario_id, constraint_name) DO UPDATE SET pi=excluded.pi",
		[(scenario_id, c_name, pi) for c_name, pi in all_duals.items()])
	actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
	series_entries = [(actual_source, full_temp, "thousandths_C"),
		("SMDAMAGE yearly revenue " + ("calibrated" if scenario.use_updated_Wpt else "uncalibrated"), all_yearlyrevenue, None),
		("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal(Fixed_Vpt), "mtC")]
	if scenario.is_revenue_neutral:
		taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
		series_entries.append((taxed_source, full_taxed_temp, "thousandths_C"))
	for series_name, year_to_value, units in series_entries:
		cursor.executemany("INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?) ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source",
			[(scenario_id, series_name, float(year), val, units, 'SMDAMAGE') for year, val in year_to_value.items()])
	if bidder_year_rows: cursor.executemany("INSERT INTO scenario_bidder_year (scenario_id, bidder, year, quantity_value, pct_max_bid, dual_price, unit_label, value_source) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(scenario_id, bidder, year) DO UPDATE SET quantity_value=excluded.quantity_value, pct_max_bid=excluded.pct_max_bid, dual_price=excluded.dual_price, unit_label=excluded.unit_label, value_source=excluded.value_source",
		[(scenario_id,) + row for row in bidder_year_rows])
	avg_ep, avg_rp, emis, removal, emitters_pay, removers_get = defaults_and_utilities.compute_scenario_summary_stats(bidder_year_rows)
	cursor.execute("UPDATE scenarios SET Avg_emitter_price_2025_2125=?, Avg_remover_price_2025_2125=?, Emissions_2025_2125=?, Removal_cost_2025_2125=?, emitters_pay=?, removers_get=? WHERE id=?",
		(avg_ep, avg_rp, emis, removal, emitters_pay, removers_get, scenario_id))
	conn.commit()
	conn.close()
	return scenario_id
# END run_SMDAMAGE_short_auctions().

def get_SMDAMAGE_temps_actual_and_taxed(scenario):
	db_path = defaults_and_utilities.getSolutionsDBPath()
	scenario_id = database_interface.get_scenario_id(db_path, defaults_and_utilities.getExperimentTag(scenario))
	if scenario_id is None: return {}, {}
	actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
	SMDAMAGE_temperature = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id, actual_source)
	if not scenario.is_revenue_neutral:
		return {}, SMDAMAGE_temperature
	taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
	taxed_temps = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id, taxed_source)
	return taxed_temps, SMDAMAGE_temperature

# Part V. Experiments are in experiments.py.
