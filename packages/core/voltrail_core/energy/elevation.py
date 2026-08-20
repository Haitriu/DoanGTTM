import numpy as np
from typing import List

def smooth_elevation(elevations_m: List[float], window_size: int = 5) -> List[float]:
    """
    Applies simple moving average smoothing to elevation profile.
    Window size should roughly correspond to >= 100m distance.
    In real app, we might use Savitzky-Golay filtering.
    """
    if len(elevations_m) < window_size:
        return elevations_m
        
    window = np.ones(window_size) / window_size
    smoothed = np.convolve(elevations_m, window, mode='valid')
    
    pad_len = (window_size - 1) // 2
    padded = np.pad(smoothed, (pad_len, len(elevations_m) - len(smoothed) - pad_len), mode='edge')
    return padded.tolist()

def compute_grades(elevations_m: List[float], distances_m: List[float]) -> List[float]:
    """
    Computes clamped grades from elevations and distances.
    Grade is clamped to ±12% (±0.12).
    """
    grades = []
    for i in range(len(elevations_m) - 1):
        if distances_m[i] <= 0:
            grades.append(0.0)
            continue
        
        rise = elevations_m[i+1] - elevations_m[i]
        grade = rise / distances_m[i]
        
        # Clamp to ±12%
        grade = max(-0.12, min(0.12, grade))
        grades.append(grade)
        
    grades.append(grades[-1] if grades else 0.0)
    return grades
