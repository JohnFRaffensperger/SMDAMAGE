# Plotting utilities for SMDAMAGE. John F. Raffensperger. 2025-03-04.

import matplotlib.pyplot as mplot

def plot_temps_SMDAMAGE_and_Hector(scenario, taxedTemperatureChange, actualTemperatureChange, Hector_temperature, getOutputDirectory, experimentTag_to_file_name):
	"""Compare temperature trajectories between SMDAMAGE and Hector models"""
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

def plot_W_Hector_and_fitted(scenario, activityname, Hector_W, fitted_W, getPulseDataLength, getOutputDirectory, experimentTag_to_file_name):
	"""Compare Hector W values with fitted W values for warming potential analysis"""
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

def plot_temps_Hector_and_fitted(scenario, Hector_temp, fit_temp, years, getOutputDirectory, experimentTag_to_file_name):
	"""Compare Hector temperature with implied SMDAMAGE temperature during calibration"""
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