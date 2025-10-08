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

import csv # input and output.
import matplotlib.pyplot as mplot # graphing.
import os # file management.
import pickle # saving and retrieving solutions, especially the calibrated Wpt.
from pulp import * #pulp.pulpTestAll() # to solve the linear programs.
import time # for timing the run.

def dateTimeString(): return time.strftime("%Y%m%d%H%M", time.localtime())

# 0. Key parameters. These parameters go to file names and headers. If you change something here, a function may be expecting the wrong filename.
#                                               2125 <<<<<<<<<<<<<< Temperature constrained <<<<<<<<<<<<<<<<< 2306 
#           2025 --------- bidding ------------------------------- 2275 
# Timeline: StartYear, StartYear+1, ..., FirstConstrainedYear, ..., StartYear + getNumber_of_bid_years(), ..., StartYear + PulseDataLength.
#                             assert (tFirstConstrainedYear <= StartYear + getNumber_of_bid_years()).
class Scenario(object):
	def __init__(self, comment = '', discount_rate = 0.03, initial_temperature = 1400.0, is_revenue_neutral = False, tau = 1.0, is_removal_luc = False, use_updated_Wpt = False):
		self.comment = comment
		self.discount_rate_base = discount_rate
		self.initial_temperature = initial_temperature
		self.is_revenue_neutral = is_revenue_neutral
		self.tau = tau
		self.is_removal_luc = is_removal_luc
		self.use_updated_Wpt = use_updated_Wpt
	def discount_rate(self, periods): return 1.0/(1.0 + self.discount_rate_base)**(periods) 	
# your_sample_scenario = Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = 971.24975, is_revenue_neutral = True, tau = 2.6, is_removal_luc = True, use_updated_Wpt = False)

def getFirstConstrainedYear(): 		return 2125.0 # This selects the SMDAMAGE output file.
def getNumber_of_bid_years(): 		return 250 # Run this long to avoid end-of-horizon effects. assert (BeginConstraintYear <= StartYear + getNumber_of_bid_years())
def getOutputDirectory(): 			return "./output/" # Must exist
def getPeriodsPerYear(): 			return 1 # Not debugged for larger values. Probably dumb, as it imposes a need for floating indices, e.g., 2025.5.
def getStartYear(): 				return 2025.0 # First year of the auction schedule.
def getPulseDataLength(): 			return 296 # Pulse data from Hector goes only 296 years. So raising this would understate later warming.
def inflate_2020_to_2025(): 		return 1.23 # Inflate prices from 2020 to 2025. From https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexhistorical_us_table.htm, I will multiply bids by $316/$257 = 1.23.
def getTreeTypes():					return ['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']

def getModelPeriods(): return [float(getStartYear()) + float(t)/float(getPeriodsPerYear()) for t in range(getPeriodsPerYear()*getPulseDataLength())]
def getBidPeriods(): return [float(getStartYear()) + float(t)/float(getPeriodsPerYear()) for t in range(getPeriodsPerYear()*getNumber_of_bid_years())] 
def getLastBidYear(): return getStartYear() + getNumber_of_bid_years() - 1.0  # Typically 100 years after first year, e.g., 2020.

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

def experimentTag_to_file_name(scenario):
	tag = getExperimentTag(scenario)
	tag = tag.replace(" ", "_")
	tag = tag.replace(",", "_")
	tag = tag.replace("__", "_")
	return tag

def SMDAMAGE_output_file_name(scenario): return getOutputDirectory() + "SMDAMAGE_soln_" + experimentTag_to_file_name(scenario) + ".csv"
def Hector_output_file_name(scenario): return getOutputDirectory() + "Hector_output_" + experimentTag_to_file_name(scenario) + ".csv"

# =============================================================================================
# Part II. Getting pulse information from Hector. John F. Raffensperger, 2019. 
# =============================================================================================
# This code changes the input to Hector, runs Hector, and reads the output,
# with a pulse increase in each chemical, one chemical at a time, and then records the change in temperature.
from math import log10, floor
import subprocess # Required to call Hector.

# Before you run this code:
# 	(1) run Hector with \input\hector_rcp26.ini and \input\emissions\rcp26_emissions.ini. You should get \output\outputstream_rcp26.csv. This output file has the base temperature by year.
# 	(2) Prepare \input\hector_rcp26_pulsed.ini:
# 		(a) open hector_rcp26.ini, 
# 		(b) in section [core], replace "run_name=rcp26" with "run_name=rcp26_emissions_pulsed". This tells Hector to write \output\outputstream_rcp26_pulsed.csv.
# 		(c) replace text "RCP26_emissions.csv" with "RCP26_emissions_pulsed.csv". 
# 		(d) Save as \input\emissions\rcp26_emissions_pulsed.ini.

# For each greenhouse gas activity, this code will:
# 	(1) modify RCP26_emissions_pulsed.csv to increase the emission for the chemical for the year 2005;
#		Why 2005 instead of, say, 2020? Some refrigerants were phased out, so they have 0 emissions in 2020, which means this code wouldn't be able to calculate a pulse for 2020.
#		In 2005, the world was emitting all the gases at relatively high rates. I guess I could find an average or largest value to pulse if its missing for a year, but let's just use 2005.
#		Pulse year should not matter in theory, as long as the pulse provides a good signal. However, Hector's output ends in the year 2300, so pulsing in 2200 gives only 100 periods of output.
# 	(2) run a batch file calling "hector input/hector_rcp26_pulsed.ini > hector_spew_all_chemicals.txt", to get Hector output RCP26_emissions_pulsed.csv;
#	(3) read RCP26_emissions_pulsed.csv for the temperature by year, subtract those temperatures from the temperatures in outputstream_rcp26.csv

# This reads the existing emission in inputfile (e.g., RCP26_emissions.csv) and increases it in outputfilename (e.g., RCP26_emissions_pulsed.csv).
# The outputfilename is the new input for Hector.
def increaseEmission(pulse_year, inputfilename, outputfilename, chemical): 
	with open (inputfilename, 'r') as inputfile, open (outputfilename, 'w') as outputfile:
		line_counter = 0
		previousline = []
		for line in inputfile:
			linelist = [item.strip() for item in line.split(',')] 
			# print (linelist)
			if line_counter == 3: # i.e., we're on the fourth line reading actual data.
				if chemical not in linelist:
					print("Fail with chemical "+ chemical) # Probably should just exit() here, because it means you're trying to pulse a chemical not in the input file.
					return 'fail', 0.0
				else: 
					chemindex = linelist.index(chemical)
					units = previousline[chemindex]
			if linelist[0] == str(pulse_year): # Are we at the line with the year to pulse?
				oldvalue = linelist[chemindex] # Existing emission.
				linelist[chemindex] = str(0.0)
				print ("Changed " + chemical + " from " + oldvalue + " to " + linelist[chemindex])
				outputfile.write(','.join(linelist) + "\n")
			else: outputfile.write(line)
			line_counter += 1
			previousline = linelist
	return units, -float(oldvalue)

def readTemperatureOutput(outputfilename): # Read the temperature output from Hector.
	yearlist = []
	templist = []
	with open (outputfilename, 'r') as youroutputfile:
		for line in youroutputfile:
			fields = line.split(',')
			if len(fields) >= 5: # temperature global average
				if fields[4] == 'Tgav':
					# print (fields[0],fields[5])
					yearlist.append(int(fields[0]))
					templist.append(float(fields[5]))
	return  yearlist, templist

# Output is Pulses_by_chemical.txt, which contains the marginal temperature changes for each chemical.
# Run once. Then you've got it and don't need to run it again.
def get_Pulses_from_Hector(): # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.
	# Start here.
	pulse_year = 2005 # Chosen because it's before the phaseout of some refrigerants.
	pathname = "D:/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	# pathname = "C:/Users/johnr/Documents/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	os.chdir(pathname)

	file_list = {"Hector_ini": "input/hector_rcp26_pulsed.ini", # You should make this in advance. In section [core], replace "run_name=rcp26" with "run_name=rcp26_emissions_pulsed". Replace text "RCP26_emissions.csv" with "RCP26_emissions_pulsed.csv".
				"Base_emissions_input": "input/emissions/RCP26_emissions.csv", # Supplied with Hector or make it yourself. Constant, should not change.
				"Base_temperature_output": "output/outputstream_rcp26.csv", # Supplied with Hector or make it yourself. Constant, should not change.
				"Hector_spew": "hector_spew_all_chemicals.txt", # created here by Hector. Absorbs Hector's command line reactions.
				"Hector_batch": "run_Hector_all_chemicals_pulsed.bat", # created by this code. Runs Hector on the right files.
				"Pulsed_emissions_input": "input/emissions/RCP26_emissions_pulsed.csv", # created by Hector when you run this code. Contains the emissions pulse input.
				"Pulsed_temperature_output": "output/outputstream_rcp26_pulsed.csv", # Created here by Hector. Contains the resulting temperatures from the emissions pulse. Delete the old one, as this code simply appends new lines.
				"Final_output_file": "Pulses_by_chemical.txt"} # Created by this code. Contains the marginal temperature changes for each chemical. Think of it as outputstream_rcp26_pulsed.csv minus outputstream_rcp26.csv.

	# Create run_hector.bat. Should say something like "hector input/hector_rcp26_pulsed.ini > hector_spew_all_chemicals.txt"
	with open (file_list["Hector_batch"], 'w') as outputfile: outputfile.write("hector " + file_list["Hector_ini"] + " > " + file_list["Hector_spew"])

	# 1. Read original temperatures.
	originalyearlist, originaltemplist = readTemperatureOutput(pathname + file_list['Base_temperature_output']) # Code should not change the base temperature file.

	# 2. Create pulse.
	# Full list of chemicals in Hector.
	chemicals = ['ffi_emissions', 'luc_emissions', 'CH4_emissions', 'N2O_emissions', 'SOx', 'SO2_emissions', 'CO_emissions', 'NMVOC_emissions', 'NOX_emissions', 'BC_emissions', 'OC_emissions', 'NH3',\
		'CF4_emissions', 'C2F6_emissions', 'C6F14', 'HFC23_emissions', 'HFC32_emissions', 'HFC4310_emissions', 'HFC125_emissions', 'HFC134a_emissions', 'HFC143a_emissions', 'HFC227ea_emissions', 'HFC245fa_emissions',\
		'SF6_emissions', 'CFC11_emissions', 'CFC12_emissions', 'CFC113_emissions', 'CFC114_emissions', 'CFC115_emissions', 'CCl4_emissions', 'CH3CCl3_emissions', 'HCF22_emissions', 'HCF141b_emissions',\
		'HCF142b_emissions', 'halon1211_emissions', 'HALON1202', 'halon1301_emissions', 'halon2402_emissions', 'CH3Br_emissions', 'CH3Cl_emissions']

	# List of chemicals in  SMDAMAGE.
	# chemicals = ['ffi_emissions', 'CH4_emissions', 'N2O_emissions', 'CF4_emissions', 'C2F6_emissions', 'HFC125_emissions', 'HFC134a_emissions', 'HFC143a_emissions', 'SF6_emissions']
	for chemical in chemicals:
		
		#3. Create an emissions pulse in the emissions input file.
		units, pulse = increaseEmission(pulse_year, pathname + file_list["Base_emissions_input"], pathname + file_list["Pulsed_emissions_input"], chemical)
		
		# 4. Run Hector to find the pulsed temperature. 
		returnvalue = subprocess.call(pathname + file_list["Hector_batch"], shell=True)

		# 5. Read the pulsed output to get the temperature in each year from the pulse.
		newyearlist, newtemplist = readTemperatureOutput(pathname + file_list["Pulsed_temperature_output"])
		temperature_pulse_list = [] # This is the marginal temperatures by year from the pulse emission.
		for i in range(len(originaltemplist)):
			if newyearlist[i] >= pulse_year:
				temperature_pulse_list.append(float(newtemplist[i]) - float(originaltemplist[i]))

		# 6. Save the pulse output.
		if abs(sum(temperature_pulse_list)) == 0.0: # effect could be positive or negative warming, depending on the gas
			print ("For " + chemical + ", total pulse effect = %f, NOTHING SAVED." % sum(temperature_pulse_list))
		else: 	
			with open (file_list ["Final_output_file"], 'a+') as outputfile: 
				# Save the chemical name, the size of the pulse, the units, and the list of marginal temperatures.
				outputfile.write(chemical + ',' + str(-pulse) + ',' + units + ',' + ','.join([str(-p) for p in temperature_pulse_list]) + '\n')
			print ("For " + chemical + ", total pulse effect = %f" % sum(temperature_pulse_list))
			print ("Normalized %f" % (sum(temperature_pulse_list)/pulse))
	print ("Done")
