# DGSpace Backend - Python Flask

## 🚀 Setup Instructions

### 1. Install Dependencies
```powershell
cd E:\DGSpace-Project\backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Edit the `.env` file and update these settings:

```env
# Database (already configured)
DB_HOST=localhost
DB_USER=dgspace_user
DB_PASSWORD=YourSecurePassword123!
DB_NAME=DGSpace

# JWT Secret (CHANGE THIS!)
JWT_SECRET_KEY=change-this-to-random-string-abc123xyz

# Email Settings (for Gmail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=noreply@dgspace.com
```

### 3. Setup Gmail App Password (for email verification)
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification
3. Go to "App passwords"
4. Create a new app password for "Mail"
5. Copy the 16-character password to `.env` file

### 4. Run the Server
```powershell
python app.py
```

Server will start on: http://localhost:5000

---

## 📝 API Endpoints

### Student Endpoints

#### Register Student
```
POST /api/students/register
Content-Type: application/json

{
  "email": "student@example.com",
  "password": "Password123!",
  "full_name": "John Doe",
  "department": "Computer Science"
}
```

#### Verify Email
```
POST /api/students/verify-email
Content-Type: application/json

{
  "email": "student@example.com",
  "code": "123456"
}
```

#### Student Login
```
POST /api/students/login
Content-Type: application/json

{
  "email": "student@example.com",
  "password": "Password123!"
}
```

#### Resend Verification Code
```
POST /api/students/resend-verification
Content-Type: application/json

{
  "email": "student@example.com"
}
```

### Admin Endpoints

#### Register Admin
```
POST /api/admins/register
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "AdminPass123!",
  "full_name": "Jane Smith",
  "role": "admin"
}
```

#### Admin Login
```
POST /api/admins/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "AdminPass123!"
}
```

### Protected Endpoints

#### Get User Profile
```
GET /api/profile
Authorization: Bearer <JWT_TOKEN>
```

---

## 🧪 Testing with Postman/Thunder Client

### 1. Register a Student
- URL: `POST http://localhost:5000/api/students/register`
- Body (JSON):
```json
{
  "email": "test@student.com",
  "password": "Test123!",
  "full_name": "Test Student",
  "department": "CS"
}
```

### 2. Check your email for verification code

### 3. Verify Email
- URL: `POST http://localhost:5000/api/students/verify-email`
- Body (JSON):
```json
{
  "email": "test@student.com",
  "code": "123456"
}
```

### 4. Login
- URL: `POST http://localhost:5000/api/students/login`
- Body (JSON):
```json
{
  "email": "test@student.com",
  "password": "Test123!"
}
```

You'll receive a JWT token in the response.

### 5. Access Protected Route
- URL: `GET http://localhost:5000/api/profile`
- Headers:
```
Authorization: Bearer <paste-your-jwt-token-here>
```

---

## 📁 Project Structure

```
backend/
├── app.py                  # Main Flask application
├── auth_service.py         # Authentication logic
├── database.py             # Database connection
├── email_service.py        # Email sending
├── config.py               # Configuration
├── .env                    # Environment variables
└── requirements.txt        # Python dependencies
```

---

## 🔒 Security Features

✅ **Password Hashing**: bcrypt encryption
✅ **JWT Tokens**: Secure authentication
✅ **Email Verification**: 6-digit codes
✅ **Code Expiration**: 15-minute validity
✅ **SQL Injection Protection**: Parameterized queries

---

## 🐛 Troubleshooting

### Can't connect to MySQL?
- Check if MySQL service is running
- Verify credentials in `.env` file
- Test connection: `mysql -u dgspace_user -p DGSpace`

### Email not sending?
- Verify Gmail app password
- Check MAIL settings in `.env`
- Enable "Less secure app access" (if needed)
- Try with SendGrid/Mailgun instead

### Port already in use?
- Change PORT in `.env` to different number (e.g., 5001)
- Or kill the process using port 5000

---

## 📧 Email Service Alternatives

If Gmail doesn't work, try:

1. **SendGrid** (free tier: 100 emails/day)
2. **Mailgun** (free tier available)
3. **AWS SES** (very cheap)
4. **Resend** (modern, developer-friendly)

---

## 🎯 Next Steps

1. ✅ Backend is ready!
2. Build the frontend (HTML/CSS/JavaScript)
3. Add 3D printer request functionality
4. Deploy to server (Heroku, AWS, DigitalOcean)

---

## 📞 Support

Database: DGSpace (MySQL 8.0.43)
Connection: dgspace_user@localhost:3306
Tables: students, admins, email_verification_codes, password_reset_tokens
