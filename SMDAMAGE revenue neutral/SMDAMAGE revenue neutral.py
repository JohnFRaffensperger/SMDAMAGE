# Simulation of SMDAMAGE, by John F Raffensperger. 10 Aug 2019, 10 Sep 2022, 17 May 2023, 6 Jan 2025, 3 Feb 2025.
# Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
# Critical values: discount rate in discount_rate(), StartYear (e.g., 2025), BeginConstraintYear (warming deadline, e.g., 2125), revenue neutrality as REVENUE_NEUTRAL, and InitialTemperature.
# Longer term: switch to auction software.

# =============================================================================================
# Part I. Preliminaries, inputs, key parameters.
# =============================================================================================
# Input files
# ../data/Calibrated_pulses_by_chemical_2025.txt
# Following are all from "Sources of data, corrected forestry.xlsm":
# ../data/Forestry_Sequestration.csv, Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
# ../data/Forestry_bid_steps.csv, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
# ../data/MtC_bid_steps.csv, 
# ../data/C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv,
# ../data/CH4_bid_steps.csv,
# ../data/N2O_bid_steps.csv,
# ../data/Agriculture_bids.csv,
# ../data/Seaweed_bids.csv.

# import csv # input and output.
import matplotlib.pyplot as mplot # graphing.
import os # file management.
import pickle # saving and retrieving solutions, especially the calibrated Wpt.
from pulp import * #pulp.pulpTestAll() # to solve the linear programs.
import time # for timing the run.
# import subprocess # for calling external processes
import hector_interface # Hector pulse generation functions.
import wpt_calibration # Wpt calibration functions
import plotting_utils # Consolidated plotting functions
import defaults_and_utilities # Default parameters and utility functions

# hector_interface.get_Pulses_from_Hector(). Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.
# ============================================================================================
# Part III. SMDAMAGE.
# ============================================================================================

def old_taxed_temps(scenario, your_taxed_temps_filename): # retrieves previously saved solution vpt.
	if not scenario.is_revenue_neutral: return {}
	print(os.getcwd())
	with open(defaults_and_utilities.getOutputDirectory() + your_taxed_temps_filename + "_taxed_temps.pkl", "rb") as mypickle: 
		taxed_temps = pickle.load(mypickle)
	return {t: scenario.initial_temperature + taxed_temps[t].varValue for t in taxed_temps}
# print(defaults_and_utilities.get_tree_schedule_carbon_removal(old_vpt(defaults_and_utilities.getExperimentTag(scenario) + ".pkl")))
# exit()
	
# def linear_interpolation(x_new, x, y): # And extrapolation.
# 	assert len(x) == len(y), "x and y must have the same length for linear_interpolation."
# 	assert(abs(x[1] - x[0]) > 0.0), "x[0] and x[1] values must differ for linear_interpolation."
# 	assert(abs(x[-1] - x[-2]) > 0.0), "x[-1] and x[-2] values must differ for linear_interpolation."

