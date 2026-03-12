"""
UFP (Ultimaker Format Package) Analysis
Extracts print time and material usage from a Cura-exported .ufp file.

A .ufp file is a ZIP archive. The metadata location differs by Cura version:
  Cura 4.x  → /Cura/print.json
  Cura 5.x  → /Cura/slicemetadata.json   (no print.json at all)
  Both also contain /3D/model.gcode, /Metadata/thumbnail.png, etc.
"""

import zipfile
import json
import os
from typing import Dict, Any


# Keys Cura uses for print time (seconds)
_TIME_KEYS = [
    'print_time',           # Cura 4 print.json
    'PrintTime',
    'estimated_print_time',
    'time',                 # slicemetadata.json (Cura 5)
    'totalPrintTime',
]

# Keys for material weight (grams)
_MATERIAL_KEYS = [
    'material_weight',      # Cura 4 print.json
    'MaterialWeight',
    'filament_weight_g',
]

# Keys for material length (mm or m)
_MATERIAL_LENGTH_KEYS = [
    'material_length',      # mm
    'MaterialLength',
    'filament_length_m',    # metres
]


def _find_key(d: dict, keys: list):
    """Return the value of the first matching key found in dict d."""
    for k in keys:
        if k in d:
            return d[k]
    return None


def _search_nested(d, keys: list):
    """Recursively search a nested dict/list for any of the given keys."""
    if isinstance(d, dict):
        val = _find_key(d, keys)
        if val is not None:
            return val
        for v in d.values():
            result = _search_nested(v, keys)
            if result is not None:
                return result
    elif isinstance(d, list):
        for item in d:
            result = _search_nested(item, keys)
            if result is not None:
                return result
    return None


def _seconds_to_hm(seconds: float) -> dict:
    """Convert seconds to hours + minutes dict."""
    total_minutes = int(seconds) // 60
    return {
        'hours':         total_minutes // 60,
        'minutes':       total_minutes % 60,
        'total_minutes': total_minutes,
        'total_hours':   round(total_minutes / 60, 2),
    }


