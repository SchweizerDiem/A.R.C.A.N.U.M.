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

        # Comportamento para gerir prioridades
        priority_template = Template()
        priority_template.set_metadata("performative", "request")
        priority_behaviour = self.PriorityManagerBehaviour()
        self.add_behaviour(priority_behaviour, priority_template)

    def set_tls_mapping(self, mapping):
        """Define o mapeamento de TLS ID para JID."""
        self.tls_mapping = mapping

    class PriorityManagerBehaviour(behaviour.CyclicBehaviour):
        """
        Recebe pedidos de prioridade (e.g., de ambulâncias) e encaminha para o semáforo correto.
        """
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                content = msg.body
                # Esperado: "priority_request:{veh_id}:{tls_id}"
                if "priority_request" in content and hasattr(self.agent, 'tls_mapping'):
                    try:
                         parts = content.split(":")
                         if len(parts) >= 3:
                             veh_id = parts[1]
                             tls_id = parts[2]
                             
                             tls_jid = self.agent.tls_mapping.get(tls_id)
                             if tls_jid:
                                 # Encaminha o pedido para o agente de semáforo
                                 forward_msg = Message(to=tls_jid)
                                 forward_msg.set_metadata("performative", "request")
                                 forward_msg.body = f"priority_request:{veh_id}"
                                 await self.send(forward_msg)
                                 print(f"[Monitor] Encaminhando pedido de {veh_id} para {tls_id} ({tls_jid})")
                             else:
                                 print(f"[Monitor] TLS ID {tls_id} não encontrado no mapeamento.")
                    except Exception as e:
                        print(f"[Monitor] Erro ao processar pedido de prioridade: {e}")



