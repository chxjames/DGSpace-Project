import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'dgspace_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'DGSpace')
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_EXPIRATION_HOURS = 24

    # Email
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')

    # Verification
    VERIFICATION_CODE_EXPIRATION_MINUTES = 15

    # Dev mode: print verification code to terminal instead of sending email
    DEV_EMAIL_MODE = os.getenv('DEV_EMAIL_MODE', 'False') == 'True'

    # ----------------------------------------------------------------
    # Google Sheets — Weekly Report (Phase 0 MVP)
    # ----------------------------------------------------------------
    # 1. Create a Service Account in Google Cloud Console
    # 2. Download the JSON key file and set SERVICE_ACCOUNT_JSON_PATH
    # 3. Share the Google Sheet with the Service Account email (read-only)
    # 4. Copy the Sheet ID from the URL:
    #    https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
    GOOGLE_SHEET_ID           = os.getenv('GOOGLE_SHEET_ID', '')
    GOOGLE_SHEET_TAB_NAME     = os.getenv('GOOGLE_SHEET_TAB_NAME', 'Sheet1')
    SERVICE_ACCOUNT_JSON_PATH = os.getenv('SERVICE_ACCOUNT_JSON_PATH', 'service_account.json')

    # Maps internal field names → exact column header strings in the Sheet.
    # Edit these if your Sheet headers differ.
    SHEET_COLUMN_MAP = {
        'submitted_at':    'Timestamp',
        'student_email':   'Email address',
        'student_name':    'Name',
        'operator_name':   'Operator',
        'printer_name':    'Printer',
        'print_time_raw':  'Print time (HH:MM)',
        'material_used_g': 'Print Consumables (g)',
        'started_at':      'Date Started',
        'is_finished':     'Finished?',
        'error_1':         'Error 1',
        'error_2':         'Error 2',
        'actual_finish':   'Actual Finish',   # optional — staff adds this column
        'file_name':       'File Name',
    }

    # Server
    PORT = int(os.getenv('PORT', 5000))

    # File uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_UPLOAD_SIZE_MB = 50  # 50 MB limit for STL files
    ALLOWED_EXTENSIONS = {'stl'}