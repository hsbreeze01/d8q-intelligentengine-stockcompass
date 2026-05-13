"""策略组引擎 — 行业数据同步服务"""
import json
import logging
import os
import time
from typing import Optional

from compass.data.database import Database

logger = logging.getLogger("compass.strategy.industry_sync")

# 同步状态（内存）
_sync_status = {
    "running": False,
    "total_industries": 0,
    "processed_industries": 0,
    "updated_stocks": 0,
    "error": None,
}


def get_sync_status() -> dict:
    """获取同步进度"""
    return _sync_status.copy()


def sync_industry_data() -> dict:
    """执行行业数据同步：akshare → stock_basic.industry"""
    global _sync_status
    _sync_status = {
        "running": True,
        "total_industries": 0,
        "processed_industries": 0,
        "updated_stocks": 0,
        "error": None,
    }

    try:
        # 尝试从 akshare 获取数据
        industry_map = _fetch_from_akshare()
        if industry_map is None:
            # 降级到本地 JSON 文件
            industry_map = _fetch_from_local()
            if industry_map is None:
                _sync_status["running"] = False
                _sync_status["error"] = "akshare 接口不可用且无本地映射文件"
                return {"updated_count": 0, "message": _sync_status["error"]}

        _sync_status["total_industries"] = len(industry_map)

        # 写入数据库
        updated = _write_to_db(industry_map)
        _sync_status["running"] = False
        _sync_status["updated_stocks"] = updated

        # 同步后质量校验
        result = {
            "updated_count": updated,
            "message": f"同步完成，更新 {updated} 条记录",
        }
        try:
            status = get_industry_status()
            rate = status.get("completion_rate", 0)
            result["completion_rate"] = rate
            if rate < 90:
                result["warning"] = (
                    f"行业补全率 {rate}% 低于 90% 阈值，建议检查数据源完整性"
                )
        except Exception as exc:
            logger.warning("同步后补全率检查失败: %s", exc)

        return result

    except Exception as exc:
        _sync_status["running"] = False
        _sync_status["error"] = str(exc)
        logger.error("行业同步失败: %s", exc, exc_info=True)
        return {"updated_count": 0, "message": str(exc)}


def get_industry_stats() -> list:
    """查询行业分布统计"""
    with Database() as db:
        _, rows = db.select_many(
            "SELECT industry, COUNT(*) as count FROM stock_basic "
            "WHERE industry IS NOT NULL AND industry != '' "
            "GROUP BY industry ORDER BY count DESC"
        )
    return rows


def get_industry_status() -> dict:
    """查询行业补全状态"""
    with Database() as db:
        _, total_row = db.select_one(
            "SELECT COUNT(*) as total FROM stock_basic"
        )
        _, has_row = db.select_one(
            "SELECT COUNT(*) as cnt FROM stock_basic "
            "WHERE industry IS NOT NULL AND industry != ''"
        )
        total = total_row["total"] if total_row else 0
        has_industry = has_row["cnt"] if has_row else 0
        rate = round(has_industry / total * 100, 2) if total else 0.0
    return {
        "total": total,
        "has_industry": has_industry,
        "completion_rate": rate,
    }


def _fetch_from_akshare() -> Optional[dict]:
    """从 akshare 获取行业 → [stock_code] 映射"""
    try:
        import akshare as ak

        # 获取所有行业板块
        boards = ak.stock_board_industry_name_em()
        industry_map = {}

        for idx, row in boards.iterrows():
            industry_name = row.get("板块名称", "")
            if not industry_name:
                continue
            try:
                cons = ak.stock_board_industry_cons_em(symbol=industry_name)
                codes = cons.get("代码", []).tolist()
                industry_map[industry_name] = codes
                _sync_status["processed_industries"] = idx + 1
            except Exception as exc:
                logger.warning("获取行业 %s 成分股失败: %s，重试...", industry_name, exc)
                # 重试 3 次
                for attempt in range(3):
                    time.sleep(2)
                    try:
                        cons = ak.stock_board_industry_cons_em(symbol=industry_name)
                        codes = cons.get("代码", []).tolist()
                        industry_map[industry_name] = codes
                        break
                    except Exception:
                        if attempt == 2:
                            logger.error("行业 %s 重试失败，跳过", industry_name)

            # 每行业间 0.5s 间隔避免 akshare 限频
            time.sleep(0.5)

        return industry_map

    except Exception as exc:
        logger.error("akshare 调用失败: %s", exc)
        return None


def _fetch_from_local() -> Optional[dict]:
    """从本地 JSON 文件读取映射"""
    local_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "industry_mapping.json"
    )
    if not os.path.exists(local_path):
        return None
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("读取本地映射文件失败: %s", exc)
        return None


def _write_to_db(industry_map: dict) -> int:
    """将行业映射写入 stock_basic.industry，返回更新数量"""
    updated = 0
    with Database() as db:
        for industry_name, codes in industry_map.items():
            if not codes:
                continue
            placeholders = ",".join(["%s"] * len(codes))
            count, _ = db.execute(
                f"UPDATE stock_basic SET industry = %s "
                f"WHERE code IN ({placeholders})",
                tuple([industry_name] + codes),
            )
            updated += count
    return updated
