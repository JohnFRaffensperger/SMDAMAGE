import time # for timing the run.
import csv # for CSV file operations
import os # for file system operations
import pickle # for pickle file operations
import hector_interface # Hector pulse generation functions.

def dateTimeString(): return time.strftime("%Y%m%d%H%M", time.localtime())

# Part 0. Key parameters. These parameters go to file names and headers. If you change something here, a function may be expecting the wrong filename.
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

def getFirstConstrainedYear(): 		return 2125.0
def getNumber_of_bid_years(): 		return 250 # Run this long to avoid end-of-horizon effects. assert (BeginConstraintYear <= StartYear + getNumber_of_bid_years())
def getOutputDirectory(): 			return "./SMDAMAGE revenue neutral/Output/" # Must exist
def getStartYear(): 				return 2025.0 # First year of the auction schedule.
def getPulseDataLength(): 			return 296 # Pulse data from Hector goes only 296 years. So raising this would understate later warming.
def inflate_2020_to_2025(): 		return 1.23 # Inflate prices from 2020 to 2025. From https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexhistorical_us_table.htm, I will multiply bids by $316/$257 = 1.23.
def getTreeTypes():					return ['Loblolly_pine_150', 'Ponderosa_pine_150', 'Black_walnut_150', 'Loblolly_pine_10', 'Ponderosa_pine_10', 'Black_walnut_10', 'Loblolly_pine_24', 'Ponderosa_pine_103', 'Black_walnut_55']

def getModelPeriods(): return [float(getStartYear()) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*getPulseDataLength())]
def getBidPeriods(): return [float(getStartYear()) + float(t)/float(hector_interface.getPeriodsPerYear()) for t in range(hector_interface.getPeriodsPerYear()*getNumber_of_bid_years())] 
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

# Forestry, carbon removed for each possible contract.
# The year of planting is the "u_emissionperiod". Pulse units are degrees/megatonnes or degrees/kilotonnes, so we have to convolve growth over time.
def get_Treetype_carbon_removal (Treetypes):
	Treetype_carbon_removal = {tree: {t: 0.0 for t in range(156)} for tree in Treetypes} # where 156 is the longest tree contract.
	with open ('./data/Forestry_Sequestration.csv') as forestryfile: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
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