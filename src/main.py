from time import sleep
import traci
import os
import sys

# --- Path Setup for Robustness ---
# 1. Get the directory of the current script (e.g., /ProjectRoot/src)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Get the PARENT directory (e.g., /ProjectRoot)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# 3. Construct the absolute path to the config file
# This is equivalent to: /ProjectRoot/sumo_environment/map.sumocfg
CONFIG_FILE = os.path.join(PROJECT_ROOT, "sumo_environment", "map.sumocfg")

# --- TraCI Setup ---
# Optionally, add SUMO_HOME tools to path if you haven't globally
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
# else:
#     # If you uncomment this, the script will stop if SUMO_HOME isn't set
#     sys.exit("Please declare the environment variable 'SUMO_HOME'")


# 4. Check if the file exists (Good practice!)
if not os.path.exists(CONFIG_FILE):
    print(f"FATAL ERROR: SUMO configuration file not found at: {CONFIG_FILE}")
    sys.exit(1) # Exit the script

# 5. Connect to SUMO simulation using the absolute path
# Use 'sumo-gui' instead of 'sumo' initially for visual debugging
traci.start(["sumo-gui", "-c", CONFIG_FILE])


# Simulation loop
step = 0
while step < 1000:
    traci.simulationStep()
    # Your agent logic will go here
    step += 1
    # Remove sleep(0.5) unless you want the simulation to run very slowly for visual inspection
    # sleep(0.5) 

# Close TraCI connection
traci.close()
