#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  AuthSystem — One-command dev bootstrap
#  Usage:  bash scripts/quickstart.sh
#
#  What this does:
#    1. Copies .env.example → .env  (if .env doesn't exist yet)
#    2. Starts Postgres + Redis via docker-compose
#    3. Waits for both services to be healthy
#    4. Runs database migrations (alembic upgrade head)
#    5. Seeds the database with default roles, an admin, and a demo user
#    6. Starts the API server on http://localhost:8000
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

info()    { echo -e "${GREEN}[quickstart]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[quickstart]${RESET} $*"; }
heading() { echo -e "\n${BOLD}$*${RESET}"; }

# ── 1. Environment file ───────────────────────────────────────────────────────
heading "Step 1/5 — Environment"
if [ ! -f .env ]; then
    cp .env.example .env
    info "Created .env from .env.example — review it if you want SMTP or OAuth."
else
    info ".env already exists — skipping copy."
fi

# ── 2. Start backing services ─────────────────────────────────────────────────
heading "Step 2/5 — Starting Postgres + Redis"
docker-compose up -d db redis
info "Waiting for services to become healthy..."

wait_healthy() {
    local service="$1"
    local max=30
    local i=0
    while [ $i -lt $max ]; do
        status=$(docker-compose ps --format json "$service" 2>/dev/null \
                 | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "")
        if [ "$status" = "healthy" ]; then
            info "$service is healthy."
            return 0
        fi
        sleep 1
        i=$((i+1))
    done
    warn "$service did not become healthy in ${max}s — continuing anyway."
}

wait_healthy db
wait_healthy redis

# ── 3. Migrations ─────────────────────────────────────────────────────────────
heading "Step 3/5 — Running migrations"
alembic upgrade head
info "Migrations applied."

# ── 4. Seed ───────────────────────────────────────────────────────────────────
heading "Step 4/5 — Seeding database"
python scripts/seed.py
info "Seed complete."

# ── 5. Start API ──────────────────────────────────────────────────────────────
heading "Step 5/5 — Starting API server"
info "API will be available at http://localhost:8000/docs"
info "Press Ctrl+C to stop.\n"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
