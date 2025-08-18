#!/bin/bash

# Script to forcefully kill backend processes running on port 4000
# Usage: ./kill_backend.sh

PORT=4000

echo "🔍 Checking for backend processes on port $PORT..."

# Find processes using port 4000
PROCESSES=$(lsof -ti:$PORT 2>/dev/null)

if [ -z "$PROCESSES" ]; then
    echo "✅ No backend processes found on port $PORT"
    exit 0
fi

echo "📋 Found backend processes on port $PORT:"
lsof -i:$PORT 2>/dev/null

echo ""
echo "🔪 Killing backend processes..."

# Kill each process
for PID in $PROCESSES; do
    echo "  Killing PID $PID..."
    kill $PID 2>/dev/null
    
    # Wait a moment for graceful shutdown
    sleep 0.5
    
    # Check if process was killed successfully
    if kill -0 $PID 2>/dev/null; then
        echo "  ⚠️  PID $PID still running, using force kill..."
        kill -9 $PID 2>/dev/null
    fi
done

# Wait and verify
sleep 1

REMAINING=$(lsof -ti:$PORT 2>/dev/null)
if [ -z "$REMAINING" ]; then
    echo "✅ All backend processes on port $PORT killed successfully"
    exit 0
else
    echo "❌ Some processes may still be running:"
    lsof -i:$PORT 2>/dev/null
    echo ""
    echo "💡 Manual intervention may be required"
    exit 1
fi