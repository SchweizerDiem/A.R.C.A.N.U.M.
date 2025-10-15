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

            current_time = traci.simulation.getTime()


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

            time_on_phase = current_time - self.agent.current_phase_start_time
            print(f"[{self.agent.name}] Tempo na Fase {current_phase}: {time_on_phase:.1f}s")


            # 1. Lógica para as Fases VERDE (Green)
            if "g" in phases[current_phase].state or "G" in phases[current_phase].state: # se verde atual

                # Lógica Adaptativa: Ajustar o tempo que esta fase VAI durar
                # Se houver muitos carros aumenta o tempo, senão diminui
                if total_vehicles > 10 and self.agent.green_time_duration < self.agent.max_green:
                    self.agent.green_time_duration += 2
                    # Nota: O tempo é ajustado para *a próxima* fase verde ou para prolongar a atual
                    print(f"[{self.agent.name}] Estendendo verde para {self.agent.green_time_duration}s")
                elif total_vehicles < 3 and self.agent.green_time_duration > self.agent.min_green:
                    self.agent.green_time_duration -= 1
                    print(f"[{self.agent.name}] Reduzindo verde para {self.agent.green_time_duration}s")

                # Decisão de MUDAR: Se atingiu o tempo mínimo E há poucos carros, OU se atingiu o tempo máximo.
                if (time_on_phase >= self.agent.min_green and total_vehicles < 5) or \
                   (time_on_phase >= self.agent.green_time_duration):
                    next_phase = current_phase + 1
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time # Reset do timer
                    print(f"[{self.agent.name}] MUDANÇA: Verde -> Amarelo. Próximo verde: {self.agent.green_time_duration}s")

            # 2. Lógica para as Fases AMARELO (Yellow)
            elif "y" in phases[current_phase].state or "Y" in phases[current_phase].state: # se amarelo atual
                # O amarelo deve durar um tempo fixo
                if time_on_phase >= self.agent.yellow_time:

                    # Próxima fase deve ser o VERMELHO para a direção atual
                    next_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time # Reset do timer
                    print(f"[{self.agent.name}] MUDANÇA: Amarelo -> Próximo. Nova fase: {next_phase}")

            # 3. Lógica para as Fases de TRANSIÇÃO/VERMELHO 
            else:
                # Usa um tempo fixo (pode ser o mesmo que o amarelo)
                transition_time = self.agent.red_time 
                
                if time_on_phase >= transition_time:
                    
                    # Próxima fase (deve ser o próximo verde)
                    next_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time # Reset do timer
                    print(f"[{self.agent.name}] MUDANÇA: Transição/Vermelho -> Próximo. Nova fase: {next_phase}")

            '''
            # Lógica adaptativa simples
            # Se houver muito trânsito, mantém verde por mais tempo
            if total_vehicles > 10 and self.agent.green_time < self.agent.max_green:
                self.agent.green_time += 2
                print(f"[{self.agent.name}] Estendendo verde para {self.agent.green_time}s")
            elif total_vehicles < 3 and self.agent.green_time > self.agent.min_green:
                self.agent.green_time -= 1
                print(f"[{self.agent.name}] Reduzindo verde para {self.agent.green_time}s")

            # Simples mudança de fase (podes adaptar depois)
            if traci.simulation.getTime() % self.agent.green_time == 0:
                next_phase = (current_phase + 1) % len(phases)
                traci.trafficlight.setPhase(tls_id, next_phase)
                print(f"[{self.agent.name}] Mudança de fase para {next_phase}")
            '''

        async def on_end(self):
            print(f"[{self.agent.name}] Finalizando comportamento.")

    async def setup(self):
        """Inicialização do agente SPADE"""
        print(f"[{self.jid}] Agente de Semáforo iniciado (controlando {self.tls_id})")

        b = self.ControlBehaviour(period=2)
        self.add_behaviour(b)

        # Parâmetros de comportamento
        self.green_time_duration = 10 # Tempo de verde decidido para o ciclo atual
        self.min_green = 5
        self.max_green = 20
        self.yellow_time = 4 # Tempo fixo para a fase amarela
        self.red_time = 4 # Tempo fixo para a fase vermelho

        # Variáveis de estado
        self.current_phase_start_time = 0.0 # Inicializa com um valor

        # Garante que o agente inicia com a hora correta da primeira fase
        try:
             self.current_phase_start_time = traci.simulation.getTime()
        except traci.exceptions.TraCIException:
             # Se o SUMO ainda não estiver ligado, o valor 0.0 é ok
             pass
