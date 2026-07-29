import sqlite3
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import database_interface
import defaults_and_utilities

SOLUTIONS_DB = os.path.join(SCRIPT_DIR, "Output", "smdamage_solutions.db")

# Using this just to analyze prices.
def get_bid_and_price_info(scenario_id, bidder, year):
    """Print all bid-step objective coefficients and the vpt dual price for a given
    scenario_id, bidder, and year.  Coefficients are calculated on the fly from
    smdamage_data.db, matching the formula used in the SMDAMAGE model."""
    conn = sqlite3.connect(SOLUTIONS_DB)
    cursor = conn.cursor()

    # Retrieve discount_rate for this scenario
    cursor.execute("SELECT discount_rate FROM scenarios WHERE id = ?", (scenario_id,))
    row = cursor.fetchone()
    if row is None:
        print(f"Scenario {scenario_id} not found in smdamage_solutions.db.")
        conn.close()
        return
    discount_rate = row[0]

    # Retrieve vpt dual price and vpt value
    cursor.execute("SELECT dual_price FROM vpt_dual_prices WHERE scenario_id = ? AND bidder = ? AND year = ?", (scenario_id, bidder, float(year)),)
    dp_row = cursor.fetchone()
    dual_price = dp_row[0] if dp_row else None

    cursor.execute("SELECT value FROM results WHERE scenario_id = ? AND bidder = ? AND year = ?", (scenario_id, bidder, float(year)),)
    vpt_row = cursor.fetchone()
    vpt_value = vpt_row[0] if vpt_row else None
    conn.close()

    # Calculate objective coefficients from smdamage_data.db
    curve = database_interface.get_bids(bidder)
    bidders_info = {b['bidder_name']: b for b in database_interface.get_bidders()}
    start_year = defaults_and_utilities.getStartYear()
    inflate = defaults_and_utilities.inflate_2020_to_2025()
    df = 1.0 / ((1.0 + discount_rate) ** (float(year) - start_year))

    print(f"Scenario {scenario_id} | bidder: {bidder} | year: {year}")
    print(f"  discount_rate: {discount_rate}  start_year: {start_year}  inflate: {inflate}")
    print(f"  vpt value: {vpt_value}  dual price: {dual_price}")
    print(f"  {'step':>5}  {'price_per_unit':>16}  {'qty':>12}  {'cumulative_qty':>16}  {'obj_coeff (inflated)':>22}")
    is_remover = bidders_info[bidder]['class'].lower() == 'remover'
    cumulative_qty = [0.0] * len(curve)
    running = 0.0
    if is_remover:
        for idx in range(len(curve)):
            running += curve[idx][1]
            cumulative_qty[idx] = running
    else:
        for idx in range(len(curve) - 1, -1, -1):
            running += curve[idx][1]
            cumulative_qty[idx] = running
    for idx, (price, qty) in enumerate(curve):
        coeff = price * inflate * df
        if bidders_info[bidder]['units'] == 'kt': coeff /= 1000.0
        print(f"  {idx:>5}  {price:>16.6f}  {qty:>12.4f}  {cumulative_qty[idx]:>16.4f}  {coeff:>22.8f}")

# get_bid_and_price_info(scenario_id=1, bidder="Agriculture", year=2102.0)

# Use the specific path where the 22MB file is
db_path = r'c:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\SMDAMAGE revenue neutral\SMDAMAGE for Git\SMDAMAGE revenue neutral\Output\smdamage_solutions.db'
if not os.path.exists(db_path):
    print(f"FAILED TO FIND {db_path}")
else:
    print(f"Connecting to {db_path}, size {os.path.getsize(db_path)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    print("Tables in smdamage_solutions.db:")
    tables = cursor.fetchall()
    for row in tables:
        print(row)
        if row[0] == 'accepted_bids':
            cursor.execute('SELECT COUNT(*) FROM accepted_bids')
            print(f"  Count in accepted_bids: {cursor.fetchone()[0]}")
        if row[0] == 'vpt_dual_prices':
            cursor.execute('SELECT COUNT(*) FROM vpt_dual_prices')
            print(f"  Count in vpt_dual_prices: {cursor.fetchone()[0]}")
    conn.close()
