import os
import sys
import traci

# =========================================================================
# 1. Configuração Robusta
# =========================================================================

# Esta linha verifica se o comando 'export' foi executado.
if 'SUMO_HOME' not in os.environ:
    sys.exit("ERRO CRÍTICO: Por favor, execute 'export SUMO_HOME=/caminho/do/seu/sumo' no terminal.")

# O código usa a variável do terminal para encontrar a pasta 'tools'.
sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))

# Configuração da simulação
SUMO_BINARY = "sumo-gui"
SUMO_CFG_FILE = "map.sumocfg" 
SUMO_CMD = [SUMO_BINARY, "-c", SUMO_CFG_FILE]

# =========================================================================
# 2. IDs do Seu Mapa (CORRIGIDOS)
# =========================================================================
# O ID que o TraCI usa para o cruzamento.
TL_ID = "25632230"
# Usamos o ID da junção (junction) que é controlável na rede
# Mantenha o ID antigo, mas trate-o como Junção controlável, não como semáforo TL
JUNCTION_ID = "25632230" 
LANE_A_ID = "1032038604#2_0"
LANE_B_ID = "-1206667334#0_0"


# =========================================================================
# 3. O Cérebro do Agente (Vê, Pensa, Faz)
# =========================================================================
# ... (código acima, incluindo a parte de Configuração do Caminho)

# ... (IDs do seu mapa, conforme corrigido acima)

def run_agent():
    try:
        print(">> A iniciar a simulação e a ligar o TraCI...")
        traci.start(SUMO_CMD)
        step = 0

        # Verifica e armazena o ID do semáforo apenas uma vez
        tl_list = traci.trafficlight.getIDList()
        if not tl_list:
            print("AVISO: NENHUM semáforo (TL) encontrado na rede. O agente não pode controlar o tráfego.")
            # Para este erro específico, vamos terminar aqui, pois o objetivo é o controlo TL.
            traci.close()
            sys.exit(0)
            
        # Assumindo que o seu TL ID é o primeiro (ou ajuste-o se for diferente)
        # Se 25632230 NÃO for um TL, vamos usar o primeiro ID encontrado (se existir)
        TL_TO_CONTROL = tl_list[0] 
        print(f"ID do Semáforo Encontrado e a ser Controlado: {TL_TO_CONTROL}")

        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            
            # --- VÊ (OBSERVAÇÃO) ---
            fila_A = traci.lane.getLastStepHaltingNumber(LANE_A_ID)
            fila_B = traci.lane.getLastStepHaltingNumber(LANE_B_ID)
            
            # --- PENSA (DECISÃO) ---
            # Assume que a fase atual é a melhor, a menos que as filas sejam drásticas
            nova_fase = traci.trafficlight.getPhase(TL_TO_CONTROL) 
            
            if fila_A > 3 * fila_B:
                nova_fase = 0 
            elif fila_B > 3 * fila_A:
                nova_fase = 1
            
            # --- FAZ (AÇÃO) ---
            traci.trafficlight.setPhase(TL_TO_CONTROL, nova_fase)
            
            step += 1
            
            if step % 100 == 0:
                 print(f"Passo: {step} | Fila A: {fila_A} | Fila B: {fila_B} | Fase Ativa: {nova_fase}")
                 
        traci.close()
        print(">> Simulação terminada.")
        
    except traci.exceptions.TraCIException as e:
        print(f"ERRO DE LIGAÇÃO. Confirme que o programa 'sumo-gui' está na sua PATH: {e}")
    except Exception as e:
        print(f"Ocorreu um erro geral: {e}")

if __name__ == "__main__":
    run_agent()
