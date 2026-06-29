# table_to_html.py | JFR Created 2026-03-23. Use this handy utility to run SQLite queries and view the results in HTML. It also exports CSVs.

import csv
from ctypes import *
from pathlib import Path
import sys
import time
import pandas, pandas.io.sql, sqlite3
import sqlite3

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "Output"
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path: sys.path.insert(0, _script_dir)
if str(OUTPUT_DIR) not in sys.path: sys.path.insert(0, str(OUTPUT_DIR))
import LocalHTML

SCRIPT_DIR = Path(__file__).resolve().parent
SOLUTIONS_DB_FILE = SCRIPT_DIR / "Output" / "smdamage_solutions.db"
DATA_DB_FILE = SCRIPT_DIR.parent / "Data" / "smdamage_data.db"

DEFAULT_DB_FILE = OUTPUT_DIR / "Busch2024_dta_outputs.sqlite"
DEFAULT_HTML_FILE = OUTPUT_DIR / "mytable.html"
DEFAULT_QUERY_CSV = OUTPUT_DIR / "myQueryOutput.csv"
DEFAULT_AGGREGATE_CSV = OUTPUT_DIR / "myAggregateOutput.csv"
DEFAULT_EXPORT_CSV = OUTPUT_DIR / "yourquery.csv"
PRIMARY_TABLE_NAME = "Busch2024_dta_outputs"

def getTableNameFromQueryString(query): # Tries to get the table name from the query string.
	start = query.find(' from ')
	substring = query[start+6:]
	end = min(substring.find('\t'), substring.find(' '))
	return query[start+6:start+6+end]

def makeHTML(rows, fieldIndices = None):
	outputfilename = DEFAULT_HTML_FILE
	if not rows:
		print ("No rows")
		return

	if fieldIndices:
		fieldnames = ['']*len(rows[0])
		for field in fieldIndices: fieldnames[fieldIndices[field]] = field
		with open(outputfilename, 'w') as f: f.write('<html>' + LocalHTML.table(rows, header_row = fieldnames) + '</html>')
	else:
		with open(outputfilename, 'w') as f: f.write('<html>' + LocalHTML.table(rows) + '</html>')
	print ("Wrote %i rows to %s." % (len(rows), outputfilename))
	return

def dumpQueryToCSV(query, databaseFileName = str(DEFAULT_DB_FILE)):
	con = sqlite3.connect(databaseFileName)
	table = pandas.io.sql.read_sql(query, con)
	table.to_csv(DEFAULT_EXPORT_CSV, index=False)
	con.close()
#dumpQueryToCSV("select * from mymaster limit 10", "eda.db")

def saveQueryToCSV (query, optionalFileName = str(DEFAULT_QUERY_CSV)):
	con = sqlite3.connect(str(DEFAULT_DB_FILE))
	cursor = con.cursor()
	cursor.execute(query)

	with open(optionalFileName, "w", newline='') as csv_file:
		csv_writer = csv.writer(csv_file, quoting=csv.QUOTE_NONNUMERIC)
		csv_writer.writerow([i[0] for i in cursor.description]) # write headers
		csv_writer.writerows(cursor)
	con.commit()
	con.close()

# saveQueryToCSV ("select sum(area) as t_area, crop_npv_oppcost from maps_atg_schema group by crop_npv_oppcost")
# saveQueryToCSV ("select cast(crop_npv_oppcost as integer) as crop_npv_oppcost_int, sum(area) as t_area from maps_atg_schema where crop_npv_oppcost < 2000 group by cast(crop_npv_oppcost as integer)")
# saveQueryToCSV ("select cast(crop_npv_oppcost as integer) as crop_npv_oppcost_int, sum(area) as t_area from maps_atg_schema group by cast(crop_npv_oppcost as integer)")
# saveQueryToCSV ("select sum(area)	 as t_area from maps_atg_schema", 'totalarea.txt')

def show(tablename): tableToHtml("select * from %s limit 500" % tablename)

def resolve_query_table_name(query, databaseFileName = str(DEFAULT_DB_FILE)):
	if "maps_atg_schema" not in query: return query
	return query.replace("maps_atg_schema", PRIMARY_TABLE_NAME)

