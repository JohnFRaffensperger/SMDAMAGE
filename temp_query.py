import sqlite3
db = r"c:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\SMDAMAGE revenue neutral\SMDAMAGE for Git\SMDAMAGE revenue neutral\Output\smdamage_solutions.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, name, solution_datetime FROM scenarios ORDER BY id")
for r in cur.fetchall(): print(r['id'], r['solution_datetime'], r['name'])
conn.close()
