# Plotting utilities for SMDAMAGE. John F. Raffensperger. 2025-03-04.

import matplotlib.pyplot as mplot
import matplotlib.ticker as mticker
import sqlite3
import database_interface
import defaults_and_utilities

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

# Figure 1 in the paper. TODO: need to pass the scenarios better.
def Uncalibrated_and_calibrated_temperature_trajectories(db_path, output_directory, scenario_id_uncalibrated=35, scenario_id_calibrated=36, scenario_id_hector=36):
	"""Plot uncalibrated and calibrated SMDAMAGE trajectories with calibrated Hector trajectory."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	smdamage_uncalibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_uncalibrated, "SMDAMAGE actual temp uncalibrated")
	smdamage_calibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_calibrated, "SMDAMAGE actual temp calibrated")
	hector_calibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_hector, "Hector with calibrated")

	uncalibrated_years = sorted(smdamage_uncalibrated.keys())
	calibrated_years = sorted(smdamage_calibrated.keys())
	hector_years = sorted(hector_calibrated.keys())

	mplot.plot(uncalibrated_years, [smdamage_uncalibrated[year]/1000.0 for year in uncalibrated_years], linestyle='--', color='black', label='SMDAMAGE actual temp uncalibrated')
	mplot.plot(calibrated_years, [smdamage_calibrated[year]/1000.0 for year in calibrated_years], linestyle='-', color='black', label='SMDAMAGE actual temp calibrated')
	mplot.plot(hector_years, [hector_calibrated[year]/1000.0 for year in hector_years], linestyle='-', color='gray', label='Hector with calibrated')

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	ax.set_ylabel("°C above base zero", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)

	ax.yaxis.set_label_coords(0.15, 0.6)
	ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5)) # Grid lines every 0.5 °C.

	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Temperature_trajectories_for_uncalibrated_and_calibrated_trajectories.svg", bbox_inches='tight', pad_inches=0)

def Temperature_trajectories_with_4_discount_rates(db_path, output_directory, scenario_id_1=37, scenario_id_2=38, scenario_id_3=39, scenario_id_4=40):
	"""Plot calibrated SMDAMAGE temperature trajectories for four discount-rate scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	source = "SMDAMAGE actual temp calibrated"
	series37 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_1, source)
	series38 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_2, source)
	series39 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_3, source)
	series40 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_4, source)
	rate37 = database_interface.get_scenario_discount_rate(db_path, scenario_id_1)
	rate38 = database_interface.get_scenario_discount_rate(db_path, scenario_id_2)
	rate39 = database_interface.get_scenario_discount_rate(db_path, scenario_id_3)
	rate40 = database_interface.get_scenario_discount_rate(db_path, scenario_id_4)

	years37 = sorted(series37.keys())
	years38 = sorted(series38.keys())
	years39 = sorted(series39.keys())
	years40 = sorted(series40.keys())

	plot_data = [(rate37, years37, [series37[year]/1000.0 for year in years37]), (rate38, years38, [series38[year]/1000.0 for year in years38]), (rate39, years39, [series39[year]/1000.0 for year in years39]), (rate40, years40, [series40[year]/1000.0 for year in years40]),]

	for rate, years, values in sorted(plot_data, key=lambda x: x[0]):
		if abs(rate - 0.06) < 1e-12: mplot.plot(years, values, color='black', linestyle=(0, (8, 4)), linewidth=1.6, label='6%')
		elif abs(rate - 0.03) < 1e-12: mplot.plot(years, values, color='black', linestyle=(0, (3, 2)), linewidth=1.3, label='3%')
		elif abs(rate - 0.015) < 1e-12: mplot.plot(years, values, color='black', linestyle=':', linewidth=1.3, label='1.5%')
		elif abs(rate - 0.0) < 1e-12: mplot.plot(years, values, color='black', linestyle='-', linewidth=1.3, label='0%')
		else: mplot.plot(years, values, color='black', linestyle='-', linewidth=1.3, label=str(100.0*rate) + '%')

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	ax.set_ylabel("°C over base zero", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)

	ax.yaxis.set_label_coords(0.15, 0.5)
	ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5)) # Grid lines every 0.5 °C.

	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Temperature_trajectories_with_4_discount_rates.svg", bbox_inches='tight', pad_inches=0)

