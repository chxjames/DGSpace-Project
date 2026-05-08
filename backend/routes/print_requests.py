import os
import re
import uuid
from flask import Blueprint, request, jsonify, send_from_directory, current_app, Response
from database import db
from auth_service import AuthService
from print_service import PrintService
from ufp_analysis import analyze_ufp
from threemf_analysis import analyze_3mf

print_bp = Blueprint('print_requests', __name__)


# ── G-code / NC estimated time parser ────────────────────────────────────────
_GCODE_TIME_PATTERNS = [
    # LightBurn: ; Total estimated time: 0:05:30
    re.compile(r';\s*Total estimated time[:\s]+(.+)',    re.IGNORECASE),
    re.compile(r';\s*estimated job time[:\s]+(.+)',      re.IGNORECASE),
    re.compile(r';\s*Estimated cutting time[:\s]+(.+)',  re.IGNORECASE),
    re.compile(r';\s*Job time[:\s]+(.+)',                re.IGNORECASE),
    re.compile(r';\s*Cut time[:\s]+(.+)',                re.IGNORECASE),
    re.compile(r';\s*Time[:\s]+(\d[\d:hms ]+)',         re.IGNORECASE),
    # Fusion 360 / Mach3 NC parenthesis-style comments
    re.compile(r'\(\s*(?:estimated\s+)?(?:cutting\s+)?(?:machining\s+)?time[:\s]+([^)]+)\)', re.IGNORECASE),
    re.compile(r'\(\s*cycle\s+time[:\s]+([^)]+)\)',     re.IGNORECASE),
    # RDWorks
    re.compile(r'%\s*time[:\s]+(.+)',                   re.IGNORECASE),
]

# Snapmaker Luban NC header key (seconds)  ;estimated_time(s):1234
_LUBAN_TIME_RE = re.compile(r';\s*estimated_time\(s\)\s*[=:]\s*(\d+)', re.IGNORECASE)

_ALLOWED_CNC_EXTS = {'.gcode', '.nc', '.ngc', '.cnc', '.tap'}

def _seconds_to_hms(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m:
        return f"{m}m {s:02d}s"
    return f"{s}s"

def _parse_gcode_time(file_path: str):
    """Scan the first 400 lines of a G-code/.nc file for estimated-time comments.
    Supports LightBurn, Snapmaker Luban, Fusion 360, Mach3, LaserGRBL."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            for i, line in enumerate(f):
                if i > 400:
                    break
                stripped = line.strip()
                # Snapmaker Luban: ;estimated_time(s):1234
                m = _LUBAN_TIME_RE.match(stripped)
                if m:
                    return _seconds_to_hms(int(m.group(1)))
                # All other formats
                for pat in _GCODE_TIME_PATTERNS:
                    m = pat.match(stripped)
                    if m:
                        return m.group(1).strip()
    except Exception:
        pass
    return None


# ==================== 3D PRINT REQUEST ENDPOINTS ====================

@print_bp.route('/api/print-requests/upload-stl', methods=['POST'])
def upload_stl():
    """Upload a .stl file before submitting a print request (Student / Student Staff / Admin)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    if not original_name.lower().endswith('.stl'):
        return jsonify({'success': False, 'message': 'Only .stl files are allowed'}), 400

    # Save as uuid.stl to avoid filename collisions
    saved_name = f"{uuid.uuid4().hex}.stl"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    return jsonify({
        'success': True,
        'filename': saved_name,
        'original_name': original_name
    }), 201


@print_bp.route('/api/print-requests/upload-stl/<filename>', methods=['DELETE'])
def delete_uploaded_stl(filename: str):
    """Delete a previously uploaded STL file before submitting a print request.

    Supports the frontend "Remove" button so mistaken uploads don't linger on disk.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    # Basic path-traversal protection: only allow the basename.
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    upload_dir = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_dir, safe_name)

    abs_upload_dir = os.path.abspath(upload_dir)
    abs_file_path = os.path.abspath(file_path)
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


# ── Laser file upload ─────────────────────────────────────────────────────────

LASER_ALLOWED_EXTENSIONS = {'.svg', '.dxf', '.pdf'}

@print_bp.route('/api/print-requests/upload-laser', methods=['POST'])
def upload_laser():
    """Upload a laser cut design file (.svg / .dxf / .pdf) before submitting a request."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    ext = os.path.splitext(original_name.lower())[1]
    if ext not in LASER_ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'message': 'Only .svg, .dxf, or .pdf files are allowed'}), 400

    saved_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    return jsonify({
        'success': True,
        'filename': saved_name,
        'original_name': original_name
    }), 201


