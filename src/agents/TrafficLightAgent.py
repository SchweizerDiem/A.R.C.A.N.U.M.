import asyncio
import spade
import time
import os
from pathlib import Path
import traci  # TraCI is the Traffic Control Interface for SUMO

# --- Configuration ---
# Default SUMO command template. The actual config path will be resolved
# at runtime by `find_sumo_config()` so the project can be run from the
# repository root or other working directories.
SUMO_CMD = ["sumo-gui", "-c", "map.sumocfg"]  # fallback, replaced at runtime
PORT = 8888  # TraCI port (default)
TRAFFIC_LIGHT_ID = None  # If None the agent will control all traffic lights found in the network
AGENT_JID = "admin@localhost"
AGENT_PASSWORD = "password"

# Possible locations (relative to repository root or current working dir) to
# search for the SUMO config file. Extend if your project keeps the file
# elsewhere.
SUMO_CONFIG_CANDIDATES = [
    "map.sumocfg",
    os.path.join("sumo_environment", "map.sumocfg"),
    os.path.join("..", "sumo_environment", "map.sumocfg"),
]


def find_sumo_config() -> str | None:
    """Return absolute path to the first existing SUMO config file we find.

    Searches candidate locations and returns None if not found.
    """
    # Try candidates first
    for candidate in SUMO_CONFIG_CANDIDATES:
        p = Path(candidate)
        if p.is_file():
            return str(p.resolve())

    # As a last resort, attempt to search the repository for .sumocfg files.
    try:
        # Search current working directory recursively (limited depth implicitly)
        cwd = Path(os.getcwd())
        for p in cwd.rglob("*.sumocfg"):
            return str(p.resolve())
    except Exception:
        pass

    return None

# --- Traffic Light Control Logic ---

def jid_localpart(jid_obj):
    """Safely return the local part/user of a JID.

    Works if jid_obj is a string (e.g. 'user@domain') or a slixmpp.jid.JID
    instance (has attribute 'user'). Falls back to str(jid_obj) if needed.
    """
    try:
        # slixmpp.jid.JID exposes .user for the local part
        if hasattr(jid_obj, "user") and jid_obj.user:
            return jid_obj.user
    except Exception:
        pass

    # If it's a string like 'user@domain', split it
    try:
        if isinstance(jid_obj, str) and "@" in jid_obj:
            return jid_obj.split("@", 1)[0]
    except Exception:
        pass

    # Fallback
    return str(jid_obj)


def get_traffic_demand(junction_id):
    """
    Checks the current traffic volume on the incoming lanes of the junction.
    Uses TraCI to retrieve the controlled lanes for the given traffic light
    and sums the number of vehicles currently on those lanes.
    """
    total_vehicles = 0

    try:
        # Get lanes controlled by this traffic light
        print(f"Querying controlled lanes for TL {junction_id}...")
        lanes = traci.trafficlight.getControlledLanes(junction_id)
        if not lanes:
            # Fallback: try getControlledLinks -> extract lane ids
            links = traci.trafficlight.getControlledLinks(junction_id)
            lanes = []
            for link_group in links:
                for link in link_group:
                    if len(link) >= 3:
                        # link format: [incomingLaneId, outgoingLaneId, ...]
                        lanes.append(link[0])

        # Remove duplicates
        lanes = list(dict.fromkeys(lanes))

        print(f"TL {junction_id} controls lanes: {lanes}")
        for lane_id in lanes:
            try:
                n = traci.lane.getLastStepVehicleNumber(lane_id)
                print(f"  Lane {lane_id}: {n} vehicles")
                total_vehicles += n
            except Exception as e:
                # Ignore missing/temporary lanes but print reason
                print(f"  Warning: couldn't read lane {lane_id}: {e}")
                continue

    except Exception as e:
        print(f"TraCI Error during traffic check for {junction_id}: {e}")
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
    
    print(f"Deciding next phase for TL {junction_id}: current={current_phase_index}, demand={traffic_demand}, threshold={TRAFFIC_THRESHOLD}")
    if traffic_demand < TRAFFIC_THRESHOLD:
        print(f"  Low traffic ({traffic_demand} < {TRAFFIC_THRESHOLD}), considering phase switch.")
        
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
        print("  Current is N-S Yellow -> switching to E-W Green (2)")
        return 2
    elif current_phase_index == 3: # E-W Yellow, go to N-S Green
        print("  Current is E-W Yellow -> switching to N-S Green (0)")
        return 0
        
    return current_phase_index # Keep the current phase if no condition is met

# --- SPADE Agent Definition ---

