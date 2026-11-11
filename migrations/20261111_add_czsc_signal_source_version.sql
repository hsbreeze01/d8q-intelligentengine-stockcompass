-- 每条信号生成时的引擎版本与部署SHA；不得用当前API进程版本回填历史信号。
ALTER TABLE czsc_signal_history
    ADD COLUMN strategy_version VARCHAR(32) NULL,
    ADD COLUMN deploy_sha VARCHAR(64) NULL;
