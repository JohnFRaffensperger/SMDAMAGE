#!/usr/bin/env python3
"""Demonstrate the new forestry sequestration functionality"""

import database_example

def test_new_forestry_sequestration():
    print("🌲 Testing New Forestry Sequestration Structure")
    print("="*60)
    
    print("\n📊 Using updated get_forestry_sequestration_from_database():")
    data = database_example.get_forestry_sequestration_from_database()
    
    print(f"\n🔍 Sample data lookup:")
    print(f"   Loblolly pine 150yr, Year 10: {data['Loblolly_pine_150'][10]:.6f} tons/ha/yr")
    print(f"   Black walnut 55yr, Year 5: {data['Black_walnut_55'][5]:.6f} tons/ha/yr") 
    print(f"   Ponderosa pine 103yr, Year 15: {data['Ponderosa_pine_103'][15]:.6f} tons/ha/yr")
    
    print(f"\n📈 Data structure verification:")
    print(f"   Number of bidders in dataset: {len(data)}")
    for bidder in sorted(data.keys())[:5]:  # Show first 5
        year_count = len(data[bidder])
        print(f"   {bidder}: {year_count} years of data")
    
if __name__ == "__main__":
    test_new_forestry_sequestration()