# get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.
# ============================================================================================
# Part III. SMDAMAGE.
# ============================================================================================
# Forestry, carbon removed for each possible contract.
# The year of planting is the "u_emissionperiod". Pulse units are degrees/megatonnes or degrees/kilotonnes, so we have to convolve growth over time.
def get_Treetype_carbon_removal (Treetypes):
	Treetype_carbon_removal = {tree: {t: 0.0 for t in range(156)} for tree in Treetypes} # where 156 is the longest tree contract.
	with open ('../data/Forestry_Sequestration.csv') as forestryfile: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in forestryfile]
		for growthyear, line in enumerate(lines[1:]): # For each row, i.e., growth year
			for treeNumber, carbonRemoval in enumerate(line[1:]): # For each column, i.e., treetype, in the table.
				Treetype_carbon_removal[Treetypes[treeNumber]][growthyear] = float(carbonRemoval)
	return Treetype_carbon_removal

# Forestry, carbon removed in the optimal auction schedule.
def get_tree_schedule_carbon_removal (vpt): # Matches the spreadsheet convolution exactly.
	Treetypes = getTreeTypes()
	Treetype_carbon_removal = get_Treetype_carbon_removal(Treetypes)
	
	mtC_removed = {t: 0.0 for t in getModelPeriods()}
	for u in getBidPeriods():
		for tree in Treetypes:
			for t in range(int(u), 1 + int(max(getModelPeriods()))): # 
				if t - u >= 156: break # don't run longer than the tree contract.
				mtC_removed [t] += vpt[tree,u].varValue*Treetype_carbon_removal[tree][t - u]
	return mtC_removed

def getPulse(): # Retrieves the marginal change in temperature in each year after a pulse emission.
	Pulse = {} # [Pulseqty, warming1, warming2, warming3,...]
	# Get warming effects for 'C2F6', 'CF4', 'CH4', 'Carbon', HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6', 'SO2'.
	# with open('../data/Calibrated_pulses_by_chemical_2025.txt', 'r') as pulsefile:
	with open('../data/Pulses_by_chemical.txt', 'r') as pulsefile:
		for line in pulsefile: # Each line looks like: ffi_emissions,13.931549999999998,GtC/yr,0.0,...
			chempulse = line.split(",") # Below, we're copying the annual warming for each period in the year.
			Pulse[chempulse[0].replace('_emissions','')] = [float(chempulse[1])] + [float(warming) for warming in chempulse[3:] for i in range(getPeriodsPerYear())]
			# At this point, Pulse['ffi'] = [7.971, -0.0, 0.00227, 0.006247, 0.009098, ... ]. The first element is the impulse size used in Hector to find a temperature change.
			# We have to normalize this, so Wput2_dict [(p, t0)] = Pulse[p1][t0+1]/Pulse[p1][0]
	return Pulse

def open_pkl(your_pkl_filename): # retrieves previously saved solution vpt.
	with open(getOutputDirectory() + your_pkl_filename + ".pkl", "rb") as mypickle: 
		return pickle.load(mypickle)

def old_taxed_temps(scenario, your_taxed_temps_filename): # retrieves previously saved solution vpt.
	if not scenario.is_revenue_neutral: return {}
	print(os.getcwd())
	with open(getOutputDirectory() + your_taxed_temps_filename + "_taxed_temps.pkl", "rb") as mypickle: 
		taxed_temps = pickle.load(mypickle)
	return {t: scenario.initial_temperature + taxed_temps[t].varValue for t in taxed_temps}
# print(get_tree_schedule_carbon_removal(old_vpt(getExperimentTag(scenario) + ".pkl")))
# exit()
	
def yourdictionary_to_CSV(yourdictionary, tag = 'your dictionary'): # Save a dictionary to a CSV file.
	with open(getOutputDirectory() + tag + '.csv', 'w', newline='', encoding='utf-8') as csv_file:
		writer = csv.writer(csv_file)
		for key, value in yourdictionary.items(): writer.writerow([key, value])

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
		if t >= getFirstConstrainedYear():
			# new_tau[t] = linear_interpolation(0.0, [old_temp[t], current_temp[t]], [old_tau[t], current_tau[t]])
			new_tau[t] = max(1.0, current_tau[t] + step_size*current_temp[t]/1000.0)
			total_change += abs(new_tau[t] - old_tau[t])
	return total_change, new_tau
# old_tau = {2125: 1.5, 2126: 1.4, 2127: 2.0}
# old_temp = {2125: 100.0, 2126: 120.0, 2127: -80.0}
# current_tau = {2125: 1.7, 2126: 1.5, 2127: 1.8}
# current_temp = {2125: -100.0, 2126: 12.0, 2127: 80.0}
# print("\n\n", update_tau(old_temp, current_temp, old_tau, current_tau, 1.0))