def _parse_slicemetadata(data: dict) -> Dict[str, Any]:
    """
    Parse Cura 5.x slicemetadata.json format.

    Real structure (from Cura source cura/API/Interface/Settings.py):
    {
      "material": { "length": [mm, mm, ...], "weight": [g, g, ...], "cost": [...] },
      "global":   { "changes": {...}, "all_settings": { "print_time": <seconds>, ... } },
      "quality":  { ... },
      "extruder_0": { "changes": {...}, "all_settings": { "layer_height": ..., "infill_sparse_density": ..., ... } },
      "extruder_1": { ... }
    }
    """
    time_raw     = None
    weight_raw   = None
    length_raw   = None
    layer_height = None
    infill       = None
    material_type  = None
    printer_name   = None

    # ── Print time: global.all_settings.print_time (seconds) ──
    global_section = data.get('global', {})
    global_all = global_section.get('all_settings', {}) if isinstance(global_section, dict) else {}
    global_changes = global_section.get('changes', {}) if isinstance(global_section, dict) else {}

    # Try global.all_settings first, then global.changes, then deep search
    for d in (global_all, global_changes):
        if isinstance(d, dict):
            for k in _TIME_KEYS:
                if k in d:
                    time_raw = d[k]
                    break
        if time_raw is not None:
            break

    # Fall back to extruder_0.all_settings if still not found
    if time_raw is None:
        for key in sorted(data.keys()):   # extruder_0, extruder_1, ...
            if not key.startswith('extruder'):
                continue
            ext_section = data[key]
            if not isinstance(ext_section, dict):
                continue
            for sub in ('all_settings', 'changes'):
                sub_d = ext_section.get(sub, {})
                if isinstance(sub_d, dict):
                    for k in _TIME_KEYS:
                        if k in sub_d:
                            time_raw = sub_d[k]
                            break
                if time_raw is not None:
                    break
            if time_raw is not None:
                break

    # ── Material weight: material.weight list (grams, per extruder) ──
    mat_section = data.get('material', {})
    if isinstance(mat_section, dict):
        weights = mat_section.get('weight', [])
        lengths = mat_section.get('length', [])
        if isinstance(weights, list) and weights:
            try:
                weight_raw = sum(float(w) for w in weights if w is not None and float(w) > 0)
            except (ValueError, TypeError):
                weight_raw = None
        if isinstance(lengths, list) and lengths:
            try:
                length_raw = sum(float(l) for l in lengths if l is not None and float(l) > 0)
            except (ValueError, TypeError):
                length_raw = None

    # ── Layer height / infill / material type: extruder_0.all_settings ──
    for key in sorted(data.keys()):
        if not key.startswith('extruder'):
            continue
        ext_section = data[key]
        if not isinstance(ext_section, dict):
            continue
        # prefer 'changes' (user overrides) then 'all_settings'
        for sub in ('changes', 'all_settings'):
            sub_d = ext_section.get(sub, {})
            if not isinstance(sub_d, dict):
                continue
            if layer_height is None and 'layer_height' in sub_d:
                layer_height = sub_d['layer_height']
            if infill is None:
                infill = sub_d.get('infill_sparse_density') or sub_d.get('infill_density')
            if material_type is None:
                material_type = (sub_d.get('material_base_name') or
                                 sub_d.get('material_type') or
                                 sub_d.get('material_brand'))
        if layer_height is not None and infill is not None:
            break

    # ── Machine name from global.all_settings ──
    if isinstance(global_all, dict):
        printer_name = global_all.get('machine_name') or global_all.get('printer_name')

    return {
        'time_raw':       time_raw,
        'weight_raw':     weight_raw,
        'length_raw':     length_raw,
        'layer_height':   layer_height,
        'infill_density': infill,
        'material_type':  str(material_type) if material_type else None,
        'printer_name':   printer_name,
    }


