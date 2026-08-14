import sqlite3
conn = sqlite3.connect('smdamage_solutions.db')
rows = conn.execute("SELECT id, name, discount_rate, tau, is_revenue_neutral, is_removal_luc, use_updated_Wpt, is_land_constraint_implicit, calibration_scenario FROM scenarios ORDER BY id").fetchall()
print(f"{'id':>4}  {'name':<22}  {'disc':>5}  {'tau':>5}  {'rev_neut':>8}  {'luc':>3}  {'upd_W':>5}  {'impl':>4}  {'cal_sc':>6}")
for r in rows:
    print(f"{r[0]:>4}  {str(r[1]):<22}  {str(r[2]):>5}  {str(r[3]):>5}  {str(r[4]):>8}  {str(r[5]):>3}  {str(r[6]):>5}  {str(r[7]):>4}  {str(r[8]):>6}")
conn.close()
