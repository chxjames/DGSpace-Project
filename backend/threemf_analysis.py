"""
3MF File Analysis
Extracts print time and material usage from a sliced .3mf file.

A .3mf file is a ZIP archive. Different slicers embed metadata differently:

  Bambu Studio  → /Metadata/slice_info.config  (XML)
  PrusaSlicer   → /Metadata/Slic3r_PE.config or /Metadata/PrusaSlicer.config (INI-style)
  Cura (3MF)    → /Cura/print.json or /Cura/slicemetadata.json  (JSON, same as .ufp)
  OrcaSlicer    → /Metadata/slice_info.config  (same structure as Bambu)
"""

import zipfile
import json
import re
import os
from typing import Dict, Any

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None  # type: ignore


def _seconds_to_hm(seconds: float) -> dict:
    """Convert seconds to hours + minutes dict."""
    total_minutes = int(seconds) // 60
    return {
        'hours':         total_minutes // 60,
        'minutes':       total_minutes % 60,
        'total_minutes': total_minutes,
        'total_hours':   round(total_minutes / 60, 2),
    }


def _derive_weight_from_length(length_mm: float) -> float:
    """Estimate PLA weight (g) from filament length (mm), 1.75mm diameter."""
    import math
    radius_cm = 0.175 / 2
    volume_cm3 = math.pi * (radius_cm ** 2) * (length_mm / 10)
    return round(volume_cm3 * 1.24, 1)  # PLA density ≈ 1.24 g/cm³


# ──────────────────────────────────────────────────────────────────────────────
# Parser 1: Bambu Studio / OrcaSlicer  →  /Metadata/slice_info.config  (XML)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_bambu_slice_info(xml_text: str) -> Dict[str, Any]:
    """
    Parse Bambu Studio slice_info.config XML.

    Typical structure:
    <config>
      <plate>
        <metadata key="index" value="1"/>
        <metadata key="prediction" value="3456"/>   <!-- seconds -->
        <metadata key="weight" value="45.32"/>       <!-- grams -->
        <filament id="1" type="PLA" color="#FF0000"
                  used_m="12.34" used_g="45.32"/>
      </plate>
    </config>
    """
    result = {
        'time_seconds':   None,
        'weight_g':       None,
        'length_mm':      None,
        'material_type':  None,
        'printer_name':   None,
        'layer_height':   None,
        'infill_density': None,
    }
    if ET is None:
        return result
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result

    # Sum across all plates
    total_seconds = 0.0
    total_weight  = 0.0
    total_length  = 0.0
    material_types = []
    found_time = False

    for plate in root.iter('plate'):
        # <metadata key="prediction" value="...">
        for meta in plate.findall('metadata'):
            key = meta.get('key', '')
            val = meta.get('value', '')
            if key == 'prediction':
                try:
                    total_seconds += float(val)
                    found_time = True
                except (ValueError, TypeError):
                    pass
            elif key == 'weight':
                try:
                    total_weight += float(val)
                except (ValueError, TypeError):
                    pass

        # <filament id="1" type="PLA" used_m="..." used_g="..."/>
        for fil in plate.findall('filament'):
            ftype = fil.get('type')
            if ftype and ftype not in material_types:
                material_types.append(ftype)
            used_m = fil.get('used_m')
            used_g = fil.get('used_g')
            if used_m:
                try:
                    total_length += float(used_m) * 1000  # metres → mm
                except (ValueError, TypeError):
                    pass
            if used_g and total_weight == 0:
                try:
                    total_weight += float(used_g)
                except (ValueError, TypeError):
                    pass

    if found_time:
        result['time_seconds'] = total_seconds
    if total_weight > 0:
        result['weight_g'] = round(total_weight, 1)
    if total_length > 0:
        result['length_mm'] = round(total_length, 1)
    if material_types:
        result['material_type'] = ', '.join(material_types)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Parser 2: Bambu Studio project_settings.config  (JSON, has printer name etc.)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_bambu_project_settings(json_text: str) -> Dict[str, Any]:
    result = {'printer_name': None, 'layer_height': None, 'infill_density': None}
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        return result

    result['printer_name']   = data.get('printer_model') or data.get('printer_name') or data.get('machine_model')
    result['layer_height']   = data.get('layer_height')
    result['infill_density'] = data.get('sparse_infill_density') or data.get('infill_density')
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Parser 3: PrusaSlicer / SuperSlicer  →  Metadata/PrusaSlicer.config (INI)
# Typical lines:
#   ; estimated printing time (normal mode) = 2h 13m 27s
#   ; filament used [mm] = 2460.00
#   ; filament used [g] = 7.26
#   ; layer_height = 0.20
#   ; fill_density = 15%
# ──────────────────────────────────────────────────────────────────────────────
_PRUSA_TIME_RE    = re.compile(r'estimated printing time.*?=\s*(.+)', re.IGNORECASE)
_PRUSA_TIME_PARTS = re.compile(r'(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?')
_PRUSA_MM_RE      = re.compile(r'filament used \[mm\]\s*=\s*([\d.]+)', re.IGNORECASE)
_PRUSA_G_RE       = re.compile(r'filament used \[g\]\s*=\s*([\d.]+)', re.IGNORECASE)
_PRUSA_LAYER_RE   = re.compile(r';\s*layer_height\s*=\s*([\d.]+)', re.IGNORECASE)
_PRUSA_INFILL_RE  = re.compile(r';\s*fill_density\s*=\s*([\d.]+)', re.IGNORECASE)
_PRUSA_PRINTER_RE = re.compile(r';\s*(?:printer_model|printer_name|machine_type)\s*=\s*(.+)', re.IGNORECASE)
_PRUSA_MATERIAL_RE = re.compile(r';\s*filament_type\s*=\s*(.+)', re.IGNORECASE)