def read_bids(scenario, Treetypes, Emitters):
	# Parameters
	AllBidPeriods = getBidPeriods()
	StartYear = getStartYear()
	
	Bapt = {} # Bid price for agent a, pollutant p, time period t.
	Uapt = {} # Upper bid quantity, kg, for agent a, pollutant p, time period t.
	APT_set = set() # [(a, p, t),...]
	PT_set = set()

	# All bids in millions of dollars per million tons.
	# 2.1 Agriculture. $US2022, Mtons C2. Based on Smith P., et ak, 2014: Agriculture, Forestry and Other Land Use (AFOLU). In: Climate Change 2014: Mitigation of Climate Change, Figure 11.17.
	with open ('../data/Agriculture_bids.csv') as agfile: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in agfile]
	Bid_Q_Agriculture = [(float (line[0]), float (line[1])) for line in lines[1:]]
	for t in AllBidPeriods:
		PT_set.add(('Agriculture',t))
		for bidstep, bid in enumerate(Bid_Q_Agriculture):
			APT_set.add((bidstep,'Agriculture',t))
			Bapt[bidstep,'Agriculture',t] = - bid[0]*scenario.discount_rate(t - StartYear) # M dollars/M tons
			Uapt[bidstep,'Agriculture',t] = bid[1]/float(getPeriodsPerYear()) # M tons per period.

	# 2.2 Carbon. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Carbon bids", columns F,G.
	# Consider increasing initial quantity of 20 to 1000 or greater.
	with open('../data/MtC_bid_steps.csv', 'r') as Carbonfile:
		lines = [line for line in Carbonfile]
	for t in AllBidPeriods:
		PT_set.add(('Carbon',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Carbon',t))
			Bapt[bidstep,'Carbon',t] = float(bid[0])*scenario.discount_rate(t - StartYear) # m dollars/m tons
			Uapt[bidstep,'Carbon',t] = float(bid[1])/float(getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# 2.3 Seaweed. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Seaweed".
	with open('../data/Seaweed_bids.csv', 'r') as Seaweedfile:
		lines = [line for line in Seaweedfile]
	for t in AllBidPeriods:
		PT_set.add(('Seaweed',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Seaweed',t))
			Bapt[bidstep,'Seaweed',t] = float(bid[0])*scenario.discount_rate(t - StartYear) # m dollars/m tons
			Uapt[bidstep,'Seaweed',t] = float(bid[1])/float(getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# Unused bid data: C6F14, HFC-152a, HFC-227ea, HFC-23, HFC245ca, HFC-32, HFC-43_10.
	# 2.3. Bid data retrieved here: C2F6, CF4, HFC-125, HFC-134a, HFC-143a, SF6.
	# File is sorted by chemical, year, price increasing.
	with open('../data/C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv', 'r') as chemicalsfile:
		lines = [line for line in chemicalsfile]
		thislist = lines[0].split(',') # header: C2F6 $/kt,C2F6 kt/year,CF4 $/kt,CF4 kt/year,HFC125 $/kt,HFC125 kt/year,HFC134a $/kt,HFC134a kt/year,HFC143a $/kt,HFC143a kt/year,SF6 $/kt,SF6 kt/year
		# Remember, Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
		chemicals = ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6'] # trust, but verify 
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
					Uapt[bidstep,chemicals[c],t] = ktons/float(getPeriodsPerYear()) # Ktons per period.

	# 2.4. CH4_bid_steps.csv.
	with open('../data/CH4_bid_steps.csv', 'r') as chemicalsfile:
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
				Uapt[bidstep,chemical,t] = mtons/float(getPeriodsPerYear())

	# 2.5. N2O_bid_steps.csv.
	with open('../data/N2O_bid_steps.csv', 'r') as chemicalsfile:
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
				Uapt[bidstep,chemical,t] = mtons/float(getPeriodsPerYear()) # Megatons

	# 2.6. Forestry_bid_steps.csv,
	with open ('../data/Forestry_bid_steps.csv', 'r') as forestryfile: # Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in forestryfile]
		# units = lines[0] # header: 'Plantable k hectares/year bid qty per crop', '2019 $/hectare Loblolly Pine', '2019 $/hectare ponderosa pine,2019 $/hectare black walnut'.
		bidstep = 0
		for line in lines[1:]: # Plantable k hectares/year bid qty per crop, 2019 $/hectare Loblolly Pine, 2019 $/hectare ponderosa pine, 2019 $/hectare black walnut
			for t in AllBidPeriods:
				for r, tree in enumerate(Treetypes):
					PT_set.add((tree, t))
					APT_set.add((bidstep, tree, t))
					Bapt[bidstep, tree, t] = - float(line[1 + r])*scenario.discount_rate(t - StartYear) # (M dollars)/(M hectares)
					Uapt[bidstep, tree, t] = float(line[0])/float(getPeriodsPerYear()) # M hectares plantable in each period.
			bidstep += 1
	return Bapt, Uapt, APT_set, PT_set

def run_SMDAMAGE(scenario): # Main function. Solve the SMDAMAGE model to find the best schedule of emissions and carbon removal.
	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Caution, Carbon is 'ffi' in pulsefile.
	# Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
	# Emitters face tax tau. Others do not.
	Emitters = ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = ['Agriculture', 'Seaweed', 'Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {'Agriculture':'mtC', 'Black_walnut_150':'mhectares', 'Black_walnut_10':'mhectares', 'Black_walnut_55':'mhectares', 'C2F6':'kt', 'CF4':'kt', 'CH4':'mt', 'Carbon':'mtC', 'HFC125':'kt', 'HFC134a':'kt', 'HFC143a':'kt', 'Loblolly_pine_150':'mhectares', 'Loblolly_pine_10':'mhectares', 'Loblolly_pine_24':'mhectares', 'N2O':'mt', 'Ponderosa_pine_150':'mhectares', 'Ponderosa_pine_10':'mhectares', 'Ponderosa_pine_103':'mhectares', 'Seaweed':'mt', 'SF6':'kt'}
	Treetypes = getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	
	# 1. Warming effects.
	print ("\nSMDAMAGE. " + getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	Pulse = getPulse() # Reads the Pulse input file.

	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	# Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(getPulseDataLength())} # >= 0.
	scaleCelsius = 1000.0 # Thousandths of a degree.

	if scenario.use_updated_Wpt: Wpt_pkl = open_pkl("SMDAMAGE_fitted_Wpt") # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
	for t0 in range(getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		if scenario.use_updated_Wpt: # If not variable in SMDAMAGE_Fit_W, then it will be the same as in the original pulse file.
			Wpt_dict [('luc', float(t0))] = Wpt_pkl[('luc', float(t0))] 
			Wpt_dict [('Carbon', float(t0))] = Wpt_pkl[('Carbon', float(t0))]
		else:
			Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
			Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('luc', float(t0))]
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]
		
		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]
		
	# A hector of tree planting convolves into future carbon removal.
	Treetype_carbon_removal = get_Treetype_carbon_removal(Treetypes)
	# A hector of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes: # Tree is planted in year 0. Tree sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		for treegrowthyear in range(0, 156): # Length of tree contract.
			for coolingyear in range(treegrowthyear, getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth. 
				Wpt_dict[(tree, float(coolingyear))] += Treetype_carbon_removal[tree][treegrowthyear]*Wpt_dict[('Agriculture', float(coolingyear - treegrowthyear))]*scaleCelsius/1000.0

	# 	CH4: MtCH4/yr, N2O: MtN2O-N/yr, C: MtC/yr, NMVOC: Mt/yr, BC: Mt/yr, OC: Mt/yr,
	# 	CF4: kt/yr, C2F6: kt/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, CFC11: kt/yr, CFC12: kt/yr, HCF22: kt/yr]
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(getPulseDataLength()):
			Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]

	# 2. Bids. ------------------------------------------------------------------------------------------
	# print ("2. Reading bids...")

	# Parameters
	Bapt = {} # Bid price for agent a, pollutant p, time period t.
	Uapt = {} # Upper bid quantity, kg, for agent a, pollutant p, time period t.
	APT_set = set() # [(a, p, t),...]
	PT_set = set()

	# All bids in millions of dollars per million tons.
	# 2.1 Agriculture. $US2022, Mtons C2. Based on Smith P., et ak, 2014: Agriculture, Forestry and Other Land Use (AFOLU). In: Climate Change 2014: Mitigation of Climate Change, Figure 11.17.
	with open ('../data/Agriculture_bids.csv') as agfile: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in agfile]
	Bid_Q_Agriculture = [(float (line[0]), float (line[1])) for line in lines[1:]]
	for t in getBidPeriods():
		PT_set.add(('Agriculture',t))
		for bidstep, bid in enumerate(Bid_Q_Agriculture):
			APT_set.add((bidstep,'Agriculture',t))
			Bapt[bidstep,'Agriculture',t] = - bid[0]*scenario.discount_rate(t - getStartYear()) # M dollars/M tons
			Uapt[bidstep,'Agriculture',t] = bid[1]/float(getPeriodsPerYear()) # M tons per period.

	# 2.2 Carbon. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Carbon bids", columns F,G.
	# Consider increasing initial quantity of 20 to 1000 or greater.
	with open('../data/MtC_bid_steps.csv', 'r') as Carbonfile:
		lines = [line for line in Carbonfile]
	for t in getBidPeriods():
		PT_set.add(('Carbon',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Carbon',t))
			Bapt[bidstep,'Carbon',t] = float(bid[0])*scenario.discount_rate(t - getStartYear()) # m dollars/m tons
			Uapt[bidstep,'Carbon',t] = float(bid[1])/float(getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# 2.3 Seaweed. $/tonne, Marginal Mtons Carbon. From "Sources of data.xlsm", sheet "Seaweed".
	with open('../data/Seaweed_bids.csv', 'r') as Seaweedfile:
		lines = [line for line in Seaweedfile]
	for t in getBidPeriods():
		PT_set.add(('Seaweed',t))
		for bidstep,line in enumerate(lines[1:]):
			bid = line.split(',')
			APT_set.add((bidstep,'Seaweed',t))
			Bapt[bidstep,'Seaweed',t] = float(bid[0])*scenario.discount_rate(t - getStartYear()) # m dollars/m tons
			Uapt[bidstep,'Seaweed',t] = float(bid[1])/float(getPeriodsPerYear()) # Millions of tons
			bidstep += 1

	# Unused bid data: C6F14, HFC-152a, HFC-227ea, HFC-23, HFC245ca, HFC-32, HFC-43_10.
	# 2.3. Bid data retrieved here: C2F6, CF4, HFC-125, HFC-134a, HFC-143a, SF6.
	# File is sorted by chemical, year, price increasing.
	with open('../data/C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv', 'r') as chemicalsfile:
		lines = [line for line in chemicalsfile]
		thislist = lines[0].split(',') # header: C2F6 $/kt,C2F6 kt/year,CF4 $/kt,CF4 kt/year,HFC125 $/kt,HFC125 kt/year,HFC134a $/kt,HFC134a kt/year,HFC143a $/kt,HFC143a kt/year,SF6 $/kt,SF6 kt/year
		# Remember, Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
		chemicals = ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6'] # trust, but verify 
		for chemical in chemicals: assert (chemical in Emitters)

		for bidstep, line in enumerate(lines[1:]): # Skip header.
			thislist = line.split(',')
			thislist = [float(item) for item in thislist]
			for c, chemical in enumerate(chemicals):
				price, ktons = thislist[2*c:2*c+2]
				for t in getBidPeriods():
					PT_set.add((chemicals[c],t))
					APT_set.add((bidstep,chemicals[c],t))
					# Data is given in $/tonne C. Quantities are kilotons, so decision variables should be $million/kiloton.
					# Thus, $500/ton --> $0.5 million per kiloton.
					Bapt[bidstep,chemicals[c],t] = price*scenario.discount_rate(t - getStartYear())/1000.0 # m dollars/k tons
					Uapt[bidstep,chemicals[c],t] = ktons/float(getPeriodsPerYear()) # Ktons per period.

	# 2.4. CH4_bid_steps.csv.
	with open('../data/CH4_bid_steps.csv', 'r') as chemicalsfile:
		chemical = 'CH4'
		lines = [line for line in chemicalsfile]
		for bidstep, line in enumerate(lines[1:]):
			price, mtons = line.split(',')
			price = float(price)
			mtons = float(mtons)
			for t in getBidPeriods():
				PT_set.add((chemical,t))
				APT_set.add((bidstep,chemical,t))
				Bapt[bidstep,chemical,t] = price*scenario.discount_rate(t  - getStartYear()) # Mega dollars/megatons
				# As described in "1-s2.0-S2352340919306882-mmc1, CH4 and NO2, jfr 1.xlsm", sheet "SSP2 CH4 N2O baseline emissions".
				Uapt[bidstep,chemical,t] = mtons/float(getPeriodsPerYear())

	# 2.5. N2O_bid_steps.csv.
	with open('../data/N2O_bid_steps.csv', 'r') as chemicalsfile:
		chemical = 'N2O'
		lines = [line for line in chemicalsfile]
		for bidstep, line in enumerate(lines[1:]):
			price, mtons = line.split(',')
			price = float(price)
			mtons = float(mtons)
			for t in getBidPeriods():
				PT_set.add((chemical,t))
				APT_set.add((bidstep,chemical,t))
				Bapt[bidstep,chemical,t] = price*scenario.discount_rate(t - getStartYear()) # Mega dollars/megatons
				# As described in "1-s2.0-S2352340919306882-mmc1, CH4 and NO2, jfr 1.xlsm", sheet "SSP2 CH4 N2O baseline emissions".
				Uapt[bidstep,chemical,t] = mtons/float(getPeriodsPerYear()) # Megatons

	# 2.6. Forestry_bid_steps.csv,
	with open ('../data/Forestry_bid_steps.csv', 'r') as forestryfile: # Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in forestryfile]
		# units = lines[0] # header: 'Plantable k hectares/year bid qty per crop', '2019 $/hectare Loblolly Pine', '2019 $/hectare ponderosa pine,2019 $/hectare black walnut'.
		bidstep = 0
		for line in lines[1:]: # Plantable k hectares/year bid qty per crop, 2019 $/hectare Loblolly Pine, 2019 $/hectare ponderosa pine, 2019 $/hectare black walnut
			for t in getBidPeriods():
				for r, tree in enumerate(Treetypes):
					PT_set.add((tree, t))
					APT_set.add((bidstep, tree, t))
					Bapt[bidstep, tree, t] = - float(line[1 + r])*scenario.discount_rate(t - getStartYear()) # (M dollars)/(M hectares)
					Uapt[bidstep, tree, t] = float(line[0])/float(getPeriodsPerYear()) # M hectares plantable in each period.
			bidstep += 1

	# 3. Set up model. ------------------------------------------------------------------------------------------
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

	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.

	# You might want to solve the model for multiple BeginConstraintYears.
	for BeginConstraintYear in range(int(getFirstConstrainedYear()), int(getFirstConstrainedYear()) + 1, 1):
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(getPeriodsPerYear()) for t in range(getPeriodsPerYear()*(getPulseDataLength() + int(getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= getStartYear() + getNumber_of_bid_years())
		
		# print ("3. Creating model for first constraint year of " + str(BeginConstraintYear))
		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
		
		# print("Objective...", sep=None)
		SMDAMAGE += inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set), "Total value"
		
		# print("Vpt rows...", sep=None)
		Vname = {}
		for (p, t) in PT_set:
			Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
			SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]

		# print("Capt rows...")
		temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in getModelPeriods()}
		
		# Measuring actual temperature change, not the "taxed" surrogate temperature. If REVENUE_NEUTRAL, Temp_t equations should not constrain the model.
		for t in getModelPeriods(): SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t]) - temperatureChange[t] == 0, "Temp_t(" + str(t) + ")"

		if scenario.is_revenue_neutral: # Taxed net zero model. 
			taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in getModelPeriods()}
			
			for t in getModelPeriods(): 
				SMDAMAGE += lpSum ([local_tau*Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u <= BeginConstraintYear - 1.0]) \
						+ lpSum ([Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u >= BeginConstraintYear]) \
					      + lpSum ([Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t]) \
						- taxedTemperatureChange[t] == 0, "TaxedTemp_t(" + str(t) + ")"
			
			for t in ConstraintPeriods: SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"
		else: 
			Capt = {t: -scenario.initial_temperature for t in ConstraintPeriods} # Allowed increase in global temp, thousandths of degrees Celsius in period t.
			for t in ConstraintPeriods: SMDAMAGE += temperatureChange [t] <= Capt[t], "Capt(" + str(t) + ")"

		# print ("4. Writing a debug model...") # SLOW! -------------------------------------------------------------
		# SMDAMAGE.writeLP(getOutputDirectory() + getExperimentTag(scenario) + ".lpt") # Easy to open with Notepad or LP_SolveIDE
		
		# print ("5. Solving the model...")
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0))]

		netrevenue = 0.0 # Show net revenue with marginal cost pricing.
		yearlyrevenue = {t: 0.0 for t in getBidPeriods()}
		for (p,t) in PT_set:
			netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
			yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		
		# Save solution to CSV.
		with open (SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
			myoutputfile.write(getExperimentTag(scenario) + ". Solve status " + solve_status + ". Total revenue " + str(netrevenue) + '\n')
			myoutputfile.write(','.join(['Year']
				+ [p + " " + Units[p] for p in Pollutants]
				+ [p + " % max bid" for p in Pollutants]
				+ [p + " $M/" + Units[p] for p in Pollutants])
				+ ',temp change'
				+ ',Capt pi\n')
			print("Wrote SMDAMAGE solution to " + SMDAMAGE_output_file_name(scenario))

			for t in getModelPeriods():
				line = [str(t)] # Year
				if t in getBidPeriods():
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
		with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
			with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		append_output_to_csv(scenario, "SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated", {t: vpt['Carbon',t].varValue for t in getBidPeriods()})
		append_output_to_csv(scenario, "SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated", yearlyrevenue)
		append_output_to_csv(scenario, "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in getBidPeriods()})
		if scenario.is_revenue_neutral: append_output_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in getBidPeriods()})

	print (f"SMDAMAGE done. Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue}. Tau {local_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths C.")
		
	# print ("Done, %s, %.1f seconds." % (time.asctime(time.localtime(time.time())), float(time.time() - startTime)))
	# print ("Reminder: convert $/ton C to $/ton CO2. Temp in 2125 is " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths of a degree C.")

	return scenario.initial_temperature + temperatureChange [2125].varValue

	# print(getCarbonRemovedByForestry("Forestry carbon" + experimentTag_to_file_name(scenario)))
# END run_SMDAMAGE().

def run_SMDAMAGE_for_tau(scenario): # This version finds the optimal tau.
	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Caution, Carbon is 'ffi' in pulsefile.
	# Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
	# Emitters face tax tau. Others do not.
	Emitters = ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = ['Agriculture', 'Seaweed', 'Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {'Agriculture':'mtC', 'Black_walnut_150':'mhectares', 'Black_walnut_10':'mhectares', 'Black_walnut_55':'mhectares', 'C2F6':'kt', 'CF4':'kt', 'CH4':'mt', 'Carbon':'mtC', 'HFC125':'kt', 'HFC134a':'kt', 'HFC143a':'kt', 'Loblolly_pine_150':'mhectares', 'Loblolly_pine_10':'mhectares', 'Loblolly_pine_24':'mhectares', 'N2O':'mt', 'Ponderosa_pine_150':'mhectares', 'Ponderosa_pine_10':'mhectares', 'Ponderosa_pine_103':'mhectares', 'Seaweed':'mt', 'SF6':'kt'}
	Treetypes = getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	
	# 1. Warming effects.
	print ("\nSMDAMAGE. " + getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	Pulse = getPulse() # Reads the Pulse input file.

	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	# Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(getPulseDataLength())} # >= 0.
	scaleCelsius = 1000.0 # Thousandths of a degree.

	if scenario.use_updated_Wpt: Wpt_pkl = open_pkl("SMDAMAGE_fitted_Wpt") # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
	for t0 in range(getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		if scenario.use_updated_Wpt: # If not variable in SMDAMAGE_Fit_W, then it will be the same as in the original pulse file.
			Wpt_dict [('luc', float(t0))] = Wpt_pkl[('luc', float(t0))] 
			Wpt_dict [('Carbon', float(t0))] = Wpt_pkl[('Carbon', float(t0))]
		else:
			Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
			Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('luc', float(t0))]
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]
		
		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]
		
	# A hector of tree planting convolves into future carbon removal.
	Treetype_carbon_removal = get_Treetype_carbon_removal(Treetypes)
	# A hector of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes: # Tree is planted in year 0. Tree sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		for treegrowthyear in range(0, 156): # Length of tree contract.
			for coolingyear in range(treegrowthyear, getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth. 
				Wpt_dict[(tree, float(coolingyear))] += Treetype_carbon_removal[tree][treegrowthyear]*Wpt_dict[('Agriculture', float(coolingyear - treegrowthyear))]*scaleCelsius/1000.0

	# 	CH4: MtCH4/yr, N2O: MtN2O-N/yr, C: MtC/yr, NMVOC: Mt/yr, BC: Mt/yr, OC: Mt/yr,
	# 	CF4: kt/yr, C2F6: kt/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, CFC11: kt/yr, CFC12: kt/yr, HCF22: kt/yr]
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(getPulseDataLength()):
			Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]

	# 2. Bids. ------------------------------------------------------------------------------------------
	Bapt, Uapt, APT_set, PT_set = read_bids(scenario, Treetypes, Emitters)

	# 3. Set up model. ------------------------------------------------------------------------------------------
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

	# You might want to solve the model for multiple BeginConstraintYears.
	for BeginConstraintYear in range(int(getFirstConstrainedYear()), int(getFirstConstrainedYear()) + 1, 1):
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(getPeriodsPerYear()) for t in range(getPeriodsPerYear()*(getPulseDataLength() + int(getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= getStartYear() + getNumber_of_bid_years())

		# Initialize tau.
		old_tau = {t: 1.0 for t in getModelPeriods()} # Net zero gets you only the current temperature.
		old_temp = {t: scenario.initial_temperature for t in ConstraintPeriods}
		current_tau = {t: scenario.tau if t in ConstraintPeriods else 1.0 for t in getModelPeriods()} # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.
		current_temp = {t: 0.0 for t in ConstraintPeriods}
		
		# Loop over tau[t] =================
		step_size = 2.0 # For subgradient optimization.
		for run in range(200):
			append_output_to_csv(scenario, "Tau", {t: current_tau[t] for t in ConstraintPeriods})
			
			# Objective
			SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize)
			SMDAMAGE += inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set), "Total value" 
			# Variables
			Vname = {}
			for (p, t) in PT_set:
				Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
				SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]
			
			# Constraints to measure actual temperature.
			temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in getModelPeriods()}
			for t in getModelPeriods(): SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t]) - temperatureChange[t] == 0, "Temp_t(" + str(t) + ")"
			
			# Constraints to constrain taxed temperature.
			taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in getModelPeriods()}	
			
			for t in getModelPeriods(): # Calcuate TaxedTemp for all periods.
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
		yearlyrevenue = {t: 0.0 for t in getBidPeriods()}
		for (p,t) in PT_set:
			netrevenue -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
			yearlyrevenue[t] -= vpt[p,t].varValue*SMDAMAGE.constraints[Vname[(p,t)]].pi
		
		# Save solution to CSV.
		with open (SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
			myoutputfile.write(getExperimentTag(scenario) + ". Solve status " + solve_status + ". Total revenue " + str(netrevenue) + '\n')
			myoutputfile.write(','.join(['Year']
				+ [p + " " + Units[p] for p in Pollutants]
				+ [p + " % max bid" for p in Pollutants]
				+ [p + " $M/" + Units[p] for p in Pollutants])
				+ ',temp change'
				+ ',Capt pi\n')
			print("Wrote SMDAMAGE solution to " + SMDAMAGE_output_file_name(scenario))

			for t in getModelPeriods():
				line = [str(t)] # Year
				if t in getBidPeriods():
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
		with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
			with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		append_output_to_csv(scenario, "SMDAMAGE Carbon calibrated" if scenario.use_updated_Wpt else "SMDAMAGE Carbon uncalibrated", {t: vpt['Carbon',t].varValue for t in getBidPeriods()})
		append_output_to_csv(scenario, "SMDAMAGE yearly revenue calibrated" if scenario.use_updated_Wpt else "SMDAMAGE yearly revenue uncalibrated", yearlyrevenue)
		append_output_to_csv(scenario, "SMDAMAGE actual temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE actual temp uncalibrated", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in getBidPeriods()})
		if scenario.is_revenue_neutral: append_output_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in getBidPeriods()})

	print (f"SMDAMAGE done. Solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Net revenue {netrevenue}. Tau {current_tau}. 2125 temp " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths C.")
		
	# print ("Done, %s, %.1f seconds." % (time.asctime(time.localtime(time.time())), float(time.time() - startTime)))
	# print ("Reminder: convert $/ton C to $/ton CO2. Temp in 2125 is " + str(round(scenario.initial_temperature + temperatureChange [2125].varValue,3)) + " thousandths of a degree C.")

	return scenario.initial_temperature + temperatureChange [2125].varValue

	# print(getCarbonRemovedByForestry("Forestry carbon" + experimentTag_to_file_name(scenario)))
# END run_SMDAMAGE().

# This is a modified copy of run_SMDAMAGE(). Must be revenue neutral. Should use updated Wpt values.
def run_SMDAMAGE_short_auctions(scenario): # Solve a sequence of SMDAMAGE models with 4-year auctions.
	AllBidPeriods = getBidPeriods()
	
	# All objective function coefficients should be millions of dollars. So a bid of 1 is a bid for $1 million per unit of the chemical.
	# Caution, Carbon is 'ffi' in pulsefile.
	# Chemicals = ['Agriculture', 'Black_walnut', 'C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'Loblolly_pine', 'N2O', 'Ponderosa_pine', 'Seaweed', 'SF6']
	# Emitters face tax tau. Others do not.
	Emitters = ['C2F6', 'CF4', 'CH4', 'Carbon', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = ['Agriculture', 'Seaweed', 'Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']

	# Agriculture and "Carbon" are in megatons of carbon (not CO2). Hector uses gigatons of carbon, so we need to convert Hector's gigatons warming effects to SMDAMAGE megatons decision variables and back again to Hector gigatons for validation.
	Units = {'Agriculture':'mtC', 'Black_walnut_150':'mhectares', 'Black_walnut_10':'mhectares', 'Black_walnut_55':'mhectares', 'C2F6':'kt', 'CF4':'kt', 'CH4':'mt', 'Carbon':'mtC', 'HFC125':'kt', 'HFC134a':'kt', 'HFC143a':'kt', 'Loblolly_pine_150':'mhectares', 'Loblolly_pine_10':'mhectares', 'Loblolly_pine_24':'mhectares', 'N2O':'mt', 'Ponderosa_pine_150':'mhectares', 'Ponderosa_pine_10':'mhectares', 'Ponderosa_pine_103':'mhectares', 'Seaweed':'mt', 'SF6':'kt'}
	Treetypes = getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	
	# 1. Warming effects.
	print ("\nSMDAMAGE short auctions. " + getExperimentTag(scenario) + ". " + time.asctime(time.localtime(time.time())) + ".")
	Pulse = getPulse() # Reads the Pulse input file.

	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	# Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(getPulseDataLength())} # >= 0.
	scaleCelsius = 1000.0 # Thousandths of a degree.

	if scenario.use_updated_Wpt: Wpt_pkl = open_pkl("SMDAMAGE_fitted_Wpt") # Retrieve the updated Wpt values from SMDAMAGE_fit_W.
	for t0 in range(getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		if scenario.use_updated_Wpt: # If not variable in SMDAMAGE_Fit_W, then it will be the same as in the original pulse file.
			Wpt_dict [('luc', float(t0))] = Wpt_pkl[('luc', float(t0))] 
			Wpt_dict [('Carbon', float(t0))] = Wpt_pkl[('Carbon', float(t0))]
		else:
			Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
			Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('luc', float(t0))]
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]
		
		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]
		
	# A hector of tree planting convolves into future carbon removal.
	Treetype_carbon_removal = get_Treetype_carbon_removal(Treetypes)
	# A hector of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes: # Tree is planted in year 0. Tree sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		for treegrowthyear in range(0, 156): # Length of tree contract.
			for coolingyear in range(treegrowthyear, getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth. 
				Wpt_dict[(tree, float(coolingyear))] += Treetype_carbon_removal[tree][treegrowthyear]*Wpt_dict[('Agriculture', float(coolingyear - treegrowthyear))]*scaleCelsius/1000.0

	# 	CH4: MtCH4/yr, N2O: MtN2O-N/yr, C: MtC/yr, NMVOC: Mt/yr, BC: Mt/yr, OC: Mt/yr,
	# 	CF4: kt/yr, C2F6: kt/yr, HFC125: kt/yr, HFC134a: kt/yr, HFC143a: kt/yr, CFC11: kt/yr, CFC12: kt/yr, HCF22: kt/yr]
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(getPulseDataLength()):
			Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]

	Bapt, Uapt, APT_set, PT_set = read_bids(scenario, Treetypes, Emitters)
	
	# 3. Set up model. ------------------------------------------------------------------------------------------
	Pollutants = sorted(list(set([p for p,t in PT_set])))
	BidStepSet = {}
	for (p,t) in PT_set: BidStepSet[p,t] = []
	TotalU = {(p,t): 0.0 for (p,t) in PT_set}
	for (a,p,t) in APT_set:
		TotalU[p,t] += Uapt[a,p,t]
		BidStepSet[p,t].append(a)

	# Create CSV file with headers.
	with open(SMDAMAGE_output_file_name(scenario), 'w') as myoutputfile:
		myoutputfile.write(getExperimentTag(scenario) + "\n")
		myoutputfile.write(','.join(['Year']
			+ [p + " " + Units[p] for p in Pollutants]
			+ [p + " % max bid" for p in Pollutants]
			+ [p + " $M/" + Units[p] for p in Pollutants])
			+ ',temp change'
			+ ',Capt pi\n')

	FixedPeriods = []
	Fixed_Vpt = {(p,t): 0.0 for (p,t) in PT_set}
	
	local_tau = scenario.tau # We have to change tau when the temperature is low enough (at the end of this loop), but we don't want to change the output filename.
	# See the end of the loop for the change in tau.

	# Run 2-year auctions.
	for startyear in range(int(min(AllBidPeriods)), int(max(AllBidPeriods)) - 2, 2):
		BidPeriods = [float(startyear), float(startyear+1)] #, float(startyear+2), float(startyear+3)]
	
		# Decision variables
		qapt = {(a,p,t): LpVariable("qapt(" + str(a) + "," + p + "," + str(t) + ")", 0.0, Uapt[a,p,t]) for (a, p, t) in APT_set if t in BidPeriods}
		vpt = {(p,t): LpVariable("vpt(" + p + "," + str(t) + ")", None, None) for (p, t) in PT_set if t in BidPeriods} # Must be a free variable.
	
		BeginConstraintYear = int(getFirstConstrainedYear())
		ConstraintPeriods = [float(BeginConstraintYear) + float(t)/float(getPeriodsPerYear()) for t in range(getPeriodsPerYear()*(getPulseDataLength() + int(getStartYear()) - int(BeginConstraintYear)))] # e.g., 2120, 2120.5, 2121, 2121.5, ..., 2301
		assert (BeginConstraintYear <= getStartYear() + getNumber_of_bid_years())
		
		SMDAMAGE = LpProblem("SMDAMAGE", LpMaximize) # Create model.
		SMDAMAGE += inflate_2020_to_2025()*lpSum(Bapt[a,p,t]*qapt[a,p,t] for (a, p, t) in APT_set if t in BidPeriods), "Total value" # Objective.
		
		# Vpt rows.
		Vname = {}
		for (p, t) in PT_set:
			if t in BidPeriods:
				Vname[(p,t)] = "Vpt(" + p + "," + str(t) + ")"
				SMDAMAGE += vpt[p,t] == lpSum ([qapt[a,p,t] for a in BidStepSet[p,t]]), Vname[(p,t)]
		
		# Measuring actual temperature change, not the "taxed" surrogate temperature. If REVENUE_NEUTRAL, Temp_t equations should not constrain the model.
		temperatureChange = {t: LpVariable("tempChange(" + str(t) + ")", None, None) for t in getModelPeriods()[len(FixedPeriods):]}
		for t in getModelPeriods()[len(FixedPeriods):] : SMDAMAGE += lpSum ([Wpt_dict[(p, float(t - u))]*vpt[p,u] for (p,u) in PT_set if u <= t and u in BidPeriods]) - temperatureChange[t] \
			+ sum([Wpt_dict[(p, float(t - u))]*Fixed_Vpt[p,u] for (p,u) in PT_set if u <= t and u in FixedPeriods]) == 0, "Temp_t(" + str(t) + ")"

		# Measuring taxed temperature change.
		taxedTemperatureChange = {t: LpVariable("taxedTempChange(" + str(t) + ")", None, None) for t in getModelPeriods()[len(FixedPeriods):]}
		for t in getModelPeriods()[len(FixedPeriods):]: 
			SMDAMAGE += lpSum ([local_tau*Wpt_dict[(p,t - u)]*vpt[p,u] for (p,u) in PT_set if p in Emitters and u <= t and u in BidPeriods] + [Wpt_dict[(p, t - u)]*vpt[p,u] for (p,u) in PT_set if p not in Emitters and u <= t and u in BidPeriods])\
				- taxedTemperatureChange[t] == 0, "TaxedTemp_t(" + str(t) + ")"
		for t in ConstraintPeriods:
			if t not in FixedPeriods: SMDAMAGE += taxedTemperatureChange [t] <= 0.0, "Capt(" + str(t) + ")"
		
		# print ("5. Solving the model...")
		solve_status = LpStatus[SMDAMAGE.solve(PULP_CBC_CMD(msg=0))]
		print (f"SMDAMAGE_short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear) + ", tau=" + str(local_tau) + ", " + str(round(scenario.initial_temperature + temperatureChange [float(startyear+1)].varValue,3)) + " thousandths C.")
		# print (f"SMDAMAGE_short_auctions, solve status {solve_status}. Objective ${value(SMDAMAGE.objective) / 1000:.2f} billion. Start year " + str(startyear))
		
		# if startyear == 2129: SMDAMAGE.writeLP(getOutputDirectory() + getExperimentTag(scenario) + "_" + str(startyear) + ".lpt") # Easy to open with Notepad or LP_SolveIDE
		
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
		with open(SMDAMAGE_output_file_name(scenario), 'a') as myoutputfile:
			for t in BidPeriods:
				line = [str(t)] # Year
				for p in Pollutants: line.append(str(vpt[p,t].varValue)) # qty units
				for p in Pollutants: line.append(str(vpt[p,t].varValue/TotalU[p,t])) # Fraction of bid
				for p in Pollutants: line.append(str(SMDAMAGE.constraints[Vname[(p,t)]].pi)) # $M/unit
				line.append(str(scenario.initial_temperature + temperatureChange[t].varValue))
				if t in ConstraintPeriods and t not in FixedPeriods: line.append(str(SMDAMAGE.constraints["Capt(" + str(t) + ")"].pi))
				else: line.append('.')
				myoutputfile.write(','.join(line) + '\n')
		
		# If near-term auctions are likely to achieve the target temperature, cancel the removal tax and retain carbon neutrality.
		# local_tau = max (1.0, local_tau - 0.01) # Example of a policy to reduce the tax rate over time.
		# if scenario.initial_temperature + temperatureChange[float(startyear+1)].varValue < 900.0 and startyear+1 >= 2050: local_tau = 1.0 # Quit early to reduce excess cooling.
		# if scenario.initial_temperature + temperatureChange[float(startyear+1)].varValue < 100.0 or startyear+1 >= 2100: local_tau = 1.0
		if startyear+1 >= getFirstConstrainedYear(): local_tau = 1.0
		
		# SMDAMAGE_fit_W uses the vpt pickle file.
		# with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + ".pkl", "wb") as mypickle: pickle.dump(vpt, mypickle)
		# if scenario.is_revenue_neutral: # get_SMDAMAGE_temps_actual_and_taxed() uses this.
		# 	with open(getOutputDirectory() + "SMDAMAGE " + experimentTag_to_file_name(scenario) + "_taxed_temps.pkl", "wb") as mypickle: pickle.dump(taxedTemperatureChange, mypickle)
		
		# Save carbon, revenue, and actual temps to CSV.
		# append_output_to_csv(scenario, str(startyear) + ", SMDAMAGE Carbon " , {t: vpt['Carbon',t].varValue for t in BidPeriods})
		# append_output_to_csv(scenario, str(startyear) + ", SMDAMAGE yearly revenue ", yearlyrevenue)
		# append_output_to_csv(scenario, str(startyear) + ", SMDAMAGE actual temp ", {t: scenario.initial_temperature + temperatureChange[t].varValue for t in BidPeriods})
		# if scenario.is_revenue_neutral: append_output_to_csv(scenario, "SMDAMAGE taxed temp calibrated" if scenario.use_updated_Wpt else "SMDAMAGE taxed temp uncalibrated", {t: scenario.initial_temperature + taxedTemperatureChange[t].varValue for t in BidPeriods})

	# return scenario.initial_temperature + temperatureChange [float(int(max(AllBidPeriods)) - 4)].varValue
	return scenario.initial_temperature + temperatureChange [float(int(max(AllBidPeriods)) - 2)].varValue
# END run_SMDAMAGE_short_auctions().

# ========================================================================================
# Part IV. Running Hector on SMDAMAGE output. Does the SMDAMAGE activity schedule result in the correct temperature trajectory in Hector?
# John F Raffensperger. 2022-07-27, 2022-09-10, 2025-01-05.
# ======================================================================================== 
# Reads the Hector input file RCP_emissions, returns a dictionary RCP_emissions [year, emissionsType] = emissionsValue.
# Called from convert_SMDAMAGE_solution_to_Hector_input().
def getHectorEmissionsDictionary(RCP26_emissions_file): # e.g., "RCP26_emissions.csv"
	with open ("../hector-2.0.1-Windows/input/emissions/" + RCP26_emissions_file) as Hector_input_file:
		lines = [line.split(',') for line in Hector_input_file]
	RCP26_emissions = {}
	header = lines[3]
	for line in lines[4:]:
		for columnNumber, item in enumerate(line[0:41]):
			year = line[0]
			emissionsType = header[columnNumber].strip()
			emissionsValue = item
			RCP26_emissions[(float(year), emissionsType)] = float(emissionsValue)
	return RCP26_emissions

# Reads SMDAMAGE output for firstConstrainedYear, e.g., smdamage_solution_2075.csv. Outputs dictionary SMDAMAGE_emissions[year, emissionsType] = emissionaValue.
# Called from getCarbonRemovedByForestry() and convert_SMDAMAGE_solution_to_Hector_input().
def get_SMDAMAGE_emissions_dictionary (scenario):
	with open (SMDAMAGE_output_file_name(scenario)) as SMDAMAGE_output_file: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in SMDAMAGE_output_file]
	SMDAMAGE_emissions = {}
	numberOfColumnsInSMDAMAGE_solution_csv = 20
	for line in lines[2:]:
		for columnNumber, item in enumerate(line[0:numberOfColumnsInSMDAMAGE_solution_csv+1]): # Columns of primal values in smdamage_solution_YYYY.csv.
			year = line[0]
			if float(year) <= getLastBidYear():
				emissionsType = lines[1][columnNumber].strip()
				emissionsValue = item
				SMDAMAGE_emissions[(float(year), emissionsType)] = (-1.0 if emissionsType == 'Agriculture mt' else 1.0)*float(emissionsValue)
	return SMDAMAGE_emissions
