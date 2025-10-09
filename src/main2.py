from agents.TrafficLightAgent2 import TrafficLightAgent
from agents.MonitoringAgent import MonitoringAgent
import asyncio
import traci
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def main():
    agent_name = os.getenv("AGENT_NAME")
    agent_password = os.getenv("AGENT_PASSWORD")

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    CONFIG_FILE = os.path.join(PROJECT_ROOT, "sumo_environment", "map.sumocfg")
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    if not os.path.exists(CONFIG_FILE):
        print(f"FATAL ERROR: SUMO configuration file not found at: {CONFIG_FILE}")
        sys.exit(1) # Exit the script
    traci.start(["sumo-gui", "-c", CONFIG_FILE])

    # Criar agentes
    monitor_agent = MonitoringAgent(f"monitor@localhost", agent_password)
    tls_agent = TrafficLightAgent(f"trafficlight@localhost", "password")
    tls_agent.tls_id = "10761260764"  # ID do semáforo no SUMO (ajusta conforme o teu .net.xml)

    await monitor_agent.start()
    await tls_agent.start()

    # Loop principal (mantém a simulação viva)
    for step in range(1000):
        traci.simulationStep()
        await asyncio.sleep(1)

    await monitor_agent.stop()
    await tls_agent.stop()
    traci.close()

if __name__ == "__main__":
    asyncio.run(main())