def Carbon_emissions_with_4_surcharge_rates(db_path, output_directory, scenario_id_1=41, scenario_id_2=42, scenario_id_3=43, scenario_id_4=44):
	"""Plot calibrated carbon emissions trajectories for four surcharge-rate scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	source = "SMDAMAGE Carbon calibrated"
	series1 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_1, source)
	series2 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_2, source)
	series3 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_3, source)
	series4 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_4, source)
	tau1 = database_interface.get_scenario_tau(db_path, scenario_id_1)
	tau2 = database_interface.get_scenario_tau(db_path, scenario_id_2)
	tau3 = database_interface.get_scenario_tau(db_path, scenario_id_3)
	tau4 = database_interface.get_scenario_tau(db_path, scenario_id_4)

	years1 = sorted(series1.keys())
	years2 = sorted(series2.keys())
	years3 = sorted(series3.keys())
	years4 = sorted(series4.keys())

	# Convert megatons to gigatons.
	plot_data = [(tau1, years1, [series1[year]/1000.0 for year in years1]), (tau2, years2, [series2[year]/1000.0 for year in years2]), (tau3, years3, [series3[year]/1000.0 for year in years3]), (tau4, years4, [series4[year]/1000.0 for year in years4])]
	line_styles = ['-', '--', ':', '-.']
	for index, (tau, years, values) in enumerate(sorted(plot_data, key=lambda x: x[0])):
		mplot.plot(years, values, color='black', linestyle=line_styles[index % len(line_styles)], linewidth=1.3, label='tau = ' + str(round(tau, 3)))

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	ax.set_ylabel("Carbon (gigatons)", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)

	ax.yaxis.set_label_coords(0.15, 0.6)
	ax.yaxis.set_major_locator(mticker.MultipleLocator(2))

	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Carbon_emissions_with_4_surcharge_rates.svg", bbox_inches='tight', pad_inches=0)

def Discounted_net_revenue_with_4_surcharge_rates(db_path, output_directory, scenario_id_1=41, scenario_id_2=42, scenario_id_3=43, scenario_id_4=44):
	"""Plot calibrated yearly revenue trajectories for four surcharge-rate scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	source = "SMDAMAGE yearly revenue calibrated"
	series1 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_1, source)
	series2 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_2, source)
	series3 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_3, source)
	series4 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_4, source)
	tau1 = database_interface.get_scenario_tau(db_path, scenario_id_1)
	tau2 = database_interface.get_scenario_tau(db_path, scenario_id_2)
	tau3 = database_interface.get_scenario_tau(db_path, scenario_id_3)
	tau4 = database_interface.get_scenario_tau(db_path, scenario_id_4)

	years1 = sorted(series1.keys())
	years2 = sorted(series2.keys())
	years3 = sorted(series3.keys())
	years4 = sorted(series4.keys())

	plot_data = [(tau1, years1, [series1[year]/1000.0 for year in years1]), (tau2, years2, [series2[year]/1000.0 for year in years2]), (tau3, years3, [series3[year]/1000.0 for year in years3]), (tau4, years4, [series4[year]/1000.0 for year in years4])]
	line_styles = ['-', '--', ':', '-.']
	for index, (tau, years, values) in enumerate(sorted(plot_data, key=lambda x: x[0])):
		mplot.plot(years, values, color='black', linestyle=line_styles[index % len(line_styles)], linewidth=1.3, label='tau = ' + str(round(tau, 3)))

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	# ax.set_ylabel("Discounted net revenue, $billions", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.text(0.01, 0.99, "Discounted net revenue, $billions", transform=ax.transAxes, ha='left', va='top', fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)
	ax.yaxis.set_major_formatter(mticker.StrMethodFormatter('${x:,.0f}'))

	ax.yaxis.set_label_coords(0.15, 0.6)
	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Discounted_net_revenue_with_4_surcharge_rates.svg", bbox_inches='tight', pad_inches=0)

