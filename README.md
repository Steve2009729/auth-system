# AuthSystem - Production-Grade Authentication & Authorization API

A complete backend authentication and authorization system built with FastAPI, PostgreSQL, and Redis. This is production-ready code that real companies use to protect their APIs and manage users.

## What's Included

This system implements:

- ✅ Email/password registration with email verification
- ✅ JWT access tokens + refresh token rotation
- ✅ OAuth2 login (Google + GitHub)
- ✅ Two-Factor Authentication (2FA) via TOTP (Google Authenticator)
- ✅ Role-Based Access Control (RBAC) with permissions
- ✅ Brute force protection and account lockout
- ✅ Rate limiting per endpoint per IP
- ✅ Token blacklisting on logout
- ✅ Active session tracking and remote session revocation
- ✅ Full audit log of every auth event
- ✅ Password reset via secure email token
- ✅ Device fingerprinting on login
- ✅ Refresh token replay attack detection

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.11+ |
| **Framework** | FastAPI | 0.111.0 |
| **Database** | PostgreSQL | 16 |
| **ORM** | SQLAlchemy | 2.0.30 |
| **Migrations** | Alembic | 1.13.1 |
| **Cache/Queue** | Redis | 7 |
| **Auth** | PyJWT, bcrypt, pyotp, authlib | Latest |
| **Validation** | Pydantic | 2.7.1 |
| **Testing** | Pytest | 8.2.2 |
| **Containerization** | Docker | Compose |

## Project Structure

```
auth-system/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Environment configuration
│   ├── dependencies.py            # FastAPI dependencies
│   │
│   ├── core/                      # Core security & business logic
│   │   ├── security.py            # JWT, password hashing, tokens
│   │   ├── oauth2.py              # Google + GitHub OAuth2
│   │   ├── totp.py                # 2FA TOTP generation/verification
│   │   ├── rate_limiter.py        # Redis-backed rate limiting
│   │   ├── email.py               # Email sending
│   │   └── audit.py               # Audit logging
│   │
│   ├── db/                        # Database setup
│   │   ├── base.py                # SQLAlchemy base & session factory
│   │   └── redis.py               # Redis connection pool
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user.py                # User model
│   │   ├── role.py                # Role & Permission models
│   │   ├── session.py             # Active session tracking
│   │   ├── audit_log.py           # Audit log model
│   │   └── token.py               # Email verification & reset tokens
│   │
│   ├── schemas/                   # Pydantic request/response models
│   │   ├── user.py                # User schemas
│   │   ├── auth.py                # Auth request/response schemas
│   │   └── token.py               # Token & session schemas
│   │
│   ├── services/                  # Business logic layer
│   │   ├── auth_service.py        # Authentication logic
│   │   ├── user_service.py        # User management
│   │   └── session_service.py     # Session & token management
│   │
│   └── routers/                   # API endpoints
│       ├── auth.py                # /auth endpoints
│       ├── users.py               # /users endpoints
│       ├── sessions.py            # /sessions endpoints
│       └── admin.py               # /admin endpoints
│
├── migrations/                    # Alembic database migrations
├── tests/                         # Unit & integration tests
├── docker-compose.yml             # Docker setup
├── Dockerfile                     # Container image
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── alembic.ini                    # Alembic configuration
├── .gitignore
└── README.md
```

## Installation

### 1. Clone or Create Project

```bash
mkdir auth-system && cd auth-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual values
```

**Required environment variables:**
- `SECRET_KEY`: Generate a secure key (min 64 chars)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SMTP_*`: Email service credentials
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google OAuth credentials
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`: GitHub OAuth credentials

### 5. Start PostgreSQL and Redis

Using Docker Compose (recommended):
```bash
docker-compose up db redis -d
```

Or install locally:
- PostgreSQL 16
- Redis 7

### 6. Initialize Database

```bash
alembic revision --autogenerate -m "initial_tables"
alembic upgrade head
```

