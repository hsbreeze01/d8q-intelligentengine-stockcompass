"""缠论核心数据结构定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Direction(Enum):
    UP = "up"
    DOWN = "down"


class FractalType(Enum):
    TOP = "top"
    BOTTOM = "bottom"


class SignalType(Enum):
    BUY1 = "buy1"   # 第一类买点
    BUY2 = "buy2"   # 第二类买点
    BUY3 = "buy3"   # 第三类买点
    SELL1 = "sell1"  # 第一类卖点
    SELL2 = "sell2"  # 第二类卖点
    SELL3 = "sell3"  # 第三类卖点


class PivotStatus(Enum):
    ACTIVE = "active"        # 进行中
    COMPLETED = "completed"  # 已完成
    EXTENDED = "extended"    # 延伸中


@dataclass
class Kline:
    """标准化K线"""
    idx: int           # 原始索引
    dt: str            # 日期时间
    open: float
    high: float
    low: float
    close: float
    volume: float
    # 包含处理后的高低点
    merged_high: float = 0.0
    merged_low: float = 0.0
    is_merged: bool = False  # 是否被合并

    def __post_init__(self):
        if self.merged_high == 0.0:
            self.merged_high = self.high
        if self.merged_low == 0.0:
            self.merged_low = self.low


@dataclass
class Fractal:
    """分型（顶分型/底分型）"""
    type: FractalType
    idx: int            # 中间K线的原始索引
    dt: str
    value: float        # 顶分型取最高价，底分型取最低价
    kline_indices: List[int] = field(default_factory=list)  # 构成分型的3根K线索引


@dataclass
class Stroke:
    """笔"""
    direction: Direction
    start_fractal: Fractal
    end_fractal: Fractal
    start_idx: int
    end_idx: int
    start_value: float
    end_value: float
    kline_count: int = 0  # 包含的K线数量

    @property
    def height(self) -> float:
        return abs(self.end_value - self.start_value)


@dataclass
class Segment:
    """线段"""
    direction: Direction
    start_idx: int
    end_idx: int
    start_value: float
    end_value: float
    strokes: List[Stroke] = field(default_factory=list)
    is_confirmed: bool = True
    gap: bool = False


@dataclass
class Pivot:
    """走势中枢"""
    start_idx: int
    end_idx: int
    zg: float          # 中枢上沿 = min(g1, g2) 前两段高点的较低者
    zd: float          # 中枢下沿 = max(d1, d2) 前两段低点的较高者
    gg: float          # 中枢最高点
    dd: float          # 中枢最低点
    direction: Optional[Direction] = None
    status: PivotStatus = PivotStatus.ACTIVE
    strokes: List[Stroke] = field(default_factory=list)  # 构成中枢的笔

    @property
    def range(self) -> float:
        return self.zg - self.zd


@dataclass
class Divergence:
    """背驰信息"""
    area_a: float       # A段MACD柱面积
    area_c: float       # C段MACD柱面积
    ratio: float        # C/A比值
    is_divergent: bool  # 是否背驰
    a_start_idx: int
    a_end_idx: int
    c_start_idx: int
    c_end_idx: int


@dataclass
class Signal:
    """买卖点信号"""
    type: SignalType
    idx: int
    dt: str
    price: float
    score: int = 0
    morphology_score: int = 0
    dynamics_score: int = 0
    environment_score: int = 0
    stop_loss: float = 0.0
    target: float = 0.0
    pivot: Optional[Pivot] = None
    divergence: Optional[Divergence] = None
    reason_chain: List[str] = field(default_factory=list)
    # P0-B2: price 现为可执行价(信号确认K线收盘价);
    # signal_ref_price 保留结构参考值(笔极值/中枢边界), 仅供分析展示。
    signal_ref_price: float = 0.0
    exec_price: float = 0.0
