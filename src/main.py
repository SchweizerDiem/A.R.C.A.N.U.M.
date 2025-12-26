from time import sleep
from spade import agent
from agents.TrafficLightAgent import TrafficLightAgent
from agents.MonitoringAgent import MonitoringAgent
from agents.CarInfo import CarInfoAgent
from agents.DisruptionAgent import DisruptionAgent
import asyncio
import traci
import os
import sys
from dotenv import load_dotenv

load_dotenv()


async def main():

    agent_name = os.getenv("AGENT_NAME")
    agent_password = os.getenv("AGENT_PASSWORD")

    # Load traffic light agent credentials
    tl_agents_credentials = []
    for i in range(1, 7):  # 6 traffic light agents
        tl_name = os.getenv(f"TL_NAME_{i}")
        tl_password = os.getenv(f"TL_PASSWORD_{i}")
        if tl_name and tl_password:
            tl_agents_credentials.append((tl_name, tl_password))

    # Load car agent credentials
    car_agents_credentials = []
    for i in range(1, 21):  # 20 car agents
        car_name = os.getenv(f"CAR_NAME_{i}")
        car_password = os.getenv(f"CAR_PASSWORD_{i}")
        if car_name and car_password:
            car_agents_credentials.append((car_name, car_password))

    # Load disruption agent credentials
    disruption_name = os.getenv("DISRUPTION_NAME")
    disruption_password = os.getenv("DISRUPTION_PASSWORD")

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
    # Add --ignore-route-errors para impedeir que o SUMO crash quando uma rota é fechada
    traci.start(["sumo-gui", "-c", CONFIG_FILE, "--max-num-vehicles", str(20), "--ignore-route-errors"])

    # Criar agentes
    monitor_agent = MonitoringAgent(str(agent_name), str(agent_password))
    print("monitor iniciado")

    # Criar agente de interrupção
    disruption_agent = DisruptionAgent(disruption_name, disruption_password)
    print("Disruption agent iniciado")

    # Create traffic light agents
    tls_agents = []
    tls_ids = ["J1", "J2", "J5", "J6", "J9", "J10"]  # SUMO traffic light IDs
    for i, (tl_name, tl_password) in enumerate(tl_agents_credentials):
        tls_id = tls_ids[i] if i < len(tls_ids) else f"J{i+1}"
        tls_agent = TrafficLightAgent(str(tl_name), str(tl_password), tls_id, str(agent_name))
        tls_agents.append(tls_agent)
    print(f"tls iniciado: {len(tls_agents)} agents")

    # Create car agents
    car_agents = []
    for car_name, car_password in car_agents_credentials:
        car_agent = CarInfoAgent(str(car_name), str(car_password), str(agent_name))
        car_agents.append(car_agent)
    print(f"car iniciado: {len(car_agents)} agents")

    # Criar agente
    await monitor_agent.start()

    await disruption_agent.start()
    
    for tls_agent in tls_agents:
        await tls_agent.start()
    
    for car_agent in car_agents:
        await car_agent.start()

    # Simulation loop
    for _ in range(1000):
        traci.simulationStep()
        await asyncio.sleep(1)

    # --- Encerrar ---
    await monitor_agent.stop()
    print("Monitor agent encerrado.")
    
    await disruption_agent.stop()
    print("Disruption agent encerrado.")

    for tls_agent in tls_agents:
        await tls_agent.stop()
    print(f"{len(tls_agents)} TL agents encerrados.")
    
    for car_agent in car_agents:
        await car_agent.stop()
    print(f"{len(car_agents)} Car agents encerrados.")
    
    traci.close()

if __name__ == "__main__":
    asyncio.run(main())
