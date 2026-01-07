
import os
import sys

# Ensure we can import the utils module
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.utils.RouteFinder import RouteFinder

def test():
    net_file = "sumo_environment/network.net.xml"
    if not os.path.exists(net_file):
        print(f"File {net_file} not found locally, trying absolute path...")
        # Adjust based on known path
        net_file = "/home/guilherme/Documents/GitHub/Intelligent-Multi-Agent-Traffic-Control-System/sumo_environment/network.net.xml"

    print(f"Loading net from {net_file}...")
    rf = RouteFinder(net_file)
    
    start_edge = "E0"
    end_edge = "E11" # Should be E0 -> E1 -> E10 -> E11 based on my quick read of XML connections
    
    print(f"Calculating route from {start_edge} to {end_edge}...")
    route = rf.find_route(start_edge, end_edge)
    
    print(f"Route found: {route}")
    
    if route == ['E0', 'E1', 'E10', 'E11']:
        print("SUCCESS: Route matches expected path.")
    else:
        print("WARNING: Route differs from expectation or is empty.")

if __name__ == "__main__":
    test()
