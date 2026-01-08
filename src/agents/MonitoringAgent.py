import asyncio
import traci
from spade import agent, behaviour
from spade.message import Message
from spade.template import Template
from utils.CongestionPredictor import CongestionPredictor


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
            
            # Coletar features e fazer previsão de congestionamento
            predictor = self.agent.congestion_predictor
            sample = predictor.collect_features()
            
            if sample:
                features, label = sample
                
                # Fazer previsão
                congestion_prob = predictor.get_congestion_probability(features)
                prediction = predictor.predict(features)
                
                # Exibir previsão a cada 5 segundos
                if int(step) % 5 == 0:
                    status = "🔴 CONGESTIONADO" if prediction == 1 else "🟢 NORMAL"
                    print(f"[Monitor] Step {int(step)}s | {status} | Probabilidade: {congestion_prob:.1%} | Veículos: {int(features[0])} | Vel.Média: {features[1]:.1f}m/s")
                
                # Adicionar amostra para treinamento
                predictor.add_sample(features, label)
                
                # Treinar modelo periodicamente
                if predictor.should_train() and not predictor.is_trained:
                    predictor.train()
                elif predictor.is_trained and len(predictor.training_features) >= predictor.min_samples_to_train:
                    # Retreinar com novos dados
                    predictor.train()

            # Exibir estados dos agentes (comentado)
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
        
        # Inicializar preditor de congestionamento
        self.congestion_predictor = CongestionPredictor(
            congestion_threshold=5.0,  # 5 m/s = ~18 km/h
            min_samples_to_train=50,
            data_dir="ml_data"  # Diretório para persistência de dados
        )
        print(f"[Monitor] 🧠 CongestionPredictor inicializado (ML ativado)")

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



