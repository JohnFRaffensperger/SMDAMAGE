# Part V. Wpt calibration functions for SMDAMAGE
# If the SMDAMAGE activity schedule did not match the temperature trajectory in Hector,
# we can calibrate the Wpt values in SMDAMAGE.
# John F Raffensperger. 2022-07-27, 2022-09-10, 2025-01-05.

import csv
import importlib.util
import matplotlib.pyplot as mplot
import os
import pickle
from pulp import *
import sys

import hector_interface
import plotting_utils
import defaults_and_utilities
import database_interface

# Import the main module with spaces in filename
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
main_file_path = os.path.join(current_dir, "SMDAMAGE revenue neutral.py")
spec = importlib.util.spec_from_file_location("smdamage_main", main_file_path)
smdamage_main = importlib.util.module_from_spec(spec)
sys.modules["smdamage_main"] = smdamage_main
spec.loader.exec_module(smdamage_main)

# Plotting functions moved to plotting_utils.py

def write_fitted_Wpt_to_csv(): # Write the fitted Wpt values to a CSV file in rows of pollutant and columns of years. Useful for analysis in Excel.
	with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE_fitted_Wpt.pkl", "rb") as mypickle: Wpt_dict = pickle.load(mypickle)
	pollutants = sorted(set(pollutant for pollutant, year in Wpt_dict.keys()))
	years = sorted(set(year for pollutant, year in Wpt_dict.keys()))
	with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE_fitted_Wpt.csv", 'w', newline='', encoding='utf-8') as csv_file:
		writer = csv.writer(csv_file)
		writer.writerow(['Pollutant'] + years)
		for pollutant in pollutants: writer.writerow([pollutant] + [Wpt_dict.get((pollutant, year), '') for year in years])

