from typing import Dict, Tuple
from voltrail_core.models import Vehicle
from .time import compute_charge_time_s

class ChargingTimeTable:
    """
    Precomputes charging times for fast O(1) lookups during routing.
    table[station_power][soc_a][soc_b]
    """
    def __init__(self, vehicle: Vehicle, battery_temp_c: float = 25.0):
        self.vehicle = vehicle
        self.battery_temp_c = battery_temp_c
        self._table: Dict[float, Dict[int, Dict[int, int]]] = {}
        
    def _build_for_power(self, station_power_kw: float):
        """Builds a 2D lookup table for a specific station power in 1% SOC increments."""
        if station_power_kw in self._table:
            return
            
        matrix = {}
        for a in range(101):
            matrix[a] = {}
            for b in range(a, 101):
                if a == b:
                    matrix[a][b] = 0
                else:
                    soc_a = a / 100.0
                    soc_b = b / 100.0
                    matrix[a][b] = compute_charge_time_s(
                        self.vehicle, station_power_kw, soc_a, soc_b, self.battery_temp_c
                    )
        self._table[station_power_kw] = matrix

    def get_time_s(self, station_power_kw: float, soc_from_frac: float, soc_to_frac: float) -> int:
        """Looks up the charging time from the precomputed table."""
        if soc_to_frac <= soc_from_frac:
            return 0
            
        if station_power_kw not in self._table:
            self._build_for_power(station_power_kw)
            
        # Round to nearest 1%
        a = int(round(soc_from_frac * 100))
        b = int(round(soc_to_frac * 100))
        
        a = max(0, min(100, a))
        b = max(0, min(100, b))
        
        if b <= a:
            return 0
            
        return self._table[station_power_kw][a][b]