@print_bp.route('/api/print-requests/upload-laser/<filename>', methods=['DELETE'])
def delete_uploaded_laser(filename: str):
    """Delete a previously uploaded laser design file."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    upload_dir = current_app.config['UPLOAD_FOLDER']
    abs_upload_dir = os.path.abspath(upload_dir)
    abs_file_path  = os.path.abspath(os.path.join(upload_dir, safe_name))
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


@print_bp.route('/api/print-requests/upload-ufp', methods=['POST'])
def upload_ufp():
    """Upload a .ufp (Ultimaker Format Package) file and return slicer estimates.

    The .ufp is a ZIP archive produced by Cura. We extract print.json from it
    to read the exact print time and material usage the slicer calculated.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    if not original_name.lower().endswith('.ufp'):
        return jsonify({'success': False, 'message': 'Only .ufp files are allowed'}), 400

    # Size limit: 100 MB (UFP contains G-code which can be large)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 100 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File exceeds 100 MB limit'}), 400

    saved_name = f"{uuid.uuid4().hex}.ufp"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    result = analyze_ufp(save_path)

    if not result.get('success'):
        try:
            os.remove(save_path)
        except OSError:
            pass
        return jsonify(result), 400

    return jsonify({
        'success':       True,
        'filename':      saved_name,
        'original_name': original_name,
        'analysis': {
            'print_time':            result['print_time'],
            'material_weight_g':     result['material_weight_g'],
            'material_length_mm':    result['material_length_mm'],
            'layer_height':          result['layer_height'],
            'infill_sparse_density': result['infill_sparse_density'],
            'material_type':         result['material_type'],
            'printer_name':          result['printer_name'],
        }
    }), 201


@print_bp.route('/api/print-requests/upload-ufp/<filename>', methods=['DELETE'])
def delete_uploaded_ufp(filename: str):
    """Delete a previously uploaded UFP file."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    safe_name = os.path.basename(filename)
    abs_upload_dir = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    abs_file_path  = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


@print_bp.route('/api/uploads/<filename>', methods=['GET'])
def serve_upload(filename: str):
    """Serve uploaded STL / UFP / 3MF files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


# ==================== 3MF UPLOAD ====================

@print_bp.route('/api/print-requests/upload-3mf', methods=['POST'])
def upload_3mf():
    """Upload a .3mf (sliced) file and return slicer estimates.

    Supports Bambu Studio, OrcaSlicer, PrusaSlicer, SuperSlicer, and Cura 3MF exports.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    if not original_name.lower().endswith('.3mf'):
        return jsonify({'success': False, 'message': 'Only .3mf files are allowed'}), 400

    # Size limit: 200 MB (Bambu 3MF files include G-code and can be large)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 200 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File exceeds 200 MB limit'}), 400

    saved_name = f"{uuid.uuid4().hex}.3mf"
    save_path  = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    result = analyze_3mf(save_path)

    if not result.get('success'):
        try:
            os.remove(save_path)
        except OSError:
            pass
        return jsonify(result), 400

    return jsonify({
        'success':       True,
        'filename':      saved_name,
        'original_name': original_name,
        'analysis': {
            'slicer':                result['slicer'],
            'print_time':            result['print_time'],
            'material_weight_g':     result['material_weight_g'],
            'material_length_mm':    result['material_length_mm'],
            'layer_height':          result['layer_height'],
            'infill_sparse_density': result['infill_sparse_density'],
            'material_type':         result['material_type'],
            'printer_name':          result['printer_name'],
        }
    }), 201


@print_bp.route('/api/print-requests/upload-3mf/<filename>', methods=['DELETE'])
def delete_uploaded_3mf(filename: str):
    """Delete a previously uploaded 3MF file."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    safe_name      = os.path.basename(filename)
    abs_upload_dir = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    abs_file_path  = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


