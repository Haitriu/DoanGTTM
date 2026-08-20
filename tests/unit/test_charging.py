import math
from voltrail_core.models import (
    Vehicle, BatterySpec, PhysicsSpec, AuxiliarySpec, ChargingSpec, ChargingCurve
)
from voltrail_core.charging import compute_charge_time_s, ChargingTimeTable

def create_mock_vehicle() -> Vehicle:
    # A realistic EV: 80 kWh usable, max 150 kW DC charging
    return Vehicle(
        id="test-car",
        name="Test Car",
        battery=BatterySpec(87.0, 80.0, 0.1),
        physics=PhysicsSpec(2000.0, 0.3, 2.5, 0.015, 0.9, 0.7),
        auxiliary=AuxiliarySpec(0.5, 3.0),
        charging=ChargingSpec(
            max_dc_power_kw=150.0, 
            max_ac_power_kw=11.0, 
            connectors=["ccs"], 
            curve=ChargingCurve([
                (0.05, 120.0),
                (0.30, 150.0),
                (0.55, 110.0),
                (0.80, 60.0),
                (0.95, 25.0)
            ])
        )
    )

def test_charge_time_non_linear():
    vehicle = create_mock_vehicle()
    
    # 70% of battery = 56 kWh
    # Scenario A: 10% to 80%
    time_10_80 = compute_charge_time_s(vehicle, 150.0, 0.10, 0.80)
    
    # Scenario B: 30% to 100%
    time_30_100 = compute_charge_time_s(vehicle, 150.0, 0.30, 1.00)
    
    # Same amount of energy, but 30-100 should take significantly longer 
    # because charging slows down heavily after 80%
    assert time_30_100 > time_10_80
    assert time_30_100 > time_10_80 * 1.2  # at least 20% slower

def test_charge_time_bounds():
    vehicle = create_mock_vehicle()
    time_s = compute_charge_time_s(vehicle, 150.0, 0.50, 0.50)
    assert time_s == 0
    
def test_charging_table_lookup():
    vehicle = create_mock_vehicle()
    table = ChargingTimeTable(vehicle)
    
    time_calc = compute_charge_time_s(vehicle, 150.0, 0.20, 0.80)
    time_lookup = table.get_time_s(150.0, 0.20, 0.80)
    
    # Lookup might have minor floating point / rounding differences if we changed logic,
    # but based on current implementation, it should match exactly.
    assert time_calc == time_lookup
    
    # Lookup for invalid ranges
    assert table.get_time_s(150.0, 0.80, 0.20) == 0

def test_station_power_limits():
    vehicle = create_mock_vehicle()
    
    time_150kw = compute_charge_time_s(vehicle, 150.0, 0.10, 0.80)
    time_50kw = compute_charge_time_s(vehicle, 50.0, 0.10, 0.80)
    
    # 50kW station should take much longer than 150kW station
    assert time_50kw > time_150kw * 1.5
