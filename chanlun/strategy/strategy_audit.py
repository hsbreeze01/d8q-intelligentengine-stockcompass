# -*- coding: utf-8 -*-
"""Read-only strategy audit and shadow metrics for chanlun signals.

This module deliberately does not participate in scanning, scoring, or order
selection.  It turns review_weekly-compatible details into deterministic JSON
and Markdown, including day-clustered coverage, horizon-matched effective RR,
and market-wide sell breadth.
"""
from __future__ import print_function

import argparse
import json
import math
import os
from collections import defaultdict
from datetime import date, timedelta

WINDOWS = (5, 10, 20)
PERCENTILES = (50, 70, 80)


def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _avg(values, digits=3):
    values = [float(v) for v in values if v is not None]
    return round(sum(values) / len(values), digits) if values else None


def _percentile(values, percentile):
    """Deterministic linear percentile compatible with small fixture sets."""
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 4)
    pos = (len(values) - 1) * float(percentile) / 100.0
    low, high = int(math.floor(pos)), int(math.ceil(pos))
    value = values[low] + (values[high] - values[low]) * (pos - low)
    return round(value, 4)


def score_bucket(score):
    score = _num(score)
    if score is None:
        return "unavailable"
    if score >= 85:
        return "85+"
    if score >= 75:
        return "75-84"
    if score >= 60:
        return "60-74"
    return "<60"


def daily_sell_breadth(signals, block_threshold=0.5):
    """Return one deterministic breadth record per signal_date.

    ``would_block_long`` is shadow-only. Equality to the threshold does not
    block; the pre-registered rule is strictly sell_share > 0.50.
    """
    by_day = defaultdict(lambda: {"buy": 0, "sell": 0, "other": 0})
    for signal in signals:
        day = str(signal.get("signal_date") or "")[:10]
        if not day:
            continue
        signal_type = str(signal.get("type") or "").lower()
        side = "buy" if signal_type.startswith("buy") else (
            "sell" if signal_type.startswith("sell") else "other")
        by_day[day][side] += 1
    rows = []
    for day in sorted(by_day):
        counts = by_day[day]
        directional = counts["buy"] + counts["sell"]
        sell_share = (float(counts["sell"]) / directional) if directional else None
        net = ((counts["buy"] - counts["sell"]) / float(directional)
               if directional else None)
        rows.append({
            "signal_date": day,
            "buy_count": counts["buy"],
            "sell_count": counts["sell"],
            "other_count": counts["other"],
            "directional_count": directional,
            "sell_share": round(sell_share, 4) if sell_share is not None else None,
            "net_breadth": round(net, 4) if net is not None else None,
            "would_block_long": bool(sell_share is not None and sell_share > block_threshold),
            "shadow_only": True,
        })
    return rows


def _window_row(detail, window):
    row = (detail.get("windows") or {}).get(str(window)) or {}
    return row if row.get("window_complete") else None


def summarize_rows(details, window):
    """Aggregate a group with buy/sell direction normalized to positive=good."""
    mature = []
    for detail in details:
        row = _window_row(detail, window)
        if row is not None:
            mature.append((detail, row))
    if not mature:
        return {"count": len(details), "mature_count": 0,
                "signal_days": len({str(d.get("signal_date"))[:10] for d in details
                                    if d.get("signal_date")}),
                "win_rate": None, "avg_direction_pnl_pct": None,
                "avg_mfe_pct": None, "avg_mae_pct": None,
                "expectancy_r": None}
    direction_pnl = []
    for detail, row in mature:
        pnl = _num(row.get("pnl_pct"))
        if pnl is not None:
            direction_pnl.append(pnl if str(detail.get("type", "")).startswith("buy") else -pnl)
    return {
        "count": len(details),
        "mature_count": len(mature),
        "signal_days": len({str(d.get("signal_date"))[:10] for d, _ in mature}),
        "win_rate": round(sum(1 for _, r in mature if r.get("win")) / float(len(mature)), 4),
        "avg_direction_pnl_pct": _avg(direction_pnl),
        "avg_mfe_pct": _avg([_num(r.get("mfe_pct")) for _, r in mature]),
        "avg_mae_pct": _avg([_num(r.get("mae_pct")) for _, r in mature]),
        "expectancy_r": _avg([_num(r.get("r_realized", r.get("r_raw")))
                               for _, r in mature]),
    }


