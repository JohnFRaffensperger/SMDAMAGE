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
import os
from smdamage_models import run_SMDAMAGE, run_SMDAMAGE_short_auctions, run_SMDAMAGE_for_tau, get_SMDAMAGE_temps_actual_and_taxed, solve_smdamage_with_implicit_land_constraints, solve_smdamage_with_implicit_land_constraints_for_tau_search, run_SMDAMAGE_short_auctions_implicit_land_constraints

# --- Intro, Figure 2: SMDAMAGE_1 (is_revenue_neutral = True), uncalibrated and calibrated temperature trajectories. ---
def run_Intro (primary_tau):
	# Specify the scenario.
	Intro_scenario = defaults_and_utilities.Scenario(comment = "Intro explicit", discount_rate = 0.03, initial_temperature = 1400.0, tau = primary_tau,
		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = False, calibration_scenario_id = None)

	# Run that scenario in SMDAMAGE_1, then immediately solve with implicit land constraints.
	Intro_uncalibrated_explicit_id = run_SMDAMAGE (Intro_scenario)
	Intro_uncalibrated_id = solve_smdamage_with_implicit_land_constraints (Intro_uncalibrated_explicit_id)

	# Assess the implicit-land solution with Hector; use its comment so calibration reads the right file.
	Intro_scenario.comment, Intro_scenario.calibration_scenario_id = Intro_scenario.comment.replace(' explicit', f' implicit, {Intro_uncalibrated_explicit_id}'), None
	if not os.path.exists(defaults_and_utilities.Hector_output_file_name(Intro_scenario)):
		hector_interface.run_Hector_with_SMDAMAGE_solution (Intro_scenario)
	if not database_interface.get_fitted_wpt(defaults_and_utilities.getSolutionsDBPath(), Intro_uncalibrated_id):
		wpt_calibration.run_SMDAMAGE_fit_W (Intro_scenario)
	Intro_scenario.comment, Intro_scenario.calibration_scenario_id = "Intro explicit", Intro_uncalibrated_id

	# Rerun SMDAMAGE_1 with the calibrated warming factors.
	Intro_scenario.use_updated_Wpt = True
	Intro_scenario.initial_temperature = database_interface.get_calibrated_initial_temp (Intro_scenario)
	Intro_calibrated_id = run_SMDAMAGE (Intro_scenario)
	Intro_implicit_id = solve_smdamage_with_implicit_land_constraints (Intro_calibrated_id)

	# Rerun Hector with the implicit-land calibrated solution.
	Intro_scenario.comment = Intro_scenario.comment.replace(' explicit', f' implicit, {Intro_calibrated_id}')
	if not os.path.exists(defaults_and_utilities.Hector_output_file_name(Intro_scenario)):
		hector_interface.run_Hector_with_SMDAMAGE_solution (Intro_scenario)
	Intro_scenario.comment = "Intro explicit"

	# Actual figure 2: SMDAMAGE uncalibrated, SMDAMAGE calibrated, Hector with SMDAMAGE calibrated.
	plotting_utils.Uncalibrated_and_calibrated_temperature_trajectories (defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), Intro_uncalibrated_id, Intro_implicit_id, Intro_implicit_id)
	return Intro_scenario, Intro_scenario.initial_temperature

