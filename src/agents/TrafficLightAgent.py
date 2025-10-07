import spade
import time
import traci  # TraCI is the Traffic Control Interface for SUMO

# --- Configuration ---
SUMO_CMD = ["sumo-gui", "-c", "map.sumocfg"]  # Replace with your SUMO configuration file
PORT = 8888  # TraCI port (default)
TRAFFIC_LIGHT_ID = "10893856743"  # Replace with the actual ID of the traffic light in your .net.xml file
AGENT_JID = "admin@localhost"
AGENT_PASSWORD = "password"

# --- Traffic Light Control Logic ---

def get_traffic_demand(junction_id):
    """
    Checks the current traffic volume on the incoming lanes of the junction.
    This is a placeholder for a more complex traffic sensing logic.
    """
    total_vehicles = 0
    # You would typically define the incoming lanes for the junction here
    # Example Lane IDs (REPLACE WITH YOUR ACTUAL LANE IDs)
    incoming_lanes = ["265390429#1_0"]

    try:
        for lane_id in incoming_lanes:
            # Get the number of vehicles on the lane
            total_vehicles += traci.lane.getLastStepVehicleNumber(lane_id)
    except Exception as e:
        # Handle cases where the lane ID might not exist yet
        print(f"TraCI Error during traffic check: {e}")
        return 0
        
    return total_vehicles

def determine_next_phase(junction_id, current_phase_index, traffic_demand):
    """
    Simple logic: If traffic on the current green phase is low, switch.
    In a real scenario, this would be a sophisticated AI/optimization model.
    
    SUMO phases are defined in the .tll.xml or the .net.xml.
    Phase 0: North-South Green (e.g., "GrGr")
    Phase 1: North-South Yellow (e.g., "yryr")
    Phase 2: East-West Green (e.g., "rGrG")
    Phase 3: East-West Yellow (e.g., "ryry")
    """
    
    # Simple threshold logic
    TRAFFIC_THRESHOLD = 5
    
    if traffic_demand < TRAFFIC_THRESHOLD:
        print(f"Low traffic ({traffic_demand}), considering phase switch.")
        
        # Determine the next phase based on the current one
        # Assuming a four-phase system: Green1 -> Yellow1 -> Green2 -> Yellow2
        if current_phase_index == 0:  # North-South Green
            # Switch to yellow (index 1) to prepare for the other direction
            return 1 
        elif current_phase_index == 2:  # East-West Green
            # Switch to yellow (index 3)
            return 3
            
    # Stay in the current phase (e.g., if it's a Yellow phase or traffic is high)
    # The actual phase management in SUMO often requires specifying the whole
    # cycle or using 'setPhase' with a specific phase index.
    
    # For simplicity in this example, we'll implement the full cycle transition:
    if current_phase_index == 1: # N-S Yellow, go to E-W Green
        return 2
    elif current_phase_index == 3: # E-W Yellow, go to N-S Green
        return 0
        
    return current_phase_index # Keep the current phase if no condition is met

# --- SPADE Agent Definition ---

class TrafficLightAgent(spade.agent.Agent):
    
    # A Behaviour that periodically checks traffic and updates the light
    class ControlBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            print(f"--- Agent {self.agent.jid.localpart} checking traffic... ---")
            
            try:
                # 1. Get current traffic light state
                current_phase_index = traci.trafficlight.getPhase(TRAFFIC_LIGHT_ID)
                current_phase_string = traci.trafficlight.getPhaseString(TRAFFIC_LIGHT_ID)
                print(f"Current Phase: Index {current_phase_index} ({current_phase_string})")
                
                # 2. Sense the environment (get traffic demand)
                traffic_demand = get_traffic_demand(TRAFFIC_LIGHT_ID)
                print(f"Detected Traffic Demand on incoming lanes: {traffic_demand} vehicles.")
                
                # 3. Decide on the next action (determine next phase)
                next_phase_index = determine_next_phase(
                    TRAFFIC_LIGHT_ID, 
                    current_phase_index, 
                    traffic_demand
                )
                
                # 4. Act on the environment (change the traffic light phase)
                if next_phase_index != current_phase_index:
                    traci.trafficlight.setPhase(TRAFFIC_LIGHT_ID, next_phase_index)
                    print(f"Traffic Light switched from index {current_phase_index} to index {next_phase_index}")
                else:
                    print(f"Traffic Light phase remains index {current_phase_index}")
                    
            except traci.exceptions.FatalTraCIError as e:
                print(f"FATAL TraCI Error: SUMO may not be running or the connection was lost: {e}")
                # Stop the agent if connection to SUMO is lost
                self.kill()
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                
            # Wait for a period before running again
            await self.agent.sleep(5) # Check every 5 seconds
            
    async def setup(self):
        print(f"Traffic Light Agent {self.jid.localpart} starting...")
        
        # Start the SUMO simulation and connect TraCI
        # IMPORTANT: Run SUMO in the background (as a separate process)
        print("Starting SUMO and connecting TraCI...")
        try:
            # This line starts SUMO and connects TraCI
            traci.start(SUMO_CMD, port=PORT, label=self.jid.localpart) 
            print("TraCI connection established.")
        except Exception as e:
            print(f"Failed to start SUMO/connect TraCI. Ensure SUMO is installed and configured: {e}")
            return # Exit setup if TraCI connection fails

        # Add the ControlBehaviour to the agent
        b = self.ControlBehaviour()
        self.add_behaviour(b)

# --- Main Execution ---

if __name__ == "__main__":
    
    # The SPADE platform must be running (e.g., as a separate process or in another terminal)
    # The agent will connect to the platform specified in AGENT_JID (e.g., '@localhost')

    tl_agent = TrafficLightAgent(
        AGENT_JID, 
        AGENT_PASSWORD
    )
    future = tl_agent.start()
    
    # Wait until the agent has connected and is running
    future.result() 

    # Keep the main thread alive so the agent can run its behaviours
    while tl_agent.is_alive():
        try:
            time.sleep(1)
            # Advance the SUMO simulation step by step
            traci.simulationStep()
            
        except KeyboardInterrupt:
            print("\nShutting down agents and SUMO...")
            break
        except traci.exceptions.FatalTraCIError:
             # SUMO was closed by the user or an error occurred
             print("\nSUMO simulation ended.")
             break
        
    # Stop the TraCI connection and shutdown the agent
    if 'traci' in globals() and traci.isEmbedded():
        traci.close()
    tl_agent.stop()
