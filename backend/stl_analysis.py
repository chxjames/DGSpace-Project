"""
STL File Analysis Service
Parses .stl files and estimates print volume, filament usage, and print time.
"""

import os
import math
import warnings
import logging
from stl import mesh as stl_mesh

# Suppress the "mesh is not closed" warning from numpy-stl
logging.getLogger('stl').setLevel(logging.ERROR)


# Material densities in g/cm³
MATERIAL_DENSITIES = {
    'PLA':   1.24,
    'ABS':   1.04,
    'PETG':  1.27,
    'TPU':   1.21,
    'Nylon': 1.14,
    'Resin': 1.10,
}

# Typical print speeds in mm³/s per material (FDM, 0.2 mm layer, 0.4 mm nozzle)
# TPU needs to be printed slowly; PLA can go faster; Resin is a different process.
MATERIAL_PRINT_SPEEDS = {
    'PLA':   5.0,
    'ABS':   4.5,
    'PETG':  4.0,
    'TPU':   2.5,
    'Nylon': 3.5,
    'Resin': 8.0,   # SLA/DLP — generally faster deposition per layer
}

# Default infill percentage (typical for functional prints)
DEFAULT_INFILL = 0.20       # 20 %

# Wall / shell thickness contributes ~30 % solid volume on average
SHELL_FRACTION = 0.30

# Additional time multiplier to account for travel moves, retraction, homing, etc.
TIME_OVERHEAD_FACTOR = 1.35


def analyze_stl(file_path: str, material: str = 'PLA', infill: float = DEFAULT_INFILL) -> dict:
    """Analyze an STL file and return estimated print metrics.

    Args:
        file_path: Absolute path to the .stl file.
        material:  Material type (PLA, ABS, PETG, TPU, Nylon, Resin).
        infill:    Infill ratio (0.0 – 1.0).  Default 0.20 (20 %).

    Returns:
        dict with keys:
            success           (bool)
            volume_cm3        (float)  – total solid volume of the mesh
            bounding_box      (dict)   – {x_mm, y_mm, z_mm} dimensions
            estimated_weight_grams    (float) – weight considering infill & shell
            estimated_print_time_hours (float) – rough time estimate
            material          (str)
            infill_percent    (int)
            message           (str)    – error message when success is False
    """
    if not os.path.isfile(file_path):
        return {'success': False, 'message': 'STL file not found'}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            stl = stl_mesh.Mesh.from_file(file_path)
    except Exception as e:
        return {'success': False, 'message': f'Failed to parse STL: {e}'}

    # ── Volume (cm³) ───────────────────────────────────────
    # numpy-stl computes volume via the signed volume of tetrahedra.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        volume_mm3, _cog, _inertia = stl.get_mass_properties()
    volume_mm3 = abs(volume_mm3)          # ensure positive
    volume_cm3 = volume_mm3 / 1000.0      # 1 cm³ = 1000 mm³

    # ── Bounding box (mm) ──────────────────────────────────
    min_coords = stl.min_
    max_coords = stl.max_
    bbox = {
        'x_mm': round(float(max_coords[0] - min_coords[0]), 1),
        'y_mm': round(float(max_coords[1] - min_coords[1]), 1),
        'z_mm': round(float(max_coords[2] - min_coords[2]), 1),
    }

    # ── Weight estimate (grams) ────────────────────────────
    # Effective solid fraction = shell + infill of interior
    effective_solid = SHELL_FRACTION + (1 - SHELL_FRACTION) * infill
    effective_volume_cm3 = volume_cm3 * effective_solid

    density = MATERIAL_DENSITIES.get(material, MATERIAL_DENSITIES['PLA'])
    weight_grams = effective_volume_cm3 * density

    # ── Print time estimate (hours) ────────────────────────
    # deposited volume in mm³
    deposited_mm3 = effective_volume_cm3 * 1000.0
    print_speed = MATERIAL_PRINT_SPEEDS.get(material, MATERIAL_PRINT_SPEEDS['PLA'])
    time_seconds = (deposited_mm3 / print_speed) * TIME_OVERHEAD_FACTOR
    time_hours = time_seconds / 3600.0

    return {
        'success': True,
        'volume_cm3':                round(volume_cm3, 2),
        'bounding_box':              bbox,
        'estimated_weight_grams':    round(weight_grams, 1),
        'estimated_print_time_hours': round(time_hours, 1),
        'material':                  material,
        'infill_percent':            int(infill * 100),
    }
