from chanlun.engine.segment_adapter import MAX_ZS_SEGS, segment_pivots
from chanlun.engine.types import Direction, Segment


def _seg(direction, start, end, idx):
    return Segment(
        direction=direction,
        start_idx=idx,
        end_idx=idx + 1,
        start_value=start,
        end_value=end,
    )


def test_segment_pivots_close_and_restart_after_departure():
    up, down = Direction.UP, Direction.DOWN
    segments = [
        _seg(up, 8, 12, 0),
        _seg(down, 13, 9, 1),
        _seg(up, 10, 14, 2),
        _seg(down, 8, 5, 3),
        _seg(up, 5, 9, 4),
        _seg(down, 10, 6, 5),
    ]

    pivots = segment_pivots(segments)

    assert len(pivots) == 2
    assert pivots[0]["zg"] == 12
    assert pivots[0]["zd"] == 10
    assert pivots[0]["seg_count"] == 3
    assert pivots[1]["zg"] == 8
    assert pivots[1]["zd"] == 6
    assert pivots[1]["seg_count"] == 3


def test_segment_pivot_extension_keeps_seed_zone_and_caps_at_nine():
    up, down = Direction.UP, Direction.DOWN
    segments = [
        _seg(up if i % 2 == 0 else down, 8, 12, i)
        for i in range(MAX_ZS_SEGS + 2)
    ]

    pivots = segment_pivots(segments)

    assert pivots[0]["zg"] == 12
    assert pivots[0]["zd"] == 8
    assert pivots[0]["seg_count"] == MAX_ZS_SEGS
