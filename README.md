# SMDAMAGE

**SMDAMAGE** is a set of linear programs that seek the least-cost allocation
of greenhouse-gas emissions and carbon removals needed to lower global warming
to a specified temperature target. Emitters bid to buy the right to emit.
Carbon removers (forestry, agriculture, seaweed) bid to offer sequestration contracts.
The code calibrates the auction warming coefficients to the [Hector](https://github.com/JGCRI/hector) climate model.

This repository accompanies my 2026 SMDAMAGE paper "Paying for Drawdown".
The 2021 paper (corrected 2024) used Stavins & Richards (2005) forestry data.
This 2026 version replaces that with the Busch et al. (2024) global reforestation dataset
and adds forestry land area constraints explicitly and implicitly.

smdamage_models.py implements 3 models:
	SMDAMAGE_0, Long-run, revenue-negative (2021 paper baseline).
	SMDAMAGE_1, Long-run, revenue-neutral (emitters pay a surcharge τ for drawdown).
	SMDAMAGE_2, Short-run, rolling auctions (4–32 year windows; implementable in an ETS).

For setting this up, you have a shortcut option which starts with smdamage_data.db.
That file has all the inputs collated already, so you can go straight to experiments.py.
Otherwise, you'll have to start with the Busch et al forestry data and rebuild everything.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | |
| [Hector v2.0.1](https://github.com/JGCRI/hector) | Climate model; Windows binary assumed. Set `HECTOR_DIR` in `hector_interface.py`. |
| Busch et al. 2024 replication data | Download from Zenodo (see Part 1 of setup). Processed by the companion [Busch2024](https://github.com/JohnFRaffensperger/Busch2024) repository. |

Python package dependencies are listed in `requirements.txt`.

## Repository Structure

README.md                          — this file
requirements.txt                   — Python dependencies
LICENSE
data_sources.txt                   — data sources and bid curve construction notes
SMDAMAGE_glossary.txt              — variable and function glossary

Data/
    Agriculture_bids.csv           — agriculture mitigation bid steps (IPCC AR5)
    Seaweed_bids.csv               — seaweed carbon removal bids
    MtC_bid_steps.csv              — fossil fuel carbon emission bid steps
    CH4_bid_steps.csv              — methane emission bid steps
    N2O_bid_steps.csv              — nitrous oxide emission bid steps
    C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv  — fluorinated gas bid steps
    Forestry_bid_steps.csv         — forestry bid steps (2021 paper, Stavins & Richards)
    Forestry_sequestration.csv     — forestry carbon removal schedules
    Calibrated_pulses_by_chemical_2025.txt  — Hector pulse responses (generate with hector_interface.py)
    README_Database.md             — database build notes

SMDAMAGE revenue neutral/
    create_database.py             — builds Data/smdamage_data.db from CSVs and Busch SQLite
    database_interface.py          — SQL query helpers
    defaults_and_utilities.py      — parameters, Scenario dataclass, utility functions
    smdamage_models.py             — SMDAMAGE LP models (SMDAMAGE_0/1/2)
    hector_interface.py            — Hector integration (pulse generation, scenario runs)
    experiments.py                 — full paper experiment sequence
    wpt_calibration.py             — warming-per-tonne (Wpt) calibration
    plotting_utils.py              — temperature and bid curve plots
    check_prices.py                — inspect bid prices in the database
    quick_check.py                 — sanity checks on solutions
    table_to_html.py               — HTML summary table generation
    LocalHTML.py                   — local HTML report utilities
    Output/                        — scenario output files and smdamage_solutions.db

## Setup

`Data/smdamage_data.db` is included in this repository, so you can run
`experiments.py` without rebuilding the input database or processing the
Busch et al. forestry dataset.

---

### Shortcut setup with `smdamage_data.db`

#### 1. Clone and install

```powershell
git clone https://github.com/JohnFRaffensperger/SMDAMAGE.git
cd SMDAMAGE
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. Install and configure Hector

Download the Hector v2.0.1 Windows binary from the
[Hector releases page](https://github.com/JGCRI/hector/releases).
Set the `HECTOR_DIR` path constant at the top of
`SMDAMAGE revenue neutral/hector_interface.py` to point to your local Hector directory.

`Data/Calibrated_pulses_by_chemical_2025.txt` is already included, so you do
not need to re-run Hector to generate pulse-response data unless you change
the climate scenario or Hector version.

#### 3. Run experiments

From the `SMDAMAGE revenue neutral/` directory:

```powershell
python experiments.py
```

---

### Full setup without `smdamage_data.db`

Use this path if you want to rebuild the input database from scratch —
for example, to change forestry contract parameters, discount rates, or
k-means cluster counts.

#### 1. Install the SMDAMAGE project. Clone and install

```powershell
git clone https://github.com/JohnFRaffensperger/SMDAMAGE.git
cd SMDAMAGE
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. Install the Busch et al (2024) project to prepare the forestry data

The forestry input comes from a four-step pipeline in the companion
[Busch2024](https://github.com/JohnFRaffensperger/Busch2024) repository.
From that repository root, create and activate a virtual environment first:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Then download the Busch et al. Zenodo replication deposit and extract
`08_input_dtas.zip` into `Busch2024\Input\` (country-level `.dta` files,
one per country code). Optionally extract `12_stata_code.zip` into
`Busch2024\DO code\` for reference.

Run the four scripts in order from `Busch2024\JFR code\`:

**a. `1a_import_Busch2024_to_SMDAMAGE.py`**
Reads `Input\*.dta`, applies Griscom area screens and permanence buffers,
selects the least-cost reforestation option per pixel, and writes one CSV
per contract length (`undiscounted_contracts_020.csv` … `_120.csv`) to
`Output\Databases\`.
_Warning: takes over an hour and uses substantial memory; a restart option is built in._

**b. `2_k_means_carbon_removal.py`**
Reads those CSVs and clusters pixels by carbon removal profile using k-means.
Writes assignments, centers, and overall CSVs to `Output\Kmeans_temp_files\`.

**c. `3_import_k_means_csv_to_sqlite.py`**
Loads pixel bids and cluster carbon schedules into
`Output\Databases\Busch2024_to_SMDAMAGE.sqlite`, creating tables
`Pixel_bids` and `cluster_carbon_schedules_{years}` for each contract length.

**d. `4_move_Busch_data_to_SMDAMAGE.py`**
Reads `Pixel_bids` and builds `cluster_forestry_bid_curves_{years}`
supply-curve tables (one per contract length and discount rate)
in the same SQLite file.

The end product is: Busch2024/Output/Databases/Busch2024_to_SMDAMAGE.sqlite

The path to this file is set in `BUSCH_DB_DEFAULT` in `create_database.py`,
or overridden at runtime via the environment variable `BUSCH_SMDAMAGE_SQLITE`.

#### 3. Install and configure Hector

Download the Hector v2.0.1 Windows binary from the
[Hector releases page](https://github.com/JGCRI/hector/releases).
Set the `HECTOR_DIR` path constant at the top of
`SMDAMAGE revenue neutral/hector_interface.py` to point to your local Hector directory.

#### 4. Generate Hector pulse-response data

Run `hector_interface.py` once to produce
`Data/Calibrated_pulses_by_chemical_2025.txt`. This file captures the marginal
temperature response to a unit pulse of each greenhouse gas under RCP2.6. You only
need to do this once unless you change the climate scenario or Hector version.

#### 5. Build the SMDAMAGE input database

Confirm the non-forestry CSV bidder files are present in `Data/`:
`Agriculture_bids.csv`, `Seaweed_bids.csv`, `MtC_bid_steps.csv`,
`CH4_bid_steps.csv`, `N2O_bid_steps.csv`,
`C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv`,
`Forestry_bid_steps.csv`, `Forestry_sequestration.csv`.
Source these from `Sources of data for SMDAMAGE 2026.xlsx` and the
literature (see [`data_sources.txt`](data_sources.txt)).

From the `SMDAMAGE revenue neutral/` directory:

```powershell
python create_database.py
```

This reads the `Data/` CSV files and imports forestry bidder data from
`Busch2024_to_SMDAMAGE.sqlite`, producing `Data/smdamage_data.db`.

#### 6. Run experiments

From the `SMDAMAGE revenue neutral/` directory:

```powershell
python experiments.py
```

---

## Running Experiments

`experiments.py` runs the full paper experiment sequence — allow a full day.
Each experiment:
1. Constructs a `Scenario` (discount rate, temperature target, τ surcharge, etc.).
2. Solves the SMDAMAGE LP via `smdamage_models.py`.
3. Runs Hector on the SMDAMAGE solution to get a temperature trajectory.
4. Calibrates warming-per-tonne (Wpt) factors and re-solves with updated values.

Results are written to `Output/smdamage_solutions.db`, with graphs and summary text files in `Output/`.

To inspect bid prices without running experiments:

```powershell
python check_prices.py
```

---

## Input Data Sources

See [`data_sources.txt`](data_sources.txt) for full citations and bid-curve construction
notes for each bidder type (Carbon, CH4, N2O, F-gases, Agriculture, Seaweed, Forestry).

---

## Key Parameters

Critical scenario parameters (set in `defaults_and_utilities.py` and `experiments.py`):

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `discount_rate` | 0.03 | Annual discount rate |
| `initial_temperature` | ~1014 (thousandths °C) | Starting temperature anomaly |
| `tau` | 1.7 | Emitter surcharge multiplier for drawdown (SMDAMAGE\_1/2) |
| `BeginConstraintYear` | 2125 | Year by which warming target must be met |
| `is_revenue_neutral` | True | Whether emitters fund removers directly |

---

## References

**This model:**
Raffensperger, J. F. (2021, corrected 2024). *A simultaneous market design for
emissions and sequestration.* [journal/preprint TBD]

**Forestry data:**
Busch, J., et al. (2024). Cost-effectiveness of natural forest regeneration and
plantations for climate mitigation. *Nature Climate Change* (or similar — cite the
Zenodo replication deposit).

**Climate model:**
Hartin, C. A., et al. (2015). A simple object-oriented and open-source model for
scientific and policy analyses of the global climate system. *Geoscientific Model
Development*, 8, 939–955. https://doi.org/10.5194/gmd-8-939-2015

**Non-CO2 abatement costs:**
Harmsen, J. H. M., et al. (2015). How many non-CO2 greenhouse gas mitigation
measures would we need to achieve the 2°C target? *Climate Policy*.

---

## License

MIT License. See [LICENSE](LICENSE).

## Contact

John F. Raffensperger
john.raffensperger@gmail.com
https://john.raffensperger.org
