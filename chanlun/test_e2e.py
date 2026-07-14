"""缠论引擎端到端测试 - 用真实股票数据验证完整链路"""
import sys
sys.path.insert(0, "/home/ecs-assist-user/d8q-intelligentengine-stockcompass")

import akshare as ak
import json
from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots, check_pivot_break
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2, detect_buy1
from chanlun.engine.types import Direction, PivotStatus


def fetch_daily_klines(stock_code: str, days: int = 120) -> list:
    """通过AKShare获取日线数据"""
    # 转换代码格式
    if stock_code.startswith("6"):
        symbol = f"sh{stock_code}"
    else:
        symbol = f"sz{stock_code}"
    
    df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
    df = df.tail(days)
    
    klines = []
    for _, row in df.iterrows():
        klines.append({
            "dt": str(row["日期"]),
            "open": float(row["开盘"]),
            "high": float(row["最高"]),
            "low": float(row["最低"]),
            "close": float(row["收盘"]),
            "volume": float(row["成交量"])
        })
    return klines


def run_full_analysis(stock_code: str, stock_name: str = ""):
    """运行完整缠论分析链路"""
    print(f"\n{'='*60}")
    print(f"  缠论分析: {stock_code} {stock_name}")
    print(f"{'='*60}")
    
    # Step 1: 获取数据
    print("\n[1/6] 获取K线数据...")
    klines = fetch_daily_klines(stock_code, days=120)
    print(f"  获取 {len(klines)} 根日线K线 ({klines[0]['dt']} ~ {klines[-1]['dt']})")
    
    # Step 2: 分型识别
    print("\n[2/6] 分型识别...")
    merged_klines, fractals = identify_fractals(klines)
    tops = [f for f in fractals if f.type.value == "top"]
    bottoms = [f for f in fractals if f.type.value == "bottom"]
    print(f"  标准化K线: {len(merged_klines)} 根（合并包含关系后）")
    print(f"  分型: {len(fractals)} 个（顶{len(tops)} + 底{len(bottoms)}）")
    
    # Step 3: 笔划分
    print("\n[3/6] 笔划分...")
    strokes = build_strokes(fractals)
    print(f"  笔: {len(strokes)} 笔")
    for i, s in enumerate(strokes[-5:], max(0, len(strokes)-5)):
        arrow = "↑" if s.direction == Direction.UP else "↓"
        print(f"    笔{i+1} {arrow} [{s.start_value:.2f} → {s.end_value:.2f}] "
              f"idx:{s.start_idx}-{s.end_idx}")
    
    # Step 4: 中枢计算
    print("\n[4/6] 中枢计算...")
    pivots = find_pivots(strokes)
    print(f"  中枢: {len(pivots)} 个")
    for i, p in enumerate(pivots):
        status_icon = "✅" if p.status == PivotStatus.COMPLETED else "🔄"
        print(f"    中枢{i+1} {status_icon} ZD={p.zd:.2f} ZG={p.zg:.2f} "
              f"DD={p.dd:.2f} GG={p.gg:.2f} [{p.status.value}]")
    
    # Step 5: MACD背驰检测
    print("\n[5/6] MACD背驰检测...")
    closes = [k["close"] for k in klines]
    dif, dea, macd_bar = compute_macd(closes)
    
    divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)
    if divergence:
        icon = "⚠️ 背驰!" if divergence.is_divergent else "✓ 无背驰"
        print(f"  {icon}")
        print(f"    A段面积: {divergence.area_a:.1f}")
        print(f"    C段面积: {divergence.area_c:.1f}")
        print(f"    面积比: {divergence.ratio:.3f} (阈值<0.7)")
    else:
        print("  无法检测（数据不足或无趋势结构）")
    
    # Step 6: 买卖点信号
    print("\n[6/6] 买卖点信号检测...")
    current_price = klines[-1]["close"]
    
    signals = []
    
    # 检测三买
    sig3 = detect_buy3(strokes, pivots, current_price)
    if sig3:
        signals.append(sig3)
    
    # 检测二买
    sig2 = detect_buy2(strokes, pivots, divergence)
    if sig2:
        signals.append(sig2)
    
    # 检测一买
    sig1 = detect_buy1(strokes, pivots, divergence, dif)
    if sig1:
        signals.append(sig1)
    
    if signals:
        for sig in signals:
            print(f"\n  🎯 {sig.type.value.upper()} 信号!")
            print(f"    价格: {sig.price:.2f}")
            print(f"    止损: {sig.stop_loss:.2f}")
            print(f"    目标: {sig.target:.2f}")
            print(f"    推理链:")
            for step in sig.reason_chain:
                print(f"      · {step}")
    else:
        print("  当前无买点信号")
    
    # 输出结构化结果
    result = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "period": f"{klines[0]['dt']} ~ {klines[-1]['dt']}",
        "current_price": current_price,
        "kline_count": len(klines),
        "fractals_count": len(fractals),
        "strokes_count": len(strokes),
        "pivots_count": len(pivots),
        "pivots": [
            {"zd": p.zd, "zg": p.zg, "dd": p.dd, "gg": p.gg, "status": p.status.value}
            for p in pivots
        ],
        "divergence": {
            "detected": divergence is not None,
            "is_divergent": divergence.is_divergent if divergence else False,
            "ratio": divergence.ratio if divergence else None
        },
        "signals": [
            {"type": s.type.value, "price": s.price, "stop_loss": s.stop_loss,
             "target": s.target, "reason": s.reason_chain}
            for s in signals
        ]
    }
    
    print(f"\n{'─'*60}")
    print("结构化输出:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return result


if __name__ == "__main__":
    # 测试标的
    test_stocks = [
        ("600519", "贵州茅台"),
        ("000858", "五粮液"),
        ("601318", "中国平安"),
    ]
    
    results = []
    for code, name in test_stocks:
        try:
            r = run_full_analysis(code, name)
            results.append(r)
        except Exception as e:
            print(f"\n❌ {code} {name} 分析失败: {e}")
    
    print(f"\n\n{'='*60}")
    print(f"  分析完成: {len(results)}/{len(test_stocks)} 只股票")
    print(f"{'='*60}")
