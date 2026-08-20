import random
from typing import List
from datetime import datetime
import json
from voltrail_core.models import Coordinate, ChargingStation, Connector, Confidence

def generate_mock_stations(center: Coordinate, radius_km: float, num_stations: int) -> List[ChargingStation]:
    stations = []
    
    # Very crude approximation: 1 degree latitude is approx 111km
    deg_per_km = 1 / 111.0
    
    operators = ["E-Boost", "Charge+ VN", "VinFast", "EV One", "Rabbit EVC"]
    
    for i in range(num_stations):
        # Random point within roughly a square of 2*radius_km
        lat = center.lat + random.uniform(-radius_km * deg_per_km, radius_km * deg_per_km)
        lon = center.lon + random.uniform(-radius_km * deg_per_km, radius_km * deg_per_km)
        
        op = random.choice(operators)
        power = random.choice([50.0, 150.0, 250.0, 11.0, 60.0])
        
        conn = Connector("ccs2", power, random.randint(1, 4))
        
        station = ChargingStation(
            id=f"SIM-{i:04d}",
            location=Coordinate(lat, lon),
            connectors=[conn],
            operator=op,
            amenities=frozenset(),
            data_confidence=Confidence.HIGH,
            last_verified_at=datetime.utcnow()
        )
        stations.append(station)
        
    return stations

if __name__ == "__main__":
    hanoi = Coordinate(21.0285, 105.8542)
    mock_stations = generate_mock_stations(hanoi, radius_km=50, num_stations=100)
    print(f"Generated {len(mock_stations)} mock stations around Hanoi.")
    
    # In a real setup, we would insert these into PostGIS.
    # For now, we can just save them to a file for testing.
    import dataclasses
    
    class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            if isinstance(o, set) or isinstance(o, frozenset):
                return list(o)
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, Confidence):
                return o.value
            return super().default(o)
            
    with open("data/mock_stations.json", "w", encoding="utf-8") as f:
        json.dump(mock_stations, f, cls=EnhancedJSONEncoder, indent=2)