# --- Estimate 1, Figure 3: SMDAMAGE_0, is_revenue_neutral = False so we have 3rd-party payments, 4 discount rates.  ---
def run_SMDAMAGE_0_Vary_discount_rate (Intro_scenario, calibrated_initial_temperature, primary_tau):
	ids = []
	for discount_rate in [0.0, 0.015, 0.03, 0.06]:
		# Specify the scenario.
		s = defaults_and_utilities.Scenario(comment = "Vary_discount_rate explicit", discount_rate = discount_rate, initial_temperature = calibrated_initial_temperature,
			tau = primary_tau, is_revenue_neutral = False, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
		# Run SMDAMAGE_0 with 4 different discount rates.
		s_id = run_SMDAMAGE (s)
		# Re-run each solution with implicit land constraints. disc=0.03 is Estimate 1.
		ids.append (solve_smdamage_with_implicit_land_constraints (s_id))

	s_id1, s_id2, estimate1_id, s_id4 = ids # estimate 1 is the 3rd_party_paymts scenario.
	db = defaults_and_utilities.getSolutionsDBPath()
	out = defaults_and_utilities.getOutputDirectory()

	# Plot Figure 3, SMDAMAGE_0, 3rd-party payments, discount rate 3%. ---
	plotting_utils.Temperature_trajectories_with_4_discount_rates (db, out, s_id1, s_id2, estimate1_id, s_id4)
	# plotting_utils.Price_trajectory_with_full_commitment (db, out, estimate1_id)

	# Print Estimate 1.
	print (defaults_and_utilities.print_results_text(estimate1_id))
	return estimate1_id

# --- Figures 4-6: SMDAMAGE_1, revenue neutral, 4 tau surcharge rates. ---
def run_Vary_tau (Intro_scenario, calibrated_initial_temperature):
	ids = []
	for tau in [1.6, 1.8, 2.0, 2.2]:
		# Define each scenario.
		s = defaults_and_utilities.Scenario(comment = "Vary_tau explicit", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
			tau = tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
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
def run_SMDAMAGE_1_preferred_tau (Intro_scenario, calibrated_initial_temperature, preferred_tau):
	estimate2 = defaults_and_utilities.Scenario(comment = "SMDAMAGE_1_preferred_tau explicit", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = preferred_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
	estimate2_id = run_SMDAMAGE (estimate2)
	estimate2_id = solve_smdamage_with_implicit_land_constraints (estimate2_id)

	# Print Figure 7.
	plotting_utils.Price_trajectory_with_full_commitment (defaults_and_utilities.getSolutionsDBPath(), defaults_and_utilities.getOutputDirectory(), estimate2_id)
	# Print Estimate 2.
	print (defaults_and_utilities.print_results_text(estimate2_id))
	return estimate2_id

# --- Estimate 3: SMDAMAGE_1, contracts with tau=3.2, warming factors for removal based on Hector's land use change ("luc") rather than fossil fuel and industrial ("ffi"). ---
def run_Contracts (calibrated_initial_temperature, preferred_tau):
	# Specify the scenario.
	contracts = defaults_and_utilities.Scenario(comment = "Contracts explicit", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = preferred_tau, is_revenue_neutral = True, is_removal_luc = True, use_updated_Wpt = False, calibration_scenario_id = None)

	# Run the optimizations.
	contracts_uncal_explicit_id = run_SMDAMAGE (contracts)
	contracts_uncal_id = solve_smdamage_with_implicit_land_constraints (contracts_uncal_explicit_id)

	# Run Hector and calibrate W.
	contracts.comment, contracts.calibration_scenario_id = contracts.comment.replace(' explicit', f' implicit, {contracts_uncal_explicit_id}'), None
	if not os.path.exists(defaults_and_utilities.Hector_output_file_name(contracts)):
		hector_interface.run_Hector_with_SMDAMAGE_solution (contracts)
	if not database_interface.get_fitted_wpt(defaults_and_utilities.getSolutionsDBPath(), contracts_uncal_id):
		wpt_calibration.run_SMDAMAGE_fit_W (contracts)

	# Rerun SMDAMAGE_1 with calibrated "luc" warming coefficients.
	contracts.comment, contracts.calibration_scenario_id = "Contracts explicit", contracts_uncal_id
	contracts.use_updated_Wpt = True
	contracts.initial_temperature = database_interface.get_calibrated_initial_temp (contracts)
	contracts.tau = 3.2 # Still not high enough to get to base zero! Bad luc.
	estimate3_explicit_id = run_SMDAMAGE (contracts)
	estimate3_id = solve_smdamage_with_implicit_land_constraints (estimate3_explicit_id)

	# Rerun Hector with the implicit-land calibrated solution.
	contracts.comment = contracts.comment.replace(' explicit', f' implicit, {estimate3_explicit_id}')
	if not os.path.exists(defaults_and_utilities.Hector_output_file_name(contracts)):
		hector_interface.run_Hector_with_SMDAMAGE_solution (contracts)
	contracts.comment = "Contracts explicit"

	# Print Estimate 3.
	print (defaults_and_utilities.print_results_text(estimate3_id))
	return estimate3_id

# --- Estimates 4a-4h: short auctions, 4 year lengths × 2 land scales (SMDAMAGE_2) ---
def run_Short_auctions (Intro_scenario, calibrated_initial_temperature, preferred_tau):
	id_list = {}
	for land_scale_factor in [1.0, 1.5]:
		for years in [4, 8, 16, 32]:
			# Specify short scenarios.
			scenario = defaults_and_utilities.Scenario(comment = f"Short auctions {years}yrs {land_scale_factor} land area explicit", discount_rate = 0.03,
				initial_temperature = calibrated_initial_temperature, tau = preferred_tau,
				is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
			# Run them through SMDAMAGE with explicit and then implicit forest area constraints.
			scenario_id = run_SMDAMAGE_short_auctions (years, land_scale_factor, scenario)
			implicit_id = run_SMDAMAGE_short_auctions_implicit_land_constraints (scenario_id)

			# Print each estimate.
			print (defaults_and_utilities.print_results_text(implicit_id))

			id_list[(years, land_scale_factor)] = implicit_id
	return id_list

# --- New experiment: SMDAMAGE_0, 3rd-party payer, full horizon, 10x land area. ---
def run_SMDAMAGE_0_expensive_forest (Intro_scenario, calibrated_initial_temperature, primary_tau, land_scale_factor=1.0):
	s = defaults_and_utilities.Scenario(comment = "SMDAMAGE_0_expensive_forest explicit", discount_rate = 0.03,
		initial_temperature = calibrated_initial_temperature, tau = primary_tau,
		is_revenue_neutral = False, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
	s_id = run_SMDAMAGE (s, land_scale_factor = land_scale_factor, forestry_price_scale = 10.0)
	implicit_id = solve_smdamage_with_implicit_land_constraints (s_id)
	print (defaults_and_utilities.print_results_text(implicit_id))
	return implicit_id

# --- New experiment: SMDAMAGE_1, revenue neutral, tau=1.7, full horizon, 10x land area. ---
def run_SMDAMAGE_1_expensive_forest (Intro_scenario, calibrated_initial_temperature, preferred_tau, land_scale_factor=1.0):
	s = defaults_and_utilities.Scenario(comment = "SMDAMAGE_1_expensive_forest explicit", discount_rate = 0.03,
		initial_temperature = calibrated_initial_temperature, tau = preferred_tau,
		is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
	s_id = run_SMDAMAGE (s, land_scale_factor = land_scale_factor, forestry_price_scale = 10.0)
	implicit_id = solve_smdamage_with_implicit_land_constraints (s_id)
	print (defaults_and_utilities.print_results_text(implicit_id))
	return implicit_id

# --- Estimate 5: time-varying tau (subgradient search) ---
def run_Dynamic_tau (Intro_scenario, calibrated_initial_temperature, primary_tau):
	# Define the scenario. Start with tau = primary_tau for each constrained year, then subgradient optimization to choose tau for each year.
	tau_search = defaults_and_utilities.Scenario(comment = "Tau search explicit", discount_rate = 0.03, initial_temperature = calibrated_initial_temperature,
		tau = primary_tau, is_revenue_neutral = True, is_removal_luc = False, use_updated_Wpt = True, calibration_scenario_id = Intro_scenario.calibration_scenario_id)
	# Run the search for tau. Takes longer than the search for Spock.
	estimate5_id = run_SMDAMAGE_for_tau (tau_search)
	# Rerun that solution with the implicit forest area constraints.
	estimate5_id = solve_smdamage_with_implicit_land_constraints_for_tau_search (estimate5_id)
	# Print Estimate 5.
	print (defaults_and_utilities.print_results_text(estimate5_id))
	return estimate5_id

def run_all_experiments ():
	primary_tau = 1.8 # An initial guess.
	preferred_tau = 1.7 # Found by running run_figures4_5_6().

	Intro_scenario, calibrated_initial_temperature = defaults_and_utilities.recover_intro_state(primary_tau)
	if Intro_scenario is None:
		Intro_scenario, calibrated_initial_temperature = run_Intro(primary_tau)
	else:
		print(f"Reusing Intro state: temp0={calibrated_initial_temperature:.3f}, cal_id={Intro_scenario.calibration_scenario_id}.")

	estimate1_id = run_SMDAMAGE_0_Vary_discount_rate (Intro_scenario, calibrated_initial_temperature, primary_tau)

	run_Vary_tau (Intro_scenario, calibrated_initial_temperature)

	estimate2_id = run_SMDAMAGE_1_preferred_tau (Intro_scenario, calibrated_initial_temperature, preferred_tau)

	estimate3_id = run_Contracts (calibrated_initial_temperature, preferred_tau)

	estimate4_ids = run_Short_auctions (Intro_scenario, calibrated_initial_temperature, preferred_tau)

	# This is miserable, takes forever, little contribution, works badly.
	# estimate5_id = run_Dynamic_tau (Intro_scenario, calibrated_initial_temperature, primary_tau)

	db = defaults_and_utilities.getSolutionsDBPath()
	out = defaults_and_utilities.getOutputDirectory()
	plotting_utils.Summary_of_estimates_to_end_global_warming (db, estimate3_id, estimate1_id, estimate4_ids[(8, 1.5)], estimate2_id, estimate5_id, out)

	run_SMDAMAGE_0_expensive_forest (Intro_scenario, calibrated_initial_temperature, primary_tau)
	run_SMDAMAGE_1_expensive_forest (Intro_scenario, calibrated_initial_temperature, preferred_tau)

if __name__ == "__main__":
	# Preliminary: get pulses from Hector. Only needed if warming_factors table is empty.
	# if not database_interface.get_hector_names():
	# 	hector_interface.get_Pulses_from_Hector() # Output is Pulses_by_chemical.txt in the Hector directory. Move that to your /data/ directory.

	# If you like, you can delete scenarios from the database, by scenario_id.
	# defaults_and_utilities.delete_scenario_solution([12,13])

	run_all_experiments()