# ==================== GCODE UPLOAD (Laser) ====================

@print_bp.route('/api/print-requests/upload-gcode', methods=['POST'])
def upload_gcode():
    """Upload a .gcode file for a laser cutter job."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    file_ext = os.path.splitext(original_name.lower())[1] if original_name else ''
    if file_ext not in _ALLOWED_CNC_EXTS:
        return jsonify({
            'success': False,
            'message': f'Only {", ".join(sorted(_ALLOWED_CNC_EXTS))} files are allowed'
        }), 400

    # Size limit: 50 MB
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 50 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File exceeds 50 MB limit'}), 400

    # Keep original extension when saving
    saved_name = f"{uuid.uuid4().hex}{file_ext}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    estimated_time = _parse_gcode_time(save_path)

    return jsonify({
        'success': True,
        'filename': saved_name,
        'original_name': original_name,
        'estimated_time': estimated_time,
    }), 201


@print_bp.route('/api/print-requests/upload-gcode/<filename>', methods=['DELETE'])
def delete_uploaded_gcode(filename: str):
    """Delete a previously uploaded G-code file."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    safe_name      = os.path.basename(filename)
    abs_upload_dir = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    abs_file_path  = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


@print_bp.route('/api/print-requests', methods=['POST'])
def create_print_request():
    """Create a new 3D print request (Student / Student Staff)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    data = request.json

    if 'project_name' not in data:
        return jsonify({'success': False, 'message': 'Project name is required'}), 400

    result = PrintService.create_print_request(
        student_email=payload['email'],
        project_name=data['project_name'],
        description=data.get('description'),
        material_type=data.get('material_type', 'PLA'),
        color_preference=data.get('color_preference'),
        is_senior_design=bool(data.get('is_senior_design', False)),
        project_context=data.get('project_context', 'individual'),
        estimated_weight_grams=data.get('estimated_weight_grams'),
        estimated_print_time_hours=data.get('estimated_print_time_hours'),
        priority=data.get('priority', 'normal'),
        stl_file_path=data.get('stl_file_path'),
        stl_original_name=data.get('stl_original_name'),
        slicer_time_minutes=float(data['slicer_time_minutes']) if data.get('slicer_time_minutes') else None,
        slicer_material_g=float(data['slicer_material_g']) if data.get('slicer_material_g') else None,
        deadline_date=data.get('deadline_date') or None,
        submitter_is_admin=payload.get('user_type') == 'admin',
        service_type=data.get('service_type', '3dprint'),
        laser_options=data.get('laser_options') or None,
    )

    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@print_bp.route('/api/print-requests/my-requests', methods=['GET'])
def get_my_requests():
    """Get all print requests for the authenticated student"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    status = request.args.get('status')
    result = PrintService.get_student_requests(payload['email'], status)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@print_bp.route('/api/print-requests/<int:request_id>', methods=['GET'])
def get_request_details(request_id):
    """Get details of a specific print request"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    result = PrintService.get_request_by_id(request_id)

    if not result['success']:
        return jsonify(result), 404

    if payload.get('user_type') == 'student':
        if result['request']['student_email'] != payload['email']:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    return jsonify(result), 200


@print_bp.route('/api/print-requests/<int:request_id>', methods=['DELETE'])
def delete_print_request(request_id):
    """Delete a pending print request (student only, own requests)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Only students can delete requests'}), 403

    result = PrintService.delete_print_request(request_id, payload['email'])

    if result['success']:
        return jsonify(result), 200
    else:
        if 'not found' in result['message']:
            return jsonify(result), 404
        if 'Unauthorized' in result['message']:
            return jsonify(result), 403
        return jsonify(result), 400