# print(get_SMDAMAGE_emissions_dictionary("Rev neutral, tau is 1.766, tax only 2125 SMDAMAGE soln 2125.csv"))

# Reads the SMDAMAGE solution for first_constrained_year and writes valid input for Hector, with RCP26_emissions.csv as a base.
def convert_SMDAMAGE_solution_to_Hector_input (scenario):
	RCP26_emissions = getHectorEmissionsDictionary("RCP26_emissions.csv")
	SMDAMAGE_emissions = get_SMDAMAGE_emissions_dictionary (scenario)
	carbonRemovedByForestry = get_tree_schedule_carbon_removal(open_pkl("SMDAMAGE " + experimentTag_to_file_name(scenario))) # getCarbonRemovedByForestry()
	firstYear = 1765 # in RCP26_emissions.csv.
	first_SMDAMAGE_year = int(getStartYear())
	lastYear = int(getLastBidYear()) # because for example smdamage_solution_2070.csv includes 2169.5.
	
	SMDAMAGE_to_Hector = {} # [(firstYear, pollutant): value, ... (lastYear, pollutant): value]
	
	# 1. Pollutants not in SMDAMAGE, all years. Using future RCP26 emissions.
	leaveAlone = ['HFC227ea_emissions', 'HFC245fa_emissions', 'HFC32_emissions', 'HFC4310_emissions', 'CFC11_emissions', 'CFC12_emissions', 'CFC113_emissions', 'CFC114_emissions', 'CFC115_emissions', 'CCl4_emissions', 'CH3CCl3_emissions', 'HCF22_emissions', 'HCF141b_emissions', 'HCF142b_emissions', 'halon1211_emissions', 'HALON1202', 'halon1301_emissions', 'halon2402_emissions', 'CH3Br_emissions', 'CH3Cl_emissions', 'SOx', 'SO2_emissions', 'CO_emissions', 'NMVOC_emissions', 'NOX_emissions', 'BC_emissions', 'OC_emissions', 'NH3', 'C6F14', 'HFC23_emissions']
	for columnNumber, pollutant in enumerate(leaveAlone):
		for year in range(firstYear, lastYear + 1): SMDAMAGE_to_Hector[(year, pollutant)] = RCP26_emissions[(year, pollutant)]
	
	# 2. Pollutants in SMDAMAGE, years < 2025.
	Matching_RCP_to_SMDAMAGE_columns = {'CH4_emissions': 'CH4 mt', 'N2O_emissions': 'N2O mt', 'CF4_emissions': 'CF4 kt', 'C2F6_emissions': 'C2F6 kt', 'HFC125_emissions': 'HFC125 kt', 'HFC134a_emissions': 'HFC134a kt', 'HFC143a_emissions': 'HFC143a kt', 'SF6_emissions': 'SF6 kt'}
	for pollutant in Matching_RCP_to_SMDAMAGE_columns:
		for year in range(firstYear, first_SMDAMAGE_year):
			SMDAMAGE_to_Hector[(year, pollutant)] = RCP26_emissions[(year, pollutant)]
	for year in range(firstYear, first_SMDAMAGE_year):
		SMDAMAGE_to_Hector[(year, 'ffi_emissions')] = RCP26_emissions[(year, 'ffi_emissions')]
		SMDAMAGE_to_Hector[(year, 'luc_emissions')] = RCP26_emissions[(year, 'luc_emissions')]

	# 3. Pollutants in SMDAMAGE, years >= 2025. Non-matching columns. ffi_emissions = 'Carbon mtC', and 'luc_emissions' = - 'Agriculture mtC' - 'Seaweed mt' - carbonRemovedByForestry.
	for pollutant in Matching_RCP_to_SMDAMAGE_columns:
		for year in range(first_SMDAMAGE_year, lastYear + 1):
			SMDAMAGE_to_Hector[(year, pollutant)] = (SMDAMAGE_emissions [(year, Matching_RCP_to_SMDAMAGE_columns[pollutant])])

	# 'ffi_emissions' and 'luc_emissions'
	for year in range(first_SMDAMAGE_year, lastYear + 1):
		# Not debugged for multiple periods per year. # SMDAMAGE_to_Hector[(year, 'ffi_emissions')] = (SMDAMAGE_emissions [(year, 'Carbon mtC')] + SMDAMAGE_emissions [(year + 0.5, 'Carbon mtC')])/1000.0 # Convert to Gt.
		# Start with the RCP26 land use change emissions, then subtract the SMDAMAGE agriculture, seaweed, and forestry emissions.
		SMDAMAGE_to_Hector[(year, 'ffi_emissions')] = (SMDAMAGE_emissions [(year, 'Carbon mtC')])/1000.0 # Convert mtC to GtC.
		SMDAMAGE_to_Hector[(year, 'luc_emissions')] = RCP26_emissions[(year, 'luc_emissions')]
		
		if scenario.is_removal_luc:	SMDAMAGE_to_Hector[(year, 'luc_emissions')] -= (SMDAMAGE_emissions [(year, 'Agriculture mtC')] + SMDAMAGE_emissions [(year, 'Seaweed mt')] + carbonRemovedByForestry [year])/1000.0 # Convert mtC to GtC.
		else: SMDAMAGE_to_Hector[(year, 'ffi_emissions')] -= (SMDAMAGE_emissions [(year, 'Agriculture mtC')] + SMDAMAGE_emissions [(year, 'Seaweed mt')] + carbonRemovedByForestry [year])/1000.0 # Convert mtC to GtC.
	return SMDAMAGE_to_Hector