# 	if x_new < x[0]: return y[0] + (x_new - x[0])*(y[1] - y[0])/(x[1] - x[0])
# 	if x_new > x[-1]: return y[-1] + (x_new - x[-1])*(y[-1] - y[-2])/(x[-1] - x[-2])
# 	for i in range(len(x) - 1):
# 		if x_new >= x[i] and x_new <= x[i + 1]: return y[i] + (x_new - x[i])*(y[i + 1] - y[i])/(x[i + 1] - x[i])
# Example: tau_i = 1.5, tau_i+1 = 1.6, temp_i = 100, temp_i = -100, desired temp = 0.
# print("\n\n", linear_interpolation(0.0, [-100.0, -80.0], [1.5, 1.55]))
# print("\n\n", linear_interpolation(0.0, [100.0, 80.0], [1.5, 1.55]))
# print("\n\n", linear_interpolation(0.0, [100.0, -80.0], [1.5, 1.55]))
# print("\n\n", linear_interpolation(0.0, [-100.0, 80.0], [1.5, 1.55]))
# print("\n\n", linear_interpolation(0.0, [-100.0, -80.0], [1.5, 1.55]))
# print("\n\n", linear_interpolation(0.0, [-80.0, -100.0], [1.5, 1.55]))

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
def get_warming_effects(scenario): # Get warming effects in degrees Celsius in each period, based on the solution vpt.
	Pulse = hector_interface.getPulse() # Reads the Pulse input file.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = defaults_and_utilities.getRemovers() # ['luc', 'Agriculture', 'Seaweed']

	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	# Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(defaults_and_utilities.getPulseDataLength())} # >= 0.
	scaleCelsius = 1000.0 # Thousandths of a degree.

	if scenario.use_updated_Wpt: Wpt_pkl = defaults_and_utilities.open_pkl("SMDAMAGE_fitted_Wpt") # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
	for t0 in range(defaults_and_utilities.getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		if scenario.use_updated_Wpt: # If not variable in SMDAMAGE_Fit_W, then it will be the same as in the original pulse file.
			Wpt_dict [('luc', float(t0))] = Wpt_pkl[('luc', float(t0))] 
			Wpt_dict [('Carbon', float(t0))] = Wpt_pkl[('Carbon', float(t0))]
		else:
			# Looks dumb to have 1000 in the numerator and denominator. Denominator 1000 converts degrees C/gigaton to degrees C/megaton. Numerator 1000 converts degrees to thousandths of a degree.
			Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
			Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('luc', float(t0))]
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]
		
		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]
		
	# A hector of tree planting convolves into future carbon removal.
	Treetypes = defaults_and_utilities.getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	Treetype_carbon_removal = defaults_and_utilities.get_Treetype_carbon_removal(Treetypes)
	# A hector of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes: # Tree is planted in year 0. Tree sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		for treegrowthyear in range(0, 156): # Length of tree contract.
			for coolingyear in range(treegrowthyear, defaults_and_utilities.getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth. 
				Wpt_dict[(tree, float(coolingyear))] += Treetype_carbon_removal[tree][treegrowthyear]*Wpt_dict[('Agriculture', float(coolingyear - treegrowthyear))]*scaleCelsius/1000.0

	# 	CH4: MtCH4/yr, N2O: MtN2O-N/yr, C: MtC/yr, NMVOC: Mt/yr, BC: Mt/yr, OC: Mt/yr,
	# 	CF4: kt/yr, C2F6: kt/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, CFC11: kt/yr, CFC12: kt/yr, HCF22: kt/yr]
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(defaults_and_utilities.getPulseDataLength()):
			Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]
	return Wpt_dict