def analyze_ufp(file_path: str) -> Dict[str, Any]:
    """
    Parse a .ufp file and return print time + material estimates.

    Supports both Cura 4.x (print.json) and Cura 5.x (slicemetadata.json).

    Returns:
        {
            'success': True,
            'print_time': {'hours': 2, 'minutes': 13, 'total_minutes': 133, 'total_hours': 2.22},
            'material_weight_g': 45.3,
            'material_length_mm': 15230.0,
            'layer_height': 0.2,
            'infill_sparse_density': 20,
            'material_type': 'PLA',
            'printer_name': 'Ultimaker S5',
            'raw': { ... }
        }
    or:
        {'success': False, 'message': '...'}
    """
    if not os.path.exists(file_path):
        return {'success': False, 'message': 'File not found'}

    if not zipfile.is_zipfile(file_path):
        return {'success': False, 'message': 'Not a valid UFP file (not a ZIP archive)'}

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            names = zf.namelist()

            # ── Locate the metadata JSON ──────────────────────────
            # Priority: print.json (Cura 4) → slicemetadata.json (Cura 5) → any .json in /Cura/
            json_path = None

            for n in names:
                nl = n.lower()
                if nl.endswith('print.json') and 'cura' in nl:
                    json_path = n
                    break

            if not json_path:
                for n in names:
                    nl = n.lower()
                    if 'slicemetadata.json' in nl:
                        json_path = n
                        break

            if not json_path:
                for n in names:
                    nl = n.lower()
                    if (nl.startswith('/cura/') or nl.startswith('cura/')) and nl.endswith('.json'):
                        json_path = n
                        break

            raw_bytes = zf.read(json_path) if json_path else None
            data = json.loads(raw_bytes.decode('utf-8')) if raw_bytes else {}

            # ── Also read G-code for ;TIME: comment (most reliable source) ──
            gcode_path = next((n for n in names if n.lower().endswith('.gcode')), None)
            gcode_time_seconds = None
            gcode_filament_mm  = None
            if gcode_path:
                # Only scan first 4 KB — the comments are at the top of the file
                gcode_head = zf.read(gcode_path)[:4096].decode('utf-8', errors='ignore')
                for line in gcode_head.splitlines():
                    line = line.strip()
                    if line.startswith(';TIME:') or line.startswith(';PRINT.TIME:'):
                        try:
                            gcode_time_seconds = float(line.split(':', 1)[1].strip())
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith(';Filament used:') or line.startswith(';FILAMENT_USED:'):
                        # e.g. ";Filament used: 2.46m" or ";Filament used: 2460.3mm"
                        try:
                            val_str = line.split(':', 1)[1].strip()
                            # strip units
                            if val_str.endswith('mm'):
                                gcode_filament_mm = float(val_str[:-2].strip())
                            elif val_str.endswith('m'):
                                gcode_filament_mm = float(val_str[:-1].strip()) * 1000
                        except (ValueError, IndexError):
                            pass
                    if gcode_time_seconds is not None and gcode_filament_mm is not None:
                        break

    except zipfile.BadZipFile:
        return {'success': False, 'message': 'Corrupt UFP file'}
    except json.JSONDecodeError as e:
        return {'success': False, 'message': f'Invalid JSON in metadata file: {e}'}
    except Exception as e:
        return {'success': False, 'message': f'Failed to read UFP: {e}'}

    # ── Extract fields from JSON metadata ────────────────────────
    parsed = _parse_slicemetadata(data) if data else {
        'time_raw': None, 'weight_raw': None, 'length_raw': None,
        'layer_height': None, 'infill_density': None,
        'material_type': None, 'printer_name': None,
    }

    # ── Print time: G-code ;TIME: comment is the most reliable source ──
    # Fall back to JSON metadata if G-code comment not found
    if gcode_time_seconds is not None:
        time_seconds = gcode_time_seconds
    elif parsed['time_raw'] is not None:
        try:
            time_seconds = float(parsed['time_raw'])
        except (ValueError, TypeError):
            time_seconds = None
    else:
        time_seconds = None

    if time_seconds is None:
        return {
            'success': False,
            'message': (
                'Could not find print time in this UFP file. '
                'Make sure you are uploading a Cura-sliced .ufp file. '
                f'(JSON top-level keys: {list(data.keys()) if data else "none"})'
            )
        }

    print_time = _seconds_to_hm(time_seconds)

    # ── Material weight (grams) ───────────────────────────────────
    material_weight_g = None
    weight_raw = parsed['weight_raw']
    if weight_raw is not None:
        try:
            material_weight_g = round(float(weight_raw), 1)
        except (ValueError, TypeError):
            pass

    # ── Material length (mm) ─────────────────────────────────────
    # Prefer G-code comment; fall back to JSON
    material_length_mm = None
    if gcode_filament_mm is not None:
        material_length_mm = round(gcode_filament_mm, 1)
    elif parsed['length_raw'] is not None:
        try:
            material_length_mm = round(float(parsed['length_raw']), 1)
        except (ValueError, TypeError):
            pass

    # ── Derive weight from length if still missing ────────────────
    if material_weight_g is None and material_length_mm is not None:
        import math
        radius_cm = 0.175 / 2  # 1.75 mm filament → radius in cm
        volume_cm3 = math.pi * (radius_cm ** 2) * (material_length_mm / 10)
        material_weight_g = round(volume_cm3 * 1.24, 1)  # PLA ≈ 1.24 g/cm³

    return {
        'success':               True,
        'print_time':            print_time,
        'material_weight_g':     material_weight_g,
        'material_length_mm':    material_length_mm,
        'layer_height':          parsed['layer_height'],
        'infill_sparse_density': parsed['infill_density'],
        'material_type':         parsed['material_type'],
        'printer_name':          parsed['printer_name'],
        'raw':                   data,
    }