# Convert SMDAMAGE output to  Hector input.
def write_SMDAMAGE_solution_to_Hector_input (scenario, SMDAMAGE_to_Hector_dict):
	years = set()
	years = sorted(list(years.union([key[0] for key in SMDAMAGE_to_Hector_dict.keys()])))
	pollutantSet = set()
	pollutantSet = pollutantSet.union([key[1] for key in SMDAMAGE_to_Hector_dict.keys()])
	
	# Write the SMDAMAGE solution dictionary to Hector input csv.
	with open (f"../hector-2.0.1-Windows/input/emissions/" + experimentTag_to_file_name(scenario) + ".csv", 'w') as outputfile:
		header = "Year," + ','.join(pollutantSet)
		outputfile.write(header + "\n")
		for year in years:
			line = str(year) + "," 
			for pollutant in pollutantSet: line = line + str(SMDAMAGE_to_Hector_dict[(year, pollutant)]) + ","
			outputfile.write(line + "\n")
	# print("Converted SMDAMAGE output to Hector input.")

def run_Hector_with_SMDAMAGE_solution(scenario): # Goal is to get the Hector temperature trajectory.
	write_SMDAMAGE_solution_to_Hector_input(scenario, convert_SMDAMAGE_solution_to_Hector_input(scenario)) # 2. Convert SMDAMAGE output to Hector input.
	original_directory = os.getcwd()
	# hector_directory = "C:/Users/johnr/Documents/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	hector_directory = "D:/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	os.chdir(hector_directory)

	# Create Hector ini file.
	hector_ini_file_name = experimentTag_to_file_name(scenario) + ".ini"
	with open ('./input/hector_rcp26 - Copy.ini') as input_ini_file, open ('./input/' + hector_ini_file_name, 'w') as output_ini_file:
		lines = input_ini_file.readlines()
		lines[3] = lines[3].replace('rcp26', experimentTag_to_file_name(scenario))  # Replace text in the header. Hector uses this to name its output file.
		for line in lines:
			output_ini_file.write(line.replace('RCP26_emissions', experimentTag_to_file_name(scenario)))

	# Create batch file to run Hector.
	with open ('run_hector.bat', 'w') as output_batch_file:
		output_batch_file.write("hector input/" + hector_ini_file_name + " > hectorspew.txt")
	
	# print("Calling Hector now...")
	subprocess.call(hector_directory + 'run_hector.bat', shell=True)
	os.chdir(original_directory)

	Hector_temps = get_Hector_temperature(scenario)
	append_output_to_csv(scenario, "Hector with calibrated" if scenario.use_updated_Wpt else "Hector with uncalibrated", {t: Hector_temps[t] for t in getModelPeriods() if t <= 2300.0})
	print("Hector done. Output is in "+ hector_directory + "/output/output_" + experimentTag_to_file_name(scenario) + ".csv. Temp in 2125 is " + str(round(Hector_temps[2125],3)) + ".")
	return 
	
