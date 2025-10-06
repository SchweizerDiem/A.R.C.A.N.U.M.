import asyncio
import traci
from spade import agent, behaviour


class MonitoringAgent(agent.Agent):
    class MonitorBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded():
                return

            step = traci.simulation.getTime()
            num_vehicles = traci.vehicle.getIDCount()
            avg_speed = 0

            if num_vehicles > 0:
                speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in traci.vehicle.getIDList()]
                avg_speed = sum(speeds) / len(speeds)

            print(f"[Monitor] Step: {step}, Vehicles: {num_vehicles}, Avg Speed: {avg_speed:.2f}")

    async def setup(self):
        print(f"[{self.jid}] Agente de Monitorização iniciado")
        monitor_behaviour = self.MonitorBehaviour(period=1)  # executa a cada 1s
        self.add_behaviour(monitor_behaviour)



