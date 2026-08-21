# AuthSystem

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/Steve2009729/auth-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Steve2009729/auth-system/actions/workflows/ci.yml)

Self-hosted FastAPI auth & authorization backend — JWT, RBAC, 2FA, OAuth2, audit logging, ready to run.

---

## Quick Start — 5 minutes to a working API

**Prerequisites:** Python 3.11+, Docker

```bash
# 1. Clone
git clone https://github.com/Steve2009729/auth-system.git
cd auth-system

# 2. Install
pip install -e ".[dev]"

# 3. Create .env with a generated SECRET_KEY
authsystem init

# 4. Start Postgres + Redis
docker-compose up -d db redis

# 5. Run migrations
authsystem migrate

# 6. Seed default users and roles
python scripts/seed.py

# 7. Start the server
authsystem serve
```

Open **http://localhost:8000/docs** — Swagger UI is your live demo.

Default credentials seeded by `seed.py`:

| Role  | Email                    | Password        |
|-------|--------------------------|-----------------|
| Admin | admin@authsystem.local   | AdminPass123!   |
| Demo  | demo@authsystem.local    | DemoPass123!    |

> SMTP and OAuth are **optional**. The app boots without them — email features log a warning and skip sending; OAuth routes return `501` until credentials are configured.

---

## Features

| Category | What's included |
|---|---|
| **Auth** | Email/password registration, email verification, login, logout |
| **Tokens** | JWT access tokens (15 min) + refresh token rotation with replay detection |
| **OAuth2** | Google + GitHub (optional — disabled if unconfigured) |
| **2FA** | TOTP (Google Authenticator compatible) with QR code setup |
| **RBAC** | Roles + permissions, per-route enforcement, admin management API |
| **Security** | Brute-force lockout, rate limiting (per IP, per endpoint), token blacklisting |
| **Sessions** | Active session tracking, device info, remote session revocation |
| **Audit log** | Every auth event recorded with user ID, IP, user-agent, metadata |
| **Email** | Verification + password reset emails (SMTP, gracefully skipped if unconfigured) |

---

## CLI Reference

```
authsystem init          # create .env with a generated SECRET_KEY
authsystem serve         # start the API (hot-reload by default)
authsystem create-admin  # interactively create a superuser
authsystem migrate       # run alembic upgrade head
authsystem --version
```

Each command has `--help`:

```bash
authsystem serve --help
```

---

## Integration Guide

Point any frontend or mobile app at the API. Here's the core flow:

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","username":"alice","password":"Secret123!"}'

# Login → get tokens
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Secret123!"}'
# → {"access_token":"...","refresh_token":"...","token_type":"bearer"}

# Call a protected endpoint
curl http://localhost:8000/users/me \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Refresh before the 15-min access token expires
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"REFRESH_TOKEN"}'
```

---

## API Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register new user |
| POST | `/login` | Login — returns tokens, or `requires_2fa: true` |
| POST | `/logout` | Revoke current session |
| POST | `/logout/all` | Revoke all sessions |
| POST | `/refresh` | Rotate refresh token, issue new access token |
| GET | `/verify-email/{token}` | Verify email address |
| POST | `/resend-verification` | Resend verification email |
| POST | `/forgot-password` | Send password reset email |
| POST | `/reset-password` | Reset password with token |
| POST | `/change-password` | Change password (authenticated) |
| GET | `/google` | Google OAuth redirect |
| GET | `/google/callback` | Google OAuth callback |
| GET | `/github` | GitHub OAuth redirect |
| GET | `/github/callback` | GitHub OAuth callback |
| POST | `/2fa/setup` | Generate TOTP secret + QR code |
| POST | `/2fa/enable` | Enable 2FA (verify TOTP code) |
| POST | `/2fa/disable` | Disable 2FA |
| POST | `/2fa/verify` | Complete login when 2FA is active |

### Users (`/users`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/me` | Get current user profile |
| PATCH | `/me` | Update profile |
| DELETE | `/me` | Delete account |
| GET | `/me/permissions` | List user's permissions |

### Sessions (`/sessions`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `` | List active sessions |
| DELETE | `/{session_id}` | Revoke a session |

### Admin (`/admin`) — requires permissions