def get_SMDAMAGE_temps_actual_and_taxed(scenario):
	SMDAMAGE_temperature = {}
	with open (SMDAMAGE_output_file_name(scenario)) as SMDAMAGE_output_file:
		lines = [line.split(',') for line in SMDAMAGE_output_file]
		for line in lines[2:]:
			year = int(float(line[0]))
			SMDAMAGE_temperature[year] = float(line[-2])
	
	taxed_temps = old_taxed_temps(scenario, "SMDAMAGE " + experimentTag_to_file_name(scenario))
	return taxed_temps, SMDAMAGE_temperature

def get_Hector_temperature(scenario):
	hector_output_file_name = "../hector-2.0.1-Windows/output/outputstream_" + experimentTag_to_file_name(scenario) + ".csv"
	with open (hector_output_file_name) as hector_output_file: lines = [line.split(',') for line in hector_output_file]

	temperature = {}
	for line in lines[2:]:
		if line[2] == '1' or int(line[0]) < getStartYear(): continue # Skip Hector spinup periods.
		else:
			if line[4] == 'Tgav' and line[6].strip() == 'degC': temperature[float(line[0])] = 1000.0*float(line[5])
	return temperature

# Examining output from SMDAMAGE and Hector.
def plot_temps_SMDAMAGE_and_Hector (scenario, taxedTemperatureChange, actualTemperatureChange, Hector_temperature):
	mplot.clf()  # Clear the current figure
	if taxedTemperatureChange == {}:
		common_years = sorted(set(actualTemperatureChange.keys()).intersection(set(Hector_temperature.keys())))
		mplot.title("Compare temperature: Actual vs Hector")
	else:
		common_years = sorted(set(taxedTemperatureChange.keys()).intersection(set(actualTemperatureChange.keys())).intersection(set(Hector_temperature.keys())))
		mplot.plot(common_years, [taxedTemperatureChange[year] for year in common_years], label="Taxed temperature change")
		mplot.title("Compare temperature: Taxed vs Actual vs Hector")
	
	mplot.plot(common_years, [actualTemperatureChange[year] for year in common_years], label="SMDAMAGE temperature change")
	mplot.plot(common_years, [Hector_temperature[year] for year in common_years], label="Hector temperature")
	mplot.xlabel("Year")
	mplot.ylabel("Temperature °C")
	
	mplot.legend()
	mplot.savefig(getOutputDirectory() + "Temps_SMDAMAGE_and_Hector_" + experimentTag_to_file_name(scenario) + ".jpg")
	# mplot.savefig(getOutputDirectory() + "Compare temps " + experimentTag_to_file_name(scenario) + ".svg")
	# mplot.show()

