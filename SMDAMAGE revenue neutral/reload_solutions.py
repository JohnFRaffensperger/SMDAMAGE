"""
Rebuilds smdamage_solutions.db from SMDAMAGE_soln_*.csv and SMDAMAGE_*.pkl files
in the Output directory.

Tables populated:
  scenarios        - one row per scenario, from CSV metadata line
  results          - vpt quantities per (bidder, year), from PKL (preferred) or CSV qty columns
  vpt_dual_prices  - constraint pi values per (bidder, year), from CSV "$M/unit" columns
  binding_constraints - Capt(t) temperature constraint duals, from CSV "Capt pi" column
  accepted_bids    - Populated by reconstructing steps from vpt value and bid curves
"""
import sqlite3
import pickle
import pandas as pd
import os
import re
from pulp import value as pulp_value

# sys.path.append(PROJECT_ROOT)
import database_interface
import defaults_and_utilities

OUTPUT_DIR = r"c:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\SMDAMAGE revenue neutral\SMDAMAGE for Git\SMDAMAGE revenue neutral\Output"
SOLUTIONS_DB = os.path.join(OUTPUT_DIR, "smdamage_solutions.db")

def init_db():
    if os.path.exists(SOLUTIONS_DB): os.remove(SOLUTIONS_DB)
    conn = sqlite3.connect(SOLUTIONS_DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE scenarios (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, discount_rate REAL, initial_temp REAL, tau REAL, is_revenue_neutral INTEGER, is_removal_luc INTEGER, use_updated_Wpt INTEGER, solver_status TEXT, net_revenue REAL, land_rent REAL, objective_value REAL, solution_datetime TEXT)""")
    c.execute("""CREATE TABLE variables (scenario_id INTEGER NOT NULL, bidder TEXT NOT NULL, year REAL NOT NULL, bid_step INTEGER NOT NULL, value REAL NOT NULL, PRIMARY KEY (scenario_id, bidder, year, bid_step), FOREIGN KEY (scenario_id) REFERENCES scenarios(id)) WITHOUT ROWID""")
    c.execute("CREATE INDEX idx_var_frontier ON variables(scenario_id, bidder, year)")
    c.execute("""CREATE TABLE constraint_duals (scenario_id INTEGER NOT NULL, constraint_name TEXT NOT NULL, pi REAL NOT NULL, PRIMARY KEY (scenario_id, constraint_name), FOREIGN KEY (scenario_id) REFERENCES scenarios(id)) WITHOUT ROWID""")
    c.execute("CREATE INDEX idx_cdual_scenario ON constraint_duals(scenario_id)")
    conn.commit()
    return conn

def parse_filename(filename):
    name_match = re.search(r'SMDAMAGE_(?:soln_)?(.*?)(?:_disc_|$)', filename)
    name = name_match.group(1) if name_match else "unknown"
    disc_match = re.search(r'disc_([\d.]+)', filename)
    discount_rate = float(disc_match.group(1)) if disc_match else 0.03
    temp_match = re.search(r'temp0_([\d.]+)', filename)
    initial_temp = float(temp_match.group(1)) if temp_match else 0.0
    tau_match = re.search(r'_tau_([\d.]+)', filename)
    tau = float(tau_match.group(1)) if tau_match else 1.0
    is_rev_neutral = 1 if "3rd_payer" in filename else 0
    is_removal_luc = 1 if "luc_removal" in filename else 0
    use_updated_Wpt = 1 if "Wpt_fitted" in filename else 0
    return dict(name=name, discount_rate=discount_rate, initial_temp=initial_temp, tau=tau, is_revenue_neutral=is_rev_neutral, is_removal_luc=is_removal_luc, use_updated_Wpt=use_updated_Wpt)

def classify_columns(columns):
    """Split CSV columns into (qty, dual) bidder lists, skipping pct-max-bid and special cols."""
    qty_cols = []   # list of (col_name, bidder_name)
    dual_cols = []  # list of (col_name, bidder_name)
    for col in columns:
        if col in ('Year', 'temp change', 'Capt pi'): continue
        if '% max bid' in col: continue
        if '$M/' in col:
            bidder = col.split(' $M/')[0]
            dual_cols.append((col, bidder))
        else:
            # Format: "bidder_name units" — bidder is everything before the last word
            bidder = col.rsplit(' ', 1)[0]
            qty_cols.append((col, bidder))
    return qty_cols, dual_cols

def safe_float(val):
    """Return float or None if val is non-numeric (NaN, '.', empty string)."""
    try:
        v = float(val)
        return None if v != v else v  # NaN != NaN
    except (ValueError, TypeError): return None

def reload_solutions():
    conn = init_db()
    c = conn.cursor()

    # Pre-cache bid curves and metadata
    all_bidders_list = database_interface.get_bidders()
    bidders_info = {b['bidder_name']: b for b in all_bidders_list}
    bid_curves = {b['bidder_name']: database_interface.get_bids(b['bidder_name']) for b in all_bidders_list}
    start_year = defaults_and_utilities.getStartYear()

    # Build PKL map: scenario tag → file path
    pkl_map = {}
    for f in os.listdir(OUTPUT_DIR):
        if (f.startswith('SMDAMAGE_') and f.endswith('.pkl') and not f.endswith('_taxed_temps.pkl') and f != 'SMDAMAGE_fitted_Wpt.pkl'):
            tag = f[len('SMDAMAGE_'):-len('.pkl')]
            pkl_map[tag] = os.path.join(OUTPUT_DIR, f)

    csv_files = sorted(f for f in os.listdir(OUTPUT_DIR) if f.startswith('SMDAMAGE_soln_') and f.endswith('.csv'))
    print(f"Found {len(csv_files)} CSV files, {len(pkl_map)} PKL files.")

    for csv_file in csv_files:
        tag = csv_file[len('SMDAMAGE_soln_'):-len('.csv')]
        path = os.path.join(OUTPUT_DIR, csv_file)
        try:
            params = parse_filename(csv_file)

            # Parse metadata from first line
            with open(path, 'r') as f: meta_line = f.readline().strip()
            status_match = re.search(r'Solve status (\w+)', meta_line)
            status = status_match.group(1) if status_match else "Optimal"
            rev_match = re.search(r'Total revenue ([\d.eE+\-]+)', meta_line)
            total_revenue = float(rev_match.group(1)) if rev_match else None

            df = pd.read_csv(path, skiprows=1, header=0, low_memory=False)

            c.execute("""INSERT INTO scenarios (name, discount_rate, initial_temp, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, solver_status, net_revenue, land_rent, objective_value, solution_datetime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (params['name'], params['discount_rate'], params['initial_temp'],
                 params['tau'], params['is_revenue_neutral'], params['is_removal_luc'],
                 params['use_updated_Wpt'], status, total_revenue, None, None, "Reloaded"))
            scenario_id = c.lastrowid
            qty_cols, dual_cols = classify_columns(df.columns)

            # --- vpt totals: prefer PKL for precision, fall back to CSV qty columns ---
            qty_rows = []  # (bidder, year, total_val)
            if tag in pkl_map:
                with open(pkl_map[tag], 'rb') as f: pkl_data = pickle.load(f)
                for (bidder, year), val_obj in pkl_data.items():
                    val = pulp_value(val_obj) or 0.0
                    if val != 0.0: qty_rows.append((bidder, float(year), float(val)))
            else:
                for _, row in df.iterrows():
                    year = safe_float(row['Year'])
                    if year is None: continue
                    for col, bidder in qty_cols:
                        v = safe_float(row[col])
                        if v is not None and v != 0.0: qty_rows.append((bidder, year, v))

            # --- constraint_duals: Vpt dual prices from CSV "$M/unit" columns ---
            dual_rows = []  # (bidder, year, pi)
            for _, row in df.iterrows():
                year = safe_float(row['Year'])
                if year is None: continue
                for col, bidder in dual_cols:
                    v = safe_float(row[col])
                    if v is not None and v != 0.0: dual_rows.append((bidder, year, v))

            cdual_rows = [(scenario_id, f"Vpt({bidder},{year})", pi) for bidder, year, pi in dual_rows]
            if cdual_rows: c.executemany("INSERT INTO constraint_duals (scenario_id, constraint_name, pi) VALUES (?,?,?)", cdual_rows)

            # --- variables: reconstruct accepted bid steps from qty totals and Vpt duals ---
            duals_map = {(b, y): pi for b, y, pi in dual_rows}
            var_rows = []
            inflate = defaults_and_utilities.inflate_2020_to_2025()
            for bidder, year, total_val in qty_rows:
                curve = bid_curves.get(bidder, [])
                if not curve: continue
                dual_price = duals_map.get((bidder, year), 0.0)
                df_factor = 1.0 / ((1.0 + params['discount_rate'])**(year - start_year))
                is_kt = bidders_info.get(bidder, {}).get('units') == 'kt'
                threshold = -dual_price
                for idx, (price, qty) in enumerate(curve):
                    coeff = price * inflate * df_factor
                    if is_kt: coeff /= 1000.0
                    if coeff >= threshold - 1e-9:
                        var_rows.append((scenario_id, bidder, year, idx, 1.0))

            if var_rows: c.executemany("INSERT OR IGNORE INTO variables (scenario_id, bidder, year, bid_step, value) VALUES (?,?,?,?,?)", var_rows)
            print(f"  {csv_file}: {len(qty_rows)} vpt, {len(cdual_rows)} duals, {len(var_rows)} variables")

        except Exception as e:
            import traceback
            print(f"  ERROR {csv_file}: {e}")
            traceback.print_exc()

    conn.commit()
    conn.close()
    print("Database reload complete.")

if __name__ == "__main__":
    reload_solutions()
