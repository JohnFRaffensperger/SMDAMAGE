# Simulation of SMDAMAGE, by John F Raffensperger. 10 Aug 2019, 10 Sep 2022, 17 May 2023, 3 Feb 2025, 17 Mar 2026, 21 Jul 2026.
# Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
# Critical values: discount rate in discount_rate(), StartYear (e.g., 2025), BeginConstraintYear (warming deadline, e.g., 2125), revenue neutrality as REVENUE_NEUTRAL, and InitialTemperature.

# =============================================================================================
# Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# >>> Part III. MAIN PROGRAM. "SMDAMAGE revenue neutral.py".
# Part IV. Running Hector on SMDAMAGE output: hector_interface.py. Called from the experiments here.
# >>> Parts V, VI, and VII: experiments are at the bottom of this file.
# =============================================================================================

import database_interface # reads the SMDAMAGE database.
import defaults_and_utilities # Default parameters and utility functions
import hector_interface # Hector pulse generation functions.
import plotting_utils # Consolidated plotting functions
from pulp import * #pulp.pulpTestAll() # to solve the linear programs.
import time # for timing the run.
import datetime
import sqlite3
import os
import numpy as np
import wpt_calibration # Wpt calibration functions

SOLVE_RESTRICTED = True

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

	if scenario.use_updated_Wpt: Wpt_pkl = database_interface.get_fitted_wpt(defaults_and_utilities.getSolutionsDBPath()) # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
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
	# Old convolution loop:
	# for tree in ForestryBidders:
	# 	removal_data = database_interface.get_forestry_carbon_removal(tree) # Returns list of (year, tc)
	# 	for year, tc in removal_data:
	# 		for coolingyear in range(year, defaults_and_utilities.getPulseDataLength()):
	# 			# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth.
	# 			Wpt_dict[(tree, float(coolingyear))] += tc * Wpt_dict [('Agriculture', float(coolingyear - year))] * scaleCelsius / 1000.0

	# 	CH4: MtCH4/yr, N2O: MtN2O-N/yr, C: MtC/yr, NMVOC: Mt/yr, BC: Mt/yr, OC: Mt/yr,
	# 	CF4: kt/yr, C2F6: kt/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, CFC11: kt/yr, CFC12: kt/yr, HCF22: kt/yr]
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(defaults_and_utilities.getPulseDataLength()): Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]
	return Wpt_dict

def get_previous_acceptedbidsteps_bindingrows_and_prices(scenario_id=None):
	"""
	Returns accepted bid steps for each (bidder, year), the set of binding land constraint names,
	and vpt dual prices keyed by (bidder, year).
	If scenario_id is given, restricts to that single scenario.
	"""
	defaults_and_utilities.ensure_solutions_db()
	db_path = defaults_and_utilities.getSolutionsDBPath()
	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()

	if scenario_id is None: cursor.execute("SELECT bid_step, bidder, year FROM variables")
	else: cursor.execute("SELECT bid_step, bidder, year FROM variables WHERE scenario_id=?", (scenario_id,))
	previous_acceptedbidsteps = {(int(r[0]), r[1], float(r[2])) for r in cursor.fetchall()}

	if scenario_id is None: cursor.execute("SELECT DISTINCT constraint_name FROM constraint_duals WHERE constraint_name LIKE 'Forestry_Land%'")
	else: cursor.execute("SELECT DISTINCT constraint_name FROM constraint_duals WHERE scenario_id=? AND constraint_name LIKE 'Forestry_Land%'", (scenario_id,))
	binding_constraints = set(r[0] for r in cursor.fetchall())

	if scenario_id is None: cursor.execute("SELECT constraint_name, MAX(pi) FROM constraint_duals WHERE constraint_name LIKE 'Vpt(%' GROUP BY constraint_name")
	else: cursor.execute("SELECT constraint_name, MAX(pi) FROM constraint_duals WHERE scenario_id=? AND constraint_name LIKE 'Vpt(%' GROUP BY constraint_name", (scenario_id,))
	vpt_duals = {}
	for c_name, pi in cursor.fetchall():
		inner = c_name[4:-1]  # "Vpt(Agriculture,2025.0)" -> "Agriculture,2025.0"
		last_comma = inner.rfind(',')
		vpt_duals[(inner[:last_comma], float(inner[last_comma + 1:]))] = pi

	conn.close()
	return previous_acceptedbidsteps, binding_constraints, vpt_duals

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

def Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants, tau_override=None, tau_mode="standard", restrict_columns=True):
	"""
	Solves the SMDAMAGE linear program using a restricted set of columns and rows.
	Implements a simplified column and row generation algorithm.
	tau_mode: "standard" uses BeginConstraintYear logic, "dynamic" uses tau_override as dict by period.
	restrict_columns: if False, all (a,p,t) columns are active (no warm-starting from DB).
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
	previous_acceptedbids, _, _ = get_previous_acceptedbidsteps_bindingrows_and_prices ()
	bidder_metadata = {b['bidder_name']: b for b in database_interface.get_bidders()}
	# If smdamage_solutions.db is empty, run the first model with all variables. It'll be slow, but later models will run much faster.
	if not previous_acceptedbids: print ("The solutions database smdamage_solutions.db is empty, so the first model run will be slow. Later models should solve much faster.")
	restricted_APT_set = set(APT_set) if (not restrict_columns or not previous_acceptedbids) else {(a, p, t) for (a, p, t) in APT_set if (a, p, t) in previous_acceptedbids}
	restricted_PT_set = {(p, t) for (a, p, t) in restricted_APT_set}

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
	forestry_meta = database_interface.get_forestry_metadata()
	total_area = sum(meta['available_area_mhectares'] for meta in forestry_meta.values())
	basis_file = os.path.abspath(os.path.join(defaults_and_utilities.getOutputDirectory(), "smdamage_warm.bas"))
	if os.path.exists(basis_file): os.remove(basis_file) # Don't bleed basis across scenarios.
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
		qapt = {(a, p, t): LpVariable(f"qapt({a},{p},{t})", 0.0, Uapt[a, p, t]) for (a, p, t) in APT_set if (a, p, t) in restricted_APT_set }

		# 3.1 Objective
		SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025() * lpSum(Bapt[a, p, t] * qapt[a, p, t] for (a, p, t) in qapt), "Total_value"

		# 3.2. Forestry land constraint: one per bid period, summed over all bidders (always all rows).
		for t in bid_periods:
			c_name = f"Forestry_Land_{t}"
			SMDAMAGE += lpSum(vpt[bidder_name, u] for bidder_name, meta in forestry_meta.items() for u in bid_periods if (bidder_name, u) in vpt and u <= t <= u + meta['rotation_year'] - 1) <= total_area, c_name

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
		solve_opts = ['-threads', '8', '-basisOut', basis_file]
		if iterations > 1 and os.path.exists(basis_file): solve_opts += ['-basisIn', basis_file]
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0, options=solve_opts))]
		if solve_status != "Optimal" and os.path.exists(basis_file): os.remove(basis_file)
		end_solve_time = time.time()
		dual_pi = {(p, t): (SMDAMAGE.constraints[Vname[(p, t)]].pi or 0.0) for (p, t) in Vname} # item 4.

		# 5. Decide whether the linear program needs more columns.
		expanded = False
		added_cols = 0

		# 5.1. Get the current highest accepted bid step number.
		current_front_max = {(p, t): -1 for (p, t) in PT_set}
		for (a, p, t) in restricted_APT_set:
			if a > current_front_max.get((p, t), -1): current_front_max[(p, t)] = a

		# for p in set(p for p, t in PT_set):
			# front_max_a = {t: current_front_max[(p, t)] for t in bid_periods if (p, t) in current_front_max}
			# next_bid_step(p, scenario, front_max_a, {u: (SMDAMAGE.constraints[Vname[(p, u)]].pi if (p, u) in Vname else 0.0) for u in bid_periods}, all_bids[p], bidder_metadata.get(p, {}), bid_periods, inflate2020_to_2025, StartYear)

		# 5.2. Decide whether to add the next bid steps.
		for (p, t) in PT_set:
			meta = bidder_metadata.get(p, {})
			if meta.get('class') == 'Emitter': continue
			max_a = current_front_max.get((p, t), -1)
			bids_p = all_bids[p]
			dual = dual_pi.get((p, t), 0.0)
			discount = inflate2020_to_2025 * scenario.discount_rate(t - StartYear)
			kt_divisor = 1000.0 if meta.get('units') == 'kt' else 1.0

			# For an emitter, if their (positive) objective coefficient + vpt.pi > 0.0, their bid should enter. The emitter is willing to pay more than that for the right to emit. obj_emitter + pi >= 0.
			# For a remover, if their (negative) objective coefficient + vpt.pi < 0.0, their bid should enter. The remover is willing to remove carbon for less than a stated price. pi - obj_remover >= 0.
			for a in range(max_a + 1, len(bids_p)):
				if (a, p, t) in restricted_APT_set: continue
				next_coeff, _ = bids_p[a]
				next_reduced_cost = next_coeff * discount / kt_divisor + dual
				if next_reduced_cost > 0.0:
					restricted_APT_set.add((a, p, t))
					expanded = True
					added_cols += 1
				else: # Add the next two bids. Experiments show this to work well.
					for extra_a in range(a, min(a + 2, len(bids_p))):
						restricted_APT_set.add((extra_a, p, t))
						added_cols += 1
					break

		obj_val = value(SMDAMAGE.objective) if solve_status == "Optimal" else 0.0
		print(f"  Iteration {iterations}. Solve Time: {end_solve_time - start_solve_time:.2f}s. status: {solve_status}. Obj: {obj_val:,.2f}. Added {added_cols} cols.")

		if not expanded:
			# Final solution reached, one last check on objective coefficients
			scenario.solution_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			return SMDAMAGE, qapt, vpt, temperatureChange, (taxedTemperatureChange if scenario.is_revenue_neutral else None), Vname, solve_status

def save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data=None, scenario_series_entries=None, bidder_year_rows=None, artifact_rows=None):
	db_path = defaults_and_utilities.getSolutionsDBPath()
	defaults_and_utilities.ensure_solutions_db()

	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()

	sol_datetime = getattr(scenario, 'solution_datetime', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
	net_revenue = -sum(vpt[p, t].varValue * SMDAMAGE.constraints[Vname[(p, t)]].pi for (p, t) in Vname if Vname[(p, t)] in SMDAMAGE.constraints)
	cursor.execute("INSERT INTO scenarios (name, discount_rate, initial_temp, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, solver_status, net_revenue, objective_value, solution_datetime) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
		(defaults_and_utilities.getExperimentTag(scenario), scenario.discount_rate_base, scenario.initial_temperature, scenario.tau, 1 if scenario.is_revenue_neutral else 0,
		1 if "luc_removal" in defaults_and_utilities.getExperimentTag(scenario) else 0, 1 if scenario.use_updated_Wpt else 0, LpStatus[SMDAMAGE.status], net_revenue, value(SMDAMAGE.objective), sol_datetime))
	scenario_id = cursor.lastrowid

	# Save the nonzero solution.
	variables = [(scenario_id, p, t, a, var.varValue) for (a, p, t), var in qapt.items() if var.varValue != 0.0]
	if variables:
		cursor.executemany(
			"""INSERT INTO variables (scenario_id, bidder, year, bid_step, value) VALUES (?,?,?,?,?)
			ON CONFLICT(scenario_id, bidder, year, bid_step) DO UPDATE SET value=excluded.value""", variables)
	duals = [(scenario_id, c_name, c.pi) for c_name, c in SMDAMAGE.constraints.items() if c.pi != 0.0]
	if duals:
		cursor.executemany(
			"""INSERT INTO constraint_duals (scenario_id, constraint_name, pi) VALUES (?,?,?)
			ON CONFLICT(scenario_id, constraint_name) DO UPDATE SET pi=excluded.pi""", duals)

	if temp_data:
		for source, year_to_value in temp_data.items():
			cursor.executemany(
				"""INSERT INTO temperature_series (scenario_id, source, year, value) VALUES (?,?,?,?)
				ON CONFLICT(scenario_id, source, year) DO UPDATE SET value=excluded.value""",
				[(scenario_id, source, float(year), value) for year, value in year_to_value.items()])
			cursor.executemany(
				"""INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?)
				ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source""",
				[(scenario_id, source, float(year), value, None, "temperature_output_csv") for year, value in year_to_value.items()])

	if scenario_series_entries:
		for series_name, year_to_value, units, series_source in scenario_series_entries:
			cursor.executemany(
				"""INSERT INTO scenario_series (scenario_id, series_name, year, value, units, series_source) VALUES (?,?,?,?,?,?)
				ON CONFLICT(scenario_id, series_name, year) DO UPDATE SET value=excluded.value, units=excluded.units, series_source=excluded.series_source""",
				[(scenario_id, series_name, float(year), value, units, series_source) for year, value in year_to_value.items()])

	if bidder_year_rows:
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
			[(scenario_id,) + row for row in bidder_year_rows])

	if artifact_rows:
		cursor.executemany(
			"INSERT INTO scenario_artifacts (scenario_id, artifact_type, artifact_path, header_text, created_at, content_hash) VALUES (?,?,?,?,?,?)",
			[(scenario_id,) + row for row in artifact_rows])

	conn.commit()
	conn.close()

	if defaults_and_utilities.write_legacy_files(): defaults_and_utilities.rebuild_temperature_output_csv_from_db()
	return scenario_id

def run_SMDAMAGE(scenario): # Main function. Solve the SMDAMAGE model to find the best schedule of emissions and carbon removal.
	print ("\nSMDAMAGE. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	start_time = time.time()

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

	# Emitters face tax tau. Others do not. Reminder, Carbon is 'ffi' in pulsefile.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']

	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.

	# Solve the model with a simple column and row generation algorithm.
	SMDAMAGE, qapt, vpt, temperatureChange, taxedTemperatureChange, Vname, solve_status = Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants)

	netrevenue = 0.0 # Show net revenue with marginal cost pricing.
	yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
	for (p,t) in PT_set:
		netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi

	print ("Saving solution to CSV.")
	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}
	bidder_year_rows = []
	for t in defaults_and_utilities.getBidPeriods():
		for p in Pollutants:
			qty = vpt[p,t].varValue
			pct = qty/TotalU[p,t] if TotalU[p,t] != 0.0 else None
			dual = SMDAMAGE.constraints[Vname[(p,t)]].pi if Vname[(p,t)] in SMDAMAGE.constraints else None
			bidder_year_rows.append((p, t, qty, pct, dual, Units[p], "derived"))

	if defaults_and_utilities.write_legacy_files():
		with open (defaults_and_utilities.SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
			myoutputfile.write(defaults_and_utilities.getExperimentTag(scenario) + ". Solve status " + solve_status + ". Total revenue " + str(netrevenue) + '\n')
			myoutputfile.write(','.join(['Year']
				+ [p + " " + Units[p] for p in Pollutants]
				+ [p + " % max bid" for p in Pollutants]
				+ [p + " $M/" + Units[p] for p in Pollutants])
				+ ',temp change'
				+ ',Capt pi\n')
			print("Wrote SMDAMAGE solution to " + defaults_and_utilities.SMDAMAGE_output_file_name(scenario))

			for t in defaults_and_utilities.getModelPeriods():
				line = [str(t)] # Year
				if t in defaults_and_utilities.getBidPeriods():
					for p in Pollutants: line.append(str(vpt[p,t].varValue)) # qty units
					for p in Pollutants: line.append(str(vpt[p,t].varValue/TotalU[p,t])) # Fraction of bid
					for p in Pollutants: line.append(str(SMDAMAGE.constraints[Vname[(p,t)]].pi)) # $M/unit
				else:
					for p in Pollutants: line.append(',,')

				line.append(str(scenario.initial_temperature + temperatureChange[t].varValue))

				if t in ConstraintPeriods: line.append(str(SMDAMAGE.constraints["Capt(" + str(t) + ")"].pi))
				else: line.append('.')
				myoutputfile.write (','.join(line) + '\n')

	# SMDAMAGE_fit_W uses vpt reconstructed from the solutions database.
	temp_data = {"SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated": {t: vpt['Carbon',t].varValue for t in defaults_and_utilities.getBidPeriods()},
		"SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated": yearlyrevenue,
		"SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated": {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()},}
	if scenario.is_revenue_neutral: temp_data["SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"] = {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()}

	actual_source = "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated"
	scenario_series_entries = [(actual_source, {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C", "smdamage_soln_csv")]
	if scenario.is_revenue_neutral:
		taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
		scenario_series_entries.append((taxed_source, {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C", "smdamage_soln_csv"))
	scenario_series_entries.append(("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal({k: v.varValue for k, v in vpt.items()}), "mtC", "smdamage_soln_csv"))
	artifact_rows = [("smdamage_soln_csv", defaults_and_utilities.SMDAMAGE_output_file_name(scenario), defaults_and_utilities.getExperimentTag(scenario) + ". Solve status " + solve_status + ". Total revenue " + str(netrevenue), getattr(scenario, 'solution_datetime', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), None)]
	# for t in defaults_and_utilities.getModelPeriods(): print ("mhectares(" + str(t) + ") = " + str(mhectares_land[t].varValue))
	for t in defaults_and_utilities.getModelPeriods():
		if f"Ag_Land({t})" in SMDAMAGE.constraints:
			print(f"Ag_Land({t}).pi: {SMDAMAGE.constraints[f'Ag_Land({t})'].pi}")
	print (f"Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue}. Tau {local_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + f" thousandths C. Total time {time.time() - start_time:.1f}s.")
	scenario_id = save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data, scenario_series_entries, bidder_year_rows, artifact_rows)
	# print ("Done, %s, %.1f seconds." % (time.asctime(time.localtime(time.time())), float(time.time() - startTime)))
	# print ("Reminder: convert $/ton C to $/ton CO2. Temp in 2125 is " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths of a degree C.")
	# print (getCarbonRemovedByForestry("Forestry carbon" + defaults_and_utilities.experimentTag_to_file_name(scenario)))

	return scenario_id
# END run_SMDAMAGE().

def update_tau (old_temp, current_temp, old_tau, current_tau, step_size):
	total_change = 0.0
	new_tau = {t: 1.0 for t in old_tau}
	for t in old_tau:
		if t >= defaults_and_utilities.getFirstConstrainedYear():
			# new_tau[t] = linear_interpolation(0.0, [old_temp[t], current_temp[t]], [old_tau[t], current_tau[t]])
			new_tau[t] = max(1.0, current_tau[t] + step_size*current_temp[t]/1000.0)
			total_change += abs(new_tau[t] - old_tau[t])
	return total_change, new_tau
# old_tau = {2125: 1.5, 2126: 1.4, 2127: 2.0}
# old_temp = {2125: 100.0, 2126: 120.0, 2127: -80.0}
# current_tau = {2125: 1.7, 2126: 1.5, 2127: 1.8}
# current_temp = {2125: -100.0, 2126: 12.0, 2127: 80.0}
# print("\n\n", update_tau(old_temp, current_temp, old_tau, current_tau, 1.0))

def run_SMDAMAGE_for_tau(scenario): # This version finds the optimal tau.
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
		old_tau = {t: 1.0 for t in defaults_and_utilities.getModelPeriods()} # Net zero gets you only the current temperature.
		old_temp = {t: scenario.initial_temperature for t in ConstraintPeriods}
		current_tau = {t: scenario.tau if t in ConstraintPeriods else 1.0 for t in defaults_and_utilities.getModelPeriods()} # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.
		current_temp = {t: 0.0 for t in ConstraintPeriods}

		# Loop over tau[t] =================
		step_size = 2.0 # For subgradient optimization.
		for run in range(200):
			# Use the restricted solver
			SMDAMAGE, qapt, vpt, temperatureChange, taxedTemperatureChange, Vname, solve_status = Solve_SMDAMAGE(scenario, APT_set, PT_set, Bapt, Uapt, Wpt_dict, BidStepSet, Pollutants,
					tau_override=current_tau, tau_mode="dynamic")

			# Calculate tau based on emissions and removals.
			for t in ConstraintPeriods: current_temp[t] = scenario.initial_temperature + temperatureChange[t].varValue

			# Subgradient optimization. Update temperature and tau for the next run.
			total_change, next_tau = update_tau(old_temp, current_temp, old_tau, current_tau, step_size)
			step_size = 0.9*step_size
			if total_change < 0.1: break
			sum_of_under_shoot = 0.0
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
		scenario_series_entries = [(actual_source, {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C", "smdamage_soln_csv")]
		if scenario.is_revenue_neutral and taxedTemperatureChange is not None:
			taxed_source = "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated"
			scenario_series_entries.append((taxed_source, {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getModelPeriods()}, "thousandths_C", "smdamage_soln_csv"))
		scenario_series_entries.append(("SMDAMAGE tau calibrated" if scenario.use_updated_Wpt else "SMDAMAGE tau uncalibrated", current_tau, "ratio", "temperature_output_csv"))
		scenario_series_entries.append(("Forestry carbon", defaults_and_utilities.get_tree_schedule_carbon_removal({k: v.varValue for k, v in vpt.items()}), "mtC", "smdamage_soln_csv"))

		Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}
		bidder_year_rows = []
		for t in defaults_and_utilities.getBidPeriods():
			for p in Pollutants:
				qty = vpt[p, t].varValue
				pct = qty/TotalU[p,t] if TotalU[p,t] != 0.0 else None
				dual = SMDAMAGE.constraints[Vname[(p,t)]].pi if (p,t) in Vname and Vname[(p,t)] in SMDAMAGE.constraints else None
				bidder_year_rows.append((p, t, qty, pct, dual, Units[p], "derived"))

		artifact_rows = [("smdamage_soln_csv", defaults_and_utilities.SMDAMAGE_output_file_name(scenario), defaults_and_utilities.getExperimentTag(scenario), getattr(scenario, 'solution_datetime', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), None)]

		scenario_id = save_solution_to_db(scenario, SMDAMAGE, vpt, qapt, Vname, temp_data, scenario_series_entries, bidder_year_rows, artifact_rows)
	return scenario_id

# This modified version of run_SMDAMAGE() runs 2-year auctions which must be revenue neutral. The auctions should use the calibrated Wpt values.
def run_SMDAMAGE_short_auctions(scenario):
	print ("\nSMDAMAGE short auctions. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	AllBidPeriods = defaults_and_utilities.getBidPeriods()

	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)
	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t]
		BidStepSet[p,t].append(a)

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {b['bidder_name']: b['units'] for b in database_interface.get_bidders()}

	# Create CSV file with headers.
	with open(defaults_and_utilities.SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
		myoutputfile.write(defaults_and_utilities.getExperimentTag(scenario) + "\n")
		myoutputfile.write(','.join(['Year'] + [p + " " + Units[p] for p in Pollutants] + [p + " % max bid" for p in Pollutants] + [p + " $M/" + Units[p] for p in Pollutants]) + ',temp change' + ',Capt pi\n')

	FixedPeriods = []
	Fixed_Vpt = {(p,t): 0.0 for (p,t) in PT_set}

	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Reminder, Carbon is 'ffi' in pulsefile.
	# Emitters face tax tau. Others do not.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']
	local_tau = scenario.tau
	forestry_meta = database_interface.get_forestry_metadata()
	total_area = sum(meta['available_area_mhectares'] for meta in forestry_meta.values())

	# Run 2-year auctions.
	for startyear in range(int(min(AllBidPeriods)), int(max(AllBidPeriods)) - 2, 2):
		BidPeriods = [float(startyear), float(startyear+1)] #, float(startyear+2), float(startyear+3)]

		# Decision variables
		qapt = {(a,p,t): LpVariable("qapt(" + str(a) + "," + p + "," + str(t) + ")", 0.0, Uapt[a,p,t]) for (a, p, t) in APT_set if t in BidPeriods}
		vpt = {(p,t): LpVariable("vpt(" + p + "," + str(t) + ")", None, None) for (p, t) in PT_set if t in BidPeriods} # Must be a free variable.

		BeginConstraintYear = int(defaults_and_utilities.getFirstConstrainedYear())
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= defaults_and_utilities.getStartYear() + defaults_and_utilities.getNumber_of_bid_years())

		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize) # Create model.
		SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set if t in BidPeriods), "Total value" # Objective.

		for t in AllBidPeriods:
			c_name = f"Forestry_Land_{t}"
			SMDAMAGE += lpSum(vpt[bidder_name, u] for bidder_name, meta in forestry_meta.items() for u in AllBidPeriods if (bidder_name, u) in vpt and u <= t <= u + meta['rotation_year'] - 1) <= total_area, c_name

		# Vpt rows.
		Vname = {}
		for (p, t) in PT_set:
			if t in BidPeriods:
				Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
				SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]

		# Measuring actual temperature change, not the "taxed" surrogate temperature. If REVENUE_NEUTRAL, Temp_t equations should not constrain the model.
		temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]}
		for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):] : SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t and u in BidPeriods]) - temperatureChange[t] \
			+ sum([Wpt_dict[(p, float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if u <= t and u in FixedPeriods]) == 0, "Temp_t(" + str(t) + ")"

		# Measuring taxed temperature change.
		taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]}
		for t in defaults_and_utilities.getModelPeriods()[len(FixedPeriods):]:
			SMDAMAGE += lpSum ([local_tau*Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in BidPeriods] + [Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t and u in BidPeriods])\
				- taxedTemperatureChange[t] == 0, "TaxedTemp_t(" + str(t) + ")"
		for t in ConstraintPeriods:
			if t not in FixedPeriods: SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"

		# print ("5. Solving the model...")
		# solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(threads=8, msg=0))]
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD('HiGHS', msg=0))]
		print (f"SMDAMAGE_short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear) + ", tau=" + str(local_tau) + ", " + str(round(scenario.initial_temperature + temperatureChange [float(startyear+1)].varValue,3)) + " thousandths C.")

		# Save a debug model. Easy to open with Notepad or LP_SolveIDE.
		# if startyear == 2129: SMDAMAGE.writeLP(defaults_and_utilities.getOutputDirectory() + defaults_and_utilities.getExperimentTag(scenario) + "_" + str(startyear) + ".lpt")

		FixedPeriods = FixedPeriods + BidPeriods # Were variable, now fixed for next auction.

		netrevenue = 0.0 # Show net revenue with marginal cost pricing.
		yearlyrevenue = {t: 0.0 for t in BidPeriods}
		for (p,t) in PT_set:
			if t in BidPeriods:
				Fixed_Vpt[(p,t)] = vpt[p,t].varValue # Will be fixed in the next auction.
				if t in BidPeriods:
					netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
					yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi

		# Append solution to CSV.
		with open(defaults_and_utilities.SMDAMAGE_output_file_name(scenario), 'a') as myoutputfile:
			for t in BidPeriods:
				line = [str(t)] # Year
				for p in Pollutants: line.append(str(vpt[p,t].varValue)) # qty units
				for p in Pollutants: line.append(str(vpt[p,t].varValue/TotalU[p,t])) # Fraction of bid
				for p in Pollutants: line.append(str(SMDAMAGE.constraints[Vname[(p,t)]].pi)) # $M/unit
				line.append(str(scenario.initial_temperature + temperatureChange[t].varValue))
				if t in ConstraintPeriods and t not in FixedPeriods: line.append(str(SMDAMAGE.constraints["Capt(" + str(t) + ")"].pi))
				else: line.append('.')
				myoutputfile.write(','.join(line) + '\n')

		if startyear+1 >= defaults_and_utilities.getFirstConstrainedYear(): local_tau = 1.0
	return scenario.initial_temperature + temperatureChange [float(int(max(AllBidPeriods)) - 2)].varValue
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

# ========================================================================================
# Part V. Main. Run experiments with SMDAMAGE; convert SMDAMAGE output to Hector input, run Hector, and compare temperatures.
# ========================================================================================
if __name__ == "__main__":
	# Preliminary: get pulses from Hector. Only needed if warming_factors table is empty.
	# if not database_interface.get_hector_names():
	# 	hector_interface.get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.
	# defaults_and_utilities.delete_scenario_solution([s for s in range(19,35)])

	# ----------------------------------------------------
	# # V.A. Figure 1. SMDAMAGE_ST uncalibrated. Uses the same tau for every year.
	primary_tau = 1.8
	figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
	fig1_Wpt_default_scenario_id = run_SMDAMAGE(figure1) # uncalibrated
	hector_interface.run_Hector_with_SMDAMAGE_solution(figure1) # Run Hector with uncalibrated SMDAMAGE output.
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(figure1) # Saves figure1.calibrated_initial_temperature
	figure1_uncalibrated_actual_temps = get_SMDAMAGE_temps_actual_and_taxed(figure1)[1]

	# # V.B. Figure 1. SMDAMAGE_ST calibrated. discount_rate 0.03, initial_temperature 1097.1234, tau 1.8, is_revenue_neutral True, is_removal_luc False, use_updated_Wpt False.
	figure1.initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	print("calibrated_initial_temperature = ", figure1.initial_temperature)
	figure1.use_updated_Wpt = True
	fig1_Wpt_fitted_scenario_id = run_SMDAMAGE(figure1) # calibrated
	hector_interface.run_Hector_with_SMDAMAGE_solution(figure1) # Run Hector with calibrated SMDAMAGE output.
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, figure1_uncalibrated_actual_temps, get_SMDAMAGE_temps_actual_and_taxed(figure1)[1], hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), fig1_Wpt_default_scenario_id, fig1_Wpt_fitted_scenario_id, fig1_Wpt_fitted_scenario_id)

	# ----------------------------------------------------
	# # V.C. Figure 2. SMDAMAGE_LT (tau is irrelevant). Robustness to discount rate: initial_temperature initial_temperature = 1097.1234, is_revenue_neutral False, tau is irrelevant, is_removal_luc to False, use_updated_Wpt = True.
	# Using the original long-term SMDAMAGE formulation, not revenue neutral.
	calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.0, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True))
	s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.015, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True))
	Estimate 1 "Full commitment".
	estimate1_LT_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True))
	s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.06, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True))
	plotting_utils.Temperature_trajectories_with_4_discount_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, estimate1_LT_scenario_id, s_id4)
	plotting_utils.Price_trajectory_with_full_commitment(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate1_LT_scenario_id)

	# ----------------------------------------------------
	# # V.D. Figures 3-5. SMDAMAGE_ST, multiple tau: discount_rate to 0.03, initial_temperature 1097.1234, is_revenue_neutral True, tau in a range, is_removal_luc False, use_updated_Wpt True.
	calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.6, is_removal_luc = False, use_updated_Wpt = True))
	s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.8, is_removal_luc = False, use_updated_Wpt = True))
	s_id3 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.0, is_removal_luc = False, use_updated_Wpt = True))
	s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.2, is_removal_luc = False, use_updated_Wpt = True))
	plotting_utils.Carbon_emissions_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Discounted_net_revenue_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Temperature_trajectories_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)

	# ----------------------------------------------------
	# # V.E. Estimate 2. Concluding paragraph after Figures 3-5. SMDAMAGE_ST with preferred tau.
	preferred_tau = 1.7 # Chosen based on the experiment of Figures 3-5, the tau that would result in base zero.
	# calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	# estimate2_ST_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = preferred_tau, is_removal_luc = False, use_updated_Wpt = True))

	# ----------------------------------------------------
	# # VI. Strength of contracts. (Figure 6 comes from the Pulse input data.)
	# # The base scenario is discount_rate to 0.03, initial_temperature from the first calibration, is_revenue_neutral True, tau is primary_tau, is_removal_luc to False, use_updated_Wpt = True, but with an earlier Wpt, so use False here.
	# VI.A. Weak contracts: first run with uncalibrated SMDAMAGE. TODO: Confirm best tau for weak contracts; guessing at tau=2.4.
	# For the case of weak contracts, use discount_rate to 0.03, initial_temperature from the first calibration, is_revenue_neutral True, tau is 2.4, is_removal_luc to True, use_updated_Wpt = False.
	# calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	# contracts_scenario = defaults_and_utilities.Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.4, is_removal_luc = True, use_updated_Wpt = False)
	# run_SMDAMAGE(contracts_scenario) # uncalibrated. Can't use the Fig 1 calibration because we changed from ffi warming coefficients to luc warming coefficients.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# # VI.B & C. Weak contracts: Calibrate W for the contracts scenario, then run the calibrated SMDAMAGE.
	# contracts_scenario.initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(contracts_scenario)
	# contracts_scenario.use_updated_Wpt = True
	# estimate3_weak_contracts_scenario_id = run_SMDAMAGE(contracts_scenario) # calibrated to luc warming coefficients.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# ----------------------------------------------------
	# # VII. Short auctions, 2 years at a time.
	# # VII.A. Calibrate with a long-term model.
	# calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	# Short_auctions_scenario = defaults_and_utilities.Scenario(comment = "Short auctions", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
	# run_SMDAMAGE(Short_auctions_scenario) # A long auction for calibrating the short auctions.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(Short_auctions_scenario) # 3. Run Hector on SMDAMAGE output.

	# # VII.B. Run the short auctions.
	# calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(Short_auctions_scenario)
	# Short_auctions_scenario.initial_temperature = calibrated_initial_temperature
	# Short_auctions_scenario.use_updated_Wpt = True # Use this updated_Wpt for the short auctions.
	# estimate4_short_auctions_scenario_id = run_SMDAMAGE_short_auctions(Short_auctions_scenario) # Results in excess cooling. Hence the search for tau by year.

	# ----------------------------------------------------
	# Search for tau. Start with tau = primary_tau for each constrained year, then subgradient optimization to choose tau for each year. Use calibrated_initial_temperature from VII.B.
	# tau_search = defaults_and_utilities.Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True)
	# estimate5_tau_search_scenario_id = run_SMDAMAGE_for_tau (tau_search) # Repeated solution of SMDAMAGE with subgradient optimization on tau.
	# print ("\nSMDAMAGE code complete. " + defaults_and_utilities.getExperimentTag(tau_search) + ". " + time.asctime(time.localtime(time.time())) + ".")
	# ----------------------------------------------------

	# Table at end
	# estimate1_LT_scenario_id = 5; estimate2_ST_scenario_id = 16; estimate3_weak_contracts_scenario_id = 13; estimate4_short_auctions_scenario_id = 14; estimate5_tau_search_scenario_id = 15
	# plotting_utils.Summary_of_estimates_to_end_global_warming(defaults_and_utilities.getSolutionsDBPath(), estimate3_weak_contracts_scenario_id, estimate1_LT_scenario_id, estimate4_short_auctions_scenario_id, estimate2_ST_scenario_id, estimate5_tau_search_scenario_id, defaults_and_utilities.getOutputDirectory())
	import winsound
	winsound.Beep(700, 500)  # Frequency: 1000 Hz, Duration: 500 ms