# ========================================================================================
# Part V. If the SMDAMAGE activity schedule did not match the temperature trajectory in Hector, we can adjust the Wpt values in SMDAMAGE.
# John F Raffensperger. 2022-07-27, 2022-09-10, 2025-01-05.
# ======================================================================================== 
# Examining Wpt from Hector (Pulse) and SMDAMAGE_Fit_W.
def plot_W_Hector_and_fitted(scenario, activityname, Hector_W, fitted_W):
	mplot.clf()  # Clear the current figure
	mplot.plot(range(getPulseDataLength()), Hector_W, label='Hector W for ' + activityname)
	mplot.plot(range(getPulseDataLength()), fitted_W, label='Fitted W for ' + activityname)
	mplot.xlabel('Years')
	mplot.ylabel('Wpt value')
	mplot.title('Comparison of Hector and fitted W for ' + activityname)
	mplot.legend()
	mplot.savefig(getOutputDirectory() + activityname + " " + experimentTag_to_file_name(scenario) + "_plot_W_Hector_and_fitted.jpg")
	# mplot.savefig(getOutputDirectory() + "Wpt_comparison_Carbon.svg")
	# mplot.show()

# Examining SMDAMAGE_Fit_W temperature and Hector temperature.
def plot_temps_Hector_and_fitted(scenario, Hector_temp, fit_temp, years):
	mplot.clf()  # Clear the current figure
	mplot.plot(years, Hector_temp, label='Hector temperature')
	mplot.plot(years, fit_temp, label='Implied SMDAMAGE temperature')
	mplot.xlabel('Years')
	mplot.ylabel('Temperature')
	mplot.title('Comparison of Hector and implied SMDAMAGE temperature')
	mplot.legend()
	mplot.savefig(getOutputDirectory() + experimentTag_to_file_name(scenario) + "_plot_temps_Hector_and_fitted.jpg")
	# mplot.savefig(getOutputDirectory() + "Temp_comparison_fittedW.svg")
	# mplot.show()

def append_output_to_csv(scenario, calling_function_name, temperature_data):
	output_file = getOutputDirectory() + "temperature_output.csv" # doesn't have to be temperature data!
	years = sorted(temperature_data.keys())
	# assert(min(years) == getStartYear()) # so they have the same columns.
	with open(output_file, 'a', newline='', encoding='utf-8') as csv_file:
		writer = csv.writer(csv_file)
		if os.stat(output_file).st_size == 0: writer.writerow(['ExperimentTag', 'FunctionName'] + years)
		writer.writerow([getExperimentTag(scenario), calling_function_name] + [temperature_data[year] for year in years])

