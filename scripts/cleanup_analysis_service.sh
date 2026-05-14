#!/bin/bash
# cleanup_analysis_service.sh — 清理 analysis batch 的一次性服务资源
# 仅在 analysis batch 全部完成后执行

SERVICE=d8q-analysis
WATCHDOG=/home/ecs-assist-user/d8q-intelligentengine-stockcompass/scripts/analysis_watchdog.sh
LOG=/var/log/d8q/analysis-batch.log

echo '=== Cleaning up analysis batch service resources ==='

# 1. Stop and disable service
systemctl stop $SERVICE 2>/dev/null
systemctl disable $SERVICE 2>/dev/null
rm -f /etc/systemd/system/${SERVICE}.service
systemctl daemon-reload
echo 'Service stopped, disabled, and unit file removed'

# 2. Remove watchdog cron
(crontab -l 2>/dev/null | grep -v analysis_watchdog) | crontab -
echo 'Watchdog cron removed'

# 3. Remove watchdog script
rm -f $WATCHDOG
echo 'Watchdog script removed'

# 4. Show final stats from log
echo ''
echo '=== Final analysis stats ==='
grep 'ANALYSIS PHASE COMPLETE' $LOG | tail -1
grep 'Analysis:.*ok' $LOG | tail -1
echo ''

echo '=== Cleanup complete. Log preserved at $LOG ==='