def read_bids(scenario):
	# Parameters
	AllBidPeriods = defaults_and_utilities.getBidPeriods()
	StartYear = defaults_and_utilities.getStartYear()
	
	Bapt = {} # Bid price for agent a, pollutant p, time period t.
	Uapt = {} # Upper bid quantity, kg, for agent a, pollutant p, time period t.
	APT_set = set() # [(a, p, t),...]
	PT_set = set()

	# All bids in millions of dollars per million tons.
	# 2.1 Agriculture. $US2022, Mtons C2. Based on Smith P., et ak, 2014: Agriculture, Forestry and Other Land Use (AFOLU). In: Climate Change 2014: Mitigation of Climate Change, Figure 11.17.
	with open ('./data/Agriculture_bids.csv') as agfile: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in agfile]
	Bid_Q_Agriculture = [(float (line[0]), float (line[1])) for line in lines[1:]]
	for t in AllBidPeriods:
		PT_set.add(('Agriculture',t))
		for bidstep, bid in enumerate(Bid_Q_Agriculture):
			APT_set.add((bidstep,'Agriculture',t))
			Bapt[bidstep,'Agriculture',t] = - bid[0]*scenario.discount_rate(t - StartYear) # M dollars/M tons
			Uapt[bidstep,'Agriculture',t] = bid[1]/float(hector_interface.getPeriodsPerYear()) # M tons per period.

	# 2.2 Carbon. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Carbon bids", columns F,G.
	# Consider increasing initial quantity of 20 to 1000 or greater.
	with open('./data/MtC_bid_steps.csv', 'r') as Carbonfile:
		lines = [line for line in Carbonfile]
	for t in AllBidPeriods:
		PT_set.add(('Carbon',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Carbon',t))
			Bapt[bidstep,'Carbon',t] = float(bid[0])*scenario.discount_rate(t - StartYear) # m dollars/m tons
			Uapt[bidstep,'Carbon',t] = float(bid[1])/float(hector_interface.getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# 2.3 Seaweed. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Seaweed".
	with open('./data/Seaweed_bids.csv', 'r') as Seaweedfile:
		lines = [line for line in Seaweedfile]
	for t in AllBidPeriods:
		PT_set.add(('Seaweed',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Seaweed',t))
			Bapt[bidstep,'Seaweed',t] = float(bid[0])*scenario.discount_rate(t - StartYear) # m dollars/m tons
			Uapt[bidstep,'Seaweed',t] = float(bid[1])/float(hector_interface.getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# Unused bid data: C6F14, HFC-152a, HFC-227ea, HFC-23, HFC245ca, HFC-32, HFC-43_10.
	# 2.3. Bid data retrieved here: C2F6, CF4, HFC-125, HFC-134a, HFC-143a, SF6.
	# File is sorted by chemical, year, price increasing.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	with open('./data/C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv', 'r') as chemicalsfile:
		lines = [line for line in chemicalsfile]
		thislist = lines[0].split(',') # header: C2F6 $/kt,C2F6 kt/year,CF4 $/kt,CF4 kt/year,HFC125 $/kt,HFC125 kt/year,HFC134a $/kt,HFC134a kt/year,HFC143a $/kt,HFC143a kt/year,SF6 $/kt,SF6 kt/year
		# Remember, Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
		chemicals = defaults_and_utilities.getChemicals() # trust, but verify  = ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6'] # trust, but verify 
		for chemical in chemicals: assert (chemical in Emitters)

		for bidstep, line in enumerate(lines[1:]): # Skip header.
			thislist = line.split(',')
			thislist = [float(item) for item in thislist]
			for c, chemical in enumerate(chemicals):
				price, ktons = thislist[2*c:2*c+2]
				for t in AllBidPeriods:
					PT_set.add((chemicals[c],t))
					APT_set.add((bidstep,chemicals[c],t))
					# Data is given in $/tonne C. Quantities are kilotons, so decision variables should be $million/kiloton.
					# Thus, $500/ton --> $0.5 million per kiloton.
					Bapt[bidstep,chemicals[c],t] = price*scenario.discount_rate(t - StartYear)/1000.0 # m dollars/k tons
					Uapt[bidstep,chemicals[c],t] = ktons/float(hector_interface.getPeriodsPerYear()) # Ktons per period.

	# 2.4. CH4_bid_steps.csv.
	with open('./data/CH4_bid_steps.csv', 'r') as chemicalsfile:
		chemical = 'CH4'
		lines = [line for line in chemicalsfile]
		for bidstep, line in enumerate(lines[1:]):
			price, mtons = line.split(',')
			price = float(price)
			mtons = float(mtons)
			for t in AllBidPeriods:
				PT_set.add((chemical,t))
				APT_set.add((bidstep,chemical,t))
				Bapt[bidstep,chemical,t] = price*scenario.discount_rate(t  - StartYear) # Mega dollars/megatons
				# As described in "1-s2.0-S2352340919306882-mmc1, CH4 and NO2, jfr 1.xlsm", sheet "SSP2 CH4 N2O baseline emissions".
				Uapt[bidstep,chemical,t] = mtons/float(hector_interface.getPeriodsPerYear())

	# 2.5. N2O_bid_steps.csv.
	with open('./data/N2O_bid_steps.csv', 'r') as chemicalsfile:
		chemical = 'N2O'
		lines = [line for line in chemicalsfile]
		for bidstep, line in enumerate(lines[1:]):
			price, mtons = line.split(',')
			price = float(price)
			mtons = float(mtons)
			for t in AllBidPeriods:
				PT_set.add((chemical,t))
				APT_set.add((bidstep,chemical,t))
				Bapt[bidstep,chemical,t] = price*scenario.discount_rate(t - StartYear) # Mega dollars/megatons
				# As described in "1-s2.0-S2352340919306882-mmc1, CH4 and NO2, jfr 1.xlsm", sheet "SSP2 CH4 N2O baseline emissions".
				Uapt[bidstep,chemical,t] = mtons/float(hector_interface.getPeriodsPerYear()) # Megatons

	# 2.6. Forestry_bid_steps.csv,
	Treetypes = defaults_and_utilities.getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	with open ('./data/Forestry_bid_steps.csv', 'r') as forestryfile: # Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in forestryfile]
		# units = lines[0] # header: 'Plantable k hectares/year bid qty per crop', '2019 $/hectare Loblolly Pine', '2019 $/hectare ponderosa pine,2019 $/hectare black walnut'.
		bidstep = 0
		for line in lines[1:]: # Plantable k hectares/year bid qty per crop, 2019 $/hectare Loblolly Pine, 2019 $/hectare ponderosa pine, 2019 $/hectare black walnut
			for t in AllBidPeriods:
				for r, tree in enumerate(Treetypes):
					PT_set.add((tree, t))
					APT_set.add((bidstep, tree, t))
					Bapt[bidstep, tree, t] = - float(line[1 + r])*scenario.discount_rate(t - StartYear) # (M dollars)/(M hectares)
					Uapt[bidstep, tree, t] = float(line[0])/float(hector_interface.getPeriodsPerYear()) # M hectares plantable in each period.
			bidstep += 1
	return Bapt, Uapt, APT_set, PT_set

def run_SMDAMAGE(scenario): # Main function. Solve the SMDAMAGE model to find the best schedule of emissions and carbon removal.
	print ("\nSMDAMAGE. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")

	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.

	# Bids. ------------------------------------------------------------------------------------------
	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	print ("2. Reading bids...")
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

	# Reminder, Carbon is 'ffi' in pulsefile.
	# Emitters face tax tau. Others do not.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']
	
	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.

	# You might want to solve the model for multiple BeginConstraintYears.
	for BeginConstraintYear in range(int(defaults_and_utilities.getFirstConstrainedYear()), int(defaults_and_utilities.getFirstConstrainedYear()) + 1, 1):
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*(defaults_and_utilities.getPulseDataLength() + int(defaults_and_utilities.getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= defaults_and_utilities.getStartYear() + defaults_and_utilities.getNumber_of_bid_years())
		
		# print ("3. Creating model for first constraint year of " + str(BeginConstraintYear))
		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
		
		# print("Objective...", sep=None)
		SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set), "Total value"
		
		# print("Vpt rows...", sep=None)
		Vname = {}
		for (p, t) in PT_set:
			Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
			SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]

		# print("Capt rows...")
		temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()}
		
		# Measuring actual temperature change, not the "taxed" surrogate temperature. If REVENUE_NEUTRAL, Temp_t equations should not constrain the model.
		for t in defaults_and_utilities.getModelPeriods(): SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t]) - temperatureChange[t] == 0, "Temp_t(" + str(t) + ")"

		if scenario.is_revenue_neutral: # Taxed net zero model. 
			taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()}
			
			for t in defaults_and_utilities.getModelPeriods(): 
				SMDAMAGE += lpSum ([local_tau*Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u <= BeginConstraintYear - 1.0]) \
						+ lpSum ([Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u >= BeginConstraintYear]) \
					      + lpSum ([Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t]) \
						- taxedTemperatureChange[t] == 0, "TaxedTemp_t(" + str(t) + ")"
			
			for t in ConstraintPeriods: SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"
		else: 
			Capt = {t: -scenario.initial_temperature for t in ConstraintPeriods} # Allowed increase in global temp, thousandths of degrees Celsius in period t.
			for t in ConstraintPeriods: SMDAMAGE += temperatureChange [t] <= Capt[t], "Capt(" + str(t) + ")"

		# print ("4. Writing a debug model...") # SLOW! -------------------------------------------------------------
		# SMDAMAGE.writeLP(defaults_and_utilities.getOutputDirectory() + defaults_and_utilities.getExperimentTag(scenario) + ".lpt") # Easy to open with Notepad or LP_SolveIDE
		
		# print ("5. Solving the model...")
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0))]

		netrevenue = 0.0 # Show net revenue with marginal cost pricing.
		yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
		for (p,t) in PT_set:
			netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
			yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		
		# Save solution to CSV.
		# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
		Units = defaults_and_utilities.getUnits()
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

		# SMDAMAGE_fit_W uses the vpt pickle file.
		with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
			with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated", {t: vpt['Carbon',t].varValue for t in defaults_and_utilities.getBidPeriods()})
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated", yearlyrevenue)
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()})
		if scenario.is_revenue_neutral: defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()})

	print (f"SMDAMAGE done. Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue}. Tau {local_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths C.")
		
	# print ("Done, %s, %.1f seconds." % (time.asctime(time.localtime(time.time())), float(time.time() - startTime)))
	# print ("Reminder: convert $/ton C to $/ton CO2. Temp in 2125 is " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths of a degree C.")
	# print(getCarbonRemovedByForestry("Forestry carbon" + defaults_and_utilities.experimentTag_to_file_name(scenario)))

	return scenario.initial_temperature + temperatureChange [2125].varValue

