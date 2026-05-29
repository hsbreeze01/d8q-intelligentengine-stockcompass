"""Seed stock2-derived initial strategy groups."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compass.data.database import Database


ARCHIVE_NAMES = ("底部共振测试", "放量突破策略")

STRATEGIES = [
    {
        "name": "stock2底部共振初始策略",
        "indicators": [
            "kdj_k",
            "kdj_d",
            "kdj_j",
            "rsi_6",
            "macd_dif",
            "change_pct",
        ],
        "signal_logic": "SCORING",
        "scoring_threshold": 5,
        "conditions": [
            {"indicator": "kdj_k", "operator": "<", "value": 35},
            {"indicator": "rsi_6", "operator": "<", "value": 45},
            {"indicator": "kdj_k", "operator": "cross_above", "compare_to": "kdj_d"},
            {"indicator": "kdj_j_delta", "operator": ">", "value": 0},
            {"indicator": "macd_dif_delta", "operator": ">", "value": 0},
            {"indicator": "change_pct", "operator": ">", "value": -7},
        ],
        "aggregation": {"dimension": "industry", "min_stocks": 3, "time_window_minutes": 4320},
    },
    {
        "name": "stock2放量KDJ突破初始策略",
        "indicators": [
            "volume_ratio",
            "kdj_k",
            "kdj_d",
            "kdj_j",
            "kdj_j_delta",
        ],
        "signal_logic": "SCORING",
        "scoring_threshold": 5,
        "conditions": [
            {"indicator": "volume_ratio", "operator": ">", "value": 1.5},
            {"indicator": "kdj_j_delta", "operator": ">", "value": 5},
            {"indicator": "kdj_j", "operator": ">", "compare_to": "prev_kdj_j"},
            {"indicator": "kdj_k", "operator": ">", "compare_to": "kdj_d"},
            {"indicator": "kdj_k", "operator": ">", "value": 79},
            {"indicator": "kdj_k", "operator": "cross_above", "compare_to": "kdj_d"},
        ],
        "aggregation": {"dimension": "concept", "min_stocks": 3, "time_window_minutes": 7200},
    },
]


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _archive_simplified_templates(db):
    placeholders = ",".join(["%s"] * len(ARCHIVE_NAMES))
    db.execute(
        f"""
        UPDATE strategy_group
        SET status = 'archived',
            name = CONCAT(name, '（简化模板归档）')
        WHERE status != 'archived'
          AND name IN ({placeholders})
        """,
        ARCHIVE_NAMES,
    )


def _upsert_strategy(db, strategy):
    _, row = db.select_one(
        "SELECT id FROM strategy_group WHERE name = %s ORDER BY id DESC LIMIT 1",
        (strategy["name"],),
    )
    params = (
        _dumps(strategy["indicators"]),
        strategy["signal_logic"],
        _dumps(strategy["conditions"]),
        strategy["scoring_threshold"],
        _dumps(strategy["aggregation"]),
    )
    if row:
        db.execute(
            """
            UPDATE strategy_group
            SET indicators = %s,
                signal_logic = %s,
                conditions = %s,
                scoring_threshold = %s,
                aggregation = %s,
                status = 'active'
            WHERE id = %s
            """,
            (*params, row["id"]),
        )
        return row["id"], "updated"

    _, strategy_id = db.execute(
        """
        INSERT INTO strategy_group
            (name, indicators, signal_logic, conditions, scoring_threshold, aggregation, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'active')
        """,
        (strategy["name"], *params),
    )
    return strategy_id, "inserted"


def main():
    with Database() as db:
        _archive_simplified_templates(db)
        for strategy in STRATEGIES:
            strategy_id, action = _upsert_strategy(db, strategy)
            print(f"{action}: {strategy_id} {strategy['name']}")


if __name__ == "__main__":
    main()