def tableToHtml(query, optionalFileName = str(DEFAULT_HTML_FILE), talk=True, databaseFileName = str(DEFAULT_DB_FILE), transpose = False):
	''' This function does the query, and writes the result to optionalFileName.
		It returns a dictionary of the field names and their indices in the rows,
		and the rows themselves.
		Optionally, it can look up some field name descriptions and field values.
	'''
	# 1. Run the requested query.
	if not Path(databaseFileName).exists():
		print("Sorry, database file '%s' does not exist." % databaseFileName) # Don't create a zero size database if it doesn't exit.
		return
	query = resolve_query_table_name(query, databaseFileName)
	# uri=True enables SQLite URI syntax; mode=ro opens read-only (ro), alternatives: rw (read-write, no create), rwc (read-write-create, default), memory (in-memory).
	con = sqlite3.connect(f"file:{databaseFileName}?mode=ro", uri=True) # Don't allow writing to the database.
	mycursor = con.cursor()
	execute_start = time.perf_counter()
	try: rowset = mycursor.execute(query)
	except Exception as e:
		print("Sorry, query '%s' failed, error %s." % (query, str(e)))
		con.close()
		return
	execute_elapsed = time.perf_counter() - execute_start
	if talk: print ("Finished execute in %.2f s, now fetching rows." % execute_elapsed)

	if rowset:
		fetch_start = time.perf_counter()
		fieldnames = [description[0] for description in rowset.description]
		fieldNameDict = {description[0]: desc_index for (desc_index, description) in enumerate(rowset.description)}
		rowList = list(rowset)
		counter = len(rowList)
		fetch_elapsed = time.perf_counter() - fetch_start
		if talk: print ("Finished fetch in %.2f s, now making HTML." % fetch_elapsed)
	con.close()

	# 4. Write the HTML file, transposing if requested.
	tablename = getTableNameFromQueryString(query)
#	print("tablename = ", tablename)
	write_start = time.perf_counter()
	with open(optionalFileName, 'w', encoding='utf-8') as htmlfile:
		if transpose:
			rowList.insert(0, fieldnames) # Put header at top.
			rowList = list(map(list, zip(*rowList))) # Transpose.
			rowList = sorted(rowList, key=lambda x:x[0].upper()) # sort by field name.
			htmlfile.write('<html><p>'+query+', ' + str(counter) + ' rows. </p>' + LocalHTML.table(rowList) + "</html>")
		else: htmlfile.write('<html><title>' + tablename + '</title><body><p>'+query+', ' + str(counter) + ' rows. </p>' + str(LocalHTML.Table(rowList, header_row = fieldnames)) + "</body></html>")
	write_elapsed = time.perf_counter() - write_start
	if talk: print ("Finished HTML write in %.2f s." % write_elapsed)
	print ("Found " + str(counter) + " rows to %s." % optionalFileName)
	return fieldNameDict, rowList

def printQueryRows(query, databaseFileName = str(DEFAULT_DB_FILE)): print((result[1] if (result := tableToHtml(query, optionalFileName='NUL', talk=False, databaseFileName=databaseFileName)) else []))

def intermediate_bid_steps(scenario_id=21):
	"""Find (bidder, year) pairs where the highest nonzero bid step is neither
	bid step 0 nor the largest step in the full bid curve for that bidder."""
	if not SOLUTIONS_DB_FILE.exists(): print(f"Solutions DB not found: {SOLUTIONS_DB_FILE}"); return
	if not DATA_DB_FILE.exists():     print(f"Data DB not found: {DATA_DB_FILE}");     return

	with sqlite3.connect(str(SOLUTIONS_DB_FILE)) as conn:
		row = conn.execute("SELECT discount_rate FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
		if row is None: print(f"Scenario {scenario_id} not found in solutions DB."); return
		discount_rate = row[0]
		active_df = pandas.read_sql_query(
			"SELECT bidder, CAST(year AS INTEGER) AS year, MAX(bid_step) AS max_active "
			"FROM variables WHERE scenario_id=? AND value > 0 GROUP BY bidder, year",
			conn, params=(scenario_id,))

	with sqlite3.connect(str(DATA_DB_FILE)) as conn:
		curve_df = pandas.read_sql_query(
			"SELECT bidder, COUNT(*) - 1 AS max_curve_step FROM bids "
			"WHERE discount_rate IS NULL OR ABS(discount_rate - ?) < 1e-12 GROUP BY bidder",
			conn, params=(discount_rate,))

	merged = active_df.merge(curve_df, on='bidder')
	result = merged[(merged['max_active'] > 0) & (merged['max_active'] < merged['max_curve_step'])].sort_values(['bidder', 'year'])

	html_file = SOLUTIONS_DB_FILE.parent / f"intermediate_bid_steps_{scenario_id}.html"
	rows = list(result.itertuples(index=False, name=None))
	with open(html_file, 'w', encoding='utf-8') as f:
		f.write(f'<html><title>Intermediate bid steps sc{scenario_id}</title><body>')
		f.write(f'<p>Bidders where highest active bid step &gt; 0 and &lt; max curve step, scenario {scenario_id} (discount_rate={discount_rate}). {len(rows)} rows.</p>')
		f.write(str(LocalHTML.Table(rows, header_row=list(result.columns))))
		f.write('</body></html>')
	print(f"Found {len(rows)} rows. Wrote to {html_file}")
	return result

intermediate_bid_steps(scenario_id=21)
tableToHtml("SELECT s.id, s.name, s.discount_rate, s.initial_temp, s.tau, s.solver_status, s.objective_value, s.solution_datetime FROM scenarios s ORDER BY s.id",
			optionalFileName=str(SOLUTIONS_DB_FILE.parent / "scenarios.html"),
			databaseFileName=str(SOLUTIONS_DB_FILE))

