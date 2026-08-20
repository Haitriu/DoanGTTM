import click
from rich.console import Console
from rich.table import Table
from pathlib import Path
from voltrail_core.models import Coordinate
from voltrail_core.models.vehicle_loader import load_all_vehicles
from voltrail_adapters.routing.fixture import FixtureRoutingProvider
from voltrail_core.energy import compute_segment_energy

console = Console()

@click.group()
def cli():
    """Voltrail - EV Route & Charging Planner"""
    pass

@cli.command()
@click.option('--from-loc', 'from_', required=True, help='Origin location (e.g., "Hà Nội")')
@click.option('--to-loc', 'to', required=True, help='Destination location (e.g., "Đà Nẵng")')
@click.option('--vehicle', required=True, help='Vehicle ID (e.g., vinfast-vf8-eco-2023)')
@click.option('--soc', type=float, default=100.0, help='Initial State of Charge (%)')
def energy(from_, to, vehicle, soc):
    """Estimate energy consumption for a route (Phase 1 Mốc A)."""
    # 1. Load vehicles
    vehicles_dir = Path("data/vehicles")
    vehicles = load_all_vehicles(vehicles_dir)
    
    if vehicle not in vehicles:
        console.print(f"[red]Error:[/] Vehicle '{vehicle}' not found. Available: {', '.join(vehicles.keys())}")
        return
        
    v = vehicles[vehicle]
    console.print(f"Vehicle: [bold]{v.name}[/] (Bat: {v.battery.usable_capacity_kwh} kWh usable)")
    
    # 2. Get Route (Using Fixture for now since we don't have a real Nominatim setup to geocode origin/dest)
    # The fixture provides a ~50km segment.
    console.print(f"Route: [bold]{from_} -> {to}[/]")
    router = FixtureRoutingProvider()
    route_segments = router.get_route(Coordinate(0,0), Coordinate(0,0))
    
    total_dist_km = sum(s.distance_m for s in route_segments) / 1000.0
    console.print(f"Distance: {total_dist_km:.1f} km")
    
    # 3. Compute Energy
    total_energy_p50 = 0.0
    total_energy_p10 = 0.0
    total_energy_p90 = 0.0
    total_time_s = 0.0
    
    # Temp 30C for summer
    temp_c = 30.0
    
    for seg in route_segments:
        est = compute_segment_energy(seg, v, temperature_c=temp_c)
        total_energy_p50 += est.total_kwh
        total_energy_p10 += est.p10_kwh
        total_energy_p90 += est.p90_kwh
        if seg.expected_speed_mps > 0:
            total_time_s += seg.distance_m / seg.expected_speed_mps
            
    # Print results
    table = Table(title=f"Energy Estimate ({temp_c}°C)")
    table.add_column("Metric", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    
    duration_h = total_time_s / 3600
    efficiency = total_energy_p50 / (total_dist_km / 100.0) if total_dist_km > 0 else 0
    
    table.add_row("Total Time", f"{duration_h:.1f} hours")
    table.add_row("Est. Energy (p50)", f"{total_energy_p50:.1f} kWh")
    table.add_row("Efficiency", f"{efficiency:.1f} kWh/100km")
    table.add_row("Range (p10 - p90)", f"{total_energy_p10:.1f} - {total_energy_p90:.1f} kWh")
    
    console.print(table)
    
if __name__ == '__main__':
    cli()
