	# SMDAMAGE SQLite Database Integration

This project creates an SQLite database from the CSV files in the [Data](Data/) directory and provides a clean Python interface for querying the data. This replaces direct CSV file reading with a more efficient database approach.

## 🗂️ Files Created

| File | Purpose |
|------|---------|
| `create_database.py` | Creates SQLite database from CSV files |
| `database_interface.py` | Python interface for querying the database |
| `database_example.py` | Example showing how to integrate with existing code |
| `smdamage_data.db` | The SQLite database (created when you run the scripts) |

## 📊 Database Structure

The database contains the following tables:

### Core Bid Data Tables
- **agriculture_bids** (114 records) - Agriculture bid prices and quantities
- **carbon_bids** (824 records) - Carbon bid steps with prices and quantities
- **seaweed_bids** (48 records) - Seaweed bid pricing data
- **ch4_bids** (402 records) - Methane bid steps
- **n2o_bids** (402 records) - Nitrous oxide bid steps

### Chemical Data Tables
- **c2f6_bids** (201 records) - C2F6 bid prices and quantities
- **cf4_bids** (201 records) - CF4 bid prices and quantities  
- **hfc125_bids** (201 records) - HFC125 bid prices and quantities
- **hfc134a_bids** (201 records) - HFC134a bid prices and quantities
- **hfc143a_bids** (201 records) - HFC143a bid prices and quantities
- **sf6_bids** (201 records) - SF6 bid prices and quantities
- **chemical_pulses** (36 records) - Pulse data with individual columns for each time step (value_001 to value_296)

*Note: Each chemical species is stored in its own table with consistent (price_per_kt, kt_per_year) schema. This decomposed structure allows for easier individual chemical analysis parallel to CH4 and N2O processing. The chemical_pulses table has been updated to store each data point in individual columns (value_001 through value_296) instead of comma-separated values.*

### Forestry Data Tables
- **forestry_bids_150** (200 records) - 150-year forestry contracts (all tree types)
- **forestry_bids_10** (200 records) - 10-year forestry contracts (all tree types)  
- **forestry_bids_24** (200 records) - 24-year forestry contracts (loblolly pine only)
- **forestry_bids_103** (200 records) - 103-year forestry contracts (ponderosa pine only)
- **forestry_bids_55** (200 records) - 55-year forestry contracts (black walnut only)
- **forestry_removal** (156 records) - Carbon removal rates by tree type and year

*Note: Forestry bid tables are now separated by contract duration for better organization and easier querying by specific contract terms.*

## 🚀 Quick Start

### 1. Create the Database

```bash
python create_database.py
```

This will:
- Read all CSV files from the `Data/` directory
- Create `smdamage_data.db` with organized tables
- Create indices for better query performance
- Show a summary of loaded data

### 2. Test the Database Interface

```bash
python database_interface.py
```

This runs tests to verify all query functions work correctly.

### 3. See Integration Example

```bash
python database_example.py
```

This demonstrates how to use the database in place of CSV file reading.

## 💻 Using the Database Interface

### Basic Usage

```python
import database_interface as db

# Get agriculture bid data
ag_bids = db.get_agriculture_bids()  # Returns [(price, quantity), ...]

# Get carbon bid data  
carbon_bids = db.get_carbon_bids()   # Returns [(price, quantity), ...]

# Get chemical pulse data
ffi_data = db.get_chemical_pulse_data('ffi_emissions')
print(f"FFI factor: {ffi_data['emission_factor']} {ffi_data['units']}")
print(f"Data points: {len(ffi_data['data_values'])}")
```

### Advanced Usage

```python
# Custom SQL queries
db_instance = db.get_db()
high_price_bids = db_instance.query_custom(
    "SELECT * FROM carbon_bids WHERE price_per_ton_c > ?", [100]
)

# Get database statistics
info = db_instance.get_database_info()
for table, count in info.items():
    print(f"{table}: {count} records")
```

### Available Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `get_agriculture_bids()` | `[(price, quantity), ...]` | Agriculture bid data |
| `get_carbon_bids()` | `[(price, quantity), ...]` | Carbon bid steps |
| `get_seaweed_bids()` | `[(price, quantity), ...]` | Seaweed bid data |
| `get_ch4_bids()` | `[(price, quantity), ...]` | Methane bid data |
| `get_n2o_bids()` | `[(price, quantity), ...]` | Nitrous oxide bids |
| `get_c2f6_bids()` | `[(price, quantity), ...]` | C2F6 bid data |
| `get_cf4_bids()` | `[(price, quantity), ...]` | CF4 bid data |
| `get_hfc125_bids()` | `[(price, quantity), ...]` | HFC125 bid data |
| `get_hfc134a_bids()` | `[(price, quantity), ...]` | HFC134a bid data |
| `get_hfc143a_bids()` | `[(price, quantity), ...]` | HFC143a bid data |
| `get_sf6_bids()` | `[(price, quantity), ...]` | SF6 bid data |
| `get_forestry_bids_150()` | `[tuple, ...]` | 150-year forestry contract bids |
| `get_forestry_bids_10()` | `[tuple, ...]` | 10-year forestry contract bids |
| `get_forestry_bids_24()` | `[tuple, ...]` | 24-year forestry contract bids |
| `get_forestry_bids_103()` | `[tuple, ...]` | 103-year forestry contract bids |
| `get_forestry_bids_55()` | `[tuple, ...]` | 55-year forestry contract bids |
| `get_forestry_bids()` | `[tuple, ...]` | Forestry pricing data |
| `get_forestry_removal()` | `[tuple, ...]` | Tree removal rates |
| `get_chemical_pulse_data(name)` | `dict` | Pulse data for specific chemical |
| `get_all_chemical_names()` | `[str, ...]` | List of available chemicals |

## 🔧 Integration with Existing Code

To integrate with your existing SMDAMAGE code:

### Instead of this CSV reading:
```python
# Old approach - reading CSV directly
with open('./data/Agriculture_bids.csv') as agfile:
    lines = [line.split(',') for line in agfile]
Bid_Q_Agriculture = [(float(line[0]), float(line[1])) for line in lines[1:]]
```

### Use this database approach:
```python
# New approach - using database
import database_interface as db
Bid_Q_Agriculture = db.get_agriculture_bids()
```

### Example: Modifying the `read_bids` function

Replace the CSV file reading sections in your `read_bids` function with database calls:

```python
def read_bids(scenario):
    # ... existing setup code ...
    
    # Replace CSV reading with database queries
    db_instance = db.get_db()
    
    # Agriculture
    agriculture_bids = db_instance.get_agriculture_bids()
    for t in AllBidPeriods:
        PT_set.add(('Agriculture', t))
        for bidstep, (price, quantity) in enumerate(agriculture_bids):
            APT_set.add((bidstep, 'Agriculture', t))
            Bapt[bidstep, 'Agriculture', t] = -price * scenario.discount_rate(t - StartYear)
            Uapt[bidstep, 'Agriculture', t] = quantity / float(hector_interface.getPeriodsPerYear())
    
    # ... continue for other data types ...
```

## ✅ Benefits

### 1. **Performance**
- Faster data loading (no CSV parsing)
- Indexed queries for better performance
- Reduced memory usage

### 2. **Data Integrity**
- Type checking and validation
- Consistent data format
- ACID compliance

### 3. **Flexibility**
- Custom SQL queries for complex analysis
- Easy data filtering and aggregation
- Simple data updates and maintenance

### 4. **Maintainability**
- Clean separation of data access logic
- Centralized data management
- Better error handling

## 🔍 Data Verification

The database preserves all original data from your CSV files:

- ✅ **Agriculture_bids.csv** → 57 records in `agriculture_bids` table
- ✅ **MtC_bid_steps.csv** → 412 records in `carbon_bids` table  
- ✅ **Seaweed_bids.csv** → 24 records in `seaweed_bids` table
- ✅ **C2F6_CF4_HFC125_HFC134a_HFC143a_SF6_bidsteps.csv** → 201 records in `chemical_bids` table
- ✅ **CH4_bid_steps.csv** → 201 records in `ch4_bids` table
- ✅ **N2O_bid_steps.csv** → 201 records in `n2o_bids` table
- ✅ **Forestry_bid_steps.csv** → 200 records in `forestry_bids` table
- ✅ **Forestry_sequestration.csv** → 156 records in `forestry_removal` table
- ✅ **Calibrated_pulses_by_chemical_2025.txt** → 36 records in `chemical_pulses` table

You can verify the data integrity by running:

```python
import database_interface as db
db.test_database_queries()  # Runs verification tests
```

## 🛠️ Troubleshooting

### Database not found error
```
FileNotFoundError: Database 'smdamage_data.db' not found
```
**Solution:** Run `python create_database.py` first to create the database.

### Missing CSV files
If you see warnings about missing CSV files during database creation, ensure all files are in the `Data/` directory.

### Performance issues
The database includes indices on commonly queried columns. For custom queries, you may want to add additional indices:

```python
conn = sqlite3.connect('smdamage_data.db')
cursor = conn.cursor()
cursor.execute('CREATE INDEX idx_my_column ON my_table(my_column)')
conn.commit()
conn.close()
```

## 🤝 Contributing

To extend the database:

1. **Add new tables**: Modify `create_tables()` in `create_database.py`
2. **Add data loading**: Update `load_csv_data()` to handle new CSV files  
3. **Add query functions**: Create new functions in `database_interface.py`
4. **Update examples**: Add usage examples to `database_example.py`

## 📈 Next Steps

Consider these enhancements:

1. **Data validation**: Add constraints and validation rules to database schema
2. **Versioning**: Track data versions and changes over time
3. **Backup/Export**: Add functions to export data back to CSV format
4. **Web interface**: Create a web dashboard for data exploration
5. **Performance monitoring**: Add query performance tracking

---

*This database integration maintains full compatibility with your existing SMDAMAGE code while providing better performance and maintainability.*