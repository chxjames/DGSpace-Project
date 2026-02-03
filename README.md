# DGSpace - 3D Printer Management System

A web application for managing 3D printer requests with student and admin authentication.

## 🚀 Tech Stack

- **Backend**: Python Flask
- **Database**: MySQL 8.0
- **Authentication**: JWT tokens + Email verification
- **Password Security**: bcrypt hashing
- **Email**: Flask-Mail (Gmail/SendGrid)

## 📁 Project Structure

```
DGSpace-Project/
├── backend/              # Python Flask API
│   ├── app.py           # Main application
│   ├── auth_service.py  # Authentication logic
│   ├── database.py      # Database connection
│   ├── email_service.py # Email verification
│   ├── config.py        # Configuration
│   ├── requirements.txt # Python dependencies
│   └── README.md        # Backend documentation
├── frontend/            # Website (HTML/CSS/JS)
└── database/            # SQL schema scripts
    └── schema.sql       # Database structure
```

## 🔧 Setup Instructions

### 1. Database Setup

```bash
# Create database and tables
mysql -u root -p < database/schema.sql

# Create database user
mysql -u root -p
CREATE USER 'dgspace_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON DGSpace.* TO 'dgspace_user'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run server
python app.py
```

Server runs on: http://localhost:5000

### 3. Frontend Setup

*(To be added by team)*

## 📊 Database Schema

### Tables:
- **students** - Student accounts (email as primary key)
- **admins** - Administrator accounts with roles
- **email_verification_codes** - Email verification system
- **password_reset_tokens** - Password reset functionality

## 🔐 API Endpoints

### Student Endpoints
- `POST /api/students/register` - Register new student
- `POST /api/students/verify-email` - Verify email with code
- `POST /api/students/login` - Student login
- `POST /api/students/resend-verification` - Resend verification code

### Admin Endpoints
- `POST /api/admins/register` - Register new admin
- `POST /api/admins/verify-email` - Verify admin email
- `POST /api/admins/login` - Admin login

### Protected Endpoints
- `GET /api/profile` - Get user profile (requires JWT token)

Full API documentation in `backend/README.md`

## 🔒 Security Features

- ✅ Password hashing with bcrypt
- ✅ JWT token authentication
- ✅ Email verification (6-digit codes, 15min expiry)
- ✅ Protected API endpoints
- ✅ SQL injection prevention (parameterized queries)

## 👥 Team Members

- [Add your team member names here]

## 📝 License

[Add your license here]

## 🤝 Contributing

1. Clone the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## ⚠️ Important Notes

- Never commit `.env` file (contains passwords!)
- Update `.env.example` if you add new environment variables
- Database files are not tracked by Git
- Each team member should set up their own local database

## 📞 Support

For questions or issues, contact [your contact info]
