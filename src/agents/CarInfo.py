import traci
from spade import agent, behaviour
from spade.message import Message
import threading
import os
import json

class CarInfoAgent(agent.Agent):
    # Shared resource to track which vehicles are already claimed by an agent
    claimed_vehicles = set()
    claim_lock = threading.Lock()
    
    # Shared routes database
    # Structure: { destination_edge_id: [ [edge_1, edge_2, ...], ... ] }
    routes_by_dest = {}
    routes_loaded = False
    routes_lock = threading.Lock()

    def __init__(self, jid, password, monitor_jid):
        super().__init__(jid, password)
        self.monitor_jid = monitor_jid
        self.rerouted_vehicles = set()
        self.vehicle_id = None  # The specific vehicle this agent is controlling
        self.ensure_routes_loaded()

    @classmethod
    def ensure_routes_loaded(cls):
        with cls.routes_lock:
            if cls.routes_loaded:
                return
            
            # Absolute path to the routes file
            # Assuming CarInfo.py is in src/agents/ and routes.json is in project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            routes_path = os.path.join(base_dir, "routes.json")
            
            if not os.path.exists(routes_path):
                print(f"[CarInfoAgent] Warning: Routes file not found at {routes_path}")
                return

            try:
                with open(routes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                count = 0
                for entry in data:
                    origin = entry.get("origin", "")
                    dest = entry.get("dest", "")
                    route_lanes = entry.get("route", [])
                    
                    # Sanitize: Strip _<lane_index> suffix to get Edge IDs
                    # Helper to strip suffix
                    def get_edge_id(lane_id):
                        if "_" in lane_id:
                            return lane_id.rsplit("_", 1)[0]
                        return lane_id

                    dest_edge = get_edge_id(dest)
                    route_edges = [get_edge_id(r) for r in route_lanes]
                    
                    if dest_edge and route_edges:
                        if dest_edge not in cls.routes_by_dest:
                            cls.routes_by_dest[dest_edge] = []
                        # Avoid duplicates
                        if route_edges not in cls.routes_by_dest[dest_edge]:
                            cls.routes_by_dest[dest_edge].append(route_edges)
                            count += 1
                
                cls.routes_loaded = True
                print(f"[CarInfoAgent] Loaded {count} unique routes from JSON file (indexed by destination).")
            except Exception as e:
                print(f"[CarInfoAgent] Error loading routes from JSON: {e}")

    class ReportStatusBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            """Envia um relatório de estado para o agente de monitorização."""
            if not traci.isLoaded():
                return

            try:
                status_msg = f"Status: {'Idle' if self.agent.vehicle_id is None else f'Controlling {self.agent.vehicle_id}'}"
                if self.agent.vehicle_id:
                     status_msg += f", Rerouted: {'Yes' if self.agent.vehicle_id in self.agent.rerouted_vehicles else 'No'}"

                msg = Message(to=self.agent.monitor_jid)
                msg.set_metadata("performative", "inform")
                msg.body = status_msg
                await self.send(msg)
            except Exception as e:
                print(f"[{self.agent.name}] Error sending report: {e}")

    class CarInfoBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded():
                return

            # If we don't have a vehicle, try to claim one
            if self.agent.vehicle_id is None:
                car_ids = traci.vehicle.getIDList()
                with CarInfoAgent.claim_lock:
                    for cid in car_ids:
                        if cid not in CarInfoAgent.claimed_vehicles:
                            try:
                                if traci.vehicle.getTypeID(cid) == "ambulance":
                                    continue
                            except Exception:
                                pass
                            self.agent.vehicle_id = cid
                            CarInfoAgent.claimed_vehicles.add(cid)
                            print(f"[{self.agent.name}] Claimed vehicle {cid}")
                            break
                
                # If still no vehicle, just return and wait for next tick
                if self.agent.vehicle_id is None:
                    return

            # If we have a vehicle, check if it still exists
            if self.agent.vehicle_id not in traci.vehicle.getIDList():
                print(f"[{self.agent.name}] Vehicle {self.agent.vehicle_id} finished/disappeared. Releasing.")
                with CarInfoAgent.claim_lock:
                    if self.agent.vehicle_id in CarInfoAgent.claimed_vehicles:
                        CarInfoAgent.claimed_vehicles.remove(self.agent.vehicle_id)
                self.agent.vehicle_id = None
                return

            # Monitor the specific vehicle
            cid = self.agent.vehicle_id
            try:
                # route = traci.vehicle.getRoute(cid) # Used below
                
                # Check if next edge is final and closed
                try:
                    route = traci.vehicle.getRoute(cid)
                    current_idx = traci.vehicle.getRouteIndex(cid)
                    if current_idx >= 0 and current_idx + 1 < len(route):
                        next_edge = route[current_idx + 1]
                        # If next edge is the last one in the route
                        if next_edge == route[-1]:
                            # Check if closed
                            is_closed = True
                            try:
                                lane_count = traci.edge.getLaneNumber(next_edge)
                                for i in range(lane_count):
                                    lane_id = f"{next_edge}_{i}"
                                    disallowed = traci.lane.getDisallowed(lane_id)
                                    if "passenger" not in disallowed:
                                        is_closed = False
                                        break
                            except Exception:
                                is_closed = False # Assume open if error checking edge
                            
                            if is_closed:
                                print(f"[{self.agent.name}] Vehicle {cid} approaching final edge {next_edge} which is closed. Despawning as arrived.")
                                traci.vehicle.remove(cid, reason=3) # 3 = REMOVE_ARRIVED
                                with CarInfoAgent.claim_lock:
                                    if self.agent.vehicle_id in CarInfoAgent.claimed_vehicles:
                                        CarInfoAgent.claimed_vehicles.remove(self.agent.vehicle_id)
                                self.agent.vehicle_id = None
                                return

                except Exception as e:
                    print(f"[{self.agent.name}] Error checking final road for {cid}: {e}")

            except Exception as e:
                print(f"[{self.agent.name}] Error reading info for {cid}: {e}")

    class RerouteBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            # Reroute only when TraCI is available
            if not traci.isLoaded():
                return
            
            # Only act if we control a vehicle
            cid = self.agent.vehicle_id
            if cid is None:
                return

            try:
                # Check if vehicle still exists (double check to avoid race conditions)
                if cid not in traci.vehicle.getIDList():
                    return

                route = traci.vehicle.getRoute(cid)
                if not route:
                    return

                # destination is last edge in route
                dest_edge = route[-1]

                # current edge/road
                current_edge = traci.vehicle.getRoadID(cid)

                # if vehicle already at destination edge, skip
                if current_edge == dest_edge or current_edge == "" or current_edge.startswith(":"):
                    return

                # find where we are in the route
                try:
                    # route_index: first occurrence of current_edge in route
                    route_index = route.index(current_edge)
                except ValueError:
                    # current edge not in original planned route; set index 0
                    route_index = 0

                remaining_edges = route[route_index:]

                # estimate remaining travel time using current traveltime estimates
                remaining_time = 0.0
                ideal_time = 0.0
                
                path_blocked = False

                for edge in remaining_edges:
                    # Check for road closures/disallowed permissions
                    try:
                        # If all lanes are closed to passenger, the edge is blocked.
                        path_blocked_edge = True
                        lane_count = traci.edge.getLaneNumber(edge)
                        for i in range(lane_count):
                            lane_id = f"{edge}_{i}"
                            disallowed = traci.lane.getDisallowed(lane_id)
                            if "passenger" not in disallowed:
                                path_blocked_edge = False
                                break
                        
                        if path_blocked_edge:
                            path_blocked = True
                            remaining_time += 1e6 # Add huge penalty
                    except Exception:
                        pass
                        
                    try:
                        remaining_time += float(traci.edge.getTraveltime(edge))
                    except Exception:
                        # if getTraveltime unavailable, fall back to length / maxSpeed
                        try:
                            remaining_time += float(traci.edge.getLength(edge)) / max(0.1, float(traci.edge.getMaxSpeed(edge)))
                        except Exception:
                            remaining_time += 0.0

                    try:
                        ideal_time += float(traci.edge.getLength(edge)) / max(0.1, float(traci.edge.getMaxSpeed(edge)))
                    except Exception:
                        ideal_time += 0.0

                # decide if reroute
                factor = self.agent.reroute_threshold_factor
                max_delay = self.agent.max_allowed_delay

                # if remaining_time is much larger than ideal OR absolute delay large OR path blocked
                if (ideal_time > 0 and remaining_time > ideal_time * factor) or (remaining_time - ideal_time > max_delay) or path_blocked:
                    # Look up routes ending at dest_edge in our static DB
                    potential_full_routes = CarInfoAgent.routes_by_dest.get(dest_edge, [])
                    
                    best_route = None
                    min_cost = float('inf')

                    for full_route in potential_full_routes:
                        # We need a route that contains current_edge
                        if current_edge not in full_route:
                            continue
                        
                        # Extract the part from current_edge to end
                        start_idx = full_route.index(current_edge)
                        candidate_path = full_route[start_idx:]

                        # Verify candidate path is not blocked and calculate cost
                        candidate_blocked = False
                        candidate_cost = 0.0
                        
                        for edge in candidate_path:
                            # Check blockage
                            is_edge_blocked = False
                            try:
                                lane_count = traci.edge.getLaneNumber(edge)
                                for i in range(lane_count):
                                    lane_id = f"{edge}_{i}"
                                    disallowed = traci.lane.getDisallowed(lane_id)
                                    if "passenger" not in disallowed:
                                        break
                                else:
                                    is_edge_blocked = True
                            except:
                                pass # Assume open

                            if is_edge_blocked:
                                candidate_blocked = True
                                break
                            
                            # Add cost
                            try:
                                candidate_cost += float(traci.edge.getTraveltime(edge))
                            except:
                                try:
                                    candidate_cost += float(traci.edge.getLength(edge)) / max(0.1, float(traci.edge.getMaxSpeed(edge)))
                                except:
                                    pass
                        
                        if not candidate_blocked:
                            # Prefer routes that are different from current plan if current plan is blocked or slow
                            # But cost is the ultimate decider.
                            if candidate_cost < min_cost:
                                min_cost = candidate_cost
                                best_route = candidate_path

                    if best_route:
                        # Only apply if it's different from what we intend to do (remaining_edges)
                        # or if our current path is blocked and this one isn't.
                        # Note: remaining_edges might include edges we just passed if route_index is stale, but usually it's correct.
                        # Simple check: if best_route is better than remaining_time (which was calculated above).
                        
                        # If path_blocked was True, and we found a valid route, we should switch!
                        should_switch = False
                        if path_blocked:
                            should_switch = True
                        elif min_cost < remaining_time * 0.9: # 10% improvement
                            should_switch = True
                        
                        if should_switch and best_route != remaining_edges:
                            try:
                                traci.vehicle.setRoute(cid, best_route)
                                self.agent.rerouted_vehicles.add(cid)
                                print(f"[{self.agent.name}] Rerouted vehicle {cid} using static route (Cost: {min_cost:.2f} vs Old: {remaining_time:.2f})")
                            except Exception as e:
                                print(f"[{self.agent.name}] Failed to set new route for {cid}: {e}")
                    else:
                         if path_blocked:
                             # print(f"[{self.agent.name}] Could not find better open route for {cid} despite blockage.")
                             pass

            except Exception as e:
                # protect behaviour from crashing on unexpected traci errors
                print(f"[{self.agent.name}] Error checking reroute for {cid}: {e}")

    async def setup(self):
        print(f"[{self.jid}] Agente de Informação de Carros iniciado")
        car_behaviour = self.CarInfoBehaviour(period=1)  # Check more frequently to claim vehicles fast
        self.add_behaviour(car_behaviour)

        # Reroute behaviour params
        self.reroute_check_period = 5  # seconds between reroute evaluations
        self.reroute_threshold_factor = 1.5  # if remaining_time > ideal_time * factor => reroute
        self.max_allowed_delay = 20.0  # seconds of absolute delay beyond ideal to trigger reroute

        reroute_behaviour = self.RerouteBehaviour(period=self.reroute_check_period)
        self.add_behaviour(reroute_behaviour)

        # Adiciona o comportamento de envio de relatórios
        report_behaviour = self.ReportStatusBehaviour(period=12) # Envia relatório a cada 12s
        self.add_behaviour(report_behaviour)
