#!/usr/bin/env python3
"""Parity checks for one scenario in smdamage_solutions.db.

Usage:
    python check_solution.py <scenario_id>

Checks:
1) temperature_output.csv rows vs temperature_series table (same scenario_id)
2) SMDAMAGE_soln_*.csv rows vs scenario_bidder_year table (same scenario_id)
3) SMDAMAGE_soln_*.csv temperature column vs scenario_series actual-temp rows
"""

import csv
import os
import sqlite3
import sys

TOL = 1e-6
ROOT = os.path.dirname(os.path.abspath(__file__))
SOLUTIONS_DB = os.path.join(ROOT, "Output", "smdamage_solutions.db")
TEMP_CSV = os.path.join(ROOT, "Output", "temperature_output.csv")


def _to_float(x):
    if x is None:
        return None
    if isinstance(x, float):
        return x
    s = str(x).strip()
    if s == "" or s == ".":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _almost_equal(a, b, tol=TOL):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _load_scenario(conn, scenario_id):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def _load_temperature_series(conn, scenario_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT source, year, value FROM temperature_series WHERE scenario_id = ?",
        (scenario_id,),
    )
    out = {}
    for source, year, value in cur.fetchall():
        out.setdefault(source, {})[float(year)] = _to_float(value)
    return out


