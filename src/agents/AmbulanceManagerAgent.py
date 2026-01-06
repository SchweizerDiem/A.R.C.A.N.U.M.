from spade import agent, behaviour
from spade.message import Message
import traci
import random
import time

class AmbulanceManagerAgent(agent.Agent):
    def __init__(self, jid, password, tls_mapping):
        super().__init__(jid, password)
        self.tls_mapping = tls_mapping # {tls_id: jid}
        self.active_ambulances = {} # {veh_id: spawn_time}
        self.ambulance_counter = 0

    class SpawnAmbulanceBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded(): return
            
            # Maintain 1 active ambulance
            current_time = time.time()
            # Clean up old ambiguous entries just in case, though Monitor handles it
            
            if len(self.agent.active_ambulances) < 1:
                 try:
                     routes = traci.route.getIDList()
                     if routes:
                         route_id = random.choice(routes)
                         veh_id = f"ambulance_{self.agent.ambulance_counter}"
                         try:
                             traci.vehicle.add(veh_id, route_id, typeID="ambulance")
                             self.agent.active_ambulances[veh_id] = current_time
                             self.agent.ambulance_counter += 1
                             print(f"[{self.agent.name}] SPAWNED AMBULANCE {veh_id} on route {route_id}")
                         except Exception as e:
                             print(f"[{self.agent.name}] Error spawning: {e}")
                 except Exception as e:
                     pass

    class MonitorAmbulanceBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded(): return

            try:
                current_vehs = set(traci.vehicle.getIDList())
                arrived_vehs = set(traci.simulation.getArrivedIDList())
            except Exception:
                return
            
            finished = []
            current_real_time = time.time()
            GRACE_PERIOD = 5.0 # seconds

            for veh_id, spawn_time in self.agent.active_ambulances.items():
                
                # Check if definitely finished
                if veh_id in arrived_vehs:
                    finished.append(veh_id)
                    continue

                # If not in running list
                if veh_id not in current_vehs:
                    # If within grace period, ignore
                    if (current_real_time - spawn_time) < GRACE_PERIOD:
                        continue
                    else:
                        # Assumed finished/failed if not running after grace period
                        finished.append(veh_id)
                else:
                    # Vehicle is running
                    try:
                        next_tls = traci.vehicle.getNextTLS(veh_id) 
                        if next_tls:
                            tls_id, tls_index, dist, state = next_tls[0]
                            if dist < 150: 
                                tls_jid = self.agent.tls_mapping.get(tls_id)
                                if tls_jid:
                                    msg = Message(to=tls_jid)
                                    msg.set_metadata("performative", "request")
                                    msg.body = f"priority_request:{veh_id}"
                                    await self.send(msg)
                    except Exception as e:
                        print(f"[{self.agent.name}] Error monitoring {veh_id}: {e}")

            for f in finished:
                if f in self.agent.active_ambulances:
                    del self.agent.active_ambulances[f]
                    print(f"[{self.agent.name}] Ambulance {f} finished.")

    async def setup(self):
         print(f"[{self.jid}] Ambulance Manager started")
         self.add_behaviour(self.SpawnAmbulanceBehaviour(period=30)) 
         self.add_behaviour(self.MonitorAmbulanceBehaviour(period=0.5)) 
