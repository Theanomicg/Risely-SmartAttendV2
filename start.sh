#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SmartAttend v2 — One-Command Startup Script
# Usage: ./start.sh [dev|prod]
# ─────────────────────────────────────────────────────────────────────────────

set -e
MODE=${1:-dev}
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │  SmartAttend v2 — Risely Platform   │"
echo "  │  Mode: $MODE                           │"
echo "  └─────────────────────────────────────┘"
echo ""

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3.10+ required. Install it first."
  exit 1
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYVER"

# ── Check Node ───────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  echo "❌ Node.js 18+ required. Install from https://nodejs.org"
  exit 1
fi
echo "✓ Node $(node --version)"

# ── Backend: venv + deps ─────────────────────────────────────────────────────
cd "$BACKEND"

if [ ! -d "venv" ]; then
  echo ""
  echo "📦 Creating Python virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
echo "✓ venv activated"

echo ""
echo "📦 Installing/updating backend dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✓ Backend dependencies ready"

# ── Backend: .env ─────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo ""
  echo "⚙️  Creating backend .env from example..."
  cp .env.example .env
  echo ""
  echo "  ╔════════════════════════════════════════════════════════╗"
  echo "  ║  IMPORTANT: Edit backend/.env before first use!       ║"
  echo "  ║  Set: SMTP_USER, SMTP_PASSWORD, SECRET_KEY            ║"
  echo "  ╚════════════════════════════════════════════════════════╝"
  echo ""
fi

# ── Frontend: deps ────────────────────────────────────────────────────────────
cd "$FRONTEND"

if [ ! -d "node_modules" ]; then
  echo ""
  echo "📦 Installing frontend dependencies (this takes ~1 min first time)..."
  npm install --silent
  echo "✓ Frontend dependencies ready"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

# ── Start both services ───────────────────────────────────────────────────────
cd "$ROOT"

if [ "$MODE" = "prod" ]; then
  echo ""
  echo "🏗  Building frontend for production..."
  cd "$FRONTEND" && npm run build
  cd "$ROOT"
  echo "✓ Frontend built to frontend/dist/"
  echo ""
  echo "🚀 Starting backend (production mode)..."
  cd "$BACKEND"
  source venv/bin/activate
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 &
  BACKEND_PID=$!
  echo "✓ Backend PID: $BACKEND_PID"
  echo ""
  echo "  Backend:  http://localhost:8000"
  echo "  API Docs: http://localhost:8000/docs"
  echo ""
  echo "  For HTTPS, configure Nginx (see docs/nginx.conf)"
  echo ""
  wait $BACKEND_PID

else
  # Dev mode — run both concurrently
  echo ""
  echo "🚀 Starting backend (dev mode)..."
  cd "$BACKEND"
  source venv/bin/activate
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
  BACKEND_PID=$!

  sleep 2  # Let backend start

  echo "🚀 Starting frontend (dev mode)..."
  cd "$FRONTEND"
  npm run dev &
  FRONTEND_PID=$!

  echo ""
  echo "  ┌────────────────────────────────────────────┐"
  echo "  │  ✅ SmartAttend is running!                │"
  echo "  │                                            │"
  echo "  │  Admin Panel:  http://localhost:5173       │"
  echo "  │  API:          http://localhost:8000       │"
  echo "  │  API Docs:     http://localhost:8000/docs  │"
  echo "  │                                            │"
  echo "  │  First time? Run setup:                   │"
  echo "  │  curl -X POST http://localhost:8000/auth/setup │"
  echo "  │    -H 'Content-Type: application/json'    │"
  echo "  │    -d '{\"name\":\"Admin\",\"email\":\"a@b.com\",\"password\":\"pass\"}' │"
  echo "  │                                            │"
  echo "  │  Press Ctrl+C to stop                     │"
  echo "  └────────────────────────────────────────────┘"
  echo ""

  # Trap Ctrl+C
  trap "echo ''; echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

  wait
fi
