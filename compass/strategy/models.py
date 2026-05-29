"""策略组引擎 — Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 条件 & 聚合 子模型
# ---------------------------------------------------------------------------

class Condition(BaseModel):
    indicator: str = Field(..., min_length=1, description="指标名")
    operator: Literal[">", "<", ">=", "<=", "==", "cross_above", "cross_below"]
    value: Optional[float] = Field(None, description="固定阈值；与 compare_to 二选一")
    compare_to: Optional[str] = Field(None, min_length=1, description="右侧比较指标名")

class AggregationRule(BaseModel):
    dimension: Literal["industry", "concept", "theme"]
    min_stocks: int = Field(..., ge=1)
    time_window_minutes: int = Field(..., ge=1)
    filters: Optional[Dict[str, Any]] = Field(None, description="增强策略前置过滤配置")


# ---------------------------------------------------------------------------
# Strategy Group — Create / Update / Response
# ---------------------------------------------------------------------------

class StrategyGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, description="策略组名称")
    indicators: List[str] = Field(..., min_items=1, description="指标列表")
    signal_logic: Literal["AND", "OR", "SCORING"]
    conditions: List[Condition] = Field(..., min_items=1, description="触发条件")
    aggregation: AggregationRule
    scan_cron: Optional[str] = None
    scoring_threshold: Optional[int] = None

class StrategyGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    indicators: Optional[List[str]] = Field(None, min_items=1)
    signal_logic: Optional[Literal["AND", "OR", "SCORING"]] = None
    conditions: Optional[List[Condition]] = None
    aggregation: Optional[AggregationRule] = None
    scan_cron: Optional[str] = None
    scoring_threshold: Optional[int] = None

class StrategyGroupStatusUpdate(BaseModel):
    status: Literal["active", "paused"]

class StrategyGroupResponse(BaseModel):
    id: int
    name: str
    indicators: List[str]
    signal_logic: str
    conditions: List[Dict[str, Any]]
    scoring_threshold: Optional[int] = None
    aggregation: Dict[str, Any]
    scan_cron: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Signal Snapshot — Response
# ---------------------------------------------------------------------------

class SignalSnapshotResponse(BaseModel):
    id: int
    strategy_group_id: int
    run_id: int
    stock_code: str
    stock_name: Optional[str] = None
    indicator_snapshot: Dict[str, Any]
    buy_star: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Group Event — Response
# ---------------------------------------------------------------------------

class GroupEventResponse(BaseModel):
    id: int
    strategy_group_id: int
    run_id: Optional[int] = None
    dimension: str
    dimension_value: str
    stock_count: int
    avg_buy_star: Optional[float] = None
    max_buy_star: Optional[int] = None
    matched_stocks: List[Dict[str, Any]]
    status: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Scan — Response
# ---------------------------------------------------------------------------

class ScanResult(BaseModel):
    scan_run_id: int
    signals_found: int
    events_created: int
    duration_seconds: float


# ---------------------------------------------------------------------------
# Industry Sync — Response
# ---------------------------------------------------------------------------

class IndustrySyncResponse(BaseModel):
    updated_count: int
    message: str

class IndustryStatsItem(BaseModel):
    industry: str
    count: int

class IndustryStatusResponse(BaseModel):
    total: int
    has_industry: int
    completion_rate: float


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