def grouped_window_stats(details):
    dimensions = {
        "type": lambda d: str(d.get("type") or "unavailable"),
        "score_bucket": lambda d: score_bucket(d.get("score")),
        "target_type": lambda d: str(d.get("target_type") or "unavailable"),
    }
    result = {}
    for dimension, keyfn in dimensions.items():
        groups = defaultdict(list)
        for detail in details:
            groups[keyfn(detail)].append(detail)
        result[dimension] = {
            key: {str(window): summarize_rows(groups[key], window) for window in WINDOWS}
            for key in sorted(groups)
        }
    return result


def build_mfe_reference(details):
    """Build horizon/type/target_type MFE percentiles from mature buy rows."""
    values = defaultdict(list)
    for detail in details:
        if not str(detail.get("type") or "").startswith("buy"):
            continue
        group = (str(detail.get("type") or "unavailable"),
                 str(detail.get("target_type") or "unavailable"))
        for window in WINDOWS:
            row = _window_row(detail, window)
            mfe = _num(row.get("mfe_pct")) if row else None
            if mfe is not None:
                values[(group[0], group[1], window)].append(max(0.0, mfe))
    references = {}
    for (signal_type, target_type, window), samples in sorted(values.items()):
        key = "%s|%s|%s" % (signal_type, target_type, window)
        references[key] = {
            "sample_count": len(samples),
            "mfe_pct": {"p%s" % p: _percentile(samples, p) for p in PERCENTILES},
        }
    return references


def effective_rr_shadow(detail, references):
    """Calculate horizon-matched RR without changing production risk_reward."""
    entry = _num(detail.get("entry_price"))
    stop = _num(detail.get("stop_loss"))
    target = _num(detail.get("target_price"))
    base = {
        "code": detail.get("code"), "signal_date": str(detail.get("signal_date") or "")[:10],
        "type": detail.get("type"), "target_type": detail.get("target_type"),
        "shadow_only": True, "windows": {},
    }
    if entry is None or stop is None or target is None or not (0 < stop < entry < target):
        base["status"] = "unavailable"
        base["reason"] = "invalid_entry_stop_target"
        return base
    risk = entry - stop
    structure_target_pct = (target / entry - 1.0) * 100.0
    base.update({
        "status": "available",
        "structure_rr": round((target - entry) / risk, 4),
        "structure_target_pct": round(structure_target_pct, 4),
    })
    for window in WINDOWS:
        ref_key = "%s|%s|%s" % (
            str(detail.get("type") or "unavailable"),
            str(detail.get("target_type") or "unavailable"), window)
        reference = references.get(ref_key)
        if not reference:
            base["windows"][str(window)] = {
                "status": "unavailable", "reason": "no_mfe_reference"}
            continue
        estimates = {}
        for p in PERCENTILES:
            label = "p%s" % p
            empirical_pct = _num(reference["mfe_pct"].get(label))
            if empirical_pct is None:
                estimates[label] = {"status": "unavailable", "reason": "no_mfe_reference"}
                continue
            effective_pct = min(structure_target_pct, max(0.0, empirical_pct))
            effective_target = entry * (1.0 + effective_pct / 100.0)
            estimates[label] = {
                "status": "available",
                "empirical_mfe_pct": round(empirical_pct, 4),
                "effective_target_pct": round(effective_pct, 4),
                "effective_target_price": round(effective_target, 4),
                "effective_rr": round((effective_target - entry) / risk, 4),
            }
        base["windows"][str(window)] = {
            "status": "available", "sample_count": reference["sample_count"],
            "estimates": estimates,
        }
    return base


