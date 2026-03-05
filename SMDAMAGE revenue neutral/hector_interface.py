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