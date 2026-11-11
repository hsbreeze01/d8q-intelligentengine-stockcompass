-- 可复算的止损/目标公式契约；仅增加可空字段，不回填或改写历史信号。
ALTER TABLE czsc_signal_history
    ADD COLUMN formula_version VARCHAR(64) NULL,
    ADD COLUMN stop_basis VARCHAR(32) NULL,
    ADD COLUMN structure_ref_type VARCHAR(32) NULL,
    ADD COLUMN structure_ref_price DECIMAL(18,4) NULL,
    ADD COLUMN structure_ref_date DATE NULL,
    ADD COLUMN stop_buffer_pct DECIMAL(10,6) NULL,
    ADD COLUMN stop_cap_pct DECIMAL(10,6) NULL,
    ADD COLUMN target_basis VARCHAR(32) NULL,
    ADD COLUMN target_ref_price DECIMAL(18,4) NULL,
    ADD COLUMN target_ref_date DATE NULL,
    ADD COLUMN rr_at_signal DECIMAL(18,8) NULL;
