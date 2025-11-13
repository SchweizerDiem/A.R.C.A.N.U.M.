"""
TrafficLightAgent.py
--------------------
Feature 2: Traffic Light Agent (com SUMO + SPADE)

Este agente controla um conjunto de semáforos numa interseção do SUMO.
Ele observa as filas através do TraCI e ajusta o tempo do verde dinamicamente.

Algoritmo (melhoria):
 - A cada ciclo (period=2s) o agente coleta por-lane o número de veículos e tempo de espera.
 - Calcula uma "demanda" por fase: demanda = vehicles + 0.2 * waiting_time.
 - Prioriza a fase com maior demanda; se outra fase tiver demanda significativamente maior
     (fator configurável) e o tempo mínimo na fase atual já passou, inicia a transição.
 - Mantém limites mínimo e máximo para o tempo de verde por fase (min_green / max_green).

Parâmetros tunáveis:
 - green_time_duration: tempo alvo atual de verde (inicial 10s)
 - min_green / max_green: limites para o verde (5s / 20s)
 - yellow_time / red_time: tempos fixos de segurança (4s cada)
 - demand_threshold_factor: quanto maior a demanda da melhor fase em relação à atual para forçar troca (default 1.25)

Essa abordagem busca reduzir o tempo de espera médio priorizando direções com filas maiores,
preservando segurança com tempos mínimos e fases de transição.

Autor: (tu)
"""

from spade import agent, behaviour
import traci
import asyncio
from spade.message import Message


class TrafficLightAgent(agent.Agent):
    def __init__(self, jid, password, tls_id, monitor_jid):
        super().__init__(jid, password)
        self.tls_id = tls_id
        self.monitor_jid = monitor_jid

    class ReportStatusBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            """Envia um relatório de estado para o agente de monitorização."""
            if not traci.isLoaded():
                return

            try:
                current_phase = traci.trafficlight.getPhase(self.agent.tls_id)
                time_on_phase = traci.simulation.getTime() - self.agent.current_phase_start_time
                status_msg = f"Phase: {current_phase}, Time on phase: {time_on_phase:.1f}s"

                msg = Message(to=self.agent.monitor_jid)
                msg.set_metadata("performative", "inform")
                msg.body = status_msg
                await self.send(msg)
            except Exception as e:
                print(f"[{self.agent.name}] Error sending report: {e}")

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

            #print(f"[{self.agent.name}] Veículos: {total_vehicles}, Espera média: {avg_waiting:.2f}s")

            time_on_phase = current_time - self.agent.current_phase_start_time
            #print(f"[{self.agent.name}] Tempo na Fase {current_phase}: {time_on_phase:.1f}s")


            # === Per-phase demand scoring ===
            # Para cada fase, somamos os veículos e o tempo de espera das lanes que têm verde nessa fase.
            phase_demands = []
            controlled_lanes = lanes
            for i, phase in enumerate(phases):
                demand_veh = 0
                demand_wait = 0
                # A string phase.state tem um char por lane na mesma ordem de controlled_lanes
                for lane_idx, lane_id in enumerate(controlled_lanes):
                    if lane_idx < len(phase.state) and phase.state[lane_idx] in ("g", "G"):
                        try:
                            v = traci.lane.getLastStepVehicleNumber(lane_id)
                            w = traci.lane.getWaitingTime(lane_id)
                        except Exception:
                            v, w = 0, 0
                        demand_veh += v
                        demand_wait += w
                # Score combina número de veículos com espera, ponderando espera menos que contagem
                score = demand_veh + 0.2 * (demand_wait)
                phase_demands.append(score)

            # Escolhe a fase com maior demanda (prioridade)
            best_phase = max(range(len(phases)), key=lambda i: phase_demands[i]) if phases else current_phase
            current_phase_demand = phase_demands[current_phase] if phases else 0
            best_phase_demand = phase_demands[best_phase] if phases else 0

            #print(f"[{self.agent.name}] Demanda por fase: {[round(x,1) for x in phase_demands]}")

            # 1. Lógica para as Fases VERDE (Green)
            if "g" in phases[current_phase].state or "G" in phases[current_phase].state:  # se verde atual

                # Lógica Adaptativa: ajusta o tempo alvo de verde com base no tráfego total
                if total_vehicles > 10 and self.agent.green_time_duration < self.agent.max_green:
                    self.agent.green_time_duration = min(self.agent.max_green, self.agent.green_time_duration + 2)
                    #print(f"[{self.agent.name}] Estendendo verde para {self.agent.green_time_duration}s")
                elif total_vehicles < 3 and self.agent.green_time_duration > self.agent.min_green:
                    self.agent.green_time_duration = max(self.agent.min_green, self.agent.green_time_duration - 1)
                    #print(f"[{self.agent.name}] Reduzindo verde para {self.agent.green_time_duration}s")

                # Decide se inicia a transição para a próxima fase:
                # - Se passou o tempo mínimo E outra fase tem demanda significativamente maior
                # - Ou se atingiu o tempo máximo planejado para esta fase
                demand_threshold_factor = 1.25
                if ((time_on_phase >= self.agent.min_green and best_phase != current_phase and best_phase_demand > current_phase_demand * demand_threshold_factor)
                        or (time_on_phase >= self.agent.green_time_duration)):
                    # Inicia a transição (normalmente a fase seguinte é o amarelo)
                    next_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time  # Reset do timer
                    #print(f"[{self.agent.name}] MUDANÇA: Verde -> Amarelo. Próximo verde alvo: {self.agent.green_time_duration}s")

            # 2. Lógica para as Fases AMARELO (Yellow)
            elif "y" in phases[current_phase].state or "Y" in phases[current_phase].state: # se amarelo atual
                # O amarelo deve durar um tempo fixo
                if time_on_phase >= self.agent.yellow_time:

                    # Próxima fase deve ser o VERMELHO para a direção atual
                    next_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time # Reset do timer
                    #print(f"[{self.agent.name}] MUDANÇA: Amarelo -> Próximo. Nova fase: {next_phase}")

            # 3. Lógica para as Fases de TRANSIÇÃO/VERMELHO
            else:
                # Usa um tempo fixo (pode ser o mesmo que o amarelo)
                transition_time = self.agent.red_time

                if time_on_phase >= transition_time:

                    # Próxima fase (deve ser o próximo verde)
                    next_phase = (current_phase + 1) % len(phases)
                    traci.trafficlight.setPhase(tls_id, next_phase)
                    self.agent.current_phase_start_time = current_time # Reset do timer
                    #print(f"[{self.agent.name}] MUDANÇA: Transição/Vermelho -> Próximo. Nova fase: {next_phase}")

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

        # Adiciona o comportamento de controlo principal
        control_behaviour = self.ControlBehaviour(period=2)
        self.add_behaviour(control_behaviour)

        # Adiciona o comportamento de envio de relatórios
        report_behaviour = self.ReportStatusBehaviour(period=10) # Envia relatório a cada 10s
        self.add_behaviour(report_behaviour)

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

