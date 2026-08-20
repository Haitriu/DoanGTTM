import pytest
from voltrail_core.models import Coordinate, ChargingStation, Connector, Confidence
from voltrail_core.models.vehicle_loader import load_vehicle_from_yaml
from voltrail_core.planner import ChargingGraph, find_optimal_plan, RestRules, RiskEngine
from pathlib import Path
from datetime import datetime, UTC

@pytest.fixture
def test_vehicle():
    return load_vehicle_from_yaml(Path("data/vehicles/vinfast-vf8-eco-2023.yaml"))

def create_station(sid: str, lat: float, lon: float, power: float) -> ChargingStation:
    return ChargingStation(
        id=sid,
        location=Coordinate(lat, lon),
        connectors=[Connector("ccs2", power, 2)],
        operator="Test",
        amenities=frozenset(),
        data_confidence=Confidence.HIGH,
        last_verified_at=datetime.now(UTC)
    )

def test_planner_algorithm(test_vehicle):
    graph = ChargingGraph()

    s0 = create_station("O", 21.0, 105.8, 0)
    s1 = create_station("S1", 20.0, 105.8, 50)
    s2 = create_station("S2", 19.0, 105.8, 150)
    s3 = create_station("D", 18.0, 105.8, 0)

    graph.build_from_stations("O", "D", [s0, s1, s2, s3], test_vehicle)

    plan = find_optimal_plan(graph, "O", "D", test_vehicle, 1.0)

    assert plan.total_duration_s > 0
    assert len(plan.legs) > 0

    # Apply rules — API mới trả về List[Warning], không mutate plan
    rest_warnings = RestRules.apply_rest_rules(plan)
    risk, risk_warnings = RiskEngine.evaluate(plan)

    assert risk is not None
    assert isinstance(rest_warnings, list)
    assert isinstance(risk_warnings, list)

