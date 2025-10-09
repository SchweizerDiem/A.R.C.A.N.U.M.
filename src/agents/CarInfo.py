import traci
from spade import agent, behaviour

class CarInfoAgent(agent.Agent):
    class CarInfoBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded():
                return

            step = traci.simulation.getTime()
            car_ids = traci.vehicle.getIDList()

            if not car_ids:
                print(f"[Car Info] Step {step}: Nenhum carro ativo.")
                return

            print(f"\n[Car Info] Step {step}")
            for cid in car_ids:
                pos = traci.vehicle.getPosition(cid)
                speed = traci.vehicle.getSpeed(cid)
                route = traci.vehicle.getRoute(cid)
                lane = traci.vehicle.getLaneID(cid)
                print(f"  → ID: {cid}, Pos: {pos}, Velocidade: {speed:.2f} m/s, Faixa: {lane}, Rota: {route}")

    async def setup(self):
        print(f"[{self.jid}] Agente de Informação de Carros iniciado")
        car_behaviour = self.CarInfoBehaviour(period=2)  # executa a cada 2s
        self.add_behaviour(car_behaviour) 