# END run_SMDAMAGE().

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
	Units = defaults_and_utilities.getUnits() # {'Agriculture':'mtC', 'Black_walnut_150':'mhectares', 'Black_walnut_10':'mhectares', 'Black_walnut_55':'mhectares', 'C2F6':'kt', 'CF4':'kt', 'CH4':'mt', 'Carbon':'mtC', 'HFC125':'kt', 'HFC134a':'kt', 'HFC143a':'kt', 'Loblolly_pine_150':'mhectares', 'Loblolly_pine_10':'mhectares', 'Loblolly_pine_24':'mhectares', 'N2O':'mt', 'Ponderosa_pine_150':'mhectares', 'Ponderosa_pine_10':'mhectares', 'Ponderosa_pine_103':'mhectares', 'Seaweed':'mt', 'SF6':'kt'}
	
	# You might want to solve the model for multiple BeginConstraintYears.
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
			defaults_and_utilities.append_temperatures_to_csv(scenario, "Tau", {t: current_tau[t] for t in ConstraintPeriods})
			
			# Objective
			SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
			SMDAMAGE += defaults_and_utilities.inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set), "Total value" 
			# Variables
			Vname = {}
			for (p, t) in PT_set:
				Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
				SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]
			
			# Constraints to measure actual temperature.
			temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()}
			for t in defaults_and_utilities.getModelPeriods(): SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t]) - temperatureChange[t] == 0, "Temp_t(" + str(t) + ")"
			
			# Constraints to constrain taxed temperature.
			taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in defaults_and_utilities.getModelPeriods()}	
			
			for t in defaults_and_utilities.getModelPeriods(): # Calcuate TaxedTemp for all periods.
				SMDAMAGE += current_tau[t]*lpSum ([Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t]) \
					+ lpSum ([Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t]) \
					- taxedTemperatureChange[t] == 0, "TaxedTemp_t(" + str(t) + ")"
			for t in ConstraintPeriods: # But constrain it only for the constraint periods.
				SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"
		
			# Solve the model.
			solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0))]
			
			# ===== Calculate tau based on emissions and removals. =======================================
			for t in ConstraintPeriods: current_temp[t] = scenario.initial_temperature + temperatureChange[t].varValue

			# Try subgradient optimization. Update temperature and tau for the next run. =======================================
			for t in ConstraintPeriods: current_temp[t] = scenario.initial_temperature + temperatureChange[t].varValue
			# See update_tau() for the formula.
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
		
		netrevenue = 0.0 # Show net revenue with marginal cost pricing.
		yearlyrevenue = {t: 0.0 for t in defaults_and_utilities.getBidPeriods()}
		for (p,t) in PT_set:
			netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
			yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		
		# Save solution to CSV.
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

		# SMDAMAGE_fit_W uses the vpt pickle file.
		with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
			with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated", {t: vpt['Carbon',t].varValue for t in defaults_and_utilities.getBidPeriods()})
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated", yearlyrevenue)
		defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()})
		if scenario.is_revenue_neutral: defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in defaults_and_utilities.getBidPeriods()})

	print (f"SMDAMAGE done. Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue}. Tau {current_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths C.")
		
	# print ("Done, %s, %.1f seconds." % (time.asctime(time.localtime(time.time())), float(time.time() - startTime)))
	# print ("Reminder: convert $/ton C to $/ton CO2. Temp in 2125 is " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths of a degree C.")

	return scenario.initial_temperature + temperatureChange [2125].varValue

	# print(getCarbonRemovedByForestry("Forestry carbon" + defaults_and_utilities.experimentTag_to_file_name(scenario)))
