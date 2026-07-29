import sqlite3
db = r"c:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\SMDAMAGE revenue neutral\SMDAMAGE for Git\SMDAMAGE revenue neutral\Output\smdamage_solutions.db"
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT id, name, land_rent, net_revenue, objective_value, solution_datetime FROM scenarios ORDER BY id DESC LIMIT 3")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
