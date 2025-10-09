"""
TrafficLightAgent.py
--------------------
Feature 2: Traffic Light Agent (com SUMO + SPADE)

Este agente controla um conjunto de semáforos numa interseção do SUMO.
Ele observa as filas através do TraCI e ajusta o tempo do verde dinamicamente.

Fluxo:
 - A cada ciclo (period=2s), o agente lê o número de veículos por lane.
 - Se a fila for grande, mantém o verde por mais tempo.
 - Caso contrário, muda para amarelo e depois vermelho.

Autor: (tu)
"""

from spade import agent, behaviour
import traci
import asyncio


class TrafficLightAgent(agent.Agent):
    class ControlBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            """Ciclo principal do agente — executa a cada 2 segundos."""

            # Identificador do semáforo controlado (ex: "junction_0")
            tls_id = self.agent.tls_id

            # Obtém estado atual do semáforo no SUMO
            current_phase = traci.trafficlight.getPhase(tls_id)
            logic = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0]
            phases = logic.getPhases()

            # Contar veículos nas lanes controladas
            lanes = traci.trafficlight.getControlledLanes(tls_id)
            total_vehicles = sum(traci.lane.getLastStepVehicleNumber(lane) for lane in lanes)
            avg_waiting = (
                sum(traci.lane.getWaitingTime(lane) for lane in lanes) / len(lanes)
                if lanes else 0
            )

            print(f"[{self.agent.name}] Veículos: {total_vehicles}, Espera média: {avg_waiting:.2f}s")

            # Lógica adaptativa simples
            # Se houver muito trânsito, mantém verde por mais tempo
            if total_vehicles > 10 and self.agent.green_time < self.agent.max_green:
                self.agent.green_time += 2
                print(f"[{self.agent.name}] ⏩ Estendendo verde para {self.agent.green_time}s")
            elif total_vehicles < 3 and self.agent.green_time > self.agent.min_green:
                self.agent.green_time -= 1
                print(f"[{self.agent.name}] ⏬ Reduzindo verde para {self.agent.green_time}s")

            # Simples mudança de fase (podes adaptar depois)
            if traci.simulation.getTime() % self.agent.green_time == 0:
                next_phase = (current_phase + 1) % len(phases)
                traci.trafficlight.setPhase(tls_id, next_phase)
                print(f"[{self.agent.name}] Mudança de fase para {next_phase}")

        async def on_end(self):
            print(f"[{self.agent.name}] Finalizando comportamento.")

    async def setup(self):
        """Inicialização do agente SPADE"""
        print(f"[{self.jid}] Agente de Semáforo iniciado (controlando {self.tls_id})")

        b = self.ControlBehaviour(period=2)
        self.add_behaviour(b)

        # Parâmetros de comportamento
        self.green_time = 10
        self.min_green = 5
        self.max_green = 20