def Temperature_trajectories_with_4_surcharge_rates(db_path, output_directory, scenario_id_1=41, scenario_id_2=42, scenario_id_3=43, scenario_id_4=44):
	"""Plot calibrated SMDAMAGE temperature trajectories for four surcharge-rate scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	source = "SMDAMAGE actual temp calibrated"
	series1 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_1, source)
	series2 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_2, source)
	series3 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_3, source)
	series4 = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_4, source)
	tau1 = database_interface.get_scenario_tau(db_path, scenario_id_1)
	tau2 = database_interface.get_scenario_tau(db_path, scenario_id_2)
	tau3 = database_interface.get_scenario_tau(db_path, scenario_id_3)
	tau4 = database_interface.get_scenario_tau(db_path, scenario_id_4)

	years1 = sorted(series1.keys())
	years2 = sorted(series2.keys())
	years3 = sorted(series3.keys())
	years4 = sorted(series4.keys())

	# Convert thousandths of degrees to degrees.
	plot_data = [(tau1, years1, [series1[year]/1000.0 for year in years1]), (tau2, years2, [series2[year]/1000.0 for year in years2]), (tau3, years3, [series3[year]/1000.0 for year in years3]), (tau4, years4, [series4[year]/1000.0 for year in years4])]
	line_styles = ['-', '--', ':', '-.']
	for index, (tau, years, values) in enumerate(sorted(plot_data, key=lambda x: x[0])):
		mplot.plot(years, values, color='black', linestyle=line_styles[index % len(line_styles)], linewidth=1.3, label='tau = ' + str(round(tau, 3)))

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	ax.set_ylabel("°C above base zero", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)

	ax.yaxis.set_label_coords(0.15, 0.55)
	ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5)) # Grid lines every 0.5 °C.

	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Temperature_trajectories_with_4_surcharge_rates.svg", bbox_inches='tight', pad_inches=0)

def Price_trajectory_with_full_commitment_tau_1_6(db_path, output_directory, scenario_id=45):
	"""Plot Carbon Vpt dual-price trajectories for full-commitment surcharge scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	series = database_interface.get_vpt_dual_series_by_scenario_id(db_path, scenario_id, 'Carbon')

	years = sorted(series.keys())

	# Converting $/ton carbon to $/ton carbon dioxide.
	mplot.plot(years, [-series[year] * 44/12 for year in years], color='black', linestyle='-', linewidth=1.3)

	mplot.xlabel('Years', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax = mplot.gca()
	ax.set_ylabel("$/ton CO\u2082", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.tick_params(axis='both', which='major', labelsize=font_size)

	ax.yaxis.set_label_coords(0.15, 0.6)
	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.savefig(output_directory + "Price_trajectory_with_full_commitment_tau_1.6.svg", bbox_inches='tight', pad_inches=0)

def Summary_of_estimates_to_end_global_warming(db_path, output_directory=None):
	"""Summarize the current solution set for the five estimate scenarios.

	The summary matches the table in Work in progress, SMDAMAGE.txt.
	"""
	begin_year = 2025.0
	end_year = 2125.0

	columns = [("Estimate 3", 46, "ST, weak contracts"), ("Estimate 1", 39, "LT"), ("Estimate 4", 50, "ST, short auctions"), ("Estimate 2", 45, "ST"), ("Estimate 5", 51, "ST, time-varying τ"), ]

	def _trim_number(value, decimals=2):
		text = f"{value:.{decimals}f}"
		return text.rstrip('0').rstrip('.')

	def _load_scalar(cursor, sql, params):
		cursor.execute(sql, params)
		row = cursor.fetchone()
		if row is None or row[0] is None: raise ValueError(f"Missing summary data for query: {sql!r} params={params!r}")
		return row[0]

	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	third_party_pays = []
	average_emitter_price = []
	average_remover_price = []
	emissions_2025_2125 = []
	removal_cost_2025_2125 = []

	for _, scenario_id, _ in columns:
		total_revenue = _load_scalar(cursor, "SELECT total_revenue FROM scenarios WHERE id = ?", (scenario_id,))
		third_party_pays.append(total_revenue / 1_000_000.0) # Convert millions to trillions.

		avg_emitter_price = _load_scalar(cursor, "SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Carbon", begin_year, end_year),)
		average_emitter_price.append((avg_emitter_price, avg_emitter_price * 44.0 / 12.0))

		avg_remover_price = _load_scalar(cursor, "SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Agriculture", begin_year, end_year), )
		average_remover_price.append((avg_remover_price, avg_remover_price * 44.0 / 12.0))

		emissions = _load_scalar(cursor, "SELECT SUM(quantity_value) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Carbon", begin_year, end_year), )
		emissions_2025_2125.append(emissions / 1000.0)

		removers = defaults_and_utilities.getRemovers()
		removal_cost = 0.0
		for remover in removers:
			cursor.execute("SELECT COALESCE(SUM(quantity_value * dual_price), 0.0) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, remover, begin_year, end_year),)
			removal_cost += cursor.fetchone()[0] or 0.0
		removal_cost_2025_2125.append(removal_cost / 1_000_000.0)

	conn.close()

	lines = []
	lines.append("\t".join([estimate_label for estimate_label, _, _ in columns]))
	lines.append("\t".join(["Model"] + [model_label for _, _, model_label in columns]))
	lines.append("\t".join(["Third party pays"] + ["$" + _trim_number(value) + " trillion" for value in third_party_pays]))
	lines.append("\t".join(["Average emitter price"] + [f"${_trim_number(price_tC)} /tC (${_trim_number(price_tCO2)} /tCO2)".replace(" ", "") for price_tC, price_tCO2 in average_emitter_price]))
	lines.append("\t".join(["Average remover price"] + [f"${_trim_number(price_tC)} /tC (${_trim_number(price_tCO2)} /tCO2)".replace(" ", "") for price_tC, price_tCO2 in average_remover_price]))
	lines.append("\t".join(["Emissions 2025-2125"] + [f"{_trim_number(value, 1)} GtC" for value in emissions_2025_2125]))
	lines.append("\t".join(["Removal cost 2025-2125"] + ["$" + _trim_number(value) + " trillion" for value in removal_cost_2025_2125]))

	table_text = "\n".join(lines)
	print(table_text)

	output_directory = output_directory or defaults_and_utilities.getOutputDirectory()
	with open(output_directory + "Summary_of_estimates_to_end_global_warming.txt", "w", encoding="utf-8") as output_file:
		output_file.write(table_text + "\n")

	return table_text
