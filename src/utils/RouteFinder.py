import xml.etree.ElementTree as ET
import heapq
import traci

class RouteFinder:
    def __init__(self, net_file):
        """
        Initialize the RouteFinder by parsing the SUMO network file.
        :param net_file: Path to the .net.xml file
        """
        self.edges = {} # id -> length
        self.graph = {} # id -> [neighbors]
        self._parse_net(net_file)

    def _parse_net(self, net_file):
        """
        Parses the .net.xml file to build the graph.
        """
        tree = ET.parse(net_file)
        root = tree.getroot()

        # Parse edges
        for edge in root.findall('edge'):
            edge_id = edge.get('id')
            
            # Skip internal edges (intesections)
            if edge.get('function') == 'internal':
                continue
            
            # Get length from the first lane
            # Structure: <edge ...> <lane ... length="..."/> </edge>
            lane = edge.find('lane')
            if lane is not None:
                length = float(lane.get('length'))
                self.edges[edge_id] = length
                self.graph[edge_id] = [] # Initialize adjacency list

        # Parse connections
        for conn in root.findall('connection'):
            from_edge = conn.get('from')
            to_edge = conn.get('to')
            
            # Ensure both edges exist in our graph (are not internal)
            if from_edge in self.edges and to_edge in self.edges:
                # Add connection if not already present
                if to_edge not in self.graph[from_edge]:
                    self.graph[from_edge].append(to_edge)

    def _is_edge_blocked(self, edge_id):
        """
        Check if an edge has all lanes closed to passenger vehicles.
        Returns True if the edge is blocked, False otherwise.
        """
        if not traci.isLoaded():
            # If TraCI is not loaded, assume edge is not blocked
            return False
        
        try:
            lane_count = traci.edge.getLaneNumber(edge_id)
            # Check all lanes - if at least one is open, edge is not blocked
            for i in range(lane_count):
                lane_id = f"{edge_id}_{i}"
                disallowed = traci.lane.getDisallowed(lane_id)
                if "passenger" not in disallowed:
                    # At least one lane is open to passengers
                    return False
            # All lanes are closed to passengers
            return True
        except Exception as e:
            # If error checking edge, assume it's not blocked
            print(f"Warning: Could not check if edge {edge_id} is blocked: {e}")
            return False

    def find_route(self, start_edge, end_edge, check_closures=True):
        """
        Finds the shortest path between start_edge and end_edge using Dijkstra's algorithm.
        Only returns routes where all edges have at least one open lane.
        
        :param start_edge: Starting edge ID
        :param end_edge: Destination edge ID
        :param check_closures: If True, skip edges with all lanes closed (default: True)
        :return: List of edge IDs representing the route, or empty list if no valid route exists
        """
        if start_edge not in self.edges or end_edge not in self.edges:
            # Try to handle the case if start_edge is internal (starts with :) 
            # ideally we would find the outgoing edge from this internal edge, but keeping it simple for now.
            print(f"Error: Start edge '{start_edge}' or End edge '{end_edge}' not found in the network.")
            return []

        # Priority Queue: (cost, current_edge)
        pq = [(0, start_edge)]
        
        # Track distances and parents for path reconstruction
        costs = {start_edge: 0}
        parents = {start_edge: None}
        visited = set()

        while pq:
            current_cost, u = heapq.heappop(pq)

            if u == end_edge:
                break
            
            if u in visited:
                continue
            visited.add(u)

            if u in self.graph:
                for v in self.graph[u]:
                    # Skip this edge if it's blocked (all lanes closed)
                    if check_closures and self._is_edge_blocked(v):
                        continue
                    
                    # Weight is the length of the current edge 'u'.
                    # We assume cost is traversing 'u' to get to 'v'.
                    weight = self.edges[u]
                    new_cost = current_cost + weight
                    
                    if new_cost < costs.get(v, float('inf')):
                        costs[v] = new_cost
                        parents[v] = u
                        heapq.heappush(pq, (new_cost, v))

        # Reconstruct path
        if end_edge not in parents:
            print(f"No path found between {start_edge} and {end_edge}")
            return []
            
        path = []
        curr = end_edge
        while curr:
            path.append(curr)
            curr = parents[curr]
        
        return path[::-1] # Reverse connection to get start -> end
