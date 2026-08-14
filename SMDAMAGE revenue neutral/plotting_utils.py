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

# Figure 2 in the paper. scenario_id_calibrated should be the same as scenario_id_hector.
def Uncalibrated_and_calibrated_temperature_trajectories(db_path, output_directory, scenario_id_uncalibrated, scenario_id_calibrated, scenario_id_hector):
	"""Plot uncalibrated and calibrated SMDAMAGE trajectories with calibrated Hector trajectory."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	smdamage_uncalibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_uncalibrated, "SMDAMAGE actual temp uncalibrated")
	smdamage_calibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_calibrated, "SMDAMAGE actual temp calibrated")
	hector_calibrated = database_interface.get_temperature_series_by_scenario_id(db_path, scenario_id_hector, "Hector with calibrated")
	assert hector_calibrated, f"No 'Hector with calibrated' series for scenario_id {scenario_id_hector}"

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

	ax.yaxis.set_label_coords(0.15, 0.45)
	ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5)) # Grid lines every 0.5 °C.

	ax.xaxis.set_label_coords(0.65, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.grid(True, which='major')
	mplot.legend(frameon=False, fontsize=font_size)
	mplot.savefig(output_directory + "Temperature_trajectories_for_uncalibrated_and_calibrated_trajectories.svg", bbox_inches='tight', pad_inches=0)

def Temperature_trajectories_with_4_discount_rates(db_path, output_directory, scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4):
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
		if abs(rate - 0.06) < 1e-12: mplot.plot(years, values, color='black', linestyle=(0, (6, 3)), linewidth=1.2, label='6%')
		elif abs(rate - 0.03) < 1e-12: mplot.plot(years, values, color='black', linestyle=(0, (3, 2)), linewidth=1.2, label='3%')
		elif abs(rate - 0.015) < 1e-12: mplot.plot(years, values, color='black', linestyle=':', linewidth=1.2, label='1.5%')
		elif abs(rate - 0.0) < 1e-12: mplot.plot(years, values, color='black', linestyle='-', linewidth=1.2, label='0%')
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

def Carbon_emissions_with_4_tau_rates(db_path, output_directory, scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4):
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
	mplot.savefig(output_directory + "Carbon_emissions_with_4_tau_rates.svg", bbox_inches='tight', pad_inches=0)

def Discounted_net_revenue_with_4_tau_rates(db_path, output_directory, scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4):
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
	mplot.savefig(output_directory + "Discounted_net_revenue_with_4_tau_rates.svg", bbox_inches='tight', pad_inches=0)

def Temperature_trajectories_with_4_tau_rates(db_path, output_directory, scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4):
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
	mplot.savefig(output_directory + "Temperature_trajectories_with_4_tau_rates.svg", bbox_inches='tight', pad_inches=0)

def Price_trajectory_with_full_commitment (db_path, output_directory, scenario_id):
	"""Plot Carbon Vpt dual-price trajectories for full-commitment surcharge scenarios."""
	font_size = 7
	mplot.clf()
	figure = mplot.gcf()
	figure.set_size_inches(4.5, 2.8, forward=True) # roughly golden ratio proportion.
	series = database_interface.get_vpt_dual_series_by_scenario_id(db_path, scenario_id, 'Carbon')

	years = sorted(series.keys())

	# Converting $/ton carbon to $/ton carbon dioxide: × 12/44 (1 tCO2 contains 12/44 tC).
	mplot.plot(years, [-series[year] * 12/44 for year in years], color='black', linestyle='-', linewidth=1.3)
	ax = mplot.gca()
	ax.tick_params(axis='both', which='major', labelsize=font_size)
	ax.grid(True, which='major')

	mplot.xlabel('Year', fontsize=font_size)
	mplot.xlim(2025, 2275)
	ax.xaxis.set_label_coords(0.45, 0.05) # Label % of graph, from bottom left.
	ax.xaxis.set_major_locator(mticker.MultipleLocator(25)) # Grid lines every 25 years.

	ax.set_ylabel("$/ton emitted CO\u2082", rotation=0, ha="right", va="center", fontsize=font_size)
	ax.yaxis.set_label_coords(0.2, 0.55)

	mplot.savefig(output_directory + "Price_trajectory_with_full_commitment_tau.svg", bbox_inches='tight', pad_inches=0)

def Summary_of_estimates_to_end_global_warming(db_path, scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4, scenario_id_5, output_directory=None):
	"""Summarize the current solution set for the five estimate scenarios.
	The summary matches the table in Work in progress, SMDAMAGE.txt.
	scenario_id_1..5 correspond to columns: Estimates 3, 1, 4, 2, 5.
	"""
	begin_year = 2025.0
	end_year = 2125.0 # calculate costs only through end_year, not through the full constraint horizon.

	# Order presented in the paper.
	columns = [("Estimate 3, weak contracts", "SMDAMAGE_1"), ("Estimate 1, 3rd party pays", "SMDAMAGE_0"), ("Estimate 4, short auctions", "SMDAMAGE_2"), ("Estimate 2, fixed tau", "SMDAMAGE_1"), ("Estimate 5, dynamic tau", "SMDAMAGE_1"),]
	scenario_ids = [scenario_id_1, scenario_id_2, scenario_id_3, scenario_id_4, scenario_id_5]

	def _trim_number(value, decimals=2):
		text = f"{value:.{decimals}f}"
		return text.rstrip('0').rstrip('.')

	def _load_scalar(cursor, sql, params):
		cursor.execute(sql, params)
		row = cursor.fetchone()
		if row is None or row[0] is None: return None
		return row[0]

	def _fmt(value, prefix="$", suffix="", decimals=2):
		if value is None: return "N/A"
		s = prefix + _trim_number(value, decimals)
		return (s + " " + suffix) if suffix else s

	conn = sqlite3.connect(db_path)
	cursor = conn.cursor()
	missing = [sid for sid in scenario_ids if _load_scalar(cursor, "SELECT id FROM scenarios WHERE id = ?", (sid,)) is None]
	if missing: raise ValueError(f"Scenario IDs not found in {db_path}: {missing}")
	third_party_pays = []
	average_emitter_price = []
	average_remover_price = []
	emissions_2025_2125 = []
	removal_cost_2025_2125 = []
	land_rents = []

	for _, scenario_id in zip(columns, scenario_ids):
		net_revenue = _load_scalar(cursor, "SELECT net_revenue FROM scenarios WHERE id = ?", (scenario_id,))
		third_party_pays.append(net_revenue if net_revenue is not None else None) # Already in trillions.

		avg_emitter_price = _load_scalar(cursor, "SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Carbon", begin_year, end_year),)
		average_emitter_price.append((avg_emitter_price, avg_emitter_price * 12.0 / 44.0) if avg_emitter_price is not None else (None, None)) # Convert $/tC to $/tCO2.

		avg_remover_price = _load_scalar(cursor, "SELECT AVG(dual_price) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Agriculture", begin_year, end_year),)
		average_remover_price.append((avg_remover_price, avg_remover_price * 12.0 / 44.0) if avg_remover_price is not None else (None, None)) # Convert $/tC to $/tCO2.

		emissions = _load_scalar(cursor, "SELECT SUM(quantity_value) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, "Carbon", begin_year, end_year),)
		emissions_2025_2125.append(emissions / 1000.0 if emissions is not None else None) # Convert mtC to gtC.

		removers = defaults_and_utilities.getRemovers()
		removal_cost = 0.0
		for remover in removers:
			cursor.execute("SELECT COALESCE(SUM(quantity_value * dual_price), 0.0) FROM scenario_bidder_year WHERE scenario_id = ? AND bidder = ? AND year >= ? AND year <= ?", (scenario_id, remover, begin_year, end_year),)
			removal_cost += cursor.fetchone()[0] # or 0.0
		removal_cost_2025_2125.append(removal_cost / 1_000_000.0)

		land_rent = _load_scalar(cursor, "SELECT land_rent FROM scenarios WHERE id = ?", (scenario_id,))
		land_rents.append(land_rent if land_rent is not None else None) # Already in trillions.

	conn.close()

	lines = []
	lines.append("\t".join([estimate_label for estimate_label, _ in columns]))
	lines.append("\t".join(["Model"] + [model_label for _, model_label in columns]))
	lines.append("\t".join(["Third party pays"] + [_fmt(v, suffix="trillion") for v in third_party_pays]))
	lines.append("\t".join(["Average emitter price"] + [f"${_trim_number(p)}/tC (${_trim_number(q)}/tCO2)" if p is not None else "N/A" for p, q in average_emitter_price]))
	lines.append("\t".join(["Average remover price"] + [f"${_trim_number(p)}/tC (${_trim_number(q)}/tCO2)" if p is not None else "N/A" for p, q in average_remover_price]))
	lines.append("\t".join(["Emissions 2025-2125"] + [_fmt(v, prefix="", suffix="GtC", decimals=1) for v in emissions_2025_2125]))
	lines.append("\t".join(["Removal cost 2025-2125"] + [_fmt(v, suffix="trillion") for v in removal_cost_2025_2125]))
	lines.append("\t".join(["Land rent"] + [_fmt(v, suffix="trillion") for v in land_rents]))

	table_text = "\n".join(lines)
	print(table_text)

	output_directory = output_directory or defaults_and_utilities.getOutputDirectory()
	with open(output_directory + "Summary_of_estimates_to_end_global_warming.txt", "w", encoding="utf-8") as output_file:
		output_file.write(table_text + "\n")

	return table_text