def _load_temperature_csv_rows_for_experiment(experiment_name):
    if not os.path.exists(TEMP_CSV):
        return {}
    with open(TEMP_CSV, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return {}

    header = rows[0]
    years = [_to_float(y) for y in header[2:]]
    out = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        source, experiment = row[0], row[1]
        if experiment != experiment_name:
            continue
        year_map = {}
        for i, y in enumerate(years):
            if y is None:
                continue
            value = _to_float(row[i + 2] if i + 2 < len(row) else None)
            year_map[y] = value
        out[source] = year_map
    return out


def _get_solution_csv_path(conn, scenario_id):
    cur = conn.cursor()
    cur.execute(
        """SELECT artifact_path FROM scenario_artifacts
        WHERE scenario_id = ? AND artifact_type = 'smdamage_soln_csv'
        ORDER BY id DESC LIMIT 1""",
        (scenario_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    path = row[0]
    if not path:
        return None
    path = os.path.normpath(path)
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    return path


def _parse_solution_csv(path):
    with open(path, newline="") as f:
        lines = list(csv.reader(f))

    if len(lines) < 3:
        return [], {}, {}

    header = lines[1]
    data_rows = lines[2:]

    first_pct = None
    for i, col in enumerate(header):
        if "% max bid" in col:
            first_pct = i
            break
    if first_pct is None:
        raise ValueError("Could not parse solution CSV header: missing '% max bid' columns")

    pollutant_cols = header[1:first_pct]
    pollutants = [c.rsplit(" ", 1)[0] for c in pollutant_cols]
    n = len(pollutants)

    bidder_year = {}
    temp_by_year = {}

    for row in data_rows:
        if not row:
            continue
        year = _to_float(row[0])
        if year is None:
            continue

        for i, bidder in enumerate(pollutants):
            qty = _to_float(row[1 + i] if 1 + i < len(row) else None)
            pct = _to_float(row[1 + n + i] if 1 + n + i < len(row) else None)
            dual = _to_float(row[1 + 2 * n + i] if 1 + 2 * n + i < len(row) else None)
            if qty is None and pct is None and dual is None:
                continue
            bidder_year[(bidder, year)] = (qty, pct, dual)

        temp_col = 1 + 3 * n
        temp_by_year[year] = _to_float(row[temp_col] if temp_col < len(row) else None)

    return pollutants, bidder_year, temp_by_year


def _load_scenario_bidder_year(conn, scenario_id):
    cur = conn.cursor()
    cur.execute(
        """SELECT bidder, year, quantity_value, pct_max_bid, dual_price
        FROM scenario_bidder_year WHERE scenario_id = ?""",
        (scenario_id,),
    )
    out = {}
    for bidder, year, q, pct, dual in cur.fetchall():
        out[(bidder, float(year))] = (_to_float(q), _to_float(pct), _to_float(dual))
    return out


def _load_scenario_series(conn, scenario_id, series_name):
    cur = conn.cursor()
    cur.execute(
        "SELECT year, value FROM scenario_series WHERE scenario_id = ? AND series_name = ?",
        (scenario_id, series_name),
    )
    return {float(y): _to_float(v) for y, v in cur.fetchall()}


def check_temperature_output_parity(conn, scenario):
    db_data = _load_temperature_series(conn, scenario["id"])
    csv_data = _load_temperature_csv_rows_for_experiment(scenario["name"])

    for source, year_map in db_data.items():
        if source not in csv_data:
            return False, f"missing source in temperature_output.csv: {source}"
        for year, value in year_map.items():
            csv_val = csv_data[source].get(year)
            if not _almost_equal(value, csv_val):
                return False, f"temperature mismatch source={source}, year={year}, db={value}, csv={csv_val}"

    return True, "matched all DB temperature_series rows"


def check_bidder_year_parity(conn, scenario):
    path = _get_solution_csv_path(conn, scenario["id"])
    if not path or not os.path.exists(path):
        return False, "missing solution CSV artifact path for scenario"

    _, csv_by, _ = _parse_solution_csv(path)
    db_by = _load_scenario_bidder_year(conn, scenario["id"])

    for key, db_vals in db_by.items():
        csv_vals = csv_by.get(key)
        if csv_vals is None:
            return False, f"missing bidder-year in solution CSV: {key}"
        if not _almost_equal(db_vals[0], csv_vals[0]):
            return False, f"quantity mismatch {key}: db={db_vals[0]}, csv={csv_vals[0]}"
        if not _almost_equal(db_vals[1], csv_vals[1]):
            return False, f"pct_max_bid mismatch {key}: db={db_vals[1]}, csv={csv_vals[1]}"
        if not _almost_equal(db_vals[2], csv_vals[2]):
            return False, f"dual_price mismatch {key}: db={db_vals[2]}, csv={csv_vals[2]}"

    return True, "matched all DB scenario_bidder_year rows"


def check_actual_temperature_series_parity(conn, scenario):
    path = _get_solution_csv_path(conn, scenario["id"])
    if not path or not os.path.exists(path):
        return False, "missing solution CSV artifact path for scenario"

    _, _, csv_temp = _parse_solution_csv(path)
    source = "SMDAMAGE actual temp calibrated" if int(scenario["use_updated_Wpt"]) else "SMDAMAGE actual temp uncalibrated"
    db_temp = _load_scenario_series(conn, scenario["id"], source)

    for year, value in csv_temp.items():
        db_val = db_temp.get(year)
        if not _almost_equal(value, db_val):
            return False, f"scenario_series mismatch source={source}, year={year}, db={db_val}, csv={value}"

    return True, f"matched scenario_series source '{source}' to solution CSV temp column"


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_solution.py <scenario_id>")
        sys.exit(1)

    scenario_id = int(sys.argv[1])
    if not os.path.exists(SOLUTIONS_DB):
        print(f"FAIL: solutions DB not found at {SOLUTIONS_DB}")
        sys.exit(2)

    conn = sqlite3.connect(SOLUTIONS_DB)
    scenario = _load_scenario(conn, scenario_id)
    if not scenario:
        print(f"FAIL: scenario_id {scenario_id} not found")
        conn.close()
        sys.exit(2)

    checks = [
        ("temperature_output_csv", check_temperature_output_parity),
        ("scenario_bidder_year_vs_solution_csv", check_bidder_year_parity),
        ("scenario_series_actual_temp_vs_solution_csv", check_actual_temperature_series_parity),
    ]

    failed = 0
    print(f"Scenario {scenario_id}: {scenario['name']}")
    for label, fn in checks:
        ok, detail = fn(conn, scenario)
        status = "PASS" if ok else "FAIL"
        print(f"{status}: {label} - {detail}")
        if not ok:
            failed += 1

    conn.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
