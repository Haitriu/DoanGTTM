import time
import math
from voltrail_core.models import (
    Coordinate, Vehicle, BatterySpec, PhysicsSpec, AuxiliarySpec, ChargingSpec, ChargingCurve, RouteSegment, RoadClass
)
from voltrail_core.energy import compute_segment_energy

def create_mock_vehicle() -> Vehicle:
    return Vehicle(
        id="test-car",
        name="Test Car",
        battery=BatterySpec(80.0, 75.0, 0.1),
        physics=PhysicsSpec(
            curb_mass_kg=2000.0,
            drag_coefficient=0.3,
            frontal_area_m2=2.5,
            rolling_resistance_coeff=0.015,
            drivetrain_efficiency=0.9,
            regen_efficiency=0.7
        ),
        auxiliary=AuxiliarySpec(0.5, 3.0),
        charging=ChargingSpec(150.0, 11.0, ["ccs"], ChargingCurve([(0.0, 150.0), (1.0, 50.0)]))
    )

def test_energy_symmetry():
    # A->B->A on a flat road
    vehicle = create_mock_vehicle()
    
    seg_ab = RouteSegment(
        distance_m=10000.0,
        start=Coordinate(0, 0),
        end=Coordinate(0, 0.1),
        elevation_gain_m=0.0,
        grade=0.0,
        speed_limit_mps=25.0,
        expected_speed_mps=25.0,
        road_class=RoadClass.HIGHWAY
    )
    
    seg_ba = RouteSegment(
        distance_m=10000.0,
        start=Coordinate(0, 0.1),
        end=Coordinate(0, 0),
        elevation_gain_m=0.0,
        grade=0.0,
        speed_limit_mps=25.0,
        expected_speed_mps=25.0,
        road_class=RoadClass.HIGHWAY
    )
    
    energy_ab = compute_segment_energy(seg_ab, vehicle, 20.0)
    energy_ba = compute_segment_energy(seg_ba, vehicle, 20.0)
    
    # On flat road, no wind, AB and BA should be identical
    assert math.isclose(energy_ab.total_kwh, energy_ba.total_kwh, rel_tol=1e-5)

def test_monotonic_mass():
    vehicle = create_mock_vehicle()
    seg = RouteSegment(10000.0, Coordinate(0,0), Coordinate(0,0), 0.0, 0.0, 25.0, 25.0, RoadClass.HIGHWAY)
    
    energy_light = compute_segment_energy(seg, vehicle, 20.0, extra_load_kg=0.0)
    energy_heavy = compute_segment_energy(seg, vehicle, 20.0, extra_load_kg=500.0)
    
    assert energy_heavy.total_kwh > energy_light.total_kwh

def test_energy_decomposition():
    vehicle = create_mock_vehicle()
    seg = RouteSegment(10000.0, Coordinate(0,0), Coordinate(0,0), 100.0, 0.05, 25.0, 25.0, RoadClass.HIGHWAY)
    
    est = compute_segment_energy(seg, vehicle, 20.0)
    
    propulsion = est.rolling_kwh + est.aero_kwh + est.grade_kwh + est.regen_kwh
    total = propulsion + est.auxiliary_kwh
    
    assert math.isclose(total, est.total_kwh, rel_tol=1e-5)

def test_temperature_effect():
    vehicle = create_mock_vehicle()
    seg = RouteSegment(10000.0, Coordinate(0,0), Coordinate(0,0), 0.0, 0.0, 25.0, 25.0, RoadClass.HIGHWAY)
    
    energy_20c = compute_segment_energy(seg, vehicle, 20.0)
    energy_minus10c = compute_segment_energy(seg, vehicle, -10.0)
    
    # -10C should consume at least 20% more than 20C (mostly due to HVAC and efficiency derate)
    assert energy_minus10c.total_kwh > energy_20c.total_kwh * 1.20

def test_performance():
    vehicle = create_mock_vehicle()
    seg = RouteSegment(10000.0, Coordinate(0,0), Coordinate(0,0), 0.0, 0.0, 25.0, 25.0, RoadClass.HIGHWAY)
    
    start = time.perf_counter()
    for _ in range(1000):
        compute_segment_energy(seg, vehicle, 20.0)
    end = time.perf_counter()
    
    avg_ms = ((end - start) / 1000) * 1000
    assert avg_ms < 1.0, f"Average execution time {avg_ms:.2f}ms is > 1ms"
