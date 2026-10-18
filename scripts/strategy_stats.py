"""Reference-portfolio accounting, calendar-block uncertainty and walk-forward."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from scripts.strategy_data import Bar


def summary(trades: list[dict]) -> dict:
    closed = [t for t in trades if t["status"] == "closed"]
    r = np.array([t["netReturn"] for t in closed], dtype=float)
    return dict(total=len(trades), closed=len(closed), open=sum(t["status"] in ("open", "pending") for t in trades),
                suppressed=sum(t["status"] == "suppressed" for t in trades),
                missing=sum(t["status"] == "missing-data" for t in trades),
                comparisonMissing=sum(t.get('excessMarket') is None or t.get('excessSector') is None or t.get('excessPeers') is None for t in closed),
                mean=float(r.mean()) if len(r) else None, median=float(np.median(r)) if len(r) else None,
                winRate=float((r > 0).mean()) if len(r) else None,
                quantiles=[float(v) for v in np.quantile(r, [.05, .25, .5, .75, .95])] if len(r) else None,
                securities=len({t["securityId"] for t in closed}), dates=len({t["signalDate"] for t in closed}),
                years=len({t["signalDate"][:4] for t in closed}))


def portfolio(trades: list[dict], bars: dict[str, list[Bar]], calendar: list[str], cost_bps: float) -> dict:
    """Value close-to-open holdings, rebalance at open, then mark at close.

    Adjusted OHLC incorporates distributions exactly once. Daily rebalance costs
    are applied to actual absolute weight changes, including drift and liquidation.
    An unresolved holding invalidates the curve; it is never dropped.
    """
    def invalid():
        return dict(status="not-evaluable", returns=[], equity=[], sharpe=None, maxDrawdown=None, turnover=None)
    if any(t["status"] == "missing-data" for t in trades):
        return invalid()
    accepted = [t for t in trades if t["entryDate"] and t["status"] != "suppressed"]
    lookup = {k: {b.date: b for b in v} for k, v in bars.items()}
    def value(identity, day, at_open):
        b = lookup.get(identity, {}).get(day)
        if b:
            return b.adjusted_open if at_open else b.adjusted_close
        settlements = [t for t in accepted if t['securityId'] == identity and t.get('reason') == 'delisting-settlement'
                       and t['exitDate'] is not None and t['exitDate'] <= day]
        return settlements[0]['exitPrice'] if settlements else None
    equity = 1.0
    peak = 1.0
    worst = 0.0
    drifted: dict[str, float] = {}
    previous_closes: dict[str, float] = {}
    returns, curve = [], []
    turnover = 0.0
    for day in calendar:
        overnight = {}
        for s in drifted:
            opening = value(s, day, True)
            if opening is None:
                return invalid()
            overnight[s] = opening / previous_closes[s] - 1
        gross_overnight = sum(drifted[s] * overnight[s] for s in drifted)
        open_weights = {s: drifted[s] * (1 + overnight[s]) / (1 + gross_overnight) for s in drifted} if gross_overnight > -1 else {}
        active = {t["securityId"] for t in accepted if t["entryDate"] <= day and (t["exitDate"] is None or day < t["exitDate"])}
        if equity == 0 or gross_overnight <= -1:
            active = set()
        target = {s: 1 / len(active) for s in active}
        change = sum(abs(target.get(s, 0) - open_weights.get(s, 0)) for s in set(target) | set(open_weights))
        turnover += change
        changes = {}
        for s in active:
            first, second = value(s, day, True), value(s, day, False)
            if first is None or second is None:
                return invalid()
            changes[s] = second / first - 1
            previous_closes[s] = second
        gross = sum(target[s] * changes[s] for s in active)
        net = (1 + gross_overnight) * (1 - change * cost_bps / 10000) * (1 + gross) - 1
        equity *= 1 + net
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
        drifted = {s: target[s] * (1 + changes[s]) / (1 + gross) for s in active}
        returns.append([day, net])
        curve.append([day, equity])
    values = np.array([r[1] for r in returns])
    std = values.std(ddof=1) if len(values) > 1 else 0
    sharpe = float(values.mean() / std * math.sqrt(252)) if std > 1e-12 else None
    return dict(status="ok", returns=returns, equity=curve, sharpe=sharpe, maxDrawdown=worst,
                turnover=turnover, totalReturn=equity - 1, cashRate=0)


def bootstrap(trades: list[dict], field: str, replicates: int = 2000, seed: int = 18002026) -> dict:
    rows = [t for t in trades if t["status"] == "closed" and t.get(field) is not None]
    missing = sum(t['status'] == 'closed' and t.get(field) is None for t in trades)
    if missing:
        return dict(mean=None, interval=None, pValue=None, missing=missing, available=len(rows))
    if len(rows) < 2:
        return dict(mean=None, interval=None, pValue=None)
    frame = pd.DataFrame({"date": pd.to_datetime([r["signalDate"] for r in rows]), "value": [r[field] for r in rows]})
    frame["week"] = frame.date.dt.to_period("W-FRI")
    weeks = pd.period_range(frame.week.min(), frame.week.max(), freq="W-FRI")
    grouped = frame.groupby("week").value.agg(["sum", "count"]).reindex(weeks, fill_value=0).to_numpy()
    # At least two blocks are needed for a meaningful calendar resample.
    if len(weeks) < 104:
        return dict(mean=float(frame.value.mean()), interval=None, pValue=None)
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(replicates):
        starts = rng.integers(0, len(weeks), math.ceil(len(weeks) / 52))
        positions = np.concatenate([(np.arange(52) + start) % len(weeks) for start in starts])[:len(weeks)]
        sums, count = grouped[positions].sum(axis=0)
        if count:
            samples.append(sums / count)
    values = np.array(samples)
    mean = float(frame.value.mean())
    p = (1 + int((np.abs(values - mean) >= abs(mean)).sum())) / (len(values) + 1)
    return dict(mean=mean, interval=[float(v) for v in np.quantile(values, [.025, .975])], pValue=p)


def holm(pvalues: list[float | None]) -> list[float | None]:
    result: list[float | None] = [None] * len(pvalues)
    # Missing primary comparisons remain part of the registered family.
    order = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    previous = 0.0
    for rank, (p, i) in enumerate(order):
        previous = max(previous, min(1.0, p * (len(pvalues) - rank)))
        result[i] = previous
    return result


def choose_exit(scores: list[dict]) -> str | None:
    valid = [s for s in scores if len(s["sharpes"]) == 3 and all(v is not None and math.isfinite(v) for v in s["sharpes"])]
    if not valid:
        return None
    best = max(float(np.median(s["sharpes"])) for s in valid)
    tied = [s for s in valid if best - float(np.median(s["sharpes"])) < .05]
    return min(tied, key=lambda s: (abs(s["maxDrawdown"]), s["turnover"], s["exitRule"]))["exitRule"]


def walk_forward(trades_by_exit: dict[str, list[dict]], bars: dict[str, list[Bar]],
                 calendar: list[str], cost_bps: float) -> dict:
    """Select using only closed, in-boundary trades; record every candidate score.

    Each outer year chooses once using three inner validation calendar years.
    Open positions retain their selected exit on future folds. New entries while
    that security remains held are recorded as suppressed.
    """
    if not calendar:
        return dict(folds=[], trades=[], portfolio=portfolio([], bars, [], cost_bps))
    first, last = int(calendar[0][:4]), int(calendar[-1][:4])
    import exchange_calendars as xcals
    schedule = xcals.get_calendar('XNYS', start=f'{first}-01-01', end=f'{last}-12-31').sessions
    first_session = schedule[0].date().isoformat()
    first_full_year = first if calendar[0] <= first_session else first + 1
    year_ends = {year: next(d.date().isoformat() for d in reversed(schedule) if d.year == year) for year in range(first, last + 1)}
    folds, selected = [], []
    for year in range(first_full_year + 5, last + 1):
        boundary = f"{year}-01-01"
        scores = []
        for rule, candidates in trades_by_exit.items():
            sharpes, drawdowns, turnovers = [], [], []
            for inner in range(year - 3, year):
                start, end = f"{inner}-01-01", f"{inner + 1}-01-01"
                # Purging uses realized entry/exit dates, not just signal dates.
                within = [t for t in candidates if t["status"] == "closed" and start <= t["signalDate"] and t["entryDate"] >= start and t["exitDate"] < end]
                from scripts.strategy_engine import suppress_overlaps
                within = suppress_overlaps(within)
                dates = [d for d in calendar if start <= d < end]
                unresolved = [t for t in candidates if t['status'] == 'missing-data' and start <= t['signalDate'] < end]
                curve = portfolio([*within, *unresolved], bars, dates, cost_bps)
                sharpes.append(curve["sharpe"])
                drawdowns.append(curve["maxDrawdown"] or 0)
                turnovers.append(curve["turnover"] or 0)
            scores.append(dict(exitRule=rule, sharpes=sharpes, maxDrawdown=min(drawdowns), turnover=sum(turnovers)))
        chosen = choose_exit(scores)
        folds.append(dict(testStart=boundary, testEnd=min(f"{year}-12-31", calendar[-1]),
                          trainingStart=f"{year - 5}-01-01", trainingEnd=f"{year - 1}-12-31",
                          complete=calendar[-1] >= year_ends[year],
                          chosenExit=chosen, candidates=scores))
        if chosen:
            # Boundaries do not force a sale: existing trades retain their rule.
            new = [t for t in trades_by_exit[chosen] if boundary <= t["signalDate"] < f"{year + 1}-01-01"]
            selected.extend(new)
    from scripts.strategy_engine import suppress_overlaps
    selected = suppress_overlaps(selected)
    first_test = folds[0]["testStart"] if folds else "9999"
    curve = portfolio(selected, bars, [d for d in calendar if d >= first_test], cost_bps)
    return dict(folds=folds, trades=selected, portfolio=curve)
