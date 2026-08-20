import numpy as np

def get_capacity_derate(temp_c: float) -> float:
    """Returns battery usable capacity derating factor based on temperature."""
    temps = [-10, 0, 10, 20, 30, 40]
    derates = [0.80, 0.88, 0.95, 1.00, 0.98, 0.94]
    return float(np.interp(temp_c, temps, derates))

def get_efficiency_derate(temp_c: float) -> float:
    """Returns drivetrain efficiency derating factor based on temperature."""
    temps = [-10, 0, 10, 20, 30, 40]
    derates = [0.90, 0.94, 0.97, 1.00, 0.99, 0.96]
    return float(np.interp(temp_c, temps, derates))

def get_hvac_power_kw(temp_c: float) -> float:
    """Returns HVAC auxiliary power consumption (kW) based on temperature."""
    temps = [-10, 0, 10, 20, 30, 40]
    powers = [4.5, 3.0, 1.2, 0.3, 2.0, 3.5]
    return float(np.interp(temp_c, temps, powers))
