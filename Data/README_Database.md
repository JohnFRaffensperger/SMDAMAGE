# SMDAMAGE Database Build And Busch 2024 Import

This README documents how `create_database.py` builds `smdamage_data.db` and how forestry data is copied from the Busch 2024 SQLite database.

## Files

- `SMDAMAGE revenue neutral/create_database.py`: builds `Data/smdamage_data.db`.
- `SMDAMAGE revenue neutral/database_interface.py`: query helpers used by SMDAMAGE.
- `Data/smdamage_data.db`: runtime database used by `SMDAMAGE revenue neutral.py`.

## What Is Imported

`create_database.py` does two things:

1. Loads non-forestry bidders from CSV files in `Data/`.
2. Imports forestry bidders, bids, and removal schedules from Busch 2024 SQLite:
     - source DB default path is set in `BUSCH_DB_DEFAULT`
     - optional override via environment variable `BUSCH_SMDAMAGE_SQLITE`

## Forestry Copy Process (Busch -> smdamage_data.db)

The function `load_forestry_from_busch_sqlite()` performs one transaction that:

1. Creates forestry bidders from Busch `(rotation_year, cluster_index)` groups.
2. Stores bidder max area in `forestry_bidder_metadata.available_area_mhectares`.
3. Imports forestry bid curves from `forestry_bid_curves` for **all discount rates** into `bids`.
4. Imports `carbon_removal_schedules` into `forestry_removal`, but only rows inside each bidder contract window.
5. Verifies any rows beyond contract window are zero (raises error if non-zero).

## Key Schema Notes

- `bids` includes `discount_rate`.
    - non-forestry rows: `discount_rate = NULL`
    - forestry rows: `discount_rate` copied from Busch
- `forestry_bidder_metadata` includes:
    - `bidder`
    - `rotation_year`
    - `cluster_index`
    - `available_area_mhectares`

This allows `SMDAMAGE revenue neutral.py` to pull bids for the scenario discount rate directly from `smdamage_data.db`.

## Build Steps

From repository root:

```powershell
# Optional: override Busch source path for this shell session
$env:BUSCH_SMDAMAGE_SQLITE = 'C:\Users\johnr\Documents\Work documents\2 Research\Global warming\Numerical Simulation\Busch2024\Output\Databases\Busch2024_to_SMDAMAGE.sqlite'

# Rebuild DB (delete existing DB first)
Remove-Item .\Data\smdamage_data.db -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe '.\SMDAMAGE revenue neutral\create_database.py'
```

## Verification Queries

Use these checks after rebuilding:

```python
import sqlite3
con = sqlite3.connect(r"Data/smdamage_data.db")
cur = con.cursor()

print("discount rates in bids:", cur.execute("""SELECT discount_rate, COUNT(*) FROM bids GROUP BY discount_rate ORDER BY discount_rate""").fetchall())
print("forestry metadata rows:", cur.execute("SELECT COUNT(*) FROM forestry_bidder_metadata").fetchone()[0])
print("sample max areas:", cur.execute("""SELECT bidder, available_area_mhectares FROM forestry_bidder_metadata ORDER BY bidder LIMIT 5 """).fetchall())
print("sample forestry bids with rate:", cur.execute("""SELECT bidder, discount_rate, price_per_unit, quantity_units FROM bids WHERE bidder LIKE 'Forestry_%' ORDER BY bidder,  discount_rate LIMIT 10""").fetchall())

con.close()
```

## Troubleshooting

- `Busch SQLite not found`:
    - set `BUSCH_SMDAMAGE_SQLITE` or update `BUSCH_DB_DEFAULT`.
- `Found non-zero forestry_removal values beyond contract year`:
    - source schedules violate contract-window assumption; inspect reported bidder/year examples.
- `Database already exists`:
    - delete `Data/smdamage_data.db` before rerunning `create_database.py`.
