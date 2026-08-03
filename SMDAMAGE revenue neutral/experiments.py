# Experiments for SMDAMAGE. John F Raffensperger with the help of Claude. 3 Aug 2026.

# Run this file directly to execute the full paper experiment sequence.
# =============================================================================================
# Part I. Preliminaries, inputs, key parameters: create_database.py, database_interface.py, and defaults_and_utilities.py.
# Part II. Getting pulse information from Hector: hector_interface.py.
# Part III. MAIN PROGRAM. "SMDAMAGE revenue neutral.py".
# Part IV. Running Hector on SMDAMAGE output: hector_interface.py. Called from the experiments here.
# >>> Parts V, VI, and VII: experiments are in this file.
# =============================================================================================

import database_interface
import defaults_and_utilities
import hector_interface
import plotting_utils
import wpt_calibration
import time
from smdamage_models import run_SMDAMAGE, run_SMDAMAGE_short_auctions, run_SMDAMAGE_for_tau, get_SMDAMAGE_temps_actual_and_taxed

if __name__ == "__main__":
	# Preliminary: get pulses from Hector. Only needed if warming_factors table is empty.
	if not database_interface.get_hector_names():
		hector_interface.get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.

	# If you like, you can delete scenarios from the database, by scenario_id.
	# defaults_and_utilities.delete_scenario_solution([12,13])

	# ----------------------------------------------------
	# # V.A. Figure 1. Temperature trajectories for SMDAMAGE uncalibrated, for Hector, and for SMDAMAGE calibrateion.
	# SMDAMAGE_1 uncalibrated. Uses the same tau for every year.
	# The code uses primary_tau and figure1 in subsequent experiments.
	primary_tau = 1.8
	figure1 = defaults_and_utilities.Scenario(comment = "Fig1", discount_rate = 0.03, initial_temperature = 1400.0, tau = primary_tau,
		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False, calibration_scenario_id = None)
	fig1_Wpt_default_scenario_id = run_SMDAMAGE(figure1) # uncalibrated
	# Figure 1. Hector result with the uncalibrated SMDAMAGE output.
	hector_interface.run_Hector_with_SMDAMAGE_solution(figure1)

	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	calibrated_initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(figure1) # Saves figure1.calibrated_initial_temperature. We'll use figure1.calibration_scenario_id to look up Wpt in smdamage_solutions.fitted_wpt.
	figure1.calibration_scenario_id = fig1_Wpt_default_scenario_id
	figure1_uncalibrated_actual_temps = get_SMDAMAGE_temps_actual_and_taxed(figure1)[1]

	# # V.B. Figure 1. SMDAMAGE_1 calibrated for scenario 1. discount_rate 0.03, initial_temperature 1097.1234, tau 1.8, is_revenue_neutral True, is_removal_luc False, use_updated_Wpt False.
	figure1.calibration_scenario_id = database_interface.get_scenario_id(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getExperimentTag(figure1)) # Look up uncalibrated Fig1 id before initial_temperature is updated.
	figure1.initial_temperature = database_interface.get_calibrated_initial_temp(figure1)
	figure1.use_updated_Wpt = True
	fig1_Wpt_fitted_scenario_id = run_SMDAMAGE(figure1) # calibrated
	# Figure 1. Hector result with the calibrated SMDAMAGE output.
	hector_interface.run_Hector_with_SMDAMAGE_solution(figure1)

	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, *get_SMDAMAGE_temps_actual_and_taxed(figure1), hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(figure1, figure1_uncalibrated_actual_temps, get_SMDAMAGE_temps_actual_and_taxed(figure1)[1], hector_interface.get_Hector_temperature(figure1), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)
	plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), fig1_Wpt_default_scenario_id, fig1_Wpt_fitted_scenario_id, fig1_Wpt_fitted_scenario_id)

	# ----------------------------------------------------
	# # V.C. Figure 2. Robustness to discount rate. SMDAMAGE_0 calibrated to scenario 1. Tau is irrelevant. : initial_temperature initial_temperature = 1097.1234,
	# is_revenue_neutral False, tau is irrelevant, is_removal_luc to False, use_updated_Wpt = True.
	# Using the original long-term SMDAMAGE formulation, not revenue neutral.
	calibrated_initial_temperature = figure1.initial_temperature  # already set at line 739
	s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.0, initial_temperature = calibrated_initial_temperature,
		is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.015, initial_temperature = calibrated_initial_temperature,
		is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))

	# Estimate 1 "Full commitment" long-term model, third party pays.
	estimate1_LT_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Fig2", discount_rate = 0.06, initial_temperature = calibrated_initial_temperature,
		is_revenue_neutral = False, tau = primary_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	plotting_utils.Temperature_trajectories_with_4_discount_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, estimate1_LT_scenario_id, s_id4)
	plotting_utils.Price_trajectory_with_full_commitment(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate1_LT_scenario_id)

	# ----------------------------------------------------
	# V.D. Figures 3-5 dynamic tau. SMDAMAGE_1 calibrated to figure1 scenario. discount_rate to 0.03, initial_temperature from figure1, is_revenue_neutral True, tau in a range, is_removal_luc False, use_updated_Wpt True.
	figure1.calibration_scenario_id = 1
	s_id1 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.6, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	s_id2 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 1.8, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	s_id3 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.0, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	s_id4 = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature, is_revenue_neutral = True, tau = 2.2, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))
	plotting_utils.Carbon_emissions_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Discounted_net_revenue_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)
	plotting_utils.Temperature_trajectories_with_4_tau_rates(defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), s_id1, s_id2, s_id3, s_id4)

	# ----------------------------------------------------
	# V.E. Estimate 2. Concluding paragraph after Figures 3-5. SMDAMAGE_1 with preferred tau.
	figure1.calibration_scenario_id = 1
	preferred_tau = 1.7 # Replaces primary_tau. Chosen based on the experiment of Figures 3-5, the tau that would result in base zero.

	estimate2_ST_scenario_id = run_SMDAMAGE(defaults_and_utilities.Scenario(comment = "Figs3-5_after", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		is_revenue_neutral = True, tau = preferred_tau, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id))

	# ----------------------------------------------------
	# # VI. Strength of contracts. Key: is_removal_luc=True. Figure 6 comes from the Pulse input data.
	contracts_scenario = defaults_and_utilities.Scenario(comment = "Contracts", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1),
		is_revenue_neutral = True, tau = preferred_tau, is_removal_luc = True, use_updated_Wpt = False, calibration_scenario_id = None)

	# # VI.A. Run SMDAMAGE_1 with uncalibrated Wpt and treating carbon removers as land use change "luc" (rather than the negative of emissions).
	# Can't use the Fig 1 calibration because we changed from ffi warming coefficients to luc warming coefficients. initial_temperature doesn't matter much here, as it still needs calibration.
	calibration_scenario_id = run_SMDAMAGE(contracts_scenario) # uncalibrated.
	hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario) # run_SMDAMAGE writes to smdamage_solutions.fitted_wpt with its scenario_id, i.e., calibration_scenario_id.
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# # VI.B. Calibrate W for weak contracts.
	contracts_scenario.initial_temperature = wpt_calibration.run_SMDAMAGE_fit_W(contracts_scenario)
	contracts_scenario.use_updated_Wpt = True
	contracts_scenario.calibration_scenario_id = calibration_scenario_id # Use the scenario just done to look up Wpt from smdamage_solutions.fitted_wpt
	contracts_scenario.tau = 2.6 # not actually high enough.

	# # VI.C. Run the auction with weak contracts, discount_rate 0.03, initial_temperature from the first calibration, is_revenue_neutral True, tau is 2.6, is_removal_luc to True, use_updated_Wpt = True.
	estimate3_weak_contracts_scenario_id = run_SMDAMAGE(contracts_scenario) # calibrated to luc warming coefficients.
	hector_interface.run_Hector_with_SMDAMAGE_solution(contracts_scenario)
	plotting_utils.plot_temps_SMDAMAGE_and_Hector(contracts_scenario, *get_SMDAMAGE_temps_actual_and_taxed(contracts_scenario), hector_interface.get_Hector_temperature(contracts_scenario), defaults_and_utilities.getOutputDirectory, defaults_and_utilities.experimentTag_to_file_name)

	# ----------------------------------------------------
	# # VII. Short auctions.
	years_in_auction_list = [2, 4, 8, 16, 32]
	land_scale_factor = 1.5 # sensitivity: scale total available forestry land relative to data.
	for years in years_in_auction_list:
		Short_auctions_scenario = defaults_and_utilities.Scenario(comment = f"Short auctions {years}yrs 1.5 land area", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1), tau = preferred_tau,
			is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = figure1.calibration_scenario_id)
		estimate4_short_auctions_scenario_id = run_SMDAMAGE_short_auctions(years, land_scale_factor, Short_auctions_scenario)

	# ----------------------------------------------------
	# VIII. Search for tau. Start with tau = primary_tau for each constrained year, then subgradient optimization to choose tau for each year. Use calibrated_initial_temperature from VII.B.
	# # Warning! Very slow, e.g., 8 hours to run this.
	tau_search = defaults_and_utilities.Scenario(comment = "Tau search", discount_rate = 0.03, initial_temperature = database_interface.get_calibrated_initial_temp(figure1), tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = None)
	estimate5_tau_search_scenario_id = run_SMDAMAGE_for_tau(tau_search)
	# ----------------------------------------------------

	# Table at end # estimate4_short_auctions_scenario_id = 21;
	# estimate3_weak_contracts_scenario_id = 17; estimate1_LT_scenario_id = 18; estimate2_ST_scenario_id = 20; estimate5_tau_search_scenario_id = 22
	plotting_utils.Summary_of_estimates_to_end_global_warming(defaults_and_utilities.getSolutionsDBPath(), estimate3_weak_contracts_scenario_id, estimate1_LT_scenario_id, estimate4_short_auctions_scenario_id, estimate2_ST_scenario_id, estimate5_tau_search_scenario_id, defaults_and_utilities.getOutputDirectory())

	print ("\nSMDAMAGE experiments are done. " + time.asctime(time.localtime(time.time())) + ". Reminder: convert $/ton C to $/ton CO2.")
	import winsound
	winsound.Beep(700, 500)  # Just to let you know it's finally finished. Frequency 700 Hz, duration 500 ms
