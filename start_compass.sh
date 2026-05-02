#!/bin/bash
cd /home/ecs-assist-user/d8q-intelligentengine-stockcompass
source venv/bin/activate
pkill -f 'gunicorn.*8087' 2>/dev/null
sleep 1
nohup gunicorn -w 2 -b 0.0.0.0:8087 --timeout 300 --access-logfile /var/log/d8q/compass-access.log --error-logfile /var/log/d8q/compass.log --log-level info 'compass.api.app:create_app()' > /tmp/compass-nohup.out 2>&1 &
echo $! > /var/run/stockcompass.pid
sleep 3
ps aux | grep gunicorn | grep 8087 | grep -v grep
netstat -tlnp | grep 8087