### 7. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Access the API:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Description | Rate Limited |
|--------|----------|-------------|-------------|
| POST | `/register` | Register new user | Yes (3/hr) |
| POST | `/login` | Login with email/password | Yes (5/5min) |
| POST | `/logout` | Logout and revoke session | No |
| POST | `/logout/all` | Logout from all devices | No |
| POST | `/refresh` | Refresh access token | Yes (10/min) |
| GET | `/verify-email/{token}` | Verify email | No |
| POST | `/resend-verification` | Resend verification email | Yes |
| POST | `/forgot-password` | Request password reset | Yes (3/hr) |
| POST | `/reset-password` | Reset password | No |
| POST | `/change-password` | Change password (auth required) | No |
| GET | `/google` | Redirect to Google OAuth | No |
| GET | `/google/callback` | Handle Google callback | No |
| GET | `/github` | Redirect to GitHub OAuth | No |
| GET | `/github/callback` | Handle GitHub callback | No |
| POST | `/2fa/setup` | Setup 2FA | No |
| POST | `/2fa/enable` | Enable 2FA | No |
| POST | `/2fa/disable` | Disable 2FA | No |
| POST | `/2fa/verify` | Verify 2FA code | No |

### Users (`/users`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|--------------|
| GET | `/me` | Get current user | Yes |
| PATCH | `/me` | Update profile | Yes |
| DELETE | `/me` | Delete account | Yes |
| GET | `/me/permissions` | Get user permissions | Yes |

### Sessions (`/sessions`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|--------------|
| GET | `` | List active sessions | Yes |
| DELETE | `/{session_id}` | Revoke session | Yes |

### Admin (`/admin`)

| Method | Endpoint | Description | Permission Required |
|--------|----------|-------------|-------------------|
| GET | `/users` | List all users | `admin:read` |
| GET | `/users/{user_id}` | Get user by ID | `admin:read` |
| PATCH | `/users/{user_id}` | Update user | `admin:write` |
| DELETE | `/users/{user_id}` | Delete user | `admin:delete` |
| POST | `/roles` | Create role | `admin:all` |
| POST | `/roles/{role_id}/permissions` | Assign permissions | `admin:all` |
| POST | `/users/{user_id}/roles` | Assign role to user | `admin:all` |
| GET | `/audit-logs` | View audit logs | `admin:read` |

## Security Features

### Password Security
- **Bcrypt hashing** with 12 rounds
- Secure password reset tokens (SHA256)
- Password change tracking

### Token Management
- **JWT access tokens** (15 min default)
- **Refresh token rotation** with replay attack detection
- Token blacklisting on logout
- Automatic session invalidation on all devices if replay detected

### Account Protection
- **Brute force protection**:
  - 3 attempts → 5 minute lockout
  - 5 attempts → 15 minute lockout
  - 10 attempts → 24 hour lockout
- Account lockout tracking with `locked_until` field
- Failed login attempt counting

### Rate Limiting
- **Login**: 5 attempts per 5 minutes
- **Register**: 3 per hour
- **Password reset**: 3 per hour
- **Token refresh**: 10 per minute
- Per-IP rate limiting via Redis

### Two-Factor Authentication
- **TOTP-based** 2FA (Google Authenticator compatible)
- QR code generation for easy setup
- Backup codes support (extensible)
- Optional 2FA enforcement

### Audit & Logging
Every action logged with:
- User ID
- Event type
- IP address & User-Agent
- Timestamp
- Metadata (additional context)

**Logged events:**
- login_success, login_failed, login_blocked
- logout, logout_all_sessions
- register_success, email_verified
- password_reset_requested, password_reset_success, password_changed
- oauth_login_google, oauth_login_github
- totp_setup_initiated, totp_enabled, totp_disabled, totp_failed
- session_revoked
- account_locked, account_unlocked
- role_assigned, permission_granted
- admin_user_updated, admin_user_deleted

### OAuth2 Integration
- **Google OAuth**: Email + profile data
- **GitHub OAuth**: Username + profile data
- Automatic user creation on first OAuth login
- Email verification bypass for OAuth users

### Session Management
- Active session tracking
- Device fingerprinting (device_info, user_agent)
- IP address logging
- Remote session revocation
- Session expiration (7 days default)
- Last-used timestamp tracking

## Running Tests

```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_auth.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=app
```

## Docker Deployment

### Build and Run Full Stack

```bash
docker-compose up --build
```

This starts:
- **API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Production Build

```bash
docker build -t authsystem:latest .
docker run -p 8000:8000 --env-file .env authsystem:latest
```

## Environment Variables Reference