def build_audit(signals, details, profile="default", period=None):
    """Build deterministic audit payload from review-compatible inputs."""
    signals = sorted(signals, key=lambda s: (
        str(s.get("signal_date") or ""), str(s.get("code") or ""), str(s.get("type") or "")))
    details = sorted(details, key=lambda d: (
        str(d.get("signal_date") or ""), str(d.get("code") or ""), str(d.get("type") or "")))
    signal_days = sorted({str(s.get("signal_date"))[:10] for s in signals
                          if s.get("signal_date")})
    mature = {str(w): sum(1 for d in details if _window_row(d, w)) for w in WINDOWS}
    references = build_mfe_reference(details)
    rr = [effective_rr_shadow(d, references) for d in details
          if str(d.get("type") or "").startswith("buy")]
    return {
        "schema_version": 1,
        "shadow_only": True,
        "profile": profile,
        "period": period,
        "coverage": {
            "signal_count": len(signals),
            "detail_count": len(details),
            "signal_day_count": len(signal_days),
            "min_signal_date": signal_days[0] if signal_days else None,
            "max_signal_date": signal_days[-1] if signal_days else None,
            "mature_by_window": mature,
        },
        "daily_sell_breadth": daily_sell_breadth(signals),
        "grouped_window_stats": grouped_window_stats(details),
        "mfe_reference": references,
        "effective_rr_shadow": rr,
    }


def render_json(audit):
    return json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_markdown(audit):
    coverage = audit["coverage"]
    lines = [
        "# Chanlun strategy audit (shadow-only)", "",
        "> profile=%s | period=%s | no trading decision is changed" %
        (audit.get("profile"), audit.get("period") or "unavailable"), "",
        "## Coverage", "",
        "- signals: %s; details: %s; independent signal days: %s" %
        (coverage["signal_count"], coverage["detail_count"], coverage["signal_day_count"]),
        "- range: %s -> %s" %
        (coverage["min_signal_date"] or "unavailable", coverage["max_signal_date"] or "unavailable"),
        "- mature: " + ", ".join("%sd=%s" % (w, coverage["mature_by_window"][str(w)])
                                  for w in WINDOWS), "", "## Daily sell breadth", "",
        "| date | buy | sell | sell share | net breadth | would block long |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in audit["daily_sell_breadth"]:
        lines.append("| {signal_date} | {buy_count} | {sell_count} | {sell_share} | "
                     "{net_breadth} | {would_block_long} |".format(**row))
    lines += ["", "## Effective RR shadow", "",
              "- rows: %s; unavailable rows remain explicit and never become zero." %
              len(audit["effective_rr_shadow"]), ""]
    return "\n".join(lines) + "\n"


def _load_from_db(since, until, profile):
    """Read production-compatible inputs in a READ ONLY transaction."""
    import pymysql
    from chanlun.strategy.czsc_scan import DB
    from chanlun.strategy.review_weekly import analyze_signal, fetch_post_signal_bars

    conn = pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("START TRANSACTION READ ONLY")
            profile_sql = "(profile=%s OR profile IS NULL)" if profile == "default" else "profile=%s"
            cur.execute("""
                SELECT h.* FROM czsc_signal_history h
                INNER JOIN (
                  SELECT signal_date,code,type,MAX(id) keep_id
                  FROM czsc_signal_history
                  WHERE signal_date BETWEEN %s AND %s AND %s
                  GROUP BY signal_date,code,type
                ) k ON h.id=k.keep_id
                ORDER BY h.signal_date,h.code,h.type
            """ % ("%s", "%s", profile_sql), (since, until, profile))
            signals = cur.fetchall()
        details = []
        for signal in signals:
            bars = fetch_post_signal_bars(conn, signal["code"], signal.get("created_at"), 20)
            detail = analyze_signal(signal, bars)
            if detail:
                for key in ("target_price", "target_type", "stop_loss"):
                    detail[key] = signal.get(key)
                details.append(detail)
        conn.rollback()
        return signals, details
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="read-only chanlun strategy audit")
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", default=date.today().isoformat())
    parser.add_argument("--profile", default="default")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    signals, details = _load_from_db(args.since, args.until, args.profile)
    audit = build_audit(signals, details, args.profile, "%s..%s" % (args.since, args.until))
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "strategy_audit_%s_%s.json" %
                             (args.since, args.until))
    md_path = os.path.join(args.output_dir, "strategy_audit_%s_%s.md" %
                           (args.since, args.until))
    with open(json_path, "w", encoding="utf-8") as handle:
        handle.write(render_json(audit))
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(render_markdown(audit))
    print(json.dumps({"json": json_path, "markdown": md_path,
                      "coverage": audit["coverage"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
