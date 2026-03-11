#!/usr/bin/env python3
"""
Example showing how to modify SMDAMAGE code to use SQLite database instead of CSV files
This demonstrates the database-based approach for the read_bids function
"""

import database_interface as db_interface

def read_bids_from_database(scenario):
    """
    Database-based version of the read_bids function from SMDAMAGE revenue neutral.py
    This replaces the original CSV file reading with database queries
    
    NOTE: This demonstrates how individual chemicals are now handled separately
    instead of being grouped together. Each chemical has its own bid function.
    You would need to integrate with your actual defaults_and_utilities and
    hector_interface modules
    """
    
    print("📊 Demonstrating database-based bid loading...")
    
    # Mock parameters for demonstration (replace with actual calls)
    # AllBidPeriods = defaults_and_utilities.getBidPeriods()
    # StartYear = defaults_and_utilities.getStartYear()
    AllBidPeriods = [2025.0, 2026.0, 2027.0]  # Mock data
    StartYear = 2025
    
    Bapt = {}  # Bid price for agent a, pollutant p, time period t.
    Uapt = {}  # Upper bid quantity, kg, for agent a, pollutant p, time period t.
    APT_set = set()  # [(a, p, t),...]
    PT_set = set()
    PeriodsPerYear = 1.0  # Mock value

    # Get database instance
    db = db_interface.get_db()

    # 2.1 Agriculture - Using database instead of CSV
    print("Loading Agriculture bids from database...")
    agriculture_bids = db.get_bids('Agriculture')  # Returns list of (price, quantity) tuples
    
    for t in AllBidPeriods:
        PT_set.add(('Agriculture', t))
        for bidstep, (price, quantity) in enumerate(agriculture_bids[:5]):  # Limit for demo
            APT_set.add((bidstep, 'Agriculture', t))
            Bapt[bidstep, 'Agriculture', t] = -price * scenario.discount_rate(t - StartYear)
            Uapt[bidstep, 'Agriculture', t] = quantity / PeriodsPerYear

    # 2.2 Carbon - Using database instead of CSV
    print("Loading Carbon bids from database...")
    carbon_bids = db.get_bids('Carbon')  # Returns list of (price, quantity) tuples
    
    for t in AllBidPeriods:
        PT_set.add(('Carbon', t))
        for bidstep, (price, quantity) in enumerate(carbon_bids[:5]):  # Limit for demo
            APT_set.add((bidstep, 'Carbon', t))
            Bapt[bidstep, 'Carbon', t] = price * scenario.discount_rate(t - StartYear)
            Uapt[bidstep, 'Carbon', t] = quantity / PeriodsPerYear

    # 2.3 Individual chemical species - Using unified database function
    chemicals = ['C2F6', 'CF4', 'HFC125', 'HFC134a', 'HFC143a', 'SF6']
    
    for chem_name in chemicals:
        print(f"Loading {chem_name} bids from database...")
        chem_bids = db.get_bids(chem_name)  # Returns list of (price, quantity) tuples
        
        for t in AllBidPeriods:
            PT_set.add((chem_name, t))
            for bidstep, (price, quantity) in enumerate(chem_bids[:3]):  # Limit for demo
                APT_set.add((bidstep, chem_name, t))
                # Note: For chemicals, price might need different treatment than carbon
                Bapt[bidstep, chem_name, t] = price * scenario.discount_rate(t - StartYear) 
                Uapt[bidstep, chem_name, t] = quantity / PeriodsPerYear

    print(f"📊 Demo loaded {len(APT_set)} bid entries from database")
    print(f"🔢 {len(PT_set)} pollutant-time combinations")
    
    return Bapt, Uapt, APT_set, PT_set

