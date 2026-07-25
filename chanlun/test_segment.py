"""线段引擎单元测试 - 构造已知笔序列验证特征序列法"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chanlun.engine.types import Stroke, Direction
from chanlun.engine.segment import build_segments


def mk(direction, sv, ev, i):
    """构造一笔: 第 i 笔占据 [i*4, i*4+4] 的K线索引"""
    return Stroke(
        direction=direction,
        start_fractal=None,
        end_fractal=None,
        start_idx=i * 4,
        end_idx=i * 4 + 4,
        start_value=sv,
        end_value=ev,
        kline_count=5,
    )


def test_up_segment_then_down():
    """向上线段(创新高后特征序列顶分型结束) + 后续向下未确认线段"""
    U, D = Direction.UP, Direction.DOWN
    strokes = [
        mk(U, 10, 12, 0),   # s0
        mk(D, 12, 11, 1),   # s1  特征 high=12
        mk(U, 11, 15, 2),   # s2
        mk(D, 15, 13, 3),   # s3  特征 high=15
        mk(U, 13, 18, 4),   # s4  线段顶 18
        mk(D, 18, 14, 5),   # s5  特征 high=18 (最高)
        mk(U, 14, 16, 6),   # s6  未创新高
        mk(D, 16, 12, 7),   # s7  特征 high=16
        mk(U, 12, 13, 8),   # s8
        mk(D, 13, 9,  9),   # s9  特征 high=13
    ]
    segs = build_segments(strokes)

    assert len(segs) == 2, "应划分出2条线段, 实际 %d" % len(segs)

    s0 = segs[0]
    assert s0.direction == U, "第1线段应向上"
    assert s0.end_value == 18, "第1线段顶应为18, 实际 %s" % s0.end_value
    assert s0.is_confirmed is True, "第1线段应确认(无缺口)"
    assert len(s0.strokes) == 5, "第1线段应含5笔, 实际 %d" % len(s0.strokes)

    s1 = segs[1]
    assert s1.direction == D, "第2线段应向下"
    print("[PASS] test_up_segment_then_down: segs=%d, seg0 top=%s confirmed=%s, seg1 dir=%s" % (
        len(segs), s0.end_value, s0.is_confirmed, s1.direction.value))


def test_too_few_strokes():
    """不足3笔不成段"""
    strokes = [
        mk(Direction.UP, 10, 12, 0),
        mk(Direction.DOWN, 12, 11, 1),
    ]
    assert build_segments(strokes) == []
    print("[PASS] test_too_few_strokes")


def test_monotonic_no_end():
    """持续创新高应作为单条(未确认)线段，不提前结束"""
    U, D = Direction.UP, Direction.DOWN
    strokes = [
        mk(U, 10, 12, 0),
        mk(D, 12, 11, 1),   # high 12
        mk(U, 11, 15, 2),
        mk(D, 15, 14, 3),   # high 15
        mk(U, 14, 18, 4),
        mk(D, 18, 17, 5),   # high 18  (特征序列 12,15,18 单调递增, 无顶分型)
        mk(U, 17, 20, 6),
    ]
    segs = build_segments(strokes)
    assert len(segs) == 1, "单调上涨应为1条线段, 实际 %d" % len(segs)
    assert segs[0].is_confirmed is False, "未出现分型的线段应标记未确认"
    print("[PASS] test_monotonic_no_end: 1条未确认线段")


if __name__ == "__main__":
    test_up_segment_then_down()
    test_too_few_strokes()
    test_monotonic_no_end()
    print("\nALL SEGMENT TESTS PASSED")
