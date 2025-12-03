#!/bin/bash
# start.sh - Start script for SelamSnap bot

echo "🚀 Starting SelamSnap Christian Photo Editor Bot..."

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install requirements
pip install -r requirements.txt

# Run the bot
python bot.py

# If bot crashes, restart after 5 seconds
echo "⚠️  Bot stopped, restarting in 5 seconds..."
sleep 5
exec bash start.sh