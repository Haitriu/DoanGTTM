import heapq
from datetime import datetime, UTC
from typing import List, Dict
from voltrail_core.models import Vehicle, TripPlan, PlanStop, PlanLeg, EnergyEstimate, SocEstimate, RiskLevel, StopReason, Warning
from voltrail_core.charging import ChargingTimeTable
from .graph import ChargingGraph

class PlannerError(Exception):
    pass

def find_optimal_plan(
    graph: ChargingGraph,
    origin_id: str,
    destination_id: str,
    vehicle: Vehicle,
    start_soc_frac: float = 1.0
) -> TripPlan:
    """
    Thuật toán Label-Setting (biến thể của Dijkstra) để tìm chuỗi trạm sạc tối ưu.
    Mục tiêu: Tối thiểu hóa tổng thời gian (lái xe + sạc).
    Ràng buộc: SOC luôn >= reserve_soc_frac.
    """
    if origin_id not in graph.nodes or destination_id not in graph.nodes:
        raise PlannerError("Origin or destination not in graph")

    reserve_soc = vehicle.battery.reserve_soc_frac
    battery_kwh = vehicle.battery.usable_capacity_kwh

    # Priority Queue: (total_time_s, current_node_id, current_soc_frac, path)
    pq = []
    heapq.heappush(pq, (0, origin_id, start_soc_frac, []))

    # best_times[node_id][soc_bucket] = min_time (rời rạc hóa SOC để tránh vòng lặp vô hạn)
    best_times: Dict[str, Dict[int, int]] = {node: {} for node in graph.nodes}

    time_table = ChargingTimeTable(vehicle)

    while pq:
        total_time, curr_id, curr_soc, path = heapq.heappop(pq)

        if curr_id == destination_id:
            return _build_trip_plan(graph, path, vehicle, origin_id)

        curr_node = graph.nodes[curr_id]

        # Thử sạc tại trạm hiện tại lên các mức SOC cao hơn
        # Rời rạc hóa: sạc lên 50%, 60%, 70%, 80%, 90%, 100%
        target_socs = [curr_soc]
        if curr_node.station.connectors and curr_id != origin_id:
            for target in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
                if target > curr_soc:
                    target_socs.append(target)

        for next_soc in target_socs:
            charge_time = 0
            if next_soc > curr_soc:
                max_power = max(c.max_power_kw for c in curr_node.station.connectors) if curr_node.station.connectors else 0
                if max_power > 0:
                    charge_time = time_table.get_time_s(max_power, curr_soc, next_soc)

            for edge in curr_node.edges:
                next_id = edge.to_node_id
                energy_needed = edge.energy_consumed_kwh
                soc_drop = energy_needed / battery_kwh
                arrival_soc = next_soc - soc_drop

                if arrival_soc >= reserve_soc:
                    new_time = total_time + charge_time + edge.drive_time_s
                    soc_bucket = int(arrival_soc * 100)

                    if soc_bucket not in best_times[next_id] or new_time < best_times[next_id][soc_bucket]:
                        best_times[next_id][soc_bucket] = new_time
                        new_path = list(path)
                        new_path.append({
                            "from": curr_id,
                            "to": next_id,
                            "departure_soc": next_soc,
                            "arrival_soc": arrival_soc,   # SOC thực sự khi đến nơi
                            "charge_time_s": charge_time,
                            "drive_time_s": edge.drive_time_s,
                            "energy_kwh": energy_needed,
                        })
                        heapq.heappush(pq, (new_time, next_id, arrival_soc, new_path))

    raise PlannerError("No feasible path found maintaining minimum SOC.")


def _build_trip_plan(graph: ChargingGraph, path: list, vehicle: Vehicle, origin_id: str) -> TripPlan:
    legs = []
    stops = []
    total_drive = 0
    total_charge = 0
    total_energy = 0.0

    for step in path:
        if step["charge_time_s"] > 0 and step["from"] != origin_id:
            station = graph.nodes[step["from"]].station
            arrival_soc_val = step["arrival_soc"]  # ← FIX: SOC khi đến (trước khi sạc)

            stops.append(PlanStop(
                station=station,
                # Dùng p10/p50/p90 đơn giản hóa: bằng nhau (cần Physics để tính bất định)
                arrival_soc=SocEstimate(
                    p10=max(0.0, arrival_soc_val - 0.05),
                    p50=arrival_soc_val,
                    p90=min(1.0, arrival_soc_val + 0.05),
                ),
                departure_soc_frac=step["departure_soc"],
                charge_duration_s=step["charge_time_s"],
                is_rest_stop=False,
                reason=StopReason("CHARGE", "Cần sạc pin"),
            ))
            total_charge += step["charge_time_s"]

        total_drive += step["drive_time_s"]
        total_energy += step["energy_kwh"]

        legs.append(PlanLeg(
            segments=[],
            energy=EnergyEstimate(
                total_kwh=step["energy_kwh"],
                rolling_kwh=0, aero_kwh=0, grade_kwh=0,
                auxiliary_kwh=0, regen_kwh=0, p10_kwh=0, p90_kwh=0
            ),
            duration_s=step["drive_time_s"],
            distance_m=0,
        ))

    return TripPlan(
        legs=legs,
        stops=stops,
        total_duration_s=total_drive + total_charge,
        total_drive_s=total_drive,
        total_charge_s=total_charge,
        total_energy_kwh=total_energy,
        estimated_cost=None,
        risk=RiskLevel.SAFE,
        alternatives=[],
        warnings=[],
    )