| Method | Endpoint | Permission |
|--------|----------|-----------|
| GET | `/users` | `admin:read` |
| GET | `/users/{id}` | `admin:read` |
| PATCH | `/users/{id}` | `admin:write` |
| DELETE | `/users/{id}` | `admin:delete` |
| POST | `/roles` | `admin:all` |
| POST | `/roles/{id}/permissions` | `admin:all` |
| POST | `/users/{id}/roles` | `admin:all` |
| GET | `/audit-logs` | `admin:read` |

---

## Architecture

```
Client
  │
  ▼
FastAPI app (app/main.py)
  │
  ├── Routers  (app/routers/)      ← HTTP layer, request validation
  │     auth.py / users.py / sessions.py / admin.py
  │
  ├── Services (app/services/)     ← Business logic
  │     auth_service.py / user_service.py / session_service.py
  │
  ├── Models   (app/models/)       ← SQLAlchemy ORM
  │     User / Role / Permission / Session / Token / AuditLog
  │
  ├── Core     (app/core/)         ← Security primitives
  │     security.py  JWT + bcrypt + token generation
  │     oauth2.py    Google + GitHub (optional)
  │     totp.py      TOTP / QR code
  │     rate_limiter.py  Redis sliding window
  │     email.py     SMTP (optional)
  │     audit.py     Audit log writer
  │
  └── DB
        PostgreSQL  (via asyncpg + SQLAlchemy async)
        Redis       (sessions, rate limits, token blacklist, 2FA sessions)
```

---

## Configuration Reference

All config is via environment variables. Copy `.env.example` to `.env` — only `SECRET_KEY` needs changing for a first dev run (auto-generated by `authsystem init`).

| Variable | Default | Required | Notes |
|---|---|---|---|
| `SECRET_KEY` | — | **Yes** | Min 64 chars. Auto-generated in dev. |
| `DEBUG` | `false` | No | Enables reload + verbose logging |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/authdb` | **Yes** | Matches docker-compose defaults |
| `REDIS_URL` | `redis://localhost:6379/0` | **Yes** | Matches docker-compose defaults |
| `SMTP_USER` | placeholder | No | Leave as placeholder to disable email |
| `SMTP_PASSWORD` | placeholder | No | Leave as placeholder to disable email |
| `GOOGLE_CLIENT_ID` | placeholder | No | Leave as placeholder to disable Google OAuth |
| `GITHUB_CLIENT_ID` | placeholder | No | Leave as placeholder to disable GitHub OAuth |

Full variable list: [`.env.example`](.env.example)

---

## Security Model

**Passwords** — bcrypt with 12 rounds. Reset tokens are SHA-256 hashed before storage.

**Tokens** — JWT access tokens (15 min, HS256). Refresh tokens are rotated on every use. Replay detection: if a used refresh token is presented again, all sessions for that user are immediately revoked.

**Brute force** — failed logins increment a counter per user:
- 3 failures → 5-minute lockout
- 5 failures → 15-minute lockout
- 10 failures → 24-hour lockout

**Rate limiting** — Redis sliding window per IP:
- Login: 5/5 min · Register: 3/hr · Password reset: 3/hr · Refresh: 10/min

**2FA** — TOTP (RFC 6238), ±30s clock drift tolerance. Setup stores a temporary secret in Redis until confirmed.

**Audit log** — every auth event written to `audit_logs` with user ID, IP, user-agent, and event metadata.

---

## Production Checklist

- [ ] Set a strong `SECRET_KEY` and `DEBUG=false`
- [ ] Use SSL for PostgreSQL and Redis
- [ ] Restrict CORS origins in `app/main.py`
- [ ] Configure SMTP with an app-specific password, not your account password
- [ ] Put the API behind a reverse proxy (nginx, Caddy) with HTTPS
- [ ] Monitor the `audit_logs` table for suspicious activity

---

## Docker

```bash
# Full stack (API + Postgres + Redis)
docker-compose up --build

# API only (with external DB/Redis)
docker build -t authsystem:latest .
docker run -p 8000:8000 --env-file .env authsystem:latest
```

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, feature requests, and PRs are welcome.

## License

[MIT](LICENSE)
