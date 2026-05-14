#!/bin/bash
# analysis_watchdog.sh — 健康监测 + 完成后自动清理
LOG=/var/log/d8q/analysis-batch.log
WATCHDOG_LOG=/var/log/d8q/analysis-watchdog.log
SERVICE=d8q-analysis
MARKER=/tmp/d8q-analysis-cleaned

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $1" >> $WATCHDOG_LOG; }

# Check if already cleaned up
if [ -f "$MARKER" ]; then exit 0; fi

# Count missing stocks
MISSING=$(mysql -u root -ppassword stock_analysis_system -N -e "
    SELECT COUNT(DISTINCT s.stock_code) FROM stock_data_daily s
    LEFT JOIN (SELECT DISTINCT stock_code FROM stock_analysis) a ON s.stock_code = a.stock_code
    WHERE a.stock_code IS NULL;" 2>/dev/null)

if [ -z "$MISSING" ] || [ "$MISSING" -eq 0 ]; then
    log "All stocks analyzed. Auto-cleaning service resources."
    systemctl stop $SERVICE 2>/dev/null
    systemctl disable $SERVICE 2>/dev/null
    rm -f /etc/systemd/system/${SERVICE}.service
    systemctl daemon-reload
    (crontab -l 2>/dev/null | grep -v analysis_watchdog) | crontab -
    rm -f $0
    touch $MARKER
    log "Cleanup complete. Service removed, cron removed, self-deleted."
    exit 0
fi

log "Missing: $MISSING stocks"

ACTIVE=$(systemctl is-active $SERVICE 2>/dev/null)
if [ "$ACTIVE" != "active" ]; then
    log "Service not active ($ACTIVE). Starting..."
    systemctl start $SERVICE
    exit 0
fi

if [ -f "$LOG" ]; then
    LAST_MOD=$(stat -c %Y "$LOG" 2>/dev/null || echo 0)
    STALL_MINS=$(( ($(date +%s) - LAST_MOD) / 60 ))
    if [ "$STALL_MINS" -gt 30 ]; then
        log "Log stalled ${STALL_MINS}min. Restarting..."
        systemctl restart $SERVICE
    else
        log "Healthy. Last update: ${STALL_MINS}min ago"
    fi
else
    systemctl start $SERVICE
fi
