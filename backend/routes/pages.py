from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def home_page():
    return render_template('home.html')

@pages_bp.route('/login')
def login_page():
    return render_template('registration/login.html')

@pages_bp.route('/signup')
def signup_page():
    return render_template('registration/signup.html')

@pages_bp.route('/reset-password')
def reset_password_page():
    return render_template('registration/reset_password.html')

@pages_bp.route('/print-requests/')
def print_requests_page():
    return render_template('print_requests.html')

@pages_bp.route('/print-requests/new/')
def print_request_new_page():
    return render_template('print_request_new.html')

@pages_bp.route('/print-requests/<int:request_id>/')
def print_request_detail_page(request_id):
    return render_template('print_request_detail.html')

@pages_bp.route('/print-requests/<int:request_id>/head/')
def print_request_detail_head_page(request_id):
    return render_template('print_request_detail_HEAD.html')

@pages_bp.route('/print-requests/<int:request_id>/return/')
def print_request_return_page(request_id):
    return render_template('print_request_return.html')

@pages_bp.route('/admin/students/')
def admin_students_page():
    return render_template('admin_students.html')

@pages_bp.route('/admin/printers/')
def admin_printers_page():
    return render_template('manage_printers.html')

@pages_bp.route('/admin/admins/')
def admin_admins_page():
    return render_template('manage_admins.html')

@pages_bp.route('/production/')
def production_page():
    return render_template('production_board.html')

@pages_bp.route('/printers/')
def printer_status_page():
    return render_template('printer_status.html')

@pages_bp.route('/reports/weekly/')
def weekly_report_page():
    return render_template('weekly_report.html')

@pages_bp.route('/profile/')
def profile_page():
    return render_template('profile.html')
