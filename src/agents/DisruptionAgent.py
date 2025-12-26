import traci
from spade import agent, behaviour
import asyncio
import random

class DisruptionAgent(agent.Agent):
    class DisruptionBehaviour(behaviour.CyclicBehaviour):
        async def on_start(self):
            print(f"[{self.agent.name}] DisruptionBehaviour starting...")
            # da algum tempo para o SUMO começar
            await asyncio.sleep(5)

        async def run(self):
            if not traci.isLoaded():
                await asyncio.sleep(1)
                return

            # lista de linhas
            lane_list = ["E1_0", "E2_0" , "E3_0",
                         "E4_0", "E5_0", "E6_0", 
                         "E7_0", "E8_0", "E9_0",
                         "E10_0", "E11_0", "E12_0",
                         "E13_0", "E14_0", "E15_0", "E16_0"]
            
            # lista de linhas (sentido oposto)
            lane_1_list = ["-E1_0", "-E2_0" , "-E3_0",
                         "-E4_0", "-E5_0", "-E6_0", 
                         "-E7_0", "-E8_0", "-E9_0",
                         "-E10_0", "-E11_0", "-E12_0",
                         "-E13_0", "-E14_0", "-E15_0", "-E16_0"]

            # escolhe uma linha aleatória
            ran = random.randint(0, len(lane_list) - 1)

            # Config
            target_lane = lane_list[ran] # Using lane ID directly
            target_lane_1 = lane_1_list[ran] # Using edge ID directly
            closure_duration = 60  # seconds
            open_duration = 30     # seconds

            # Close the road
            try:
                # Para as linhas
                print(f"[{self.agent.name}] CLOSING lane {target_lane} for {closure_duration}s")
                # proibe 'passenger' (carros)
                # traci.lane.getDisallowed retorna uma tuple/list de strings
                current_disallowed = set(traci.lane.getDisallowed(target_lane))
                current_disallowed.add("passenger")
                traci.lane.setDisallowed(target_lane, list(current_disallowed))
                
                # Feedback visual (muda cor)
                traci.gui.toggleSelection(target_lane, "lane") 

                # Para as linhas (sentido oposto)
                print(f"[{self.agent.name}] CLOSING lane {target_lane_1} for {closure_duration}s")
                # proibe 'passenger' (carros)
                # traci.lane.getDisallowed retorna uma tuple/list de strings
                current_disallowed = set(traci.lane.getDisallowed(target_lane_1))
                current_disallowed.add("passenger")
                traci.lane.setDisallowed(target_lane_1, list(current_disallowed))
                
                # Feedback visual (muda cor)
                traci.gui.toggleSelection(target_lane_1, "lane") 
                
            except Exception as e:
                print(f"[{self.agent.name}] Error closing lane: {e}")

            await asyncio.sleep(closure_duration)

            # Re-open the road
            if traci.isLoaded():
                try:
                    # Abre as linhas
                    print(f"[{self.agent.name}] OPENING lane {target_lane} for {open_duration}s")
                    current_disallowed = set(traci.lane.getDisallowed(target_lane))
                    if "passenger" in current_disallowed:
                        current_disallowed.remove("passenger")
                    traci.lane.setDisallowed(target_lane, list(current_disallowed))
                    
                    # Abre as linhas (sentido oposto)
                    print(f"[{self.agent.name}] OPENING lane {target_lane_1} for {open_duration}s")
                    current_disallowed = set(traci.lane.getDisallowed(target_lane_1))
                    if "passenger" in current_disallowed:
                        current_disallowed.remove("passenger")
                    traci.lane.setDisallowed(target_lane_1, list(current_disallowed))
                    
                except Exception as e:
                    print(f"[{self.agent.name}] Error opening lane: {e}")

            await asyncio.sleep(open_duration)

    async def setup(self):
        print(f"[{self.jid}] DisruptionAgent started")
        b = self.DisruptionBehaviour()
        self.add_behaviour(b)
