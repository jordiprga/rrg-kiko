"""Causal signal detection and end-of-day, next-open event simulation."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from bisect import bisect_right
from datetime import timedelta
import math
from typing import Iterable

import numpy as np
import pandas as pd

from scripts.strategy_data import Bar, Delisting, digest

EPS = 1e-6
ENTRY_NAMES = {
    "turn-up": "Giro hacia arriba en Rezagado", "turn-right": "Giro hacia la derecha en Rezagado",
    "lagging-improving": "Rezagado → Mejorando", "improving-leading": "Mejorando → Líder",
}


def quadrant(x: float, y: float) -> str:
    if abs(x - 100) < EPS or abs(y - 100) < EPS:
        return "neutral"
    return ("leading" if y > 100 else "weakening") if x > 100 else ("improving" if y > 100 else "lagging")


@dataclass(frozen=True)
class Signal:
    id: str
    security_id: str
    reference: str
    timeframe: str
    rule: str
    confirmation: int
    origin_date: str
    date: str
    available_at: str
    x: float
    y: float
    sector: str | None = None
    sector_strong: bool | None = None
    relative_volume: float | None = None
    x_percentile: float | None = None
    y_percentile: float | None = None
    volume_percentile: float | None = None
    zone: tuple[int, int] | None = None
    percentile_count: int = 0


def detect(rows: list[list], calendar: list[str], security_id: str, reference: str,
           tf: str, confirmation: int = 1, availability: dict[str, str] | None = None) -> list[Signal]:
    if confirmation not in (1, 2):
        raise ValueError("Confirmación no soportada")
    positions = {d: i for i, d in enumerate(calendar)}
    result = []
    last_q = None
    pending: list[tuple[str, str]] = []
    for i, row in enumerate(rows):
        day, x, y = row[:3]
        if day not in positions or not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("Observación fuera del calendario o no finita")
        q = quadrant(x, y)
        adjacent = i > 0 and positions[day] == positions[rows[i - 1][0]] + 1
        if not adjacent:
            last_q = None
            pending = []
        dx = x - rows[i - 1][1] if adjacent else 0
        dy = y - rows[i - 1][2] if adjacent else 0
        def emit(rule, origin):
            identity = digest([security_id, reference, tf, rule, confirmation, origin, day])[:24]
            result.append(Signal(identity, security_id, reference, tf, rule, confirmation, origin, day,
                                 (availability or {}).get(day, day + "T23:59:59Z"), x, y))
        for rule, origin in pending:
            persists = {"turn-up": q == "lagging" and dy > EPS,
                        "turn-right": q == "lagging" and dx > EPS,
                        "lagging-improving": q == "improving",
                        "improving-leading": q == "leading"}[rule]
            if adjacent and persists:
                emit(rule, origin)
        pending = []
        rules = []
        if adjacent and last_q == "lagging" and q == "improving":
            rules.append("lagging-improving")
        if adjacent and last_q == "improving" and q == "leading":
            rules.append("improving-leading")
        if adjacent and i >= 2 and positions[rows[i - 1][0]] == positions[rows[i - 2][0]] + 1:
            if q == quadrant(*rows[i - 1][1:3]) == "lagging":
                if rows[i - 1][2] - rows[i - 2][2] <= EPS and dy > EPS:
                    rules.append("turn-up")
                if rows[i - 1][1] - rows[i - 2][1] <= EPS and dx > EPS:
                    rules.append("turn-right")
        for rule in rules:
            if confirmation == 1:
                emit(rule, day)
            else:
                pending.append((rule, day))
        if q != "neutral":
            last_q = q
    return result


def research_points(asset: list[Bar], benchmark: list[Bar], calendar: list[str], tf: str) -> list[list]:
    # Reindex BEFORE rolling: absent sessions are not compressed into adjacent periods.
    a = pd.Series({b.date: b.adjusted_close for b in asset}).reindex(calendar)
    b = pd.Series({b.date: b.adjusted_close for b in benchmark}).reindex(calendar)
    rs = a / b
    if tf == "weekly":
        x = 100 * rs.rolling(10).mean() / rs.rolling(30).mean()
        y = 100 * x / x.rolling(9).mean()
        frame = pd.DataFrame(dict(x=x, y=y, price=a)).iloc[50:]
    elif tf == "daily":
        # Restart the EMA after every gap, including warmup, rather than filling it.
        valid = rs.notna()
        segments = (~valid).cumsum()
        parts = []
        for _, group in rs[valid].groupby(segments[valid]):
            xx = 100 * group / group.ewm(span=50, adjust=False).mean()
            yy = 100 * xx / xx.ewm(span=20, adjust=False).mean()
            parts.append(pd.DataFrame(dict(x=xx, y=yy, price=a.loc[group.index])).iloc[250:])
        frame = pd.concat(parts) if parts else pd.DataFrame(columns=["x", "y", "price"])
    else:
        raise ValueError("Periodicidad inválida")
    return [[day, float(r.x), float(r.y), float(r.price)] for day, r in frame.dropna().iterrows()]


def relative_volumes(bars: list[Bar], calendar: list[str], tf: str) -> dict[str, float | None]:
    # Normalize historical shares only for splits, never for dividends.
    volumes = {}
    future_splits = 1.0
    for b in reversed(bars):
        volumes[b.date] = (b.volume * future_splits if b.volume_basis == 'raw' else b.volume
                          if b.volume_basis == 'split-adjusted' else float('nan')) if b.volume is not None else float("nan")
        future_splits *= b.split
    s = pd.Series(volumes).sort_index()
    if tf == "weekly":
        periods = pd.to_datetime(s.index).to_period("W-FRI")
        # Any missing volume makes the whole week's volume unavailable.
        s = s.groupby(periods).agg(lambda v: v.mean() if v.notna().all() else float("nan"))
        week_ends = {pd.Timestamp(d).to_period('W-FRI'): d for d in calendar}
        s.index = [week_ends.get(p, str(p.end_time.date())) for p in s.index]
        s = s.reindex(calendar)
        baseline = s.shift(1).rolling(10).mean()
    else:
        s = s.reindex(calendar)
        baseline = s.shift(1).rolling(20).mean()
    ratios = s / baseline.where(baseline > 0)
    return {d: float(v) if pd.notna(v) and math.isfinite(v) else None for d, v in ratios.items()}


def cross_section(rows: list[dict]) -> list[dict]:
    """Input must be one date/reference pool; sector-relative pools stay separate."""
    if not rows:
        return []
    if len({(r["date"], r["reference"]) for r in rows}) != 1:
        raise ValueError("Percentiles requieren la misma fecha y benchmark")
    out = [dict(r) for r in rows]
    for key in ["x", "y", "relativeVolume"]:
        s = pd.Series([r.get(key) for r in rows], dtype=float)
        n = s.count()
        ranks = (s.rank(method="average") - 1) / (n - 1) * 100 if n > 1 else s * 0 + 50
        for r, value in zip(out, ranks):
            r[key + "Percentile"] = float(value) if pd.notna(value) else None
    for r in out:
        r["zone"] = [min(2, int(r[k] / (100 / 3))) for k in ["xPercentile", "yPercentile"]]
    return out


def atr_values(bars: list[Bar], period: int = 22) -> dict[str, float]:
    result = {}
    ranges = []
    previous = None
    value = None
    for b in bars:
        high, low, close = b.high * b.factor, b.low * b.factor, b.adjusted_close
        tr = high - low if previous is None else max(high - low, abs(high - previous), abs(low - previous))
        ranges.append(tr)
        if len(ranges) == period:
            value = float(np.mean(ranges))
        elif value is not None:
            value = (value * (period - 1) + tr) / period
        if value is not None:
            result[b.date] = value
        previous = close
    return result


def exit_candidates() -> list[str]:
    trails = ["pct-10", "pct-15", "pct-20", "atr-2", "atr-3", "atr-4"]
    return ["orbit", *trails, *[s + "+orbit" for s in trails], "time-13", "time-26"]


def simulate(signal: Signal, bars: list[Bar], points: list[list], exit_rule: str,
             cost_bps: float = 10, horizon_weeks: int | None = None,
             expected_sessions: list[str] | None = None, delisting: Delisting | None = None,
             open_times: dict[str, str] | None = None, as_of: str | None = None,
             point_calendar: list[str] | None = None, prepared_atr: dict[str, float] | None = None) -> dict:
    if exit_rule not in exit_candidates() and exit_rule != "fixed":
        raise ValueError("Salida no registrada")
    if not 0 <= cost_bps < 10000:
        raise ValueError("Costes inválidos")
    available = pd.Timestamp(signal.available_at)
    usable = [b for b in bars if as_of is None or b.date <= as_of]
    first_entry = bisect_right([b.date for b in usable], signal.date)
    while first_entry < len(usable) and open_times is not None and pd.Timestamp(open_times[usable[first_entry].date]) < available:
        first_entry += 1
    trade = dict(version=1, signalId=signal.id, securityId=signal.security_id, rule=signal.rule,
                 signalDate=signal.date, availableAt=signal.available_at, exitRule=exit_rule,
                 costBps=cost_bps, status="pending", netReturn=None, entryDate=None, exitDate=None,
                 entryPrice=None, exitPrice=None, mfe=None, mae=None, durationDays=None, reason=None)
    if first_entry >= len(usable):
        return trade
    i = first_entry
    entry = usable[i]
    if expected_sessions:
        expected = [d for d in expected_sessions if signal.date < d <= entry.date
                    and (open_times is None or pd.Timestamp(open_times[d]) >= available)]
        if expected and expected[0] != entry.date:
            return {**trade, "status": "missing-data", "reason": "missing-entry-session"}
    entry_price = entry.adjusted_open
    trade.update(entryDate=entry.date, entryPrice=entry_price, status="open")
    weeks = horizon_weeks if horizon_weeks is not None else int(exit_rule.split("-")[1]) if exit_rule.startswith("time-") else 52
    due = (pd.Timestamp(entry.date) + pd.Timedelta(weeks=min(52, weeks))).date().isoformat()
    orbit_dates = set()
    last_q = None
    last_day = None
    period_positions = {day: n for n, day in enumerate(point_calendar or (expected_sessions if signal.timeframe == "daily" else []) or [])}
    for p in points:
        q = quadrant(*p[1:3])
        continuous = last_day is not None and (period_positions.get(p[0], -2) == period_positions.get(last_day, -4) + 1 if period_positions
                       else (pd.Timestamp(p[0]) - pd.Timestamp(last_day)).days <= (10 if signal.timeframe == "weekly" else 4))
        if not continuous:
            last_q = None
        if continuous and last_q == "leading" and q == "weakening":
            orbit_dates.add(p[0])
        if q != "neutral":
            last_q = q
        last_day = p[0]
    atr = prepared_atr if prepared_atr is not None else atr_values(usable)
    base_rule = exit_rule.split("+")[0]
    if base_rule.startswith("atr-") and entry.date not in atr:
        return {**trade, "status": "missing-data", "reason": "atr-warmup"}
    peak, stop = entry_price, -math.inf
    high_water, low_water = entry_price, entry_price
    bar_dates = {b.date for b in usable}
    missing = set(expected_sessions or []) - bar_dates
    def finish(day: str, price: float, reason: str) -> dict:
        c = cost_bps / 10000
        return {**trade, "status": "closed", "exitDate": day, "exitPrice": price,
                "reason": reason, "netReturn": price * (1 - c) / (entry_price * (1 + c)) - 1,
                "mfe": high_water / entry_price - 1, "mae": low_water / entry_price - 1,
                "durationDays": (pd.Timestamp(day) - pd.Timestamp(entry.date)).days}
    for j in range(i, len(usable)):
        b = usable[j]
        if any(entry.date <= d <= b.date for d in missing):
            return {**trade, "status": "missing-data", "reason": "missing-holding-session"}
        peak = max(peak, b.adjusted_close)
        high_water = max(high_water, b.high * b.factor)
        low_water = min(low_water, b.low * b.factor)
        triggered = None
        if base_rule.startswith("pct-"):
            stop = max(stop, peak * (1 - int(base_rule.split("-")[1]) / 100))
        if base_rule.startswith("atr-") and b.date in atr:
            stop = max(stop, peak - int(base_rule.split("-")[1]) * atr[b.date])
        if b.adjusted_close <= stop:
            triggered = base_rule
        if (exit_rule == "orbit" or "+orbit" in exit_rule) and b.date in orbit_dates:
            triggered = triggered or "orbit"
        if b.date >= due:
            triggered = triggered or ("horizon" if exit_rule == "fixed" else "time-limit")
        if triggered:
            if j + 1 < len(usable):
                nxt = usable[j + 1]
                if any(b.date < d <= nxt.date for d in missing):
                    return {**trade, "status": "missing-data", "reason": "missing-exit-session"}
                # High/low of the exit day are NOT observable before an open fill.
                high_water = max(high_water, nxt.adjusted_open)
                low_water = min(low_water, nxt.adjusted_open)
                return finish(nxt.date, nxt.adjusted_open, triggered)
            return {**trade, "reason": "awaiting-next-open"}
        if delisting and b.date == delisting.last_trading_date:
            if as_of is None or delisting.settlement_date <= as_of:
                price = delisting.settlement_price * b.factor
                high_water, low_water = max(high_water, price), min(low_water, price)
                return finish(delisting.settlement_date, price, "delisting-settlement")
    if expected_sessions and usable and any(entry.date <= d <= (as_of or usable[-1].date) and d not in bar_dates for d in expected_sessions):
        return {**trade, "status": "missing-data", "reason": "missing-tail-sessions"}
    return {**trade, "reason": "right-censored"}


def suppress_overlaps(trades: Iterable[dict]) -> list[dict]:
    busy: dict[str, str] = {}
    result = []
    for t in sorted(trades, key=lambda t: (t["signalDate"], t["signalId"])):
        identity = t["securityId"]
        if t["signalDate"] <= busy.get(identity, ""):
            result.append({**t, "status": "suppressed", "netReturn": None, "reason": "position-already-open"})
        else:
            result.append(t)
            if t["entryDate"] and t["status"] != "suppressed":
                busy[identity] = t["exitDate"] or "9999-12-31"
    return result
