import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', '3306') or '3306')
    DB_USER = os.getenv('DB_USER', 'dgspace_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'DGSpace')
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_EXPIRATION_HOURS = 24

    # Gmail API (OAuth2)
    GMAIL_CLIENT_ID = os.getenv('GMAIL_CLIENT_ID')
    GMAIL_CLIENT_SECRET = os.getenv('GMAIL_CLIENT_SECRET')
    GMAIL_REFRESH_TOKEN = os.getenv('GMAIL_REFRESH_TOKEN')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')

    # Verification
    VERIFICATION_CODE_EXPIRATION_MINUTES = 15

    # Dev mode: print verification code to terminal instead of sending email
    DEV_EMAIL_MODE = os.getenv('DEV_EMAIL_MODE', 'False') == 'True'

    # Server
    PORT = int(os.getenv('PORT', '5000') or '5000')

    # File uploads
    # On Railway, set UPLOAD_FOLDER env var to the volume mount path (e.g. /data)
    # Locally, falls back to backend/uploads/
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'uploads'))
    MAX_UPLOAD_SIZE_MB = 50  # 50 MB limit for STL files
    ALLOWED_EXTENSIONS = {'stl'}

    # Railway Cron Job secret — set CRON_SECRET env var in Railway dashboard
    CRON_SECRET = os.getenv('CRON_SECRET', '')