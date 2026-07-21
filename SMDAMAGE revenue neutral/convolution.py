# convolution.py: Convolution utilities for SMDAMAGE.
# Wpt_dict[('Carbon', t0)] is the warming in degrees Celsius (thousandths) per megaton of carbon emitted,
# t0 years after emission. Read from row ffi_emissions in table warming_factors of smdamage_data.db.

import sqlite3
import os
import math
import numpy as np
from functools import lru_cache

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(os.path.dirname(SCRIPT_DIR), "Data", "smdamage_data.db")
PULSE_DATA_LENGTH = 296  # Pulse data from Hector goes only 296 years.
SCALE_CELSIUS = 1000.0   # Thousandths of a degree.

@lru_cache(maxsize=None) # Query the database just once for the carbon warming factors.
def get_carbon_wpt():
	"""Read Wpt_dict[('Carbon', t0)] from ffi_emissions row in warming_factors table. Result is cached."""
	conn = sqlite3.connect(DB_NAME)
	cursor = conn.cursor()
	cursor.execute("SELECT * FROM warming_factors WHERE hector_name = 'ffi_emissions'")
	row = cursor.fetchone()
	conn.close()
	emission_factor = row[2] # Usually 1.0 for carbon. Row layout: id, hector_name, emission_factor, hector_units, year_001, year_002, ..., year_296
	year_values = row[4:]  # year_001 through year_296
	# Carbon pulse units are degrees C/gigaton; divide by 1000 to convert GtC to MtC. scaleCelsius converts degrees to thousandths of a degree.
	carbon_wpt = [float(year_values[t0]) * SCALE_CELSIUS / emission_factor / 1000.0 for t0 in range(PULSE_DATA_LENGTH)]
	return carbon_wpt

def get_warming(emissions):
	"""
	Convolve a sequence of annual carbon emissions (MtC/yr) with the Carbon impulse response.
	Parameters: carbon emissions in MtC for each year, e.g. [c1, c2, ..., c100].
	Returns: temperature change in thousandths of a degree Celsius for each year.
	    warming[T] = sum_{t=0}^{T} emissions[t] * Wpt('Carbon', T-t)
	"""
	carbon_wpt = get_carbon_wpt()
	n = len(emissions)
	warming = [0.0] * n
	for T in range(n):
		for t in range(T + 1):
			lag = T - t
			if lag < PULSE_DATA_LENGTH: warming[T] += emissions[t] * carbon_wpt[lag]
	print (warming)
	# print (carbon_wpt)
	return warming

def get_warming1(emissions):
	"""
	Convolve a sequence of annual carbon emissions (MtC/yr) with the Carbon impulse response.
	Same as get_warming but uses numpy.convolve for speed.
	Parameters: emissions as a list or dict keyed by year index.
	Returns: temperature change in thousandths of a degree Celsius for each year.
	"""
	carbon_wpt = get_carbon_wpt()
	if isinstance(emissions, dict): emissions_arr = np.array([emissions[t] for t in sorted(emissions)])
	else: emissions_arr = np.asarray(emissions)
	n = len(emissions_arr)
	return np.convolve(emissions_arr, carbon_wpt)[:n]

def calculate_warming ():
	plantation_rotation_year = 32 # Contract length
	pl_A = 80 # Chapman growth factor,
	pl_k = 0.03 # Chapman growth factor,
	PLANTATION_SOIL_C = 0.092749069
	pl_rootshoot= 0.26
	w = 0.268 # wood storage share
	AGB_C_POOL= 1
	BGB_C_POOL = 1
	SOIL_C_POOL = 1
	# HARVEST_C_POOL = 1
	harvest = False
	carbon_schedule = {} # Busch code calculates carbon based on year 1, not year 0, not my fault.
	for year in range (0, plantation_rotation_year + (0 if harvest else 1)):
		 carbon_schedule [year] = 2*pl_A*pl_k*(AGB_C_POOL+BGB_C_POOL*pl_rootshoot)*(math.exp(-pl_k*(1 + year)) - math.exp(-2*pl_k*(1 + year))) + SOIL_C_POOL*PLANTATION_SOIL_C
	if harvest: carbon_schedule [plantation_rotation_year] = pl_A*(1-math.exp(-pl_k*(1 + year)))^2
	# print (carbon_schedule)
	get_warming(carbon_schedule)
calculate_warming ()