class TrafficLightAgent(spade.agent.Agent):
    
    # A Behaviour that periodically checks traffic and updates the light
    class ControlBehaviour(spade.behaviour.CyclicBehaviour):
        async def run(self):
            print(f"--- Agent {jid_localpart(self.agent.jid)} checking traffic... ---")
            
            try:
                print("A")
                # 1. Get current traffic light state
                # Control one or all traffic lights depending on configuration
                tl_ids = [TRAFFIC_LIGHT_ID] if TRAFFIC_LIGHT_ID else traci.trafficlight.getIDList()
                print(f"Discovered traffic lights to control: {tl_ids}")

                for tl in tl_ids:
                    current_phase_index = traci.trafficlight.getPhase(tl)
                    try:
                        current_phase_string = traci.trafficlight.getPhaseString(tl)
                    except Exception:
                        current_phase_string = ""

                    print(f"TL {tl} - Current Phase: Index {current_phase_index} ({current_phase_string})")

                    # Sense the environment (get traffic demand)
                    traffic_demand = get_traffic_demand(tl)
                    print(f"TL {tl} - Detected Traffic Demand on incoming lanes: {traffic_demand} vehicles.")

                    # Decide on the next action (determine next phase)
                    next_phase_index = determine_next_phase(
                        tl,
                        current_phase_index,
                        traffic_demand
                    )

                    # Act on the environment (change the traffic light phase)
                    if next_phase_index != current_phase_index:
                        traci.trafficlight.setPhase(tl, next_phase_index)
                        print(f"TL {tl} switched from index {current_phase_index} to index {next_phase_index}")
                    else:
                        print(f"TL {tl} phase remains index {current_phase_index}")
                    
            except traci.exceptions.FatalTraCIError as e:
                print(f"FATAL TraCI Error: SUMO may not be running or the connection was lost: {e}")
                # Stop the agent if connection to SUMO is lost
                self.kill()
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                
            # Wait for a period before running again
            await self.agent.sleep(5) # Check every 5 seconds
            
    async def setup(self):
        print(f"Traffic Light Agent {jid_localpart(self.jid)} starting...")

        # Start the SUMO simulation and connect TraCI
        # IMPORTANT: Run SUMO in the background (as a separate process)
        print("Starting SUMO and connecting TraCI...")
        config_path = find_sumo_config()
        if not config_path:
            print("Could not find a SUMO configuration file (map.sumocfg)."
                  " Look in the repository root or the sumo_environment/ folder.")
            return

        # Build the command using the discovered absolute config path
        cmd = ["sumo-gui", "-c", config_path]
        print(f"Using SUMO config: {config_path}")
        print(f"Starting SUMO with command: {cmd}")

        # Try starting SUMO, but be explicit about errors and don't crash the whole agent
        try:
            traci.start(cmd, port=PORT, label=jid_localpart(self.jid))
            print("TraCI connection established.")
        except Exception as e:
            print(f"Failed to start SUMO/connect TraCI. Ensure SUMO is installed and configured: {e}")
            return # Exit setup if TraCI connection fails

        print("AA") # debug marker
        # After TraCI started, list traffic lights found
        try:
            tl_list = traci.trafficlight.getIDList()
            print(f"Traffic lights found in network: {tl_list}")
        except Exception:
            print("Warning: could not list traffic lights after TraCI start")

        # Add the ControlBehaviour to the agent
        b = self.ControlBehaviour()
        self.add_behaviour(b)

        print("AAA")

# --- Main Execution ---

async def main():
    # The SPADE platform must be running (e.g., as a separate process or in another terminal)
    # The agent will connect to the platform specified in AGENT_JID (e.g., '@localhost')

    tl_agent = TrafficLightAgent(
        AGENT_JID, 
        AGENT_PASSWORD
    )
    await tl_agent.start()
    #future = tl_agent.start()
    
    # Wait until the agent has connected and is running
    #future.result() 

    # Keep the main thread alive so the agent can run its behaviours
    # Keep the main thread alive so the agent can run its behaviours
    step = 0
    while tl_agent.is_alive():
        try:
            time.sleep(1)
            # Advance the SUMO simulation step by step
            traci.simulationStep()
            step += 1

            # Print traffic light info for this step
            try:
                tl_ids = traci.trafficlight.getIDList()
                print(f"\nSUMO step {step} - Traffic Light status:")
                for tl in tl_ids:
                    try:
                        phase = traci.trafficlight.getPhase(tl)
                        rgy = traci.trafficlight.getRedYellowGreenState(tl)
                    except Exception:
                        phase = None
                        rgy = ""

                    # Controlled lanes and vehicle counts
                    try:
                        lanes = traci.trafficlight.getControlledLanes(tl)
                        # fallback to links if lanes empty
                        if not lanes:
                            links = traci.trafficlight.getControlledLinks(tl)
                            lanes = []
                            for link_group in links:
                                for link in link_group:
                                    if len(link) >= 3:
                                        lanes.append(link[0])
                        lanes = list(dict.fromkeys(lanes))
                        veh_count = 0
                        for lane in lanes:
                            try:
                                veh_count += traci.lane.getLastStepVehicleNumber(lane)
                            except Exception:
                                continue
                    except Exception:
                        lanes = []
                        veh_count = 0

                    print(f"  TL {tl}: phase={phase} state={rgy} lanes={lanes} vehicles={veh_count}")
            except Exception as e:
                print(f"  Warning: couldn't read traffic light list/status: {e}")

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

if __name__ == "__main__":
    asyncio.run(main())
