#!/bin/bash
# Proteus startup script

echo "Starting Proteus services..."

# Start PostgreSQL if not running
pg_isready -q 2>/dev/null || brew services start postgresql@14

# Start Redis if not running
redis-cli ping 2>/dev/null || brew services start redis

# Start backend
cd "$(dirname "$0")/../backend"
source venv/bin/activate
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/proteus_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Start frontend
cd "$(dirname "$0")/../frontend"
nohup npm run dev > /tmp/proteus_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "=== Proteus is running ==="
echo "Frontend: http://localhost:5173"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Backend log: tail -f /tmp/proteus_backend.log"
echo "Frontend log: tail -f /tmp/proteus_frontend.log"
