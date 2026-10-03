#!/bin/bash
# XHS Generic Monitor Runner
# --------------------------
# 1. Runs the node script for a custom keyword
# 2. Captures the report output
# 3. Sends it to Telegram via openclaw agent (Direct)

export XHS_COOKIE="YOUR_XHS_COOKIE_HERE"
export NODE_PATH=/usr/lib/node_modules
TARGET_ID="telegram:YOUR_CHAT_ID_HERE"
QUERY="${1}"
LOG_FILE="/data/root/xhs_generic_cron.log"

if [ -z "$QUERY" ]; then
    echo "Error: No query specified."
    exit 1
fi

echo "[$(date)] Starting XHS Generic Search: $QUERY" >> $LOG_FILE

# Execute Node.js script and capture output
REPORT=$(/usr/bin/node /root/.openclaw/workspace/skills/xhs-generic-monitor/scripts/generic_monitor.js "$QUERY" 2>>$LOG_FILE)

if [ $? -eq 0 ] && [ ! -z "$REPORT" ]; then
    # Send report via openclaw agent
    /usr/bin/openclaw agent \
        --to "$TARGET_ID" \
        --channel "telegram" \
        --message "$REPORT" \
        --deliver >> $LOG_FILE 2>&1
    echo "[$(date)] Generic Search delivered to $TARGET_ID" >> $LOG_FILE
else
    echo "[$(date)] Error: Script failed or empty report" >> $LOG_FILE
fi