def write_fitted_Wpt_to_csv(): # Write the fitted Wpt values to a CSV file in rows of pollutant and columns of years. Useful for analysis in Excel.
	with open(getOutputDirectory() + "SMDAMAGE_fitted_Wpt.pkl", "rb") as mypickle: Wpt_dict = pickle.load(mypickle)
	pollutants = sorted(set(pollutant for pollutant, year in Wpt_dict.keys()))
	years = sorted(set(year for pollutant, year in Wpt_dict.keys()))
	with open(getOutputDirectory() + "SMDAMAGE_fitted_Wpt.csv", 'w', newline='', encoding='utf-8') as csv_file:
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
	
	Emitters = ['Carbon', 'C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O','SF6']
	Removers = ['Agriculture', 'Seaweed', 'Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	Pulse = getPulse() # Reads the Pulse input file. Includes 'luc'.

	# Load default Wpt_dict. ------------------------------------------------------------------------------------------
	# Wpt0 = a unit emission of pollutant or planting p induces degrees Celsius/kg marginal warming Wpt0[p, t0], t0 years after emission or tree planting.
	Wpt_dict = {(p, float(t0)): 0.0 for p in Emitters + Removers for t0 in range(getPulseDataLength())} # Time subscripts are floats because periods could be more often than years, e.g., 2025.0, 2025.5, ...
	scaleCelsius = 1000.0 # Thousandths of a degree.

	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t0 in range(getPulseDataLength()): Wpt_dict[(p, float(t0))] = Pulse[p][1 + t0]*scaleCelsius/Pulse[p][0]

	for t0 in range(getPulseDataLength()): # Divide by Pulse[p][0] for Hector greenhouse gasses to normalize the pulse size.
		# Always calculate error from the original Wpt, not to previously fitted Wpt.
		# Carbon. Degrees C in warmingperiod per million tons emitted in emissionperiod. Carbon pulse units are degrees C/gigaton (ffi: GtC/yr), hence divide Carbon pulse by 1000 to convert GtC to MtC.
		Wpt_dict [('Carbon', float(t0))] = Pulse['ffi'][1 + t0]*scaleCelsius/Pulse['ffi'][0]/1000.0
		Wpt_dict [('luc', float(t0))] = Pulse['luc'][1 + t0]*scaleCelsius/Pulse['luc'][0]/1000.0
		
		# Agriculture. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because carbon pulse units are degrees C/gigaton.
		if scenario.is_removal_luc: Wpt_dict [('Agriculture', float(t0))] = - Pulse['luc'][1 + t0]*scaleCelsius/Pulse['luc'][0]/1000.0
		else: Wpt_dict [('Agriculture', float(t0))] = - Wpt_dict [('Carbon', float(t0))]
		
		# Seaweed has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector. Degrees C in warmingperiod per million tons emitted in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
		Wpt_dict [('Seaweed', float(t0))] = Wpt_dict [('Agriculture', float(t0))]

	Treetypes = getTreeTypes() #['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']
	Treetype_carbon_removal = get_Treetype_carbon_removal(Treetypes)
	# A hectare of tree planting convolves into future carbon removal, which convolves into future cooling.
	# Forestry, cooling effects. Convolution of tree growth with carbon pulse. Degrees C in warmingperiod per million tons sequestered in emissionperiod. Divide by 1000 because Carbon pulse units are degrees C/gigaton.
	for tree in Treetypes: # Tree is planted in year 0. Tree sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		for treegrowthyear in range(0, 156): # Length of tree contract.
			for coolingyear in range(treegrowthyear, getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
				# Forestry has same cooling effects as Agriculture, following either "luc" or "ffi" in Hector, convolved with tree growth. 
				Wpt_dict[(tree, float(coolingyear))] += Treetype_carbon_removal[tree][treegrowthyear]*Wpt_dict[('Agriculture', float(coolingyear - treegrowthyear))]*scaleCelsius/1000.0

	# Load Vpt_dict. ------------------------------------------------------------------------------------------
	# Data is the previous vpt solution from SMDAMAGE and the Hector temperature.
	my_old_vpt = open_pkl("SMDAMAGE " + experimentTag_to_file_name(scenario)) # amount of activity p in year t from solution of model P1 or P2.
	Vpt = {(p,t): my_old_vpt[p,t].varValue for (p,t) in my_old_vpt}
	
	# Construct PT_set. ------------------------------------------------------------------------------------------
	Constant_PT_set = set() # Use constant W for activities you're not trying to fit.
	for p in ['C2F6', 'CF4', 'CH4', 'HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6']:
		for t in getBidPeriods(): Constant_PT_set.add((p,t))
	# if scenario.is_removal_luc:
	# 	for t in getBidPeriods(): Constant_PT_set.add(('Carbon',t))
	# else: luc is not part of the model.

	Variable_PT_set = set() # But note that "luc" is not an activity in SMDAMAGE.
	# if scenario.is_removal_luc: Variable_w_activities = ['luc'] + ['Agriculture', 'Seaweed'] + getTreeTypes()
	if scenario.is_removal_luc: Variable_w_activities = ['Carbon'] + ['luc'] + ['Agriculture', 'Seaweed'] + getTreeTypes()
	else: Variable_w_activities = ['Carbon'] + ['Agriculture', 'Seaweed'] + getTreeTypes()

	for p in Variable_w_activities:
		for t in getBidPeriods(): Variable_PT_set.add((p,t))
		
	# Decision variables ------------------------------------------------------------------------------------------
	wpt = {}

	for t in range(getPulseDataLength()): 
		wpt[('Carbon',float(t))] = LpVariable("wpt(Carbon," + str(t) + ")", 0.0, None) # >= 0
		if scenario.is_removal_luc: wpt[('luc',float(t))] = LpVariable("wpt(luc," + str(t) + ")", 0.0, None) # >= 0 # Watch the bounds! Emitter w >= 0, remover w <= 0.
		# else: wpt[('Carbon',float(t))] = LpVariable("wpt(Carbon," + str(t) + ")", 0.0, None) # >= 0
	
		wpt[('Seaweed',float(t))] = LpVariable("wpt(Seaweed," + str(t) + ")", None, 0.0) # <= 0
		wpt[('Agriculture',float(t))] = LpVariable("wpt(Agriculture," + str(t) + ")", None, 0.0) # <= 0
		for tree in Treetypes: wpt[(tree,float(t))] = LpVariable("wpt(" + tree + "," + str(t) + ")", None, 0.0) # <= 0
		
	over_error_t = {t: LpVariable("over_error_t(" + str(t) + ")", 0.0, None) for t in getModelPeriods()} # error below HectorTempt in year t.
	under_error_t = {t: LpVariable("under_error_t(" + str(t) + ")", 0.0, None) for t in getModelPeriods()} # error above HectorTempt in year t.
	SMDAMAGE_temp_t = {t: LpVariable("SMDAMAGE_temp_t(" + str(t) + ")", None, None) for t in getModelPeriods()} # Implied SMDAMAGE temperature.
	
	W_over_error_t = {t: LpVariable("over_error_t(" + str(t) + ")", 0.0, None) for t in range(getPulseDataLength())} # error below HectorTempt in year t.
	W_under_error_t = {t: LpVariable("under_error_t(" + str(t) + ")", 0.0, None) for t in range(getPulseDataLength())} # error above HectorTempt in year t.
	initial_Temp = LpVariable("initial_Temp", None, None)
	# initial_ghg_p = {p: LpVariable("initial_ghg_p(" + str(p) + ")", 0.0, None) for p in Emitters}
	
	# Objective: minimize total error --------------------
	SMDAMAGE_fit_W = LpProblem("SMDAMAGE_fit_W", LpMinimize) # Temperature error is in 1000s, W error is in 0.001s, so we need to scale W error.
	SMDAMAGE_fit_W += lpSum(over_error_t[t] + under_error_t[t] for t in getModelPeriods()), "Total error"
	# SMDAMAGE_fit_W += lpSum(over_error_t[t] + under_error_t[t] for t in getModelPeriods()) + 100000.0*lpSum(W_over_error_t[t] + W_under_error_t[t] for t in range(getPulseDataLength())), "Total error"
	
	# Constraints: temperature error. --------------------
	HectorTemp = get_Hector_temperature(scenario) # the temperature in year t from Hector simulating solution Vp,t.
	
	# Constraints: warming  --------------------
	for t in getModelPeriods():
		if t <= 2300.0: # HectorTemp goes only to 2300.
			# Different experiments. 

			# Warming constraints. Ag, seaweed, and trees use the "luc" warming factors, but "luc" itself is not activity. No Vpt['luc',u] exists.
			SMDAMAGE_fit_W +=  initial_Temp \
				+ lpSum ([wpt[(p, float(t - u))]*Vpt[p,u] for (p,u) in Variable_PT_set if u <= t and p != "luc"])\
				+ sum([Wpt_dict[(p, float(t - u))]*Vpt[p,u] for (p,u) in Constant_PT_set if u <= t])\
				== SMDAMAGE_temp_t[t], "SMDAMAGE_Temp(" + str(t) + ")"
			
			SMDAMAGE_fit_W += SMDAMAGE_temp_t[t] - over_error_t[t] + under_error_t[t] == HectorTemp[t], "Temp_t(" + str(t) + ")"
			
	# Constraints: calculate W error.  --------------------
	# for u in range(getPulseDataLength()): # Both ffi and luc pulses peak before 20 years after emission.
	# 	if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('luc', float(u))] - W_over_error_t[u] + W_under_error_t[u] == Wpt_dict[('luc', float(u))], "W_fit(" + str(u) + ")"
	# 	else: SMDAMAGE_fit_W += wpt[('Carbon', float(u))] - W_over_error_t[u] + W_under_error_t[u] == Wpt_dict[('Carbon', float(u))], "W_fit(" + str(u) + ")"

	# Constraints: consistency between activity types.  --------------------
	for u in range(getPulseDataLength()): 
		if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('Agriculture', float(u))] == - wpt[('luc', float(u))], "W_agriculture(" + str(u) + ")"
		else:               SMDAMAGE_fit_W += wpt[('Agriculture', float(u))] == - wpt[('Carbon', float(u))], "W_agriculture(" + str(u) + ")"
		SMDAMAGE_fit_W += wpt[('Seaweed', float(u))] == wpt[('Agriculture', float(u))], "W_seaweed(" + str(u) + ")"
	
	# Constraints: convolution for trees.  
	for tree in Treetypes: # If tree is planted in year 0, it sequesters TonsSequesteredPerPeriod tonnes/hectare in each sequesterperiod from 0 to 155.
		# Example: wpt[5] = growth[0]*wpt[5] + growth[1]*wpt[4] + growth[2]*wpt[3] + growth[3]*wpt[2] + growth[4]*wpt[1] + growth[5]*wpt[0]
		for coolingyear in range(0, getPulseDataLength()): # Growth in the last year of the contract has future cooling effects.
			SMDAMAGE_fit_W += wpt[(tree, float(coolingyear))] \
				== lpSum(Treetype_carbon_removal[tree][treegrowthyear] * wpt[('Agriculture', float(coolingyear - treegrowthyear))] * scaleCelsius / 1000.0 \
					for treegrowthyear in range(0, min(156, coolingyear + 1))), "W_tree(" + tree + "," + str(coolingyear) + ")" # 156 year contract.

	# Constraints: physics pulse consistency.  --------------------
	# SMDAMAGE_fit_W += wpt[('Carbon', 0.0)] == 0.0, "W_consistency(0.0)"
	# for u in range(1, 15): # Both ffi and luc pulses peak before 20 years after emission.
	# 	SMDAMAGE_fit_W += wpt[('Carbon', float(u))] <= wpt[('Carbon', float(u + 1))], "W_consistency(" + str(u) + ")"
	for u in range(20, getPulseDataLength() - 1): # Both ffi and luc pulses peak before 20 years after emission.
		if scenario.is_removal_luc: SMDAMAGE_fit_W += wpt[('luc', float(u))] >= wpt[('luc', float(u + 1))], "W_luc_consistency(" + str(u) + ")"
		# else: SMDAMAGE_fit_W += wpt[('Carbon', float(u))] >= wpt[('Carbon', float(u + 1))], "W_consistency(" + str(u) + ")"
		SMDAMAGE_fit_W += wpt[('Carbon', float(u))] >= wpt[('Carbon', float(u + 1))], "W_carbon_consistency(" + str(u) + ")"
	
	# Write a debug model. Easy to open with Notepad or LP_SolveIDE.
	# SMDAMAGE_fit_W.writeLP(getOutputDirectory() + "Calibrate W " + getExperimentTag() + ".lpt")
	
	solve_status = LpStatus[SMDAMAGE_fit_W.solve(PULP_CBC_CMD(msg=0))]
	print (f"SMDAMAGE_Fit_W done. Solve status: {solve_status}, total error = {value(SMDAMAGE_fit_W.objective)}. Initial temperature = {value(initial_Temp.varValue)}")
	
	plot_W_Hector_and_fitted(scenario, "Carbon", [Wpt_dict[('Carbon', float(t))] for t in range(getPulseDataLength())], [wpt[('Carbon', float(t))].varValue for t in range(getPulseDataLength())])
	if scenario.is_removal_luc: plot_W_Hector_and_fitted(scenario, "luc", [Wpt_dict[('luc', float(t))] for t in range(getPulseDataLength())], [wpt[('luc', float(t))].varValue for t in range(getPulseDataLength())])
	# else: plot_W_Hector_and_fitted(scenario, "Carbon", [Wpt_dict[('Carbon', float(t))] for t in range(getPulseDataLength())], [wpt[('Carbon', float(t))].varValue for t in range(getPulseDataLength())], getPulseDataLength())
	plot_temps_Hector_and_fitted(scenario, [HectorTemp[t] for t in getModelPeriods() if t <= 2300], [SMDAMAGE_temp_t[t].varValue for t in getModelPeriods() if t <= 2300], [t for t in getModelPeriods() if t <= 2300])

	for p in Variable_w_activities:
		for t in range(getPulseDataLength()): Wpt_dict[(p,float(t))] = wpt[(p, float(t))].varValue 
	# yourdictionary_to_CSV(Wpt_dict, "Wpt_dict " + experimentTag_to_file_name(scenario))
	with open(getOutputDirectory() + "SMDAMAGE_fitted_Wpt.pkl", "wb") as mypickle: pickle.dump(Wpt_dict, mypickle)
	return initial_Temp.varValue
# End run_SMDAMAGE_fit_W().
# ========================================================================================
# Part VI. Main. Run SMDAMAGE, convert SMDAMAGE output to Hector input, run Hector, and compare temperatures.
# ========================================================================================
# Preliminary: get pulses from Hector.
# get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.

# VI.A. Figure 1. SMDAMAGE uncalibrated. Uses the same tau for every year.
# figure1 = Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = 2.5, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
# run_SMDAMAGE(figure1)
# run_Hector_with_SMDAMAGE_solution(figure1) # 3. Run Hector on SMDAMAGE output.
# plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), get_Hector_temperature(figure1)) 
# calibrated_initial_temperature = run_SMDAMAGE_fit_W(figure1) # Should return 971.24975.

# # VI.B. Figure 1. SMDAMAGE calibrated. discount_rate 0.03, initial_temperature 971.24975, tau 2.5, is_revenue_neutral True, is_removal_luc False, use_updated_Wpt False.
# figure1.initial_temperature = calibrated_initial_temperature
# figure1.use_updated_Wpt = True
# run_SMDAMAGE(figure1) #  Uses the same tau for every year.
# run_Hector_with_SMDAMAGE_solution(figure1) # What does the Hector trajectory look like with the calibrated SMDAMAGE solution?
# plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), get_Hector_temperature(figure1)) 

# # # VI.C. Figure 2, robustness to discount rate: initial_temperature initial_temperature = 971.24975, is_revenue_neutral False, tau is irrelevant, is_removal_luc to False, use_updated_Wpt = True.
# calibrated_initial_temperature = 971.24975
# run_SMDAMAGE(Scenario(comment = "Fig2", discount_rate = 0.0, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
# run_SMDAMAGE(Scenario(comment = "Fig2", discount_rate = 0.015, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
# Estimate 1 comes from the solution with discount_rate = 0.03.
# run_SMDAMAGE(Scenario(comment = "Fig2", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))
# run_SMDAMAGE(Scenario(comment = "Fig2", discount_rate = 0.06, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = False, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))

# # VI.D. Figures 3-5, revenue neutrality: discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau ranges from 1.0 to 2.5, is_removal_luc False, use_updated_Wpt True.
# calibrated_initial_temperature = 971.24975
# # Sequentially run SMDAMAGE with tau = 1, 1.5, 2.0, 2.5.
# run_SMDAMAGE(Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.0, is_removal_luc = False, use_updated_Wpt = True))
# run_SMDAMAGE(Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.5, is_removal_luc = False, use_updated_Wpt = True))
# run_SMDAMAGE(Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.0, is_removal_luc = False, use_updated_Wpt = True))
# run_SMDAMAGE(Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.5, is_removal_luc = False, use_updated_Wpt = True))

# VI.E. # Estimate 2. Concluding paragraph after Figures 3-5.
# run_SMDAMAGE(Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.6, is_removal_luc = False, use_updated_Wpt = True))

# VII. Strength of contracts. (Figure 6 comes from the Pulse input data.)
# The base scenario is discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau is 1.55, is_removal_luc to False, use_updated_Wpt = True, but with an earlier Wpt, so use False here.

# VII.A. Uncalibrated SMDAMAGE.
# For the case of strong contracts, use discount_rate to 0.03, initial_temperature 971.24975, is_revenue_neutral True, tau is 2.4 (you can vary tau in repeat runs of SMDAMAGE to confirm), is_removal_luc to True, use_updated_Wpt = False.
contracts_scenario = Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = 971.24975, is_revenue_neutral = True, tau = 2.1, is_removal_luc = True, use_updated_Wpt = False)
SMDAMAGE_final_temp = run_SMDAMAGE(contracts_scenario)
run_Hector_with_SMDAMAGE_solution(contracts_scenario)
# # plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), get_Hector_temperature(contracts_scenario))

# # # VII.B. Calibrate W.
calibrated_initial_temperature = run_SMDAMAGE_fit_W(contracts_scenario)

# # # VII.C. Calibrated SMDAMAGE.
contracts_scenario.use_updated_Wpt = True
contracts_scenario.initial_temperature = calibrated_initial_temperature # 1255.5764
SMDAMAGE_final_temp = run_SMDAMAGE(contracts_scenario)

# run_Hector_with_SMDAMAGE_solution(contracts_scenario)
# plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), get_Hector_temperature(contracts_scenario))

# VIII. Short auctions, 2 years at a time.
# VIII.A. Calibrate with a long-term model.
# Short_auctions_scenario = Scenario(comment = "Short auctions", discount_rate = 0.03, initial_temperature = 971.24975, tau = 1.5, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False)
# run_SMDAMAGE(Short_auctions_scenario) # A long auction for calibrating the short auctions.
# run_Hector_with_SMDAMAGE_solution(Short_auctions_scenario) # 3. Run Hector on SMDAMAGE output.

# calibrated_initial_temperature = run_SMDAMAGE_fit_W(Short_auctions_scenario) # Should return 895.95254.

# VIII.B. Run the short auctions.
# Short_auctions_scenario.initial_temperature = 895.95254 # calibrated_initial_temperature
# Short_auctions_scenario.use_updated_Wpt = True # Use this updated_Wpt for the short auctions.
# run_SMDAMAGE_short_auctions(Short_auctions_scenario) # Results in excess cooling. Hence the search for tau by year.

# Search for tau. Starts with tau = 1.7 for every constrained year, then uses subgradient optimization to choose a tau for each year.
# tau_search = Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = 971.24975, tau = 1.7, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True)
# run_SMDAMAGE_for_tau (tau_search) # Repeated solution of SMDAMAGE with subgradient optimization on tau.

# write_fitted_Wpt_to_csv() # if you want to analyze the Wpt values in Excel.
import winsound
winsound.Beep(700, 500)  # Frequency: 1000 Hz, Duration: 500 ms