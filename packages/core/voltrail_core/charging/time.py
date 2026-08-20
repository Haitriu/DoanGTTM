from voltrail_core.models import Vehicle

def actual_power_kw(vehicle: Vehicle, station_max_power_kw: float, soc_frac: float, battery_temp_c: float) -> float:
    """
    Computes actual charging power taking into account station limit, vehicle max limit,
    the vehicle's charging curve, and battery temperature.
    """
    # For simplicity, temperature derating of charging power can be a simple factor
    # E.g. cold battery charges slower.
    temp_derate = 1.0
    if battery_temp_c < 10.0:
        # Example simplistic derate: Below 10C, power is reduced linearly down to 10% at -10C
        temp_derate = max(0.1, 1.0 - (10.0 - battery_temp_c) * 0.045)
    
    curve_limit = vehicle.charging.curve.at(soc_frac)
    
    return min(
        station_max_power_kw,
        vehicle.charging.max_dc_power_kw,
        curve_limit
    ) * temp_derate

def compute_charge_time_s(
    vehicle: Vehicle, 
    station_power_kw: float, 
    soc_from: float, 
    soc_to: float, 
    battery_temp_c: float = 25.0
) -> int:
    """
    Integrates over the charging curve to find total time to charge from soc_from to soc_to.
    Formula: t = integral(C_usable / P(s)) ds
    """
    if soc_to <= soc_from:
        return 0
        
    usable_capacity_kwh = vehicle.battery.usable_capacity_kwh
    
    # Numerical integration with 1% SOC steps
    # Or 100 steps between soc_from and soc_to
    steps = 100
    soc_step = (soc_to - soc_from) / steps
    
    total_hours = 0.0
    current_soc = soc_from
    
    for _ in range(steps):
        # We can evaluate power at the midpoint of the step for slightly better accuracy
        mid_soc = current_soc + (soc_step / 2.0)
        power_kw = actual_power_kw(vehicle, station_power_kw, mid_soc, battery_temp_c)
        
        # If power is 0 (or very close), avoid division by zero
        if power_kw < 0.1:
            power_kw = 0.1
            
        energy_step_kwh = usable_capacity_kwh * soc_step
        time_step_hours = energy_step_kwh / power_kw
        
        total_hours += time_step_hours
        current_soc += soc_step
        
    # Constant connection/disconnection time: e.g. 3 minutes
    setup_time_s = 3 * 60
    
    return int(total_hours * 3600) + setup_time_s
