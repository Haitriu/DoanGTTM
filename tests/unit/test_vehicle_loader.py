import pytest
from pathlib import Path
from voltrail_core.models.vehicle_loader import load_vehicle_from_yaml, load_all_vehicles

def test_load_vehicle():
    yaml_path = Path("data/vehicles/vinfast-vf8-eco-2023.yaml")
    vehicle = load_vehicle_from_yaml(yaml_path)
    
    assert vehicle.id == "vinfast-vf8-eco-2023"
    assert vehicle.battery.usable_capacity_kwh == 82.0
    assert vehicle.charging.max_dc_power_kw == 150.0
    assert vehicle.physics.drag_coefficient == 0.31

def test_load_all_vehicles():
    vehicles = load_all_vehicles(Path("data/vehicles/"))
    assert len(vehicles) >= 6
    assert "tesla-model-3-lr-2023" in vehicles
    assert "vinfast-vf9-eco-2023" in vehicles