```env
# App Configuration
APP_NAME=AuthSystem              # Application name
DEBUG=false                      # Debug mode
SECRET_KEY=...                   # JWT signing key (min 64 chars)
ALGORITHM=HS256                  # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES=15   # Access token TTL
REFRESH_TOKEN_EXPIRE_DAYS=7      # Refresh token TTL

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/authdb

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password
EMAILS_FROM=noreply@authsystem.com

# Frontend
FRONTEND_URL=http://localhost:3000

# OAuth - Google
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# OAuth - GitHub
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback
```

## Database Models

### User
- ID (UUID primary key)
- Email, username (unique)
- Hashed password (optional, null for OAuth)
- Profile: full_name, avatar_url
- Status: is_active, is_verified, is_superuser
- OAuth: oauth_provider, oauth_id
- 2FA: totp_secret, totp_enabled
- Security: failed_login_attempts, locked_until, last_login, last_login_ip
- Timestamps: created_at, updated_at

### Role & Permission
- Role: id, name (unique), description
- Permission: id, name (unique), description
- UserRole: many-to-many junction table
- role_permissions: many-to-many permissions per role

### Session
- ID (UUID primary key)
- User ID (foreign key)
- Refresh token hash (unique)
- Device info & IP tracking
- Status: is_active
- Expiration: expires_at, last_used_at
- Timestamps: created_at

### AuditLog
- ID (UUID primary key)
- User ID (nullable)
- Event (event type name)
- IP address & User-Agent
- Metadata (JSON)
- Timestamp: created_at

### Token
- ID (UUID primary key)
- User ID (foreign key)
- Token hash (unique)
- Type: email_verification or password_reset
- Status: is_used
- Expiration: expires_at
- Timestamp: created_at

## Example Workflows

### User Registration & Login

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
  }'

# 2. Verify email (link from email)
curl -X GET "http://localhost:8000/auth/verify-email/TOKEN_FROM_EMAIL"

# 3. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'

# Response includes access_token & refresh_token
```

### Using Protected Endpoints

```bash
curl -X GET http://localhost:8000/users/me \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### Refresh Token

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "REFRESH_TOKEN"}'
```

## Security Considerations

### In Production

1. **Change default values:**
   - Generate strong SECRET_KEY
   - Use environment-specific .env files
   - Never commit .env to version control

2. **Database:**
   - Use strong PostgreSQL password
   - Enable SSL for database connections
   - Regular backups
   - Restrict database access

3. **Redis:**
   - Enable password authentication
   - Use Redis over TLS
   - Restrict network access

4. **Email:**
   - Use OAuth2/app-specific passwords (not account password)
   - Consider using transactional email service (SendGrid, AWS SES)

5. **HTTPS:**
   - Always use HTTPS in production
   - Set secure cookie flags
   - Enable HSTS

6. **CORS:**
   - Restrict allowed origins
   - Remove wildcard if specific domains known

7. **Rate Limiting:**
   - Adjust limits based on actual usage
   - Consider per-user limits in addition to IP limits

8. **Monitoring:**
   - Monitor audit logs for suspicious activity
   - Set up alerts for repeated failed login attempts
   - Track token refresh patterns

## Extending the System

### Add Custom Permissions

1. Create permissions in database
2. Assign to roles
3. Check in route: `await user_service.check_permission(user_id, "permission:name")`

### Add Custom OAuth Provider

1. Create OAuth client in `app/core/oauth2.py`
2. Create login route in `app/routers/auth.py`
3. Handle user creation/update

### Customize Token Claims

Modify `create_access_token()` in `app/core/security.py` to include additional claims.

### Add Email Templates

Extend `app/core/email.py` with HTML templates for different email types.

## Troubleshooting

### Database Connection Error
- Check PostgreSQL is running: `psql -U user -d authdb`
- Verify DATABASE_URL in .env
- Run migrations: `alembic upgrade head`

### Redis Connection Error
- Check Redis is running: `redis-cli ping`
- Verify REDIS_URL in .env

### Email Not Sending
- Check SMTP credentials
- Enable "Less secure apps" for Gmail
- Or use app-specific password

### OAuth Callback Error
- Verify redirect URIs match in .env and OAuth provider settings
- Check callback parameters are correct

## License

MIT

## Support

For issues, questions, or contributions, please refer to the project documentation or contact the development team.

---

**Built with ❤️ using FastAPI, PostgreSQL, and Redis**
