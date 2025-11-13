from time import sleep
from spade import agent
from agents.TrafficLightAgent import TrafficLightAgent
from agents.MonitoringAgent import MonitoringAgent
from agents.CarInfo import CarInfoAgent
import asyncio
import traci
import os
import sys
from dotenv import load_dotenv

load_dotenv()


async def main():

    agent_name = os.getenv("AGENT_NAME")
    agent_password = os.getenv("AGENT_PASSWORD")

    tl_name = os.getenv("TL_NAME")
    tl_password = os.getenv("TL_PASSWORD")

    ic_name = os.getenv("IC_NAME")
    ic_password = os.getenv("IC_PASSWORD")
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

    # Criar agentes
    monitor_agent = MonitoringAgent(str(agent_name), str(agent_password))
    print("monitor iniciado")

    tls_id = "J5"  # ID do semáforo no SUMO
    tls_agent = TrafficLightAgent(str(tl_name), str(tl_password), tls_id, str(agent_name))
    print("tls iniciado")

    car_agent = CarInfoAgent(str(ic_name), str(ic_password), str(agent_name))
    print("car iniciado")


    # Criar agente
    await monitor_agent.start()
    await tls_agent.start()
    await car_agent.start()

    # Simulation loop
    for _ in range(1000):
        traci.simulationStep()
        await asyncio.sleep(1)

    # --- Encerrar ---
    await monitor_agent.stop()
    print("Agente encerrado.")

    # Close TraCI connection
    await tls_agent.stop()
    await car_agent.stop()
    traci.close()

if __name__ == "__main__":
    asyncio.run(main())
