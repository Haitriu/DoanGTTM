from typing import List, Dict, Optional
from dataclasses import dataclass
from voltrail_core.models import ChargingStation, RouteSegment, Vehicle
from voltrail_core.energy import compute_segment_energy

@dataclass
class GraphEdge:
    to_node_id: str
    distance_m: float
    drive_time_s: int
    energy_consumed_kwh: float

@dataclass
class GraphNode:
    station: ChargingStation
    edges: List[GraphEdge]

class ChargingGraph:
    """
    Biểu diễn đồ thị trạm sạc cho thuật toán tìm đường.
    Node là các trạm sạc (cộng thêm Origin và Destination).
    Edge là chặng đường lái xe giữa hai trạm.
    """
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        
    def add_node(self, station: ChargingStation):
        if station.id not in self.nodes:
            self.nodes[station.id] = GraphNode(station=station, edges=[])
            
    def add_edge(self, from_id: str, to_id: str, distance_m: float, drive_time_s: int, energy_consumed_kwh: float):
        if from_id in self.nodes and to_id in self.nodes:
            self.nodes[from_id].edges.append(GraphEdge(
                to_node_id=to_id,
                distance_m=distance_m,
                drive_time_s=drive_time_s,
                energy_consumed_kwh=energy_consumed_kwh
            ))
            
    def build_from_stations(
        self, 
        origin_id: str, 
        destination_id: str, 
        stations: List[ChargingStation],
        vehicle: Vehicle,
        # Giả lập logic tính cạnh. Trong thực tế sẽ gọi OSRM để tính distance/time/energy giữa từng cặp trạm
    ):
        """
        Dựng đồ thị đầy đủ từ danh sách trạm sạc. 
        Trong Phase 2 rút gọn, ta nối các trạm kề nhau theo khoảng cách chim bay.
        """
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lon1, lat1, lon2, lat2):
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            return 2 * asin(sqrt(a)) * 6371000 
            
        for s in stations:
            self.add_node(s)
            
        # O(N^2) nối các trạm nằm trong tầm với (VD < 400km)
        max_reach_m = 400000 
        
        station_ids = list(self.nodes.keys())
        for i in range(len(station_ids)):
            for j in range(i + 1, len(station_ids)):
                id1 = station_ids[i]
                id2 = station_ids[j]
                
                s1 = self.nodes[id1].station
                s2 = self.nodes[id2].station
                
                dist_m = haversine(s1.location.lon, s1.location.lat, s2.location.lon, s2.location.lat)
                if dist_m <= max_reach_m:
                    # Giả định đường thẳng, tốc độ 80km/h
                    speed_mps = 80 * 1000 / 3600
                    drive_time = int(dist_m / speed_mps)
                    
                    # Giả định tiêu thụ năng lượng trung bình 18kWh/100km
                    energy = (dist_m / 100000) * 18.0
                    
                    self.add_edge(id1, id2, dist_m, drive_time, energy)
                    self.add_edge(id2, id1, dist_m, drive_time, energy)
