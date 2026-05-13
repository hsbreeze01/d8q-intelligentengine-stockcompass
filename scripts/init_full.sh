#!/bin/bash
# Compass Data Pipeline - Full Initialization
# Phase 1: kline + indicators (skip analysis)
# Phase 2: analysis (after Phase 1 completes)

PIPELINE="/home/ecs-assist-user/d8q-intelligentengine-stockcompass/venv/bin/python /home/ecs-assist-user/d8q-intelligentengine-stockcompass/scripts/pipeline.py"
LOG="/var/log/d8q/datapipeline-init.log"

echo "=== Phase 1: K-line + Indicators ===" | tee -a "$LOG"
date | tee -a "$LOG"
$PIPELINE --mode init --skip-analysis --sleep 0.3 2>&1 | tee -a "$LOG"

echo "=== Phase 2: Analysis ===" | tee -a "$LOG"
date | tee -a "$LOG"
$PIPELINE --mode analyze 2>&1 | tee -a "$LOG"

echo "=== Full Init Complete ===" | tee -a "$LOG"
date | tee -a "$LOG"