def get_pulse_data_from_database():
    """
    Example function showing how to get pulse data from database
    This can replace direct file reading in hector_interface.py
    """
    print("Loading pulse data from database...")
    
    db = db_interface.get_db()
    
    # Get all available hector names
    hector_names = db.get_hector_names()
    print(f"Available hector names in warming factor data: {hector_names}")
    
    # Example: Get warming factor data for a specific hector name
    ffi_data = db.get_warming_factors('ffi_emissions')
    if ffi_data:
        print(f"FFI emissions factor: {ffi_data['emission_factor']} {ffi_data['hector_units']}")
        print(f"First 10 data points: {ffi_data['data_values'][:10]}")
    
    # Build pulse dictionary similar to original code
    Pulse = {}
    for hector_name in hector_names:
        pulse_data = db.get_warming_factors(hector_name)
        if pulse_data:
            # Extract the chemical name without '_emissions' suffix if present
            clean_name = hector_name.replace('_emissions', '')
            Pulse[clean_name] = [pulse_data['emission_factor']] + pulse_data['data_values']
    
    print(f"🧪 Loaded pulse data for {len(Pulse)} chemicals")
    return Pulse

def get_forestry_removal_from_database():
    """
    Example function to get forestry removal data from database
    Uses the new normalized table structure with bidder, year, tons_per_hectare_per_year columns
    """
    print("Loading forestry removal data from database...")
    
    # Get all forestry removal data from the new normalized table
    forestry_data = db_interface.get_forestry_removal_data()
    
    # Convert to the format expected by the original code
    # Original code expects: Treetype_carbon_removal[tree][year] = tons_per_hectare
    Treetype_carbon_removal = {}
    
    # Process the normalized data
    for bidder, year, tons_per_hectare in forestry_data:
        if bidder not in Treetype_carbon_removal:
            Treetype_carbon_removal[bidder] = {}
        Treetype_carbon_removal[bidder][year] = tons_per_hectare
    
    # Get unique bidders and years for reporting
    forestry_bidders = db_interface.get_forestry_bidder_names()
    years = set(year for _, year, _ in forestry_data)
    
    print(f"🌲 Loaded removal data for {len(forestry_bidders)} forestry bidders, {len(years)} years")
    print(f"   Forestry bidders: {', '.join(forestry_bidders)}")
    return Treetype_carbon_removal

def get_forestry_bids_from_database():
    """
    Example function showing how to get forestry bid data from separate contract duration tables
    This demonstrates the new structure with individual tables per contract duration
    """
    print("Loading forestry bid data from database...")
    
    db = db_interface.get_db()
    
    # Get bids for different contract durations
    forestry_bids_150 = []  # Get all 150-year forestry contracts
    for bidder in ['Black_walnut_150', 'Loblolly_pine_150', 'Ponderosa_pine_150']:
        forestry_bids_150.extend(db.get_bids(bidder))
    
    forestry_bids_10 = []  # Get all 10-year forestry contracts  
    for bidder in ['Black_walnut_10', 'Loblolly_pine_10', 'Ponderosa_pine_10']:
        forestry_bids_10.extend(db.get_bids(bidder))
    
    forestry_bids_24 = db.get_bids('Loblolly_pine_24')    # 24-year contracts (loblolly only)
    forestry_bids_103 = db.get_bids('Ponderosa_pine_103')  # 103-year contracts (ponderosa only)
    forestry_bids_55 = db.get_bids('Black_walnut_55')    # 55-year contracts (black walnut only)
    
    print(f"🌲 150-year contracts: {len(forestry_bids_150)} bids (all tree types)")
    print(f"🌲 10-year contracts: {len(forestry_bids_10)} bids (all tree types)")
    print(f"🌲 24-year contracts: {len(forestry_bids_24)} bids (loblolly pine only)")
    print(f"🌲 103-year contracts: {len(forestry_bids_103)} bids (ponderosa pine only)")
    print(f"🌲 55-year contracts: {len(forestry_bids_55)} bids (black walnut only)")
    
    # Example: Show price comparison for 150-year vs 10-year contracts
    if forestry_bids_150 and forestry_bids_10:
        print("\n📊 Price comparison (first bid):")
        bid_150 = forestry_bids_150[0]  # (price, quantity) tuple
        bid_10 = forestry_bids_10[0]    # (price, quantity) tuple
        
        print(f"   150-year: ${bid_150[0]:.2f}/tC at {bid_150[1]:.1f} tC")
        print(f"   10-year:  ${bid_10[0]:.2f}/tC at {bid_10[1]:.1f} tC")
    
    return {
        '150': forestry_bids_150,
        '10': forestry_bids_10,
        '24': forestry_bids_24,
        '103': forestry_bids_103,
        '55': forestry_bids_55
    }

