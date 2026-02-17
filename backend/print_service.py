"""
3D Print Request Service
Handles business logic for 3D print request management
"""
from database import db
from datetime import datetime
from typing import Dict, List, Optional

class PrintService:
    """Service for managing 3D print requests"""
    
    @staticmethod
    def create_print_request(
        student_email: str,
        project_name: str,
        description: Optional[str] = None,
        material_type: str = 'PLA',
        color_preference: Optional[str] = None,
        estimated_weight_grams: Optional[float] = None,
        estimated_print_time_hours: Optional[float] = None,
        priority: str = 'normal'
    ) -> Dict:
        """
        Create a new 3D print request
        
        Args:
            student_email: Email of the student making the request
            project_name: Name of the 3D printing project
            description: Detailed description of the request
            material_type: Type of material (PLA, ABS, PETG, TPU, Nylon, Other)
            color_preference: Preferred color for the print
            estimated_weight_grams: Estimated weight in grams
            estimated_print_time_hours: Estimated print time in hours
            priority: Priority level (low, normal, high, urgent)
        
        Returns:
            Dict with success status, message, and request_id if successful
        """
        try:
            # Validate student exists
            check_student_query = "SELECT email FROM students WHERE email = %s AND email_verified = TRUE"
            result = db.execute_query(check_student_query, (student_email,))
            
            if not result:
                return {
                    'success': False,
                    'message': 'Student not found or email not verified'
                }
            
            # Insert print request
            query = """
                INSERT INTO print_requests 
                (student_email, project_name, description, material_type, 
                color_preference, estimated_weight_grams, estimated_print_time_hours, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                student_email, project_name, description, material_type,
                color_preference, estimated_weight_grams, estimated_print_time_hours, priority
            )
            
            db.execute_query(query, values)
            
            # Get the created request ID
            request_id = db.connection.cursor().lastrowid
            
            # Add to history
            history_query = """
                INSERT INTO print_request_history (request_id, new_status, changed_by)
                VALUES (%s, 'pending', %s)
            """
            db.execute_query(history_query, (request_id, student_email))
            
            return {
                'success': True,
                'message': 'Print request created successfully',
                'request_id': request_id
            }
            
        except Exception as e:
            print(f"Error creating print request: {e}")
            return {
                'success': False,
                'message': f'Failed to create print request: {str(e)}'
            }
    
    @staticmethod
    def get_student_requests(student_email: str, status: Optional[str] = None) -> Dict:
        """
        Get all print requests for a specific student
        
        Args:
            student_email: Email of the student
            status: Optional filter by status
        
        Returns:
            Dict with success status and list of requests
        """
        try:
            if status:
                query = """
                    SELECT request_id, project_name, description, material_type, 
                           color_preference, estimated_weight_grams, estimated_print_time_hours,
                           priority, status, admin_notes, reviewed_by, reviewed_at,
                           created_at, updated_at, completed_at
                    FROM print_requests 
                    WHERE student_email = %s AND status = %s
                    ORDER BY created_at DESC
                """
                results = db.execute_query(query, (student_email, status))
            else:
                query = """
                    SELECT request_id, project_name, description, material_type, 
                           color_preference, estimated_weight_grams, estimated_print_time_hours,
                           priority, status, admin_notes, reviewed_by, reviewed_at,
                           created_at, updated_at, completed_at
                    FROM print_requests 
                    WHERE student_email = %s
                    ORDER BY created_at DESC
                """
                results = db.execute_query(query, (student_email,))
            
            requests = []
            if results:
                for row in results:
                    requests.append({
                        'request_id': row[0],
                        'project_name': row[1],
                        'description': row[2],
                        'material_type': row[3],
                        'color_preference': row[4],
                        'estimated_weight_grams': float(row[5]) if row[5] else None,
                        'estimated_print_time_hours': float(row[6]) if row[6] else None,
                        'priority': row[7],
                        'status': row[8],
                        'admin_notes': row[9],
                        'reviewed_by': row[10],
                        'reviewed_at': row[11].isoformat() if row[11] else None,
                        'created_at': row[12].isoformat() if row[12] else None,
                        'updated_at': row[13].isoformat() if row[13] else None,
                        'completed_at': row[14].isoformat() if row[14] else None
                    })
            
            return {
                'success': True,
                'requests': requests,
                'count': len(requests)
            }
            
        except Exception as e:
            print(f"Error getting student requests: {e}")
            return {
                'success': False,
                'message': f'Failed to get requests: {str(e)}'
            }
    
    @staticmethod
    def get_request_by_id(request_id: int) -> Dict:
        """
        Get a specific print request by ID
        
        Args:
            request_id: ID of the print request
        
        Returns:
            Dict with success status and request details
        """
        try:
            query = """
                SELECT pr.request_id, pr.student_email, s.full_name, pr.project_name, 
                       pr.description, pr.material_type, pr.color_preference,
                       pr.estimated_weight_grams, pr.estimated_print_time_hours,
                       pr.priority, pr.status, pr.admin_notes, pr.reviewed_by,
                       pr.reviewed_at, pr.created_at, pr.updated_at, pr.completed_at
                FROM print_requests pr
                JOIN students s ON pr.student_email = s.email
                WHERE pr.request_id = %s
            """
            result = db.execute_query(query, (request_id,))
            
            if not result:
                return {
                    'success': False,
                    'message': 'Request not found'
                }
            
            row = result[0]
            request_data = {
                'request_id': row[0],
                'student_email': row[1],
                'student_name': row[2],
                'project_name': row[3],
                'description': row[4],
                'material_type': row[5],
                'color_preference': row[6],
                'estimated_weight_grams': float(row[7]) if row[7] else None,
                'estimated_print_time_hours': float(row[8]) if row[8] else None,
                'priority': row[9],
                'status': row[10],
                'admin_notes': row[11],
                'reviewed_by': row[12],
                'reviewed_at': row[13].isoformat() if row[13] else None,
                'created_at': row[14].isoformat() if row[14] else None,
                'updated_at': row[15].isoformat() if row[15] else None,
                'completed_at': row[16].isoformat() if row[16] else None
            }
            
            return {
                'success': True,
                'request': request_data
            }
            
        except Exception as e:
            print(f"Error getting request: {e}")
            return {
                'success': False,
                'message': f'Failed to get request: {str(e)}'
            }
    
    @staticmethod
    def get_all_requests(status: Optional[str] = None, priority: Optional[str] = None) -> Dict:
        """
        Get all print requests (admin view)
        
        Args:
            status: Optional filter by status
            priority: Optional filter by priority
        
        Returns:
            Dict with success status and list of all requests
        """
        try:
            query = """
                SELECT pr.request_id, pr.student_email, s.full_name, pr.project_name,
                       pr.description, pr.material_type, pr.priority, pr.status,
                       pr.created_at, pr.reviewed_by, pr.reviewed_at
                FROM print_requests pr
                JOIN students s ON pr.student_email = s.email
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND pr.status = %s"
                params.append(status)
            
            if priority:
                query += " AND pr.priority = %s"
                params.append(priority)
            
            query += " ORDER BY pr.created_at DESC"
            
            results = db.execute_query(query, tuple(params) if params else None)
            
            requests = []
            if results:
                for row in results:
                    requests.append({
                        'request_id': row[0],
                        'student_email': row[1],
                        'student_name': row[2],
                        'project_name': row[3],
                        'description': row[4],
                        'material_type': row[5],
                        'priority': row[6],
                        'status': row[7],
                        'created_at': row[8].isoformat() if row[8] else None,
                        'reviewed_by': row[9],
                        'reviewed_at': row[10].isoformat() if row[10] else None
                    })
            
            return {
                'success': True,
                'requests': requests,
                'count': len(requests)
            }
            
        except Exception as e:
            print(f"Error getting all requests: {e}")
            return {
                'success': False,
                'message': f'Failed to get requests: {str(e)}'
            }
    
    @staticmethod
    def update_request_status(
        request_id: int,
        new_status: str,
        admin_email: str,
        admin_notes: Optional[str] = None,
        change_reason: Optional[str] = None
    ) -> Dict:
        """
        Update the status of a print request (admin action)
        
        Args:
            request_id: ID of the print request
            new_status: New status (approved, rejected, in_progress, completed, cancelled)
            admin_email: Email of the admin making the change
            admin_notes: Optional notes from admin
            change_reason: Reason for the status change
        
        Returns:
            Dict with success status and message
        """
        try:
            # Get current status
            get_query = "SELECT status FROM print_requests WHERE request_id = %s"
            result = db.execute_query(get_query, (request_id,))
            
            if not result:
                return {
                    'success': False,
                    'message': 'Request not found'
                }
            
            old_status = result[0][0]
            
            # Update the request
            update_query = """
                UPDATE print_requests 
                SET status = %s, reviewed_by = %s, reviewed_at = NOW(), admin_notes = %s
                WHERE request_id = %s
            """
            db.execute_query(update_query, (new_status, admin_email, admin_notes, request_id))
            
            # Add to history
            history_query = """
                INSERT INTO print_request_history 
                (request_id, old_status, new_status, changed_by, change_reason)
                VALUES (%s, %s, %s, %s, %s)
            """
            db.execute_query(history_query, (request_id, old_status, new_status, admin_email, change_reason))
            
            # If completed, set completed_at timestamp
            if new_status == 'completed':
                complete_query = "UPDATE print_requests SET completed_at = NOW() WHERE request_id = %s"
                db.execute_query(complete_query, (request_id,))
            
            return {
                'success': True,
                'message': f'Request status updated to {new_status}',
                'old_status': old_status,
                'new_status': new_status
            }
            
        except Exception as e:
            print(f"Error updating request status: {e}")
            return {
                'success': False,
                'message': f'Failed to update status: {str(e)}'
            }
    
    @staticmethod
    def get_request_history(request_id: int) -> Dict:
        """
        Get the status change history for a request
        
        Args:
            request_id: ID of the print request
        
        Returns:
            Dict with success status and history list
        """
        try:
            query = """
                SELECT history_id, old_status, new_status, changed_by, 
                       change_reason, created_at
                FROM print_request_history
                WHERE request_id = %s
                ORDER BY created_at ASC
            """
            results = db.execute_query(query, (request_id,))
            
            history = []
            if results:
                for row in results:
                    history.append({
                        'history_id': row[0],
                        'old_status': row[1],
                        'new_status': row[2],
                        'changed_by': row[3],
                        'change_reason': row[4],
                        'created_at': row[5].isoformat() if row[5] else None
                    })
            
            return {
                'success': True,
                'history': history,
                'count': len(history)
            }
            
        except Exception as e:
            print(f"Error getting request history: {e}")
            return {
                'success': False,
                'message': f'Failed to get history: {str(e)}'
            }
    
    @staticmethod
    def get_statistics() -> Dict:
        """
        Get statistics about print requests (for dashboard)
        
        Returns:
            Dict with various statistics
        """
        try:
            stats = {}
            
            # Total requests
            total_query = "SELECT COUNT(*) FROM print_requests"
            result = db.execute_query(total_query)
            stats['total_requests'] = result[0][0] if result else 0
            
            # Requests by status
            status_query = """
                SELECT status, COUNT(*) 
                FROM print_requests 
                GROUP BY status
            """
            results = db.execute_query(status_query)
            stats['by_status'] = {row[0]: row[1] for row in results} if results else {}
            
            # Requests by priority
            priority_query = """
                SELECT priority, COUNT(*) 
                FROM print_requests 
                GROUP BY priority
            """
            results = db.execute_query(priority_query)
            stats['by_priority'] = {row[0]: row[1] for row in results} if results else {}
            
            # Pending requests
            pending_query = "SELECT COUNT(*) FROM print_requests WHERE status = 'pending'"
            result = db.execute_query(pending_query)
            stats['pending_count'] = result[0][0] if result else 0
            
            # Completed this month
            completed_query = """
                SELECT COUNT(*) FROM print_requests 
                WHERE status = 'completed' 
                AND MONTH(completed_at) = MONTH(CURRENT_DATE())
                AND YEAR(completed_at) = YEAR(CURRENT_DATE())
            """
            result = db.execute_query(completed_query)
            stats['completed_this_month'] = result[0][0] if result else 0
            
            return {
                'success': True,
                'statistics': stats
            }
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {
                'success': False,
                'message': f'Failed to get statistics: {str(e)}'
            }
