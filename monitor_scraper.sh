#!/bin/bash

# Monitor script for slow_market_scraper.sh

# Find the most recent state file
STATE_FILE=$(ls -t Production_Markets_*_state.json 2>/dev/null | head -1)
LOG_FILE=$(ls -t Production_Markets_*_scraper.log 2>/dev/null | head -1)

if [ -z "$STATE_FILE" ] || [ -z "$LOG_FILE" ]; then
    echo "No active scraping session found."
    exit 1
fi

echo "Monitoring scraping session..."
echo "State file: $STATE_FILE"
echo "Log file: $LOG_FILE"
echo ""

# Display current state
if [ -f "$STATE_FILE" ]; then
    echo "Current state:"
    python3 -c "
import json
with open('$STATE_FILE', 'r') as f:
    state = json.load(f)
    print(f\"  Current market: {state['current_market']}\")
    print(f\"  Completed markets: {state['completed_markets']}\")
    print(f\"  Last update: {state['timestamp']}\")
"
fi

echo ""
echo "Recent activity:"
tail -20 "$LOG_FILE" | grep -E "(INFO|SUCCESS|ERROR|WARNING)" | tail -10

echo ""
echo "Press Ctrl+C to exit monitoring"
echo ""

# Continuous monitoring
while true; do
    # Get the last line with progress info
    LAST_PROGRESS=$(grep -E "(Progress:|Break remaining:|Starting analysis for market:|Completed market:)" "$LOG_FILE" | tail -1)
    if [ ! -z "$LAST_PROGRESS" ]; then
        printf "\r%-80s" "$LAST_PROGRESS"
    fi
    sleep 5
done