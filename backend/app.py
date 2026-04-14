import os
import threading
from datetime import date, datetime
import decimal

from flask import Flask, jsonify, request
from flask_cors import CORS

from database import db
from auth_service import AuthService
from config import Config

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Custom JSON serializer -- handles datetime / date / Decimal
class _AppEncoder(app.json_provider_class):
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)

app.json_provider_class = _AppEncoder
app.json = _AppEncoder(app)

# Configure upload folder
app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# Register blueprints
from routes.pages import pages_bp
from routes.auth import auth_bp
from routes.print_requests import print_bp
from routes.admin import admin_bp

app.register_blueprint(pages_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(print_bp)
app.register_blueprint(admin_bp)

# Cron / manual cleanup routes (import functions from jobs package)
from jobs.cleanup import _cleanup_old_files, _cleanup_unverified, start_jobs


@app.route("/api/admin/cleanup", methods=["POST"])
def manual_cleanup():
    """Admin-only: trigger file cleanup immediately."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(" ")[1])
    if not payload or payload.get("user_type") not in ("admin", "student_staff"):
        return jsonify({"success": False, "message": "Forbidden"}), 403

    threading.Thread(target=_cleanup_old_files, daemon=True).start()
    return jsonify({"success": True, "message": "Cleanup triggered in background"}), 200


@app.route("/api/internal/cron/cleanup", methods=["POST"])
def cron_cleanup():
    """Railway Cron Job endpoint -- authenticated via CRON_SECRET header."""
    expected = Config.CRON_SECRET
    if not expected:
        return jsonify({"success": False, "message": "CRON_SECRET not configured"}), 500

    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {expected}":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    _cleanup_old_files()
    _cleanup_unverified()
    return jsonify({"success": True, "message": "Cron cleanup completed"}), 200


@app.before_request
def before_request():
    if not db.connection or not db.connection.is_connected():
        db.connect()


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error"}), 500


# Start background cleanup jobs
start_jobs()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("Starting DGSpace Backend Server...")
    print(f"Database: {Config.DB_NAME}")
    print(f"Server running on: http://localhost:{port}")
    db.connect()
    app.run(host="0.0.0.0", port=port, debug=True)