# END run_SMDAMAGE().

# This is a modified copy of run_SMDAMAGE(). Must be revenue neutral. Should use updated Wpt values.
def run_SMDAMAGE_short_auctions(scenario): # Solve a sequence of SMDAMAGE models with 4-year auctions.
	print ("\nSMDAMAGE short auctions. " + defaults_and_utilities.getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	AllBidPeriods = defaults_and_utilities.getBidPeriods()
		
	Wpt_dict = get_warming_effects(scenario) # Get warming effects in degrees Celsius in each period, based on the solution vpt.

	Bapt, Uapt, APT_set, PT_set = read_bids(scenario)
	
	# 3. Set up model. ------------------------------------------------------------------------------------------
	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t]
		BidStepSet[p,t].append(a)

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = defaults_and_utilities.getUnits()

	# Create CSV file with headers.
	with open(defaults_and_utilities.SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
		myoutputfile.write(defaults_and_utilities.getExperimentTag(scenario) + "\n")
		myoutputfile.write(','.join(['Year']
			+ [p + " " + Units[p] for p in Pollutants]
			+ [p + " % max bid" for p in Pollutants]
			+ [p + " $M/" + Units[p] for p in Pollutants])
			+ ',temp change'
			+ ',Capt pi\n')

	FixedPeriods = []
	Fixed_Vpt = {(p,t): 0.0 for (p,t) in PT_set}
	
	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Reminder, Carbon is 'ffi' in pulsefile.
	# Emitters face tax tau. Others do not.
	Emitters = defaults_and_utilities.getEmitters() # ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']
	
	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.
	# See the end of the loop for the change in tau.

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
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0))]
		print (f"SMDAMAGE_short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear) + ", tau=" + str(local_tau) + ", " + str(round(scenario.initial_temperature + temperatureChange [float(startyear+1)].varValue,3)) + " thousandths C.")
		# print (f"SMDAMAGE_short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear))
		
		# if startyear == 2129: SMDAMAGE.writeLP(defaults_and_utilities.getOutputDirectory() + defaults_and_utilities.getExperimentTag(scenario) + "_" + str(startyear) + ".lpt") # Easy to open with Notepad or LP_SolveIDE
		
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
		
		# SMDAMAGE_fit_W uses the vpt pickle file.
		# with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		# if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
		# 	with open(defaults_and_utilities.getOutputDirectory() + "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		# Save carbon, revenue, and actual temps to CSV.
		# defaults_and_utilities.append_temperatures_to_csv(scenario, str(startyear) + ", SMDAMAGE Carbon " , {t: vpt['Carbon',t].varValue for t in BidPeriods})
		# defaults_and_utilities.append_temperatures_to_csv(scenario, str(startyear) + ", SMDAMAGE yearly revenue ", yearlyrevenue)
		# defaults_and_utilities.append_temperatures_to_csv(scenario, str(startyear) + ", SMDAMAGE actual temp ", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in BidPeriods})
		# if scenario.is_revenue_neutral: defaults_and_utilities.append_temperatures_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in BidPeriods})

	# return scenario.initial_temperature + temperatureChange [float(int(max(AllBidPeriods)) - 4)].varValue
	return scenario.initial_temperature + temperatureChange [float(int(max(AllBidPeriods)) - 2)].varValue
# END run_SMDAMAGE_short_auctions(). 
	
def get_SMDAMAGE_temps_actual_and_taxed(scenario):
	SMDAMAGE_temperature = {}
	with open (defaults_and_utilities.SMDAMAGE_output_file_name(scenario)) as SMDAMAGE_output_file:
		lines = [line.split(',') for line in SMDAMAGE_output_file]
		for line in lines[2:]:
			year = int(float(line[0]))
			SMDAMAGE_temperature[year] = float(line[-2])
	
	taxed_temps = old_taxed_temps(scenario, "SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario))
	return taxed_temps, SMDAMAGE_temperature

# ========================================================================================
# Part VI. Main. Run experiments with SMDAMAGE; convert SMDAMAGE output to Hector input, run Hector, and compare temperatures.
# ========================================================================================
if __name__ == "__main__":
	# Preliminary: get pulses from Hector.
	# hector_interface.get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.

	# VI.A. Figure 1. SMDAMAGE uncalibrated. Uses the same tau for every year.
	figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = 2.5, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
	run_SMDAMAGE(figure1)
	hector_interface.run_Hector_with_SMDAMAGE_solution(figure1) # 3. Run Hector on SMDAMAGE output.
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name) 
	calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(figure1) # Should return 971.24975.

	# # VI.B. Figure 1. SMDAMAGE calibrated. discount_rate 0.03, initial_temperature 971.24975, tau 2.5, is_revenue_neutral True, is_removal_luc False, use_updated_Wpt False.
	# figure1.initial_temperature = calibrated_initial_temperature
	# figure1.use_updated_Wpt = True
	# run_SMDAMAGE(figure1) #  Uses the same tau for every year.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(figure1) # What does the Hector trajectory look like with the calibrated SMDAMAGE solution?
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name) 
	
	# # # # VI.C. Figure 2, robustness to discount rate: initial_temperature initial_temperature = 971.24975, is_revenue_neutral False, tau is irrelevant, is_removal_luc to False, use_updated_Wpt = True.
	# calibrated_initial_temperature = 971.24975
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.0, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.015, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
	# # Estimate 1 comes from the solution with discount_rate = 0.03.
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.06, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))

	# # VI.D. Figures 3-5, revenue neutrality: discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau ranges from 1.0 to 2.5, is_removal_luc False, use_updated_Wpt True.
	# calibrated_initial_temperature = 971.24975
	# # # Sequentially run SMDAMAGE with tau = 1, 1.5, 2.0, 2.5.
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.0, is_removal_luc = False, use_updated_Wpt = True))
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.5, is_removal_luc = False, use_updated_Wpt = True))
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.0, is_removal_luc = False, use_updated_Wpt = True))
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))

	# VI.E. # Estimate 2. Concluding paragraph after Figures 3-5.
	# run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.6, is_removal_luc = False, use_updated_Wpt = True))

	# VII. Strength of contracts. (Figure 6 comes from the Pulse input data.)
	# The base scenario is discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau is 1.55, is_removal_luc to False, use_updated_Wpt = True, but with an earlier Wpt, so use False here.

	# VII.A. Uncalibrated SMDAMAGE.
	# For the case of strong contracts, use discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau is 2.4 (you can vary tau in repeat runs of SMDAMAGE to confirm), is_removal_luc to True, use_updated_Wpt = False.
	# contracts_scenario = defaults_and_utilities.Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = 971.24975, is_revenue_neutral = True, tau = 2.1, is_removal_luc = True, use_updated_Wpt = False)
	# SMDAMAGE_final_temp = run_SMDAMAGE(contracts_scenario)
	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# # # # VII.B. Calibrate W.
	# calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(contracts_scenario)

	# # # # VII.C. Calibrated SMDAMAGE.
	# contracts_scenario.use_updated_Wpt = True
	# contracts_scenario.initial_temperature = calibrated_initial_temperature # 1255.5764
	# SMDAMAGE_final_temp = run_SMDAMAGE(contracts_scenario)

	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# VIII. Short auctions, 2 years at a time.
	# VIII.A. Calibrate with a long-term model.
	Short_auctions_scenario = defaults_and_utilities.Scenario(comment = "Short auctions", discount_rate = 0.03, initial_temperature = 971.24975, tau = 1.5, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
	# run_SMDAMAGE(Short_auctions_scenario) # A long auction for calibrating the short auctions.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(Short_auctions_scenario) # 3. Run Hector on SMDAMAGE output.

	# calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(Short_auctions_scenario) # Should return 895.95254.

	# VIII.B. Run the short auctions.
	Short_auctions_scenario.initial_temperature = 895.95254 # calibrated_initial_temperature
	Short_auctions_scenario.use_updated_Wpt = True # Use this updated_Wpt for the short auctions.
	run_SMDAMAGE_short_auctions(Short_auctions_scenario) # Results in excess cooling. Hence the search for tau by year.

	# Search for tau. Starts with tau = 1.7 for every constrained year, then uses subgradient optimization to choose a tau for each year.
	tau_search = defaults_and_utilities.Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = 971.24975, tau = 1.7, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True)
	run_SMDAMAGE_for_tau (tau_search) # Repeated solution of SMDAMAGE with subgradient optimization on tau.

	# wpt_calibration.write_fitted_Wpt_to_csv() # if you want to analyze the Wpt values in Excel.
	import winsound
	winsound.Beep(700, 500)  # Frequency: 1000 Hz, Duration: 500 ms