# Part II. Getting pulse information from Hector. John F. Raffensperger, 2019. 
# =============================================================================================
# This code changes the input to Hector, runs Hector, and reads the output,
# with a pulse increase in each chemical, one chemical at a time, and then records the change in temperature.

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

import os
import subprocess
from math import log10, floor
import defaults_and_utilities

def getPeriodsPerYear(): 
	return 1 # Not debugged for larger values. Probably dumb, as it imposes a need for floating indices, e.g., 2025.5. Depends on your climate simulator's ability to handle fractional years, i.e., getPulse().

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

# Run once. Output is Pulses_by_chemical.txt, which contains the marginal temperature changes for each chemical.
# Move Pulses_by_chemical.txt from the Hector directory to your /data/ directory.
# Then you've got it and don't need to run it again.
def get_Pulses_from_Hector(): 
	pulse_year = 2005 # Chosen because it's before the phaseout of some refrigerants.
	pathname = "D:/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	# pathname = "C:/Users/johnr/Documents/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	os.chdir(pathname)

	file_list = {"Hector_ini": "input/hector_rcp26_pulsed.ini", # You should make this in advance. In section [core], replace "run_name=rcp26" with "run_name=rcp26_emissions_pulsed". Replace text "RCP26_emissions.csv" with "RCP26_emissions_pulsed.csv".
				"Base_emissions_input": "input/emissions/RCP26_emissions.csv", # Supplied with Hector or make it yourself. Constant, should not change.
				"Base_temperature_output": "output/outputstream_rcp26.csv", # Supplied with Hector or make it yourself. Constant, should not change.
				"Hector_spew": "hector_spew_all_chemicals.txt", # created here by Hector. Records Hector's command line output.
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
	# chemicals = ['ffi_emissions', 'luc_emissions', 'CH4_emissions', 'N2O_emissions', 'SOx', 'SO2_emissions', 'CO_emissions', 'NMVOC_emissions', 'NOX_emissions', 'BC_emissions', 'OC_emissions', 'NH3',\
	# 	'CF4_emissions', 'C2F6_emissions', 'C6F14', 'HFC23_emissions', 'HFC32_emissions', 'HFC4310_emissions', 'HFC125_emissions', 'HFC134a_emissions', 'HFC143a_emissions', 'HFC227ea_emissions', 'HFC245fa_emissions',\
	# 	'SF6_emissions', 'CFC11_emissions', 'CFC12_emissions', 'CFC113_emissions', 'CFC114_emissions', 'CFC115_emissions', 'CCl4_emissions', 'CH3CCl3_emissions', 'HCF22_emissions', 'HCF141b_emissions',\
	# 	'HCF142b_emissions', 'halon1211_emissions', 'HALON1202', 'halon1301_emissions', 'halon2402_emissions', 'CH3Br_emissions', 'CH3Cl_emissions']

	# List of chemicals in  SMDAMAGE. We need to pulse only the ones in SMDAMAGE.
	chemicals = ['ffi_emissions', 'CH4_emissions', 'N2O_emissions', 'CF4_emissions', 'C2F6_emissions', 'HFC125_emissions', 'HFC134a_emissions', 'HFC143a_emissions', 'SF6_emissions']
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

# ========================================================================================
# Part IV. Running Hector on SMDAMAGE output. Does the SMDAMAGE activity schedule result in the correct temperature trajectory in Hector?
# John F Raffensperger. 2022-07-27, 2022-09-10, 2025-01-05.
# ======================================================================================== 
# Reads the Hector input file RCP_emissions, returns a dictionary RCP_emissions [year, emissionsType] = emissionsValue.
# Called from convert_SMDAMAGE_solution_to_Hector_input().
def getHectorEmissionsDictionary(RCP26_emissions_file): # e.g., "RCP26_emissions.csv"
	with open ("../../hector-2.0.1-Windows/input/emissions/" + RCP26_emissions_file) as Hector_input_file:
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
	with open (defaults_and_utilities.SMDAMAGE_output_file_name(scenario)) as SMDAMAGE_output_file: # Year, Tonnes/hectare/year Loblolly pine, Tonnes/hectare/year Ponderosa pine	Tonnes/hectare/year Black walnut
		lines = [line.split(',') for line in SMDAMAGE_output_file]
	SMDAMAGE_emissions = {}
	numberOfColumnsInSMDAMAGE_solution_csv = 20
	for line in lines[2:]:
		for columnNumber, item in enumerate(line[0:numberOfColumnsInSMDAMAGE_solution_csv+1]): # Columns of primal values in smdamage_solution_YYYY.csv.
			year = line[0]
			if float(year) <= defaults_and_utilities.getLastBidYear():
				emissionsType = lines[1][columnNumber].strip()
				emissionsValue = item
				SMDAMAGE_emissions[(float(year), emissionsType)] = (-1.0 if emissionsType == 'Agriculture mt' else 1.0)*float(emissionsValue)
	return SMDAMAGE_emissions
# print(get_SMDAMAGE_emissions_dictionary("Rev neutral, tau is 1.766, tax only 2125 SMDAMAGE soln 2125.csv"))

# Reads the SMDAMAGE solution for first_constrained_year and writes valid input for Hector, with RCP26_emissions.csv as a base.
def convert_SMDAMAGE_solution_to_Hector_input (scenario):
	RCP26_emissions = getHectorEmissionsDictionary("RCP26_emissions.csv")
	SMDAMAGE_emissions = get_SMDAMAGE_emissions_dictionary (scenario)
	carbonRemovedByForestry = defaults_and_utilities.get_tree_schedule_carbon_removal(defaults_and_utilities.open_pkl("SMDAMAGE " + defaults_and_utilities.experimentTag_to_file_name(scenario))) # getCarbonRemovedByForestry()
	firstYear = 1765 # in RCP26_emissions.csv.
	first_SMDAMAGE_year = int(defaults_and_utilities.getStartYear())
	lastYear = int(defaults_and_utilities.getLastBidYear()) # because for example smdamage_solution_2070.csv includes 2169.5.
	
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
	with open (f"../../hector-2.0.1-Windows/input/emissions/" + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".csv", 'w') as outputfile:
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
	hector_directory = "C:/Users/johnr/Documents/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	# hector_directory = "D:/Work documents/2 Research/Global warming/Numerical Simulation/hector-2.0.1-Windows/"
	os.chdir(hector_directory)

	# Create Hector ini file.
	hector_ini_file_name = defaults_and_utilities.experimentTag_to_file_name(scenario) + ".ini"
	with open ('./input/hector_rcp26 - Copy.ini') as input_ini_file, open ('./input/' + hector_ini_file_name, 'w') as output_ini_file:
		lines = input_ini_file.readlines()
		lines[3] = lines[3].replace('rcp26', defaults_and_utilities.experimentTag_to_file_name(scenario))  # Replace text in the header. Hector uses this to name its output file.
		for line in lines:
			output_ini_file.write(line.replace('RCP26_emissions', defaults_and_utilities.experimentTag_to_file_name(scenario)))

	# Create batch file to run Hector.
	with open ('run_hector.bat', 'w') as output_batch_file:
		output_batch_file.write("hector input/" + hector_ini_file_name + " > hectorspew.txt")
	
	# print("Calling Hector now...")
	subprocess.call(hector_directory + 'run_hector.bat', shell=True)
	os.chdir(original_directory)

	Hector_temps = get_Hector_temperature(scenario)
	defaults_and_utilities.append_temperatures_to_csv(scenario, "Hector with calibrated" if scenario.use_updated_Wpt else "Hector with uncalibrated", {t: Hector_temps[t] for t in defaults_and_utilities.getModelPeriods() if t <= 2300.0})
	print("Hector done. Output is in "+ hector_directory + "/output/output_" + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".csv. Temp in 2125 is " + str(round(Hector_temps[2125],3)) + ".")
	return

def get_Hector_temperature(scenario):
	hector_output_file_name = "../../hector-2.0.1-Windows/output/outputstream_" + defaults_and_utilities.experimentTag_to_file_name(scenario) + ".csv"
	with open (hector_output_file_name) as hector_output_file: lines = [line.split(',') for line in hector_output_file]

	temperature = {}
	for line in lines[2:]:
		if line[2] == '1' or int(line[0]) < defaults_and_utilities.getStartYear(): continue # Skip Hector spinup periods.
		else:
			if line[4] == 'Tgav' and line[6].strip() == 'degC': temperature[float(line[0])] = 1000.0*float(line[5])
	return temperature

def getPulse(): # Retrieves the marginal change in temperature in each year after a pulse emission.
	Pulse = {} # [Pulseqty, warming1, warming2, warming3,...]
	# Get warming effects for 'C2F6', 'CF4', 'CH4', 'Carbon', HFC125', 'HFC134a', 'HFC143a', 'N2O', 'SF6', 'SO2'.
	with open('./data/Calibrated_pulses_by_chemical_2025.txt', 'r') as pulsefile:
		for line in pulsefile: # Each line looks like: ffi_emissions,13.931549999999998,GtC/yr,0.0,...
			chempulse = line.split(",") # Below, we're copying the annual warming for each period in the year.
			# GetPeriodsPerYear() is important because if you have more than one period per year, you need to copy the warming effect for each period in the year. For example, if you have 2 periods per year, you need to interpolate the warming effect for each period.
			# Hector may have the ability to simulate climate in sub-annual periods, e.g., 2025.0, 2025.5, 2026.0, etc. If so, we would use the warming effect for each period in the year, not just once per year.
			Pulse[chempulse[0].replace('_emissions','')] = [float(chempulse[1])] + [float(warming) for warming in chempulse[3:] for i in range(getPeriodsPerYear())]
			# At this point, Pulse['ffi'] = [7.971, -0.0, 0.00227, 0.006247, 0.009098, ... ]. The first element is the impulse size used in Hector to find a temperature change.
			# We have to normalize this, so Wput2_dict [(p, t0)] = Pulse[p1][t0+1]/Pulse[p1][0]
	return Pulse