def run_SMDAMAGE_fit_W(scenario):
	# 	If scenario.is_removal_luc,
	# 		apply Wpt_dict[('luc',t)] for ['Agriculture', 'Seaweed'] + getTreetypes().
	# 		fit both 'Carbon' and 'luc'.
	#	else
	# 		fit only Carbon, and
	# 		apply Wpt_dict[('Carbon',t)] for ['Agriculture', 'Seaweed'] + getTreetypes().

	Emitters = defaults_and_utilities.getEmitters() # ['Carbon', 'C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = defaults_and_utilities.getRemovers() # ['Agriculture', 'Seaweed', 'Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	Pulse = database_interface.getPulse() # Reads the Pulse input file from database. Includes 'luc'.

	# Load default Wpt_dict. ------------------------------------------------------------------------------------------
	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(defaults_and_utilities.getPulseDataLength())} # Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	scaleCelsius = 1000.0 # Thousandths of a degree.

	for p in defaults_and_utilities.getChemicals(): #['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(defaults_and_utilities.getPulseDataLength()): Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]

	for t0 in range(defaults_and_utilities.getPulseDataLength()):  # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Always calculate error from the original Wpt, not to previously fitted Wpt.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['luc'][0]/1000.0

		# Agriculture. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because carbon pulse units are degrees C/gigaton.
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Pulse['luc'][1 + t0]*scaleCelsius/Pulse['luc'][0]/1000.0
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]

		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]

	Treetypes = defaults_and_utilities.getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	# A hectare of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes:
		removal_data = database_interface.get_forestry_carbon_removal(tree)
		for year, tc in removal_data:
			for coolingyear in range(year, defaults_and_utilities.getPulseDataLength()):
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth.
				Wpt_dict[(tree, float(coolingyear))] += tc * Wpt_dict[('Agriculture', float(coolingyear - year))] * scaleCelsius / 1000.0

	# Load Vpt_dict. ------------------------------------------------------------------------------------------
	# Data is the previous vpt solution from SMDAMAGE and the Hector temperature.
	my_old_vpt = defaults_and_utilities.open_pkl("SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario)) # amount of activity p in year t from solution of model P1 or P2.
	Vpt = {(p,t): my_old_vpt[p,t].varValue for (p,t) in my_old_vpt}

	# Construct PT_set. ------------------------------------------------------------------------------------------
	Constant_PT_set = set() # Use constant W for activities you're not trying to fit.
	for p in defaults_and_utilities.getChemicals():
		for t in defaults_and_utilities.getBidPeriods(): Constant_PT_set.add((p,t))
	# if scenario.is_removal_luc:
	# 	for t in defaults_and_utilities.getBidPeriods(): Constant_PT_set.add(('Carbon',t))
	# else: luc is not part of the model.

	Variable_PT_set = set() # But note that "luc" is not an activity in SMDAMAGE.
	# if scenario.is_removal_luc: Variable_w_activities = ['luc'] + ['Agriculture', 'Seaweed'] + defaults_and_utilities.getTreeTypes()
	if scenario.is_removal_luc: Variable_w_activities = ['Carbon'] + ['luc'] + ['Agriculture', 'Seaweed'] + defaults_and_utilities.getTreeTypes()
	else: Variable_w_activities = ['Carbon'] + ['Agriculture', 'Seaweed'] + defaults_and_utilities.getTreeTypes()

	for p in Variable_w_activities:
		for t in defaults_and_utilities.getBidPeriods(): Variable_PT_set.add((p,t))

	# Decision variables ------------------------------------------------------------------------------------------
	wpt = {}

	for t in range(defaults_and_utilities.getPulseDataLength()):
		wpt[('Carbon',float(t))] = LpVariable("wpt(Carbon," + str(t) + ")", 0.0, None) # >= 0
		if scenario.is_removal_luc: wpt[('luc',float(t))] = LpVariable("wpt(luc," + str(t) + ")", 0.0, None) # >= 0 # Watch the bounds! Emitter w >= 0, remover w <= 0.
		# else: wpt[('Carbon',float(t))] = LpVariable("wpt(Carbon," + str(t) + ")", 0.0, None) # >= 0

		wpt[('Seaweed',float(t))] = LpVariable("wpt(Seaweed," + str(t) + ")", None, 0.0) # <= 0
		wpt[('Agriculture',float(t))] = LpVariable("wpt(Agriculture," + str(t) + ")", None, 0.0) # <= 0
		for tree in Treetypes: wpt[(tree,float(t))] = LpVariable("wpt(" + tree + "," + str(t) + ")", None, 0.0) # <= 0

	over_error_t = {t: LpVariable("over_error_t(" + str(t) + ")", 0.0, None) for t in defaults_and_utilities.getModelPeriods()} # error below HectorTempt in year t.
	under_error_t = {t: LpVariable("under_error_t(" + str(t) + ")", 0.0, None) for t in defaults_and_utilities.getModelPeriods()} # error above HectorTempt in year t.
	SMDAMAGE_temp_t = {t: LpVariable("SMDAMAGE_temp_t(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()} # Implied SMDAMAGE temperature.

	W_over_error_t = {t: LpVariable("over_error_t(" + str(t) + ")", 0.0, None) for t in range(defaults_and_utilities.getPulseDataLength())} # error below HectorTempt in year t.
	W_under_error_t = {t: LpVariable("under_error_t(" + str(t) + ")", 0.0, None) for t in range(defaults_and_utilities.getPulseDataLength())} # error above HectorTempt in year t.
	initial_Temp = LpVariable("initial_Temp", None, None)
	# initial_ghg_p = {p: LpVariable("initial_ghg_p(" + str(p) + ")", 0.0, None) for p in Emitters}

	# Objective: minimize total error --------------------
	SMDAMAGE_fit_W = LpProblem("SMDAMAGE_fit_W", LpMinimize) # Temperature error is in 1000s, W error is in 0.001s, so we need to scale W error.
	SMDAMAGE_fit_W += lpSum(over_error_t[t] + under_error_t[t] for t in defaults_and_utilities.getModelPeriods()), "Total error"
	# SMDAMAGE_fit_W += lpSum(over_error_t[t] + under_error_t[t] for t in defaults_and_utilities.getModelPeriods()) + 100000.0*lpSum(W_over_error_t[t] + W_under_error_t[t] for t in range(defaults_and_utilities.getPulseDataLength())), "Total error"

	# Constraints: temperature error. --------------------
	HectorTemp = hector_interface.get_Hector_temperature(scenario) # the temperature in year t from Hector simulating solution Vp,t.

	# Constraints: warming  --------------------
	for t in defaults_and_utilities.getModelPeriods():
		if t <= 2300.0: # HectorTemp goes only to 2300.
			# Different experiments.

			# Warming constraints. Ag, seaweed, and trees use the "luc" warming factors, but "luc" itself is not activity. No Vpt['luc',u] exists.
			SMDAMAGE_fit_W +=  initial_Temp \
				+ lpSum ([wpt[(p, float(t - u))]*Vpt[p,u] for (p,u) in Variable_PT_set if u <= t and p != "luc"])\
				+ sum([Wpt_dict[(p, float(t - u))]*Vpt[p,u] for (p,u) in Constant_PT_set if u <= t])\
				== SMDAMAGE_temp_t[t], "SMDAMAGE_Temp(" + str(t) + ")"

			SMDAMAGE_fit_W += SMDAMAGE_temp_t[t] - over_error_t[t] + under_error_t[t] == HectorTemp[t], "Temp_t(" + str(t) + ")"

	# Constraints: calculate W error.  --------------------
	# for u in range(defaults_and_utilities.getPulseDataLength()): # Both ffi and luc pulses peak before 20 years after emission.
	# 	if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('luc', float(u))] - W_over_error_t[u] + W_under_error_t[u] == Wpt_dict[('luc', float(u))], "W_fit(" + str(u) + ")"
	# 	else: SMDAMAGE_fit_W += wpt[('Carbon', float(u))] - W_over_error_t[u] + W_under_error_t[u] == Wpt_dict[('Carbon', float(u))], "W_fit(" + str(u) + ")"

	# Constraints: consistency between activity types.  --------------------
	for u in range(defaults_and_utilities.getPulseDataLength()):
		if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('Agriculture', float(u))] == - wpt[('luc', float(u))], "W_agriculture(" + str(u) + ")"
		else:               SMDAMAGE_fit_W += wpt[('Agriculture', float(u))] == - wpt[('Carbon', float(u))], "W_agriculture(" + str(u) + ")"
		SMDAMAGE_fit_W += wpt[('Seaweed', float(u))] == wpt[('Agriculture', float(u))], "W_seaweed(" + str(u) + ")"

	# Memoize removal schedules for all relevant trees
	RemovalSchedules = {}
	for tree in Treetypes:
		removal_data = database_interface.get_forestry_carbon_removal(tree)
		# Convert [(year, value), ...] to {year: value, ...}
		# Ensure growth years cover at least the rotation length found in metadata
		RemovalSchedules[tree] = {int(year): val for year, val in removal_data}

	# Constraints: convolution for trees.  --------------------
	for tree in Treetypes: # If tree is planted in year 0, it sequesters from database in each sequesterperiod.
		# Example: wpt[5] = growth[0]*wpt[5] + growth[1]*wpt[4] + growth[2]*wpt[3] + growth[3]*wpt[2] + growth[4]*wpt[1] + growth[5]*wpt[0]
		schedule = RemovalSchedules[tree]
		max_growth_year = max(schedule.keys()) if schedule else 0

		for coolingyear in range(0, defaults_and_utilities.getPulseDataLength()):
			SMDAMAGE_fit_W += wpt[(tree, float(coolingyear))] \
				== lpSum(schedule.get(treegrowthyear, 0.0) * wpt[('Agriculture', float(coolingyear - treegrowthyear))] * scaleCelsius / 1000.0 \
					for treegrowthyear in range(0, min(max_growth_year + 1, coolingyear + 1))), "W_tree(" + tree + "," + str(coolingyear) + ")"

	# Constraints: physics pulse consistency.  --------------------
	# SMDAMAGE_fit_W += wpt[('Carbon', 0.0)] == 0.0, "W_consistency(0.0)"
	# for u in range(1, 15): # Both ffi and luc pulses peak before 20 years after emission.
	# 	SMDAMAGE_fit_W += wpt[('Carbon', float(u))] <= wpt[('Carbon', float(u + 1))], "W_consistency(" + str(u) + ")"
	for u in range(20, defaults_and_utilities.getPulseDataLength() - 1): # Both ffi and luc pulses peak before 20 years after emission.
		if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('luc', float(u))] >= wpt[('luc', float(u + 1))], "W_luc_consistency(" + str(u) + ")"
		# else: SMDAMAGE_fit_W += wpt[('Carbon', float(u))] >= wpt[('Carbon', float(u + 1))], "W_consistency(" + str(u) + ")"
		SMDAMAGE_fit_W += wpt[('Carbon', float(u))] >= wpt[('Carbon', float(u + 1))], "W_carbon_consistency(" + str(u) + ")"

	# Write a debug model. Easy to open with Notepad or LP_SolveIDE.
	# SMDAMAGE_fit_W.writeLP(defaults_and_utilities.getOutputDirectory() + "Calibrate W " + defaults_and_utilities.getExperimentTag() + ".lpt")

	solve_status = LpStatus[SMDAMAGE_fit_W.solve(PULP_CBC_CMD(msg=0))]
	print (f"SMDAMAGE_Fit_W done. Solve status: {solve_status}, total error = {value(SMDAMAGE_fit_W.objective)}. Initial temperature = {value(initial_Temp.varValue)}")

	plotting_utils.plot_W_Hector_and_fitted(scenario, "Carbon", [Wpt_dict[('Carbon', float(t))] for t in range(defaults_and_utilities.getPulseDataLength())], [wpt[('Carbon', float(t))].varValue for t in range(defaults_and_utilities.getPulseDataLength())], defaults_and_utilities.getPulseDataLength, defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	if scenario.is_removal_luc: plotting_utils.plot_W_Hector_and_fitted(scenario, "luc", [Wpt_dict[('luc', float(t))] for t in range(defaults_and_utilities.getPulseDataLength())], [wpt[('luc', float(t))].varValue for t in range(defaults_and_utilities.getPulseDataLength())], defaults_and_utilities.getPulseDataLength, defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	# else: plotting_utils.plot_W_Hector_and_fitted(scenario, "Carbon", [Wpt_dict[('Carbon', float(t))] for t in range(defaults_and_utilities.getPulseDataLength())], [wpt[('Carbon', float(t))].varValue for t in range(defaults_and_utilities.getPulseDataLength())], defaults_and_utilities.getPulseDataLength, defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	plotting_utils.plot_temps_Hector_and_fitted(scenario, [HectorTemp[t] for t in defaults_and_utilities.getModelPeriods() if t <= 2300], [SMDAMAGE_temp_t[t].varValue for t in defaults_and_utilities.getModelPeriods() if t <= 2300], [t for t in defaults_and_utilities.getModelPeriods() if t <= 2300], defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	for p in Variable_w_activities:
		for t in range(defaults_and_utilities.getPulseDataLength()): Wpt_dict[(p,float(t))] = wpt[(p, float(t))].varValue
	# defaults_and_utilities.yourdictionary_to_CSV(Wpt_dict, "Wpt_dict " + defaults_and_utilities.experimentTag_to_file_name(scenario))
	with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE_fitted_Wpt.pkl", "wb") as mypickle: pickle.dump(Wpt_dict, mypickle)
	return initial_Temp.varValue



