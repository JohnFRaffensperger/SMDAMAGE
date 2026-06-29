
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'SMDAMAGE revenue neutral'))
import database_interface

bidders = database_interface.get_bidders()
print(f"Total bidders: {len(bidders)}")
forestry_names = database_interface.get_forestry_bidder_names()
print(f"Forestry names count: {len(forestry_names)}")
for b in bidders:
    if b['bidder_name'] in forestry_names:
        print(f"Sample Forestry: {b['bidder_name']}, Class: {b['class']}")
        break