# Demonstration function
def demonstrate_database_usage():
    """Demonstrate how to use the database instead of CSV files"""
    
    print("🗄️  SMDAMAGE Database Usage Example")
    print("=" * 50)
    
    try:
        # Example scenario object (you would use your actual scenario)
        class MockScenario:
            def discount_rate(self, years):
                return 1.0  # Simplified discount rate
        
        scenario = MockScenario()
        
        # Show database info
        db = db_interface.get_db()
        info = db.get_database_info()
        print("📊 Database contains:")
        for table, count in info.items():
            if table != 'sqlite_sequence':  # Skip system table
                print(f"  • {table}: {count} records")
        
        print("\n" + "="*50)
        print("🔄 Usage Examples:")
        print("="*50)
        
        # Example 1: Direct data access
        print("\n1️⃣  Direct data access:")
        ag_bids = db_interface.get_bids('Agriculture')
        print(f"   Agriculture bids: {len(ag_bids)} entries")
        print(f"   First bid: ${ag_bids[0][0]:.2f}/MgtonC, {ag_bids[0][1]:.1f} MgtonC")
        
        # Individual chemical access
        print("   Individual chemical bids:")
        c2f6_bids = db_interface.get_bids('C2F6')
        print(f"   C2F6 bids: {len(c2f6_bids)} entries")
        print(f"   First C2F6 bid: ${c2f6_bids[0][0]:.2f}/kt, {c2f6_bids[0][1]:.1f} kt/year")
        
        sf6_bids = db_interface.get_bids('SF6')
        print(f"   SF6 bids: {len(sf6_bids)} entries")
        print(f"   First SF6 bid: ${sf6_bids[0][0]:.2f}/kt, {sf6_bids[0][1]:.1f} kt/year")
        
        # Example 2: Warming factor data access
        print("\n2️⃣  Warming factor data:")
        hector_names = db_interface.get_all_hector_names()
        print(f"   Available hector names: {len(hector_names)}")
        
        ffi = db_interface.get_warming_factor_data('ffi_emissions')
        if ffi:
            print(f"   FFI factor: {ffi['emission_factor']} {ffi['hector_units']}")
        
        # Example 3: Custom queries
        print("\n3️⃣  Custom database queries:")
        high_carbon_bids = db.query_custom(
            "SELECT price_per_unit, quantity_units FROM bids WHERE bidder = 'Carbon' AND price_per_unit > 50 LIMIT 5"
        )
        print(f"   High-price carbon bids (>$50/ton): {len(high_carbon_bids)} found")
        for price, qty in high_carbon_bids[:3]:
            print(f"     ${price:.2f}/ton, {qty:.1f} Mtons")
        
        # Example 4: Forestry contract comparisons
        print("\n4️⃣  Forestry contract data by duration:")
        forestry_data = get_forestry_bids_from_database()
        print("   ✓ Loaded all forestry contract duration tables")
        
        print("\n✅ Database integration working successfully!")
        print("\n💡 Next steps:")
        print("   1. Replace CSV reading code in your main SMDAMAGE script")
        print("   2. Use database_interface.py functions instead of file I/O")
        print("   3. All bidders now use the unified get_bids(bidder_name) function")
        print("   4. Each forestry contract duration has its own table and function")
        print("   5. Benefit from faster queries and better data organization")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure the database has been created with create_database.py")

if __name__ == "__main__":
    demonstrate_database_usage()