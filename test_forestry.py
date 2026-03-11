#!/usr/bin/env python3
"""Test script for the refactored forestry_removal table"""
# Made by Claude with JFR's guidance. Tests the new structure of the forestry_removal table in the database.

import database_interface as db

def test_forestry_removal():
    print("🌲 Testing Refactored Forestry Removal Table")
    print("="*60)
    
    # Get database instance
    database = db.get_db()
    
    # Test 1: Get all forestry bidders
    forestry_bidders = database.get_all_forestry_bidders()
    print(f"📊 Found {len(forestry_bidders)} forestry bidders:")
    for bidder in forestry_bidders:
        print(f"   • {bidder}")
    
    # Test 2: Get data for a specific bidder and year
    print(f"\n🔍 Year 10 data for Loblolly_pine_150:")
    loblolly_data = database.get_forestry_removal('Loblolly_pine_150', 10)
    for bidder, year, tons in loblolly_data:
        print(f"   {bidder} (Year {year}): {tons:.6f} tons/ha/yr")
    
    # Test 3: Get all data for a specific year  
    print(f"\n📅 All bidders in year 5:")
    for bidder in forestry_bidders:
        bidder_year5_data = database.get_forestry_removal(bidder, 5)
        for bidder_name, year, tons in bidder_year5_data:
            print(f"   {bidder_name}: {tons:.6f} tons/ha/yr")
    
    # Test 4: Get all data for a specific bidder (first 10 years)
    print(f"\n🌳 Black walnut 55yr contract (first 10 years):")
    walnut_data = database.get_forestry_removal('Black_walnut_55')[:10]
    for bidder, year, tons in walnut_data:
        print(f"   Year {year}: {tons:.6f} tons/ha/yr")
    
    # Test 5: Check total record count
    all_data = []
    for bidder in forestry_bidders:
        bidder_data = database.get_forestry_removal(bidder)
        all_data.extend(bidder_data)
    print(f"\n📈 Total forestry removal records: {len(all_data)}")
    
    # Verify structure: should be 156 years × 9 bidders = 1,404 records
    expected_records = 156 * 9
    print(f"   Expected records (156 years × 9 bidders): {expected_records}")
    print(f"   Records match expectation: {len(all_data) == expected_records}")

if __name__ == "__main__":
    test_forestry_removal()