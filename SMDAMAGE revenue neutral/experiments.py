# Experiments for SMDAMAGE. John F Raffensperger with the help of Claude. 3 Aug 2026.

# Run this file directly to execute the full paper experiment sequence. Set aside a full day, 'cause it's nontrivial work.
# =============================================================================================
# Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. KEY PROGRAM smdamage_models.py.
# Part IV. Running Hector on SMDAMAGE output: hector_interface.py. Called from the experiments here.
# >>> Parts V, VI, and VII: experiments are in this file.
# =============================================================================================

import database_interface
import defaults_and_utilities
import hector_interface
import plotting_utils
import wpt_calibration
import time
from smdamage_models import run_SMDAMAGE, run_SMDAMAGE_short_auctions, run_SMDAMAGE_for_tau, get_SMDAMAGE_temps_actual_and_taxed, solve_smdamage_with_implicit_land_constraints, solve_smdamage_with_implicit_land_constraints_for_tau_search, run_SMDAMAGE_short_auctions_implicit_land_constraints

# --- Figure 2: SMDAMAGE_1 (is_revenue_neutral = True), uncalibrated and calibrated temperature trajectories. ---
def run_figure2 (primary_tau):
	# Specify the scenario.
	figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = primary_tau,
		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False, calibration_scenario_id = None)
	# Run that scenario in SMDAMAGE_1.
	fig1_uncalibrated_id = run_SMDAMAGE (figure1)
	# Assess that solution with Hector.
	hector_interface.run_Hector_with_SMDAMAGE_solution (figure1)
	# Nice plots.
	plotting_utils.plot_temps_SMDAMAGE_and_Hector (figure1, *get_SMDAMAGE_temps_actual_and_taxed (figure1), hector_interface.get_Hector_temperature (figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	fig1_uncalibrated_actual_temps = get_SMDAMAGE_temps_actual_and_taxed (figure1)[1]  # capture before figure1.use_updated_Wpt changes

	# Run SMDAMAGE with implicit land contraints.
	fig1_uncalibrated_id = solve_smdamage_with_implicit_land_constraints (fig1_uncalibrated_id)   # implicit land, uncalibrated
	figure1.calibration_scenario_id = fig1_uncalibrated_id

	# Calibrate the warming factors.
	wpt_calibration.run_SMDAMAGE_fit_W (figure1)

	# Rerun SMDAMAGE_1 with the calibrated warming factors.
	figure1.use_updated_Wpt = True
	figure1.initial_temperature = database_interface.get_calibrated_initial_temp (figure1)
	fig1_calibrated_id = run_SMDAMAGE (figure1)

	# Rerun Hector with the calibrated SMDAMAGE solution.
	hector_interface.run_Hector_with_SMDAMAGE_solution (figure1)

	# Nice plots.
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector (figure1, *get_SMDAMAGE_temps_actual_and_taxed (figure1), hector_interface.get_Hector_temperature (figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector (figure1, fig1_uncalibrated_actual_temps, get_SMDAMAGE_temps_actual_and_taxed (figure1)[1], hector_interface.get_Hector_temperature (figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# Convert the explicit forest area constraints to implicit area constraints.
	fig1_implicit_id = solve_smdamage_with_implicit_land_constraints (fig1_calibrated_id)

	# Actual figure 2.
	plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories (defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), fig1_uncalibrated_id, fig1_implicit_id, fig1_calibrated_id)
	return figure1, figure1.initial_temperature

# --- Estimate 1, Figure 3: SMDAMAGE_0, is_revenue_neutral = False so we have 3rd-party payments, 4 discount rates.  ---
def run_figure3_estimate1 (figure1, calibrated_initial_temperature, primary_tau):
	ids = []
	for discount_rate in [0.0, 0.015, 0.03, 0.06]:
		# Specify the scenario.
		s = defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = discount_rate, initial_temperature = calibrated_initial_temperature,
			tau = primary_tau, is_revenue_neutral = False, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
		# Run SMDAMAGE_0 with 4 different discount rates.
		s_id = run_SMDAMAGE (s)
		# Re-run each solution with implicit land constraints. disc=0.03 is Estimate 1.
		ids.append (solve_smdamage_with_implicit_land_constraints (s_id))

	s_id1, s_id2, estimate1_id, s_id4 = ids
	db = defaults_and_utilities.getSolutionsDBPath()
	out = defaults_and_utilities.getOutputDirectory()

	# Plot Figure 3, SMDAMAGE_0, 3rd-party payments, discount rate 3%. ---
	plotting_utils.Temperature_trajectories_with_4_discount_rates (db, out, s_id1, s_id2, estimate1_id, s_id4)
	# plotting_utils.Price_trajectory_with_full_commitment (db, out, estimate1_id)

	# Print Estimate 1.
	print (defaults_and_utilities.print_results_text(estimate1_id))
	return estimate1_id

# --- Figures 4-6: SMDAMAGE_1, revenue neutral, 4 tau surcharge rates. ---
def run_figures4_5_6 (figure1, calibrated_initial_temperature):
	ids = []
	for tau in [1.6, 1.8, 2.0, 2.2]:
		# Define each scenario.
		s = defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
			tau = tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
		# Run SMDAMAGE with the scenario and explicit forest area constraints.
		s_id = run_SMDAMAGE (s)
		# Run SMDAMAGE with implicit forest area constraints.
		ids.append (solve_smdamage_with_implicit_land_constraints (s_id))
	s_id1, s_id2, s_id3, s_id4 = ids
	db = defaults_and_utilities.getSolutionsDBPath()
	out = defaults_and_utilities.getOutputDirectory()

	# Plot Figures 4, 5, and 6.
	plotting_utils.Carbon_emissions_with_4_tau_rates (db, out, s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Discounted_net_revenue_with_4_tau_rates (db, out, s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Temperature_trajectories_with_4_tau_rates (db, out, s_id1, s_id2, s_id3, s_id4)

# --- Figure 7, Estimate 2: SMDAMAGE_1, preferred tau, emitters' price trajectory. ---
def run_estimate2_figure7 (figure1, calibrated_initial_temperature, preferred_tau):
	estimate2 = defaults_and_utilities.Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = preferred_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
	estimate2_id = run_SMDAMAGE (estimate2)
	estimate2_id = solve_smdamage_with_implicit_land_constraints (estimate2_id)

	# Print Figure 7.
	plotting_utils.Price_trajectory_with_full_commitment (defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate2_id)
	# Print Estimate 2.
	print (defaults_and_utilities.print_results_text(estimate2_id))
	return estimate2_id

# --- Estimate 3: SMDAMAGE_1, contracts with tau=3.2, warming factors for removal based on Hector's land use change ("luc") rather than fossil fuel and industrial ("ffi"). ---
def run_estimate3 (figure1, calibrated_initial_temperature, preferred_tau):
	# Specify the scenario.
	contracts = defaults_and_utilities.Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = preferred_tau, is_revenue_neutral = True, is_removal_luc = True, use_updated_Wpt = False, calibration_scenario_id = None)
	contracts_uncal_id = run_SMDAMAGE (contracts)
	hector_interface.run_Hector_with_SMDAMAGE_solution (contracts)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector (contracts, *get_SMDAMAGE_temps_actual_and_taxed (contracts), hector_interface.get_Hector_temperature (contracts), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	contracts.calibration_scenario_id = contracts_uncal_id
	# Calibrate for luc warming coefficients.
	wpt_calibration.run_SMDAMAGE_fit_W (contracts)
	contracts.use_updated_Wpt = True
	contracts.initial_temperature = database_interface.get_calibrated_initial_temp (contracts)
	contracts.tau = 3.2 # Still not high enough to get to base zero! Bad luc.
	# Rerun SMDAMAGE_1 with calibrated "luc" warming coefficients.
	estimate3_id = run_SMDAMAGE (contracts)
	# Rerun hector to compare calibrated SMDAMAGE to climate simulator.
	hector_interface.run_Hector_with_SMDAMAGE_solution (contracts)

	# plotting_utils.plot_temps_SMDAMAGE_and_Hector (contracts, *get_SMDAMAGE_temps_actual_and_taxed (contracts), hector_interface.get_Hector_temperature (contracts), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	# Update emissions and prices for implicit forest area constraint.
	estimate3_id = solve_smdamage_with_implicit_land_constraints (estimate3_id)
	# Print Estimate 3.
	print (defaults_and_utilities.print_results_text(estimate3_id))
	return estimate3_id

# --- Estimates 4a-4h: short auctions, 4 year lengths × 2 land scales (SMDAMAGE_2) ---
def run_estimates4 (figure1, calibrated_initial_temperature, preferred_tau):
	id_list = {}
	for land_scale_factor in [1.0, 1.5]:
		for years in [4, 8, 16, 32]:
			# Specify short scenarios.
			scenario = defaults_and_utilities.Scenario(comment = f"Short auctions {years}yrs {land_scale_factor} land area", discount_rate = 0.03,
				initial_temperature = calibrated_initial_temperature, tau = preferred_tau,
				is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
			# Run them through SMDAMAGE with explicit and then implicit forest area constraints.
			scenario_id = run_SMDAMAGE_short_auctions (years, land_scale_factor, scenario)
			implicit_id = run_SMDAMAGE_short_auctions_implicit_land_constraints (scenario_id)

			# Print each estimate.
			print (defaults_and_utilities.print_results_text(implicit_id))

			id_list[(years, land_scale_factor)] = implicit_id
	return id_list

# --- Estimate 5: time-varying tau (subgradient search) ---
def run_estimate5 (figure1, calibrated_initial_temperature, primary_tau):
	# Define the scenario. Start with tau = primary_tau for each constrained year, then subgradient optimization to choose tau for each year.
	tau_search = defaults_and_utilities.Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
	# Run the search for tau. Takes longer than the search for Spock.
	estimate5_id = run_SMDAMAGE_for_tau (tau_search)
	# Rerun that solution with the implicit forest area constraints.
	estimate5_id = solve_smdamage_with_implicit_land_constraints_for_tau_search (estimate5_id)
	# Print Estimate 5.
	print (defaults_and_utilities.print_results_text(estimate5_id))
	return estimate5_id

def run_all_experiments ():
	primary_tau = 1.8
	preferred_tau = 1.7

	figure1, calibrated_initial_temperature = run_figure2 (primary_tau)

	estimate1_id = run_figure3_estimate1 (figure1, calibrated_initial_temperature, primary_tau)

	run_figures4_5_6 (figure1, calibrated_initial_temperature)

	estimate2_id = run_estimate2_figure7 (figure1, calibrated_initial_temperature, preferred_tau)

	estimate3_id = run_estimate3 (figure1, calibrated_initial_temperature, preferred_tau)

	estimate4_ids = run_estimates4 (figure1, calibrated_initial_temperature, preferred_tau)

	estimate5_id = run_estimate5 (figure1, calibrated_initial_temperature, primary_tau)

	db = defaults_and_utilities.getSolutionsDBPath()
	out = defaults_and_utilities.getOutputDirectory()
	plotting_utils.Summary_of_estimates_to_end_global_warming (db, estimate3_id, estimate1_id, estimate4_ids[(8, 1.5)], estimate2_id, estimate5_id, out)

if __name__ == "__main__":
	# Preliminary: get pulses from Hector. Only needed if warming_factors table is empty.
	# if not database_interface.get_hector_names():
	# 	hector_interface.get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.

	# If you like, you can delete scenarios from the database, by scenario_id.
	# defaults_and_utilities.delete_scenario_solution([12,13])
	# ----------------------------------------------------
	# OFF BY ONE in figure numbering, since I added the "Influence diagram for weak carbon removal" as Figure 1. Apologies.

	# # V.A. Temperature trajectories for SMDAMAGE uncalibrated, for Hector, and for SMDAMAGE calibration.
	# SMDAMAGE_1 uncalibrated. Uses the same tau for every year.
	# The code uses primary_tau and figure1 in subsequent experiments.
	# primary_tau = 1.8
	# figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = primary_tau,
	# 	is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False, calibration_scenario_id = None)
	# print ("SMDAMAGE_1 starting. " + time.asctime(time.localtime(time.time())))
	# fig1_Wpt_default_scenario_id = run_SMDAMAGE(figure1) # uncalibrated
	# Hector result with the uncalibrated SMDAMAGE output for Figure 1.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(figure1)

	# Nice to have jpg.
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	# print ("SMDAMAGE_fit_W starting. " + time.asctime(time.localtime(time.time())))
	# calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(figure1) # Saves figure1.calibrated_initial_temperature. We'll use figure1.calibration_scenario_id to look up Wpt in smdamage_solutions.fitted_wpt.
	# figure1.calibration_scenario_id = fig1_Wpt_default_scenario_id
	# figure1_uncalibrated_actual_temps = get_SMDAMAGE_temps_actual_and_taxed(figure1)[1]

	# # V.B. SMDAMAGE_1 calibrated for scenario 1. discount_rate 0.03, initial_temperature 1097.1234, tau 1.8, is_revenue_neutral True, is_removal_luc False, use_updated_Wpt False.
	# figure1.calibration_scenario_id = database_interface.get_scenario_id(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getExperimentTag(figure1)) # Look up uncalibrated Fig1 id before initial_temperature is updated.
	# figure1.initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	# figure1.use_updated_Wpt = True
	# print ("SMDAMAGE_1 starting. " + time.asctime(time.localtime(time.time())))
	# fig1_Wpt_fitted_scenario_id = run_SMDAMAGE(figure1) # calibrated
	# Hector result with the calibrated SMDAMAGE output for Figure 1.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(figure1)

	# Nice-to-have jpgs.
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, figure1_uncalibrated_actual_temps, get_SMDAMAGE_temps_actual_and_taxed(figure1)[1], hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# Figure 1. Uncalibrated and calibrated temperature trajectories. SVG file.
	# fig1_Wpt_default_scenario_id = 1; fig1_Wpt_fitted_scenario_id = 2
	# plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), fig1_Wpt_default_scenario_id, fig1_Wpt_fitted_scenario_id, fig1_Wpt_fitted_scenario_id)

	# ----------------------------------------------------
	# # V.C. Robustness to discount rate. SMDAMAGE_0 calibrated to scenario 1. Tau is irrelevant.
	# 	initial_temperature initial_temperature = 1097.1234, is_revenue_neutral False, tau is irrelevant, is_removal_luc to False, use_updated_Wpt = True.
	# Using the original long-term SMDAMAGE formulation, not revenue neutral.
	# print ("SMDAMAGE_0 starting. " + time.asctime(time.localtime(time.time())))
	# figure1.calibration_scenario_id = database_interface.get_scenario_id(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getExperimentTag(figure1)) # Look up uncalibrated Fig1 id before initial_temperature is updated.
	# calibrated_initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	# s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.0, initial_temperature = calibrated_initial_temperature,
	# 	is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.015, initial_temperature = calibrated_initial_temperature,
	# 	is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))

	# Estimate 1 "Full commitment" long-term model, third party pays.
	# estimate1_LT_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
	# 	is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.06, initial_temperature = calibrated_initial_temperature,
	# 	is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))

	# Figure 2. Temperature trajectories with full commitment, a 2125 deadline, and 4 different discount rates.
	# plotting_utils.Temperature_trajectories_with_4_discount_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, estimate1_LT_scenario_id, s_id4)
	# plotting_utils.Price_trajectory_with_full_commitment(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate1_LT_scenario_id)

	# ----------------------------------------------------
	# V.D. Figures 3-5 dynamic tau. SMDAMAGE_1 calibrated to figure1 scenario. discount_rate to 0.03, initial_temperature from figure1, is_revenue_neutral True, tau in a range, is_removal_luc False, use_updated_Wpt True.
	# print ("SMDAMAGE_1 starting. " + time.asctime(time.localtime(time.time())))
	# figure1.calibration_scenario_id = 1
	# s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.6, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.8, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# s_id3 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.0, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.2, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))

	# # Figure 3. Carbon emissions with full commitment, a 2125 deadline, 3% discount rate, and four surcharge rates τ
	# plotting_utils.Carbon_emissions_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	# # Figure 4. Discounted net revenue full commitment, a 2125 deadline, 3% discount rate, and four surcharge rates τ
	# plotting_utils.Discounted_net_revenue_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	# # Figure 5. Temperature trajectories full commitment, a 2125 deadline, 3% discount rate, and four surcharge rates τ
	# plotting_utils.Temperature_trajectories_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	# # ----------------------------------------------------
	# # V.E. Estimate 2. Concluding paragraph after Figures 3-5. SMDAMAGE_1 with preferred tau.
	# figure1.calibration_scenario_id = 1
	# preferred_tau = 1.7 # Replaces primary_tau. Chosen based on the experiment of Figures 3-5, the tau that would result in base zero.

	# estimate2_ST_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
	# 	is_revenue_neutral = True, tau = preferred_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	# # Figure 6. Price trajectory with full commitment, a 2125 deadline, 3% discount rate, and τ = preferred_tau.
	# plotting_utils.Price_trajectory_with_full_commitment(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate2_ST_scenario_id)

	# # ----------------------------------------------------
	# # # VI. Strength of contracts. Key: is_removal_luc=True. Figure 7 comes from the Pulse input data.
	# contracts_scenario = defaults_and_utilities.Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1),
	#  	is_revenue_neutral = True, tau = preferred_tau, is_removal_luc = True, use_updated_Wpt = False, calibration_scenario_id = None)

	# # VI.A. Run SMDAMAGE_1 with uncalibrated Wpt and treating carbon removers as land use change "luc" (rather than the negative of emissions).
	# Can't use the Fig 1 calibration because we changed from ffi warming coefficients to luc warming coefficients. initial_temperature doesn't matter much here, as it still needs calibration.
	# calibration_scenario_id = run_SMDAMAGE(contracts_scenario) # uncalibrated.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario) # run_SMDAMAGE writes to smdamage_solutions.fitted_wpt with its scenario_id, i.e., calibration_scenario_id.
	# # Nice to have jpg.
	# # plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# # # VI.B. Calibrate W for weak contracts.
	# contracts_scenario.initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(contracts_scenario)

	# # # VI.C. Run the auction with weak contracts, discount_rate 0.03, initial_temperature from the first calibration, is_revenue_neutral True, tau is 2.6, is_removal_luc to True, use_updated_Wpt = True.
	# I haven't designed a convenient way to specify the calibration scenario, so it's easy to get wrong.
	# contracts_scenario.use_updated_Wpt = True
	# contracts_scenario.calibration_scenario_id = 12 # calibration_scenario_id # Use the scenario just done to look up Wpt from smdamage_solutions.fitted_wpt
	# contracts_scenario.initial_temperature = database_interface.get_calibrated_initial_temp(contracts_scenario)
	# contracts_scenario.tau = 3.2 # not high enough!
	# estimate3_weak_contracts_scenario_id = run_SMDAMAGE(contracts_scenario) # calibrated to luc warming coefficients.
	# hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	# Nice-to-have jpg.
	# plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# ----------------------------------------------------
	# # VII. Short auctions.
	# years_in_auction_list = [4, 8, 16, 32]
	# estimate4_short_auctions_scenario_id = {y: 0 for y in years_in_auction_list}
	# land_scale_factor = 1.0 # sensitivity: scale total available forestry land relative to data.
	# for years in years_in_auction_list:
	# 	Short_auctions_scenario = defaults_and_utilities.Scenario(comment = f"Short auctions {years}yrs {land_scale_factor} land area", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1), tau = preferred_tau,
	# 		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
	# 	estimate4_short_auctions_scenario_id[years] = run_SMDAMAGE_short_auctions(years, land_scale_factor, Short_auctions_scenario)

	# land_scale_factor = 1.5 # sensitivity: scale total available forestry land relative to data.
	# for years in years_in_auction_list:
	# 	Short_auctions_scenario = defaults_and_utilities.Scenario(comment = f"Short auctions {years}yrs {land_scale_factor} land area", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1), tau = preferred_tau,
	# 		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
	# 	run_SMDAMAGE_short_auctions(years, land_scale_factor, Short_auctions_scenario)

	# ----------------------------------------------------
	# VIII. Search for tau. Start with tau = primary_tau for each constrained year, then subgradient optimization to choose tau for each year. Use calibrated_initial_temperature from VII.B.
	# # Warning! Very slow, e.g., 8 hours to run this.
	# tau_search = defaults_and_utilities.Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1), tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = 1)
	# estimate5_tau_search_scenario_id = run_SMDAMAGE_for_tau(tau_search)
	# ----------------------------------------------------

	# Table at end # estimate4_short_auctions_scenario_id = 21;
	# estimate1_LT_scenario_id = 5; estimate2_ST_scenario_id = 11;
	# estimate3_weak_contracts_scenario_id = 17; estimate5_tau_search_scenario_id = 22
	# plotting_utils.Summary_of_estimates_to_end_global_warming(defaults_and_utilities.getSolutionsDBPath(), estimate3_weak_contracts_scenario_id, estimate1_LT_scenario_id, estimate4_short_auctions_scenario_id, estimate2_ST_scenario_id, estimate5_tau_search_scenario_id, defaults_and_utilities.getOutputDirectory())

	# Solve the same scenario with implicit land constraints. The objective value should be the same, but prices and emissions will change.
	# for scenario_id in range(16,24):
	# 	implicit_land_scenario_id = solve_smdamage_with_implicit_land_constraints(scenario_id)
	# 	print (defaults_and_utilities.print_results_text(implicit_land_scenario_id))
	# implicit_land_scenario_id = solve_smdamage_with_implicit_land_constraints_for_tau_search(24)
	# print ("\n", defaults_and_utilities.print_results_text(implicit_land_scenario_id))
	# print ("\nSMDAMAGE experiments are done. " + time.asctime(time.localtime(time.time())) + ". Reminder: convert $/ton C to $/ton CO2.")
	# import winsound
	# winsound.Beep(700, 500)  # Just to let you know it's finally finished. Frequency 700 Hz, duration 500 ms.
	# db = defaults_and_utilities.getSolutionsDBPath()
	# out = defaults_and_utilities.getOutputDirectory()
	# # If you have run everything, you can retrieve the solutions from smdamage_solutions.db.
	# # Figure 2: calibrated & uncalibrated, scenarios 1:26 and 2:27.
	# figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = 1.8,
	# 	is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = 27)
	# figure1.initial_temperature = database_interface.get_calibrated_initial_temp (figure1)

	# hector_interface.run_Hector_with_SMDAMAGE_solution(figure1)
	# # 26=uncal explicit, 27=uncal implicit, 28=cal explicit (Hector stored here), 29=cal implicit.
	# plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories (db, out, 27, 29, 28)

	# # Figure 3: 4 discount rates, scenarios 3:28, 4:29, 5:30, 6:31.
	# plotting_utils.Temperature_trajectories_with_4_discount_rates (db, out, 28, 29, 30, 31)

	# # Estimate 1: 3rd party payments, scenario 5:30.
	# print (defaults_and_utilities.print_results_text(30))

	# # Figures 4-6, scenarios 7:32, 8:33, 9:34, 10:35.
	# plotting_utils.Carbon_emissions_with_4_tau_rates (db, out, 32, 33, 34, 35)
	# plotting_utils.Discounted_net_revenue_with_4_tau_rates (db, out, 32, 33, 34, 35)
	# plotting_utils.Temperature_trajectories_with_4_tau_rates (db, out, 32, 33, 34, 35)

	# # Figure 7: SMDAMAGE_1 with tau=1.7, emitters' price trajectory, scenarios 11:25.
	# plotting_utils.Price_trajectory_with_full_commitment (defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), 25)
	# # Estimate 2: SMDAMAGE_1 with tau=1.7, scenario 11:25.
	# print (defaults_and_utilities.print_results_text(25))

	# # Estimate 3: SMDAMAGE_1, contracts with tau=3.2, scenario 37:38.
	# print (defaults_and_utilities.print_results_text(38))

	# Estimates 4a, 4b, 4c, 4d, 4e, 4f: SMDAMAGE_2, short auctions of years length 4, 8, 16, 32, with land scale 1.0 and 1.5: scenarios 16:40, 17:41, ..., 23:47. Make a table.
	# for scenario_id in [40, 41, 42, 43, 44, 45, 46, 47]: print (defaults_and_utilities.print_results_text(scenario_id))

	# # Estimate 5, time varying tau: scenario 24:39
	# print (defaults_and_utilities.print_results_text(39))
	run_all_experiments()
