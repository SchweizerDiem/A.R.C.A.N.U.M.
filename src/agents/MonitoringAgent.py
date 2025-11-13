import asyncio
import traci
from spade import agent, behaviour
from spade.message import Message
from spade.template import Template


class MonitoringAgent(agent.Agent):
    """
    Agente de Monitorização que recolhe e exibe dados da simulação de tráfego
    e o estado de outros agentes.
    """

    class MonitorBehaviour(behaviour.PeriodicBehaviour):
        """
        Comportamento periódico para recolher e exibir dados da simulação.
        """
        async def run(self):
            if not traci.isLoaded():
                return

            step = traci.simulation.getTime()
            num_vehicles = traci.vehicle.getIDCount()
            avg_speed = 0

            if num_vehicles > 0:
                speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in traci.vehicle.getIDList()]
                avg_speed = sum(speeds) / len(speeds)

            #print(f"[Monitor] Step: {step}, Vehicles: {num_vehicles}, Avg Speed: {avg_speed:.2f}")

            # Exibir estados dos agentes
            '''if self.agent.agent_states:
                print("[Monitor] Agent States:")
                for agent_jid, status in self.agent.agent_states.items():
                    print(f"  - {agent_jid}: {status}")'''

    class ReceiveReportBehaviour(behaviour.CyclicBehaviour):
        """
        Comportamento cíclico para receber e processar relatórios de outros agentes.
        """
        async def run(self):
            msg = await self.receive(timeout=10)  # Espera por uma mensagem por 10 segundos
            if msg:
                # Atualiza o estado do agente que enviou a mensagem
                self.agent.agent_states[str(msg.sender)] = msg.body
                print(f"[Monitor] Received report from {msg.sender}: {msg.body}")

    async def setup(self):
        """
        Configuração inicial do agente.
        """
        print(f"[{self.jid}] Agente de Monitorização iniciado")
        self.agent_states = {}

        # Comportamento para monitorizar a simulação
        monitor_behaviour = self.MonitorBehaviour(period=1)  # executa a cada 1s
        self.add_behaviour(monitor_behaviour)

        # Comportamento para receber relatórios de outros agentes
        report_template = Template()
        report_template.set_metadata("performative", "inform")
        receive_behaviour = self.ReceiveReportBehaviour()
        self.add_behaviour(receive_behaviour, report_template)



