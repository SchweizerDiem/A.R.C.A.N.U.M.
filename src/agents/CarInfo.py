import traci
from spade import agent, behaviour
from spade.message import Message
from spade.message import Message
import threading
import sys
import os

# Ensure we can find the util
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from src.utils.RouteFinder import RouteFinder

class CarInfoAgent(agent.Agent):
    # Shared resource to track which vehicles are already claimed by an agent
    claimed_vehicles = set()
    claim_lock = threading.Lock()
    
    # Shared RouteFinder instance (Singleton)
    route_finder = None
    route_finder_lock = threading.Lock()

    def __init__(self, jid, password, monitor_jid):
        super().__init__(jid, password)
        self.monitor_jid = monitor_jid
        self.rerouted_vehicles = set()
        self.vehicle_id = None  # The specific vehicle this agent is controlling

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
                pos = traci.vehicle.getPosition(cid)
                speed = traci.vehicle.getSpeed(cid)
                route = traci.vehicle.getRoute(cid)
                lane = traci.vehicle.getLaneID(cid)
                # print(f"[{self.agent.name}] Monitoring {cid} -> Pos: {pos}, Speed: {speed:.2f}, Lane: {lane}")

                # Check if next edge is final and closed
                try:
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
                if current_edge == dest_edge or current_edge == "":
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
                        # traci.edge.getDisallowed does not exist. Must check lanes.
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
                    # compute alternative route from current_edge to dest
                    try:
                        # Use custom RouteFinder instead of traci.simulation.findRoute
                        # Initialize if needed (double-checked locking pattern)
                        if CarInfoAgent.route_finder is None:
                            with CarInfoAgent.route_finder_lock:
                                if CarInfoAgent.route_finder is None:
                                    # Assuming path is relative to repo root, or we can use absolute path
                                    # Adjust this path if necessary to match runtime CWD
                                    net_file = "sumo_environment/network.net.xml"
                                    if not os.path.exists(net_file):
                                        # If running from src/ or agents/, try stepping back
                                        net_file = "../sumo_environment/network.net.xml" 
                                        if not os.path.exists(net_file):
                                             net_file = "../../sumo_environment/network.net.xml"
                                    
                                    print(f"[{self.agent.name}] Initializing shared RouteFinder with {net_file}...")
                                    CarInfoAgent.route_finder = RouteFinder(net_file)

                        print(f"[{self.agent.name}] Custom RouteFinder calculating route...")
                        new_edges = CarInfoAgent.route_finder.find_route(current_edge, dest_edge)
                        
                    except Exception as e:
                        print(f"[{self.agent.name}] RouteFinder error: {e}")
                        new_edges = None

                    if new_edges and len(new_edges) > 0 and new_edges != remaining_edges:
                        try:
                            traci.vehicle.setRoute(cid, new_edges)
                            self.agent.rerouted_vehicles.add(cid)
                            print(f"[{self.agent.name}] Rerouted vehicle {cid} (Path valid/better? {not path_blocked})")
                        except Exception as e:
                            print(f"[{self.agent.name}] Failed to set new route for {cid}: {e}")

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
