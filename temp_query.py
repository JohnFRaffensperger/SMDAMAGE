import sqlite3
db = r"c:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\SMDAMAGE revenue neutral\SMDAMAGE for Git\SMDAMAGE revenue neutral\Output\smdamage_solutions.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for sid in (14, 26):
    cur.execute("SELECT year, value FROM scenario_series WHERE scenario_id=? AND series_name LIKE '%actual temp%' AND year BETWEEN 2124.9 AND 2125.1 ORDER BY year", (sid,))
    for r in cur.fetchall(): print(f"actual temp sid={sid} year={r['year']} val={round(r['value'],3)}")

cur.execute("SELECT year, value FROM scenario_series WHERE scenario_id=26 AND series_name LIKE '%taxed temp%' AND year BETWEEN 2124.9 AND 2125.1 ORDER BY year")
for r in cur.fetchall(): print(f"taxed temp sid=26 year={r['year']} val={round(r['value'],3)}")

emitters = {'C2F6','CF4','CH4','Carbon','HFC125','HFC134a','HFC143a','N2O','SF6'}
for sid in (14, 26):
    cur.execute("SELECT bidder, SUM(quantity_value) as tq, AVG(dual_price) as ap FROM scenario_bidder_year WHERE scenario_id=? AND year>=2025 AND year<=2125 GROUP BY bidder ORDER BY tq DESC", (sid,))
    print(f"--- scenario {sid} ---")
    for r in cur.fetchall():
        tag = 'E' if r['bidder'] in emitters else 'R'
        print(f"  {tag} {r['bidder']}: qty={round(r['tq'],1)}, avg_price={round(r['ap'],2)}")

conn.close()
