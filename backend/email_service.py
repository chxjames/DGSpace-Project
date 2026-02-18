from flask_mail import Mail, Message
from config import Config

mail = Mail()

class EmailService:
    
    @staticmethod
    def send_verification_email(to_email, verification_code, full_name):
        """Send verification email to user"""
        try:
            msg = Message(
                subject='Verify Your Email - DGSpace',
                recipients=[to_email],
                sender=Config.MAIL_DEFAULT_SENDER
            )
            
            msg.html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; }}
                    .code {{ font-size: 32px; font-weight: bold; color: #4CAF50; text-align: center; 
                             padding: 20px; background-color: #fff; border: 2px dashed #4CAF50; 
                             margin: 20px 0; letter-spacing: 5px; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to DGSpace!</h1>
                    </div>
                    <div class="content">
                        <h2>Hi {full_name},</h2>
                        <p>Thank you for registering with DGSpace. Please verify your email address by entering the code below:</p>
                        <div class="code">{verification_code}</div>
                        <p><strong>This code will expire in 15 minutes.</strong></p>
                        <p>If you didn't create an account with DGSpace, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 DGSpace. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            mail.send(msg)
            return {'success': True, 'message': 'Verification email sent'}
        except Exception as e:
            print(f"[ERROR] Error sending email: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def send_password_reset_email(to_email, reset_token, full_name):
        """Send password reset email"""
        try:
            reset_link = f"http://localhost:3000/reset-password?token={reset_token}"
            
            msg = Message(
                subject='Reset Your Password - DGSpace',
                recipients=[to_email],
                sender=Config.MAIL_DEFAULT_SENDER
            )
            
            msg.html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #FF5722; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; }}
                    .button {{ display: inline-block; padding: 12px 30px; background-color: #FF5722; 
                              color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Password Reset Request</h1>
                    </div>
                    <div class="content">
                        <h2>Hi {full_name},</h2>
                        <p>We received a request to reset your password. Click the button below to create a new password:</p>
                        <p style="text-align: center;">
                            <a href="{reset_link}" class="button">Reset Password</a>
                        </p>
                        <p><strong>This link will expire in 1 hour.</strong></p>
                        <p>If you didn't request a password reset, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2026 DGSpace. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            mail.send(msg)
            return {'success': True, 'message': 'Password reset email sent'}
        except Exception as e:
            print(f"[ERROR] Error sending email: {e}")
            return {'success': False, 'message': str(e)}
