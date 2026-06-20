# >>> Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. SMDAMAGE: "SMDAMAGE revenue neutral.py"
# Part IV. Running Hector on SMDAMAGE output. hector_interface.py.
# =============================================================================================

import time # for timing the run.
import csv # for CSV file operations
import os # for file system operations
import pickle # for pickle file operations
import hector_interface # Hector pulse generation functions.
import database_interface # for dynamic bidder and tree data.

# Directories and file names.
def getOutputDirectory(): 			return "./SMDAMAGE revenue neutral/Output/" # Must exist
def SMDAMAGE_output_file_name(scenario): return getOutputDirectory() + "SMDAMAGE_soln_" + experimentTag_to_file_name(scenario) + ".csv"
def Hector_output_file_name(scenario): return getOutputDirectory() + "Hector_output_" + experimentTag_to_file_name(scenario) + ".csv"

# These are the market participants. Emitters face tax tau. Removers do not.
def getEmitters(): return [b['bidder_name'] for b in database_interface.get_bidders() if b['class'].lower() == 'emitter']
def getRemovers(): return [b['bidder_name'] for b in database_interface.get_bidders() if b['class'].lower() == 'remover']
def getChemicals(): return ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6'] # Must be within Emitters.
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

def append_temperatures_to_csv(scenario, calling_function_name, temperature_data):
	output_filename = getOutputDirectory() + "temperature_output.csv"
	with open(output_filename, mode='a', newline='', encoding='utf-8') as csv_file: # Append to CSV file.
		writer = csv.writer(csv_file)
		write_header = not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0
		if write_header: writer.writerow(['Source', 'Experiment'] + [str(t) for t in getModelPeriods()])
		writer.writerow([calling_function_name, getExperimentTag(scenario)] + [temperature_data.get(t, '') for t in getModelPeriods()])

def yourdictionary_to_CSV(yourdictionary, tag = 'your dictionary'): # Save a dictionary to a CSV file.
	with open(getOutputDirectory() + tag + '.csv', 'w', newline='', encoding='utf-8') as csv_file:
		writer = csv.writer(csv_file)
		for key, value in yourdictionary.items(): writer.writerow([key, value])

def open_pkl(your_pkl_filename): # retrieves previously saved solution vpt.
	with open(getOutputDirectory() + your_pkl_filename + ".pkl", "rb") as mypickle:
		return pickle.load(mypickle)

# Forestry, carbon removed in the optimal auction schedule.
def get_tree_schedule_carbon_removal (vpt): # Matches the spreadsheet convolution exactly.
	Treetypes = getTreeTypes()
	mtC_removed = {t: 0.0 for t in getModelPeriods()}

	for tree in Treetypes:
		removal_data = database_interface.get_forestry_carbon_removal(tree)
		tc_dict = {int(year): tc for year, tc in removal_data}

		for u in getBidPeriods():
			if (tree, u) in vpt:
				vpt_val = vpt[tree,u].varValue
				if vpt_val is not None and vpt_val != 0:
					for growth_year, tc in tc_dict.items():
						t = u + float(growth_year)
						if t in mtC_removed:
							mtC_removed[t] += vpt_val * tc
	return mtC_removed