def _parse_prusa_time(time_str: str) -> float | None:
    """Convert '2h 13m 27s' or '1d 2h 3m 4s' to seconds."""
    m = _PRUSA_TIME_PARTS.match(time_str.strip())
    if not m or not any(m.groups()):
        return None
    days    = int(m.group(1) or 0)
    hours   = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    secs    = int(m.group(4) or 0)
    total = days * 86400 + hours * 3600 + minutes * 60 + secs
    return float(total) if total > 0 else None


def _parse_prusa_config(config_text: str) -> Dict[str, Any]:
    result = {
        'time_seconds':   None,
        'weight_g':       None,
        'length_mm':      None,
        'material_type':  None,
        'printer_name':   None,
        'layer_height':   None,
        'infill_density': None,
    }

    for line in config_text.splitlines():
        if result['time_seconds'] is None:
            m = _PRUSA_TIME_RE.search(line)
            if m:
                result['time_seconds'] = _parse_prusa_time(m.group(1))

        if result['length_mm'] is None:
            m = _PRUSA_MM_RE.search(line)
            if m:
                try:
                    result['length_mm'] = float(m.group(1))
                except ValueError:
                    pass

        if result['weight_g'] is None:
            m = _PRUSA_G_RE.search(line)
            if m:
                try:
                    result['weight_g'] = float(m.group(1))
                except ValueError:
                    pass

        if result['layer_height'] is None:
            m = _PRUSA_LAYER_RE.search(line)
            if m:
                try:
                    result['layer_height'] = float(m.group(1))
                except ValueError:
                    pass

        if result['infill_density'] is None:
            m = _PRUSA_INFILL_RE.search(line)
            if m:
                try:
                    val = m.group(1).replace('%', '').strip()
                    result['infill_density'] = float(val)
                except ValueError:
                    pass

        if result['printer_name'] is None:
            m = _PRUSA_PRINTER_RE.search(line)
            if m:
                result['printer_name'] = m.group(1).strip()

        if result['material_type'] is None:
            m = _PRUSA_MATERIAL_RE.search(line)
            if m:
                result['material_type'] = m.group(1).strip().split(';')[0].strip()

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Parser 4: Cura JSON inside 3MF (same as UFP)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_cura_json(json_text: str) -> Dict[str, Any]:
    result = {
        'time_seconds':   None,
        'weight_g':       None,
        'length_mm':      None,
        'material_type':  None,
        'printer_name':   None,
        'layer_height':   None,
        'infill_density': None,
    }
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        return result

    # Try print_time from global.all_settings
    global_all = data.get('global', {}).get('all_settings', {})
    for k in ('print_time', 'PrintTime', 'estimated_print_time', 'time', 'totalPrintTime'):
        if k in global_all:
            try:
                result['time_seconds'] = float(global_all[k])
                break
            except (ValueError, TypeError):
                pass

    mat = data.get('material', {})
    weights = mat.get('weight', [])
    lengths = mat.get('length', [])
    if isinstance(weights, list) and weights:
        try:
            result['weight_g'] = round(sum(float(w) for w in weights if w), 1)
        except (ValueError, TypeError):
            pass
    if isinstance(lengths, list) and lengths:
        try:
            result['length_mm'] = round(sum(float(l) for l in lengths if l), 1)
        except (ValueError, TypeError):
            pass

    result['printer_name']   = global_all.get('machine_name') or global_all.get('printer_name')
    result['layer_height']   = global_all.get('layer_height')
    result['infill_density'] = global_all.get('infill_sparse_density') or global_all.get('infill_density')

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────
def analyze_3mf(file_path: str) -> Dict[str, Any]:
    """
    Parse a .3mf file and return print time + material estimates.

    Supports Bambu Studio, OrcaSlicer, PrusaSlicer, SuperSlicer, and Cura 3MF exports.

    Returns:
        {
            'success': True,
            'print_time': {'hours': 2, 'minutes': 13, 'total_minutes': 133, 'total_hours': 2.22},
            'material_weight_g': 45.3,
            'material_length_mm': 15230.0,
            'layer_height': 0.2,
            'infill_sparse_density': 20,
            'material_type': 'PLA',
            'printer_name': 'Bambu Lab X1 Carbon',
            'slicer': 'bambu' | 'prusa' | 'cura' | 'unknown',
        }
    or:
        {'success': False, 'message': '...'}
    """
    if not os.path.exists(file_path):
        return {'success': False, 'message': 'File not found'}

    if not zipfile.is_zipfile(file_path):
        return {'success': False, 'message': 'Not a valid 3MF file (not a ZIP archive)'}

    slicer    = 'unknown'
    parsed    = None

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            names     = [n for n in zf.namelist()]
            names_low = [n.lower() for n in names]

            def read(path: str) -> str | None:
                """Read a file from zip by case-insensitive match."""
                for real, low in zip(names, names_low):
                    if low == path.lower() or low.endswith('/' + path.lower()):
                        return zf.read(real).decode('utf-8', errors='replace')
                return None

            # ── 1. Bambu / OrcaSlicer: Metadata/slice_info.config ──
            slice_info = read('Metadata/slice_info.config')
            if slice_info:
                slicer = 'bambu'
                parsed = _parse_bambu_slice_info(slice_info)

                # Supplement with project_settings.config for printer name / layer height
                proj = read('Metadata/project_settings.config')
                if proj:
                    proj_data = _parse_bambu_project_settings(proj)
                    if not parsed.get('printer_name'):
                        parsed['printer_name'] = proj_data.get('printer_name')
                    if not parsed.get('layer_height'):
                        parsed['layer_height'] = proj_data.get('layer_height')
                    if not parsed.get('infill_density'):
                        parsed['infill_density'] = proj_data.get('infill_density')

            # ── 2. PrusaSlicer / SuperSlicer: Metadata/PrusaSlicer.config ──
            if parsed is None or parsed.get('time_seconds') is None:
                for cfg_name in ('Metadata/PrusaSlicer.config',
                                 'Metadata/Slic3r_PE.config',
                                 'Metadata/SuperSlicer.config'):
                    cfg_text = read(cfg_name)
                    if cfg_text:
                        slicer = 'prusa'
                        candidate = _parse_prusa_config(cfg_text)
                        if candidate.get('time_seconds'):
                            parsed = candidate
                            break

            # ── 3. Cura JSON (3MF exported from Cura) ──
            if parsed is None or parsed.get('time_seconds') is None:
                for json_name in ('Cura/print.json', 'Cura/slicemetadata.json'):
                    json_text = read(json_name)
                    if json_text:
                        slicer = 'cura'
                        candidate = _parse_cura_json(json_text)
                        if candidate.get('time_seconds'):
                            parsed = candidate
                            break

            # ── 4. Fallback: scan all files for G-code TIME comment ──
            if parsed is None or parsed.get('time_seconds') is None:
                for real, low in zip(names, names_low):
                    if low.endswith('.gcode') or low.endswith('.bgcode'):
                        head = zf.read(real)[:8192].decode('utf-8', errors='ignore')
                        for line in head.splitlines():
                            line = line.strip()
                            if line.startswith(';TIME:') or line.startswith(';PRINT.TIME:'):
                                try:
                                    t = float(line.split(':', 1)[1].strip())
                                    if parsed is None:
                                        parsed = {'time_seconds': t, 'weight_g': None,
                                                  'length_mm': None, 'material_type': None,
                                                  'printer_name': None, 'layer_height': None,
                                                  'infill_density': None}
                                    else:
                                        parsed['time_seconds'] = t
                                except (ValueError, IndexError):
                                    pass
                        break

    except zipfile.BadZipFile:
        return {'success': False, 'message': 'Corrupt 3MF file'}
    except Exception as e:
        return {'success': False, 'message': f'Failed to read 3MF: {e}'}

    if parsed is None or parsed.get('time_seconds') is None:
        return {
            'success': False,
            'message': (
                'Could not find print time in this 3MF file. '
                'Please make sure the file has been sliced (not just exported from CAD). '
                'Supported slicers: Bambu Studio, OrcaSlicer, PrusaSlicer, SuperSlicer, Cura.'
            )
        }

    time_seconds = parsed['time_seconds']
    print_time   = _seconds_to_hm(time_seconds)

    weight_g  = parsed.get('weight_g')
    length_mm = parsed.get('length_mm')

    # Derive weight from length if missing
    if weight_g is None and length_mm is not None and length_mm > 0:
        weight_g = _derive_weight_from_length(length_mm)

    return {
        'success':               True,
        'slicer':                slicer,
        'print_time':            print_time,
        'material_weight_g':     round(weight_g, 1) if weight_g else None,
        'material_length_mm':    round(length_mm, 1) if length_mm else None,
        'layer_height':          parsed.get('layer_height'),
        'infill_sparse_density': parsed.get('infill_density'),
        'material_type':         parsed.get('material_type'),
        'printer_name':          parsed.get('printer_name'),
    }