@print_bp.route('/api/print-requests/<int:request_id>/resubmit', methods=['PATCH'])
def resubmit_print_request(request_id):
    """Student resubmits a revision_requested request in-place."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Only students can resubmit requests'}), 403

    data = request.json or {}

    result = PrintService.resubmit_request(
        request_id=request_id,
        student_email=payload['email'],
        project_name=data.get('project_name'),
        description=data.get('description'),
        stl_file_path=data.get('stl_file_path'),
        stl_original_name=data.get('stl_original_name'),
        material_type=data.get('material_type'),
        color_preference=data.get('color_preference'),
    )

    if result['success']:
        return jsonify(result), 200
    if 'not found' in result['message']:
        return jsonify(result), 404
    if 'Unauthorized' in result['message']:
        return jsonify(result), 403
    return jsonify(result), 400


@print_bp.route('/api/print-requests/<int:request_id>/history', methods=['GET'])
def get_request_history(request_id):
    """Get status change history for a print request"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    request_result = PrintService.get_request_by_id(request_id)

    if not request_result['success']:
        return jsonify(request_result), 404

    if payload.get('user_type') == 'student':
        if request_result['request']['student_email'] != payload['email']:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403


    result = PrintService.get_request_history(request_id)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


# ==================== DESIGN FILE PREVIEW ====================

@print_bp.route('/api/print-requests/<int:request_id>/preview-design', methods=['GET'])
def preview_design(request_id):
    """Convert and return the design file as SVG/inline for preview.
    - SVG  → served directly
    - DXF  → converted to SVG via ezdxf
    - PDF  → served as application/pdf (browser renders inline)
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    row = db.fetch_one(
        "SELECT stl_file_path, stl_original_name FROM print_requests WHERE request_id = %s",
        (request_id,)
    )
    if not row or not row.get('stl_file_path'):
        return jsonify({'success': False, 'message': 'No design file found'}), 404

    stored_name   = row['stl_file_path']
    original_name = row.get('stl_original_name') or stored_name
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''

    upload_dir = current_app.config['UPLOAD_FOLDER']
    file_path  = os.path.join(upload_dir, stored_name)

    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': 'File not found on server'}), 404

    if ext == 'svg':
        return send_from_directory(upload_dir, stored_name, mimetype='image/svg+xml')

    elif ext == 'pdf':
        return send_from_directory(upload_dir, stored_name, mimetype='application/pdf')

    elif ext == 'dxf':
        try:
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.svg import SVGBackend

            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()
            ctx = RenderContext(doc)

            # Build config that skips text (no system fonts on Railway)
            config = None
            try:
                from ezdxf.addons.drawing.config import Configuration, TextPolicy
                for policy_name in ('IGNORE', 'SUBSTITUTE', 'REPLACE', 'FILLING'):
                    policy = getattr(TextPolicy, policy_name, None)
                    if policy is not None:
                        config = Configuration.defaults().with_changes(text_policy=policy)
                        break
            except Exception:
                pass

            def _make_frontend(be):
                return Frontend(ctx, be, config=config) if config else Frontend(ctx, be)

            svg_string = None

            # ── Attempt A: ezdxf ≥ 1.1 ─────────────────────────────────────
            # draw_layout(finalize=True) returns a Page object;
            # SVGBackend.get_string(page) takes that page.
            try:
                backend_a = SVGBackend()
                fe_a = _make_frontend(backend_a)
                page = fe_a.draw_layout(msp, finalize=True)
                if page is not None:
                    svg_string = backend_a.get_string(page)
            except TypeError:
                pass  # finalize kwarg not supported → fall through
            except Exception:
                pass

            # ── Attempt B: ezdxf 1.0.x ──────────────────────────────────────
            # draw_layout() returns None; SVGBackend exposes get_xml_root()
            if not svg_string:
                try:
                    import xml.etree.ElementTree as ET
                    backend_b = SVGBackend()
                    fe_b = _make_frontend(backend_b)
                    fe_b.draw_layout(msp)
                    xml_root = backend_b.get_xml_root()
                    svg_string = ET.tostring(xml_root, encoding='unicode')
                except (AttributeError, TypeError):
                    pass

            # ── Attempt C: last-resort get_string() with no args ────────────
            if not svg_string:
                backend_c = SVGBackend()
                fe_c = _make_frontend(backend_c)
                fe_c.draw_layout(msp)
                svg_string = backend_c.get_string()  # type: ignore[call-arg]

            return Response(svg_string, mimetype='image/svg+xml')
        except Exception as exc:
            return jsonify({'success': False, 'message': f'DXF preview failed: {exc}'}), 500

    else:
        return jsonify({'success': False, 'message': f'Preview not supported for .{ext} files'}), 415
