#!/bin/bash

# 设置环境变量
export DevENV=stg

# 获取脚本的绝对路径
SCRIPT_DIR=$(cd $(dirname $0); pwd)
LOG_FILE="$SCRIPT_DIR/stockdata.log"
PID_FILE="$SCRIPT_DIR/stockdata.pid"

start() {
    if [ -f $PID_FILE ]; then
        echo "Process is already running with PID $(cat $PID_FILE)"
        exit 1
    fi

    echo "Starting stockdata with gunicorn..."
    nohup gunicorn -c $SCRIPT_DIR/stockdata/main.py main:app > $LOG_FILE 2>&1 &
    echo $! > $PID_FILE
    echo "Stockdata started with PID $(cat $PID_FILE)"
}

stop() {
    if [ ! -f $PID_FILE ]; then
        echo "No running process found."
        exit 1
    fi

    echo "Stopping stockdata..."
    kill $(cat $PID_FILE)
    rm $PID_FILE
    echo "Stockdata stopped."
}

restart() {
    stop
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
