import traci
from spade import agent, behaviour


class CarInfoAgent(agent.Agent):
    """Agente leve para observação de veículos e rerouting reativo.

    Comportamentos:
    - CarInfoBehaviour: imprime estado dos carros (debug)
    - RerouteBehaviour: verifica, a cada N segundos, se um carro está muito atrasado
      comparado ao tempo ideal restante e tenta rerotar usando `simulation.findRoute`.

    Parâmetros importantes (definidos em `setup`):
    - reroute_check_period: segundos entre checagens de reroute
    - reroute_threshold_factor: se remaining_time > ideal_time * factor => tenta reroute
    - max_allowed_delay: se remaining_time - ideal_time > this => tenta reroute
    """

    class CarInfoBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            if not traci.isLoaded():
                return

            step = traci.simulation.getTime()
            car_ids = traci.vehicle.getIDList()

            if not car_ids:
                print(f"[Car Info] Step {step}: Nenhum carro ativo.")
                return

            print(f"\n[Car Info] Step {step}")
            for cid in car_ids:
                try:
                    pos = traci.vehicle.getPosition(cid)
                    speed = traci.vehicle.getSpeed(cid)
                    route = traci.vehicle.getRoute(cid)
                    lane = traci.vehicle.getLaneID(cid)
                    print(f"  → ID: {cid}, Pos: {pos}, Velocidade: {speed:.2f} m/s, Faixa: {lane}, Rota: {route}")
                except Exception as e:
                    print(f"[Car Info] Erro lendo info do veículo {cid}: {e}")

    class RerouteBehaviour(behaviour.PeriodicBehaviour):
        async def run(self):
            # Reroute only when TraCI is available
            if not traci.isLoaded():
                return

            # iterate vehicles and decide if reroute is beneficial
            car_ids = traci.vehicle.getIDList()
            for cid in car_ids:
                try:
                    route = traci.vehicle.getRoute(cid)
                    if not route:
                        continue

                    # destination is last edge in route
                    dest_edge = route[-1]

                    # current edge/road
                    current_edge = traci.vehicle.getRoadID(cid)

                    # if vehicle already at destination edge, skip
                    if current_edge == dest_edge or current_edge == "":
                        continue

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
                    for edge in remaining_edges:
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

                    # if remaining_time is much larger than ideal OR absolute delay large
                    if (ideal_time > 0 and remaining_time > ideal_time * factor) or (remaining_time - ideal_time > max_delay):
                        # compute alternative route from current_edge to dest
                        try:
                            new_route = traci.simulation.findRoute(current_edge, dest_edge)
                            # new_route may be a FindRouteResult with .edges attribute
                            if hasattr(new_route, 'edges'):
                                new_edges = new_route.edges
                            elif isinstance(new_route, (list, tuple)):
                                new_edges = list(new_route)
                            else:
                                # try to coerce
                                new_edges = list(getattr(new_route, 'route', []) or [])
                        except Exception as e:
                            new_edges = None

                        if new_edges and len(new_edges) > 0 and new_edges != remaining_edges:
                            try:
                                traci.vehicle.setRoute(cid, new_edges)
                                print(f"[Reroute] Vehicle {cid}: rerouted at edge {current_edge}. Old remaining: {remaining_edges} New: {new_edges}")
                            except Exception as e:
                                print(f"[Reroute] Vehicle {cid}: failed to set new route: {e}")

                except Exception as e:
                    # protect behaviour from crashing on unexpected traci errors
                    print(f"[Reroute] Error checking vehicle {cid}: {e}")

    async def setup(self):
        print(f"[{self.jid}] Agente de Informação de Carros iniciado")
        car_behaviour = self.CarInfoBehaviour(period=2)  # executa a cada 2s
        self.add_behaviour(car_behaviour)

        # Reroute behaviour params
        self.reroute_check_period = 5  # seconds between reroute evaluations
        self.reroute_threshold_factor = 1.5  # if remaining_time > ideal_time * factor => reroute
        self.max_allowed_delay = 20.0  # seconds of absolute delay beyond ideal to trigger reroute

        reroute_behaviour = self.RerouteBehaviour(period=self.reroute_check_period)
        self.add_behaviour(reroute_behaviour)
