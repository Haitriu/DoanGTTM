import yaml
from pathlib import Path
from typing import Dict, Any
from .vehicle import (
    Vehicle, BatterySpec, PhysicsSpec, AuxiliarySpec, ChargingSpec, ChargingCurve
)

class VehicleLoaderError(Exception):
    pass

def load_vehicle_from_yaml(file_path: Path) -> Vehicle:
    """
    Loads a Vehicle definition from a YAML file.
    Validates required fields and applies defaults for missing optional fields.
    """
    if not file_path.exists():
        raise VehicleLoaderError(f"Vehicle file not found: {file_path}")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise VehicleLoaderError(f"Error parsing YAML in {file_path}: {e}")
        
    try:
        # Extract specs
        bat_data = data["battery"]
        battery = BatterySpec(
            nominal_capacity_kwh=bat_data.get("nominal_capacity_kwh", bat_data["usable_capacity_kwh"] * 1.05),
            usable_capacity_kwh=bat_data["usable_capacity_kwh"],
            reserve_soc_frac=bat_data.get("reserve_soc_frac", 0.10)
        )
        
        phys_data = data["physics"]
        physics = PhysicsSpec(
            curb_mass_kg=phys_data["curb_mass_kg"],
            drag_coefficient=phys_data["drag_coefficient"],
            frontal_area_m2=phys_data["frontal_area_m2"],
            rolling_resistance_coeff=phys_data.get("rolling_resistance_coeff", 0.010),
            drivetrain_efficiency=phys_data.get("drivetrain_efficiency", 0.90),
            regen_efficiency=phys_data.get("regen_efficiency", 0.70)
        )
        
        aux_data = data.get("auxiliary", {})
        auxiliary = AuxiliarySpec(
            base_power_kw=aux_data.get("base_power_kw", 0.5),
            hvac_max_power_kw=aux_data.get("hvac_max_power_kw", 5.0)
        )
        
        char_data = data["charging"]
        curve_points = [(float(p[0]), float(p[1])) for p in char_data["curve"]]
        charging = ChargingSpec(
            max_dc_power_kw=char_data["max_dc_power_kw"],
            max_ac_power_kw=char_data.get("max_ac_power_kw", 11.0),
            connectors=char_data.get("connectors", ["ccs2"]),
            curve=ChargingCurve(curve_points)
        )
        
        return Vehicle(
            id=data["id"],
            name=data["name"],
            battery=battery,
            physics=physics,
            auxiliary=auxiliary,
            charging=charging
        )
    except KeyError as e:
        raise VehicleLoaderError(f"Missing required field {e} in {file_path}")
    except ValueError as e:
        raise VehicleLoaderError(f"Invalid value type in {file_path}: {e}")

def load_all_vehicles(directory: Path) -> Dict[str, Vehicle]:
    """Loads all .yaml vehicle files in the given directory."""
    vehicles = {}
    if not directory.exists() or not directory.is_dir():
        return vehicles
        
    for yaml_file in directory.glob("*.yaml"):
        try:
            vehicle = load_vehicle_from_yaml(yaml_file)
            vehicles[vehicle.id] = vehicle
        except VehicleLoaderError as e:
            # We might want to just log it in a real app, but for now we'll fail fast
            # or just print a warning. Let's just print a warning to keep it resilient.
            print(f"Warning: {e}")
            
    return vehicles
