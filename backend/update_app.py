"""
Script to add print request endpoints to app.py
"""

# Read the original file
with open('app.py.backup', 'r', encoding='utf-8') as f:
    lines = f.readlines()


# Find the line with "from config import Config"
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if 'from config import Config`nfrom print_service import PrintService' in line:
        # Replace the malformed line
        new_lines[-1] = 'from config import Config\nfrom print_service import PrintService\n'

# Find where to insert the new endpoints (before error handlers)
insert_index = -1
for i, line in enumerate(new_lines):
    if '# Error handlers' in line:
        insert_index = i
        break

# Prepare the new endpoints
new_endpoints = '''
# ==================== 3D PRINT REQUEST ENDPOINTS ====================

@app.route('/api/print-requests', methods=['POST'])
def create_print_request():
    """Create a new 3D print request (Student)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'student':
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
        estimated_weight_grams=data.get('estimated_weight_grams'),
        estimated_print_time_hours=data.get('estimated_print_time_hours'),
        priority=data.get('priority', 'normal')
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route('/api/print-requests/my-requests', methods=['GET'])
def get_my_requests():
    """Get all print requests for the authenticated student"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'student':
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401
    
    status = request.args.get('status')
    result = PrintService.get_student_requests(payload['email'], status)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/print-requests/<int:request_id>', methods=['GET'])
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


@app.route('/api/print-requests/<int:request_id>/history', methods=['GET'])
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


# ==================== ADMIN PRINT REQUEST ENDPOINTS ====================

@app.route('/api/admin/print-requests', methods=['GET'])
def admin_get_all_requests():
    """Get all print requests (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    status = request.args.get('status')
    priority = request.args.get('priority')
    
    result = PrintService.get_all_requests(status, priority)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/<int:request_id>/status', methods=['PATCH'])
def admin_update_request_status(request_id):
    """Update the status of a print request (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    data = request.json
    
    if 'status' not in data:
        return jsonify({'success': False, 'message': 'Status is required'}), 400
    
    valid_statuses = ['approved', 'rejected', 'in_progress', 'completed', 'cancelled']
    if data['status'] not in valid_statuses:
        return jsonify({'success': False, 'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    result = PrintService.update_request_status(
        request_id=request_id,
        new_status=data['status'],
        admin_email=payload['email'],
        admin_notes=data.get('admin_notes'),
        change_reason=data.get('change_reason')
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/statistics', methods=['GET'])
def admin_get_statistics():
    """Get print request statistics (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    result = PrintService.get_statistics()
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

'''

# Insert the new endpoints
if insert_index != -1:
    new_lines.insert(insert_index, new_endpoints)

# Write the updated file
with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Successfully added print request endpoints to app.py")
print("📝 New endpoints added:")
print("   - POST /api/print-requests (Create print request)")
print("   - GET /api/print-requests/my-requests (Get student's requests)")
print("   - GET /api/print-requests/<id> (Get request details)")
print("   - GET /api/print-requests/<id>/history (Get request history)")
print("   - GET /api/admin/print-requests (Admin: Get all requests)")
print("   - PATCH /api/admin/print-requests/<id>/status (Admin: Update status)")
print("   - GET /api/admin/print-requests/statistics (Admin: Get stats)")
