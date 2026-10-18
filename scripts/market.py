from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = {"daily": (50, 20), "weekly": (10, 4)}
SMA_METHOD = "relative-sma-10-30-9-v2"


class DataProvider(Protocol):
    def history(self, instrument: dict) -> pd.Series: ...


class YahooProvider:
    """Explicit fields: price indices use Close; ETFs use Adj Close."""

    def history(self, instrument: dict) -> pd.Series:
        field = "Close" if instrument["type"] == "index" else "Adj Close"
        for attempt in range(3):
            try:
                frame = yf.download(
                    instrument["ticker"], period="5y", interval="1d", auto_adjust=False,
                    progress=False, threads=False, timeout=25, multi_level_index=False,
                )
                if frame is None or frame.empty or field not in frame:
                    raise ValueError(f"Sin histórico {field}")
                return clean_series(frame[field])
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Descarga no completada")


def clean_series(series: pd.Series) -> pd.Series:
    series = series.copy()
    series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    series = pd.to_numeric(series, errors="coerce")
    return series[series.notna() & (series > 0) & series.map(math.isfinite)]


def schedule_for(now: pd.Timestamp) -> pd.DataFrame:
    start = (now - pd.DateOffset(years=6)).date().isoformat()
    end = (now + pd.Timedelta(days=14)).date().isoformat()
    return xcals.get_calendar("XNYS", start=start, end=end).schedule


def closed_schedule(schedule: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    # Leave time for an EOD provider to finalize the session.
    return schedule.loc[schedule["close"] + pd.Timedelta(minutes=90) <= now]


def completed_week_ends(schedule: pd.DataFrame, now: pd.Timestamp) -> pd.DatetimeIndex:
    # Group the full calendar, including future days this week, before filtering.
    frame = schedule.copy()
    frame["week"] = pd.DatetimeIndex(frame.index).to_period("W-FRI")
    ends = frame.groupby("week", sort=True).tail(1)
    ends = closed_schedule(ends, now)
    return pd.DatetimeIndex(ends.index).tz_localize(None).normalize()


def indicators(asset: pd.Series, benchmark: pd.Series, n: int, m: int) -> pd.DataFrame:
    pair = pd.concat([asset.rename("price"), benchmark.rename("benchmark")], axis=1).dropna()
    pair = pair[(pair["price"] > 0) & (pair["benchmark"] > 0)]
    rs = pair["price"] / pair["benchmark"]
    x = 100 * rs / rs.ewm(span=n, adjust=False).mean()
    y = 100 * x / x.ewm(span=m, adjust=False).mean()
    # Five slow EMA spans make initial seed effects negligible for this V1.
    return pd.DataFrame({"x": x, "y": y, "price": pair["price"]}).iloc[5 * n:]


def sma_indicators(asset: pd.Series, benchmark: pd.Series) -> pd.DataFrame:
    """Empirically validated weekly approximation; no claim of original JdK code."""
    pair = pd.concat([asset.rename("price"), benchmark.rename("benchmark")], axis=1).dropna()
    pair = pair[(pair.price > 0) & (pair.benchmark > 0)]
    rs = pair.price / pair.benchmark
    x = 100 * rs.rolling(10).mean() / rs.rolling(30).mean()
    y = 100 * x / x.rolling(9).mean()
    # Keep the same first available date as the former weekly engine.
    # The SMA itself has finite memory: 38 common weekly observations suffice.
    return pd.DataFrame({"x": x, "y": y, "price": pair.price}).iloc[50:]


def make_view(prices: dict[str, pd.Series], ids: list[str], benchmark: str,
              timeframe: str, schedule: pd.DataFrame, now: pd.Timestamp) -> dict:
    n, m = PARAMETERS[timeframe]
    use_sma = timeframe == "weekly" and benchmark == "GSPC"
    sessions = pd.DatetimeIndex(closed_schedule(schedule, now).index).tz_localize(None)
    if timeframe == "weekly":
        sessions = completed_week_ends(schedule, now)
    reference = prices[benchmark].loc[prices[benchmark].index.isin(sessions)]
    assets = {}
    for identity in ids:
        if identity not in prices:
            continue
        series = prices[identity].loc[prices[identity].index.isin(sessions)]
        computed = sma_indicators(series, reference) if use_sma else indicators(series, reference, n, m)
        if len(computed) < 31:
            raise ValueError(f"Histórico insuficiente: {identity}/{timeframe}")
        assets[identity] = [
            [day.date().isoformat(), round(float(row.x), 6), round(float(row.y), 6), round(float(row.price), 6)]
            for day, row in computed.iterrows()
        ]
    if not assets:
        raise ValueError(f"Sin activos para {benchmark}/{timeframe}")
    first = min(values[0][0] for values in assets.values())
    return {
        "method": SMA_METHOD if use_sma else "relative-ema-v1", "calculationVersion": 2 if use_sma else 1,
        "parameters": {"short": 10, "long": 30, "m": 9} if use_sma else {"n": n, "m": m},
        "benchmark": [[day.date().isoformat(), round(float(price), 6)]
                      for day, price in reference.items() if day.date().isoformat() >= first],
        "assets": assets,
    }


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def refresh(provider: DataProvider, output: Path, now: pd.Timestamp, offline: bool = False) -> dict:
    config = json.loads((ROOT / "config/catalog.json").read_text(encoding="utf-8"))
    cache = ROOT / ".cache/prices"
    cache.mkdir(parents=True, exist_ok=True)
    schedule = schedule_for(now)
    expected = closed_schedule(schedule, now).index[-1].date().isoformat()
    prices, errors = {}, {}
    for instrument in config["instruments"]:
        identity = instrument["id"]
        file = cache / f"{identity}.csv"
        try:
            if offline:
                series = pd.read_csv(file, index_col=0, parse_dates=True).iloc[:, 0]
                series = clean_series(series)
            else:
                series = provider.history(instrument)
            if len(series) < 800:
                raise ValueError("Menos de 800 sesiones válidas")
            if series.index[-1].date().isoformat() < expected:
                raise ValueError(f"Última sesión {series.index[-1].date()}, esperada {expected}")
            prices[identity] = series
            if not offline:
                series.to_csv(file, header=["price"])
            print(f"OK {identity}: {len(series)} sesiones, {series.index[-1].date()}", flush=True)
        except Exception as error:
            errors[identity] = str(error)
            print(f"ERROR {identity}: {error}", flush=True)
    # A previous valid snapshot is never replaced by a partial refresh.
    if errors and output.exists():
        raise ValueError(f"Actualización parcial; se conserva el dataset anterior: {errors}")
    views, groups = {}, {}
    for group, settings in config["groups"].items():
        benchmarks = [b for b in settings["benchmarks"] if b in prices]
        ids = [i["id"] for i in config["instruments"] if i["group"] == group and i["id"] in prices]
        defaults = [i for i in settings["defaults"] if i in prices]
        if not benchmarks or len(defaults) < 4:
            continue
        groups[group] = {**settings, "benchmarks": benchmarks, "defaults": defaults,
                         "defaultBenchmark": settings["defaultBenchmark"] if settings["defaultBenchmark"] in benchmarks else benchmarks[0]}
        for benchmark in benchmarks:
            views[benchmark] = {tf: make_view(prices, ids, benchmark, tf, schedule, now) for tf in PARAMETERS}
    if not groups:
        raise ValueError("No hay un conjunto válido con referencia y al menos cuatro activos")
    dataset = {
        "version": 1,
        "generatedAt": now.isoformat(), "source": "Yahoo Finance · yfinance",
        "sourceUrl": "https://finance.yahoo.com/", "latestSession": expected,
        "expectedWeeklySession": completed_week_ends(schedule, now)[-1].date().isoformat(),
        "priceConvention": "Índices: cierre de precio. ETFs: cierre ajustado por dividendos y splits. No mezclar familias.",
        "method": "relative-models-v2", "usage": "personal-research",
        "catalog": [i for i in config["instruments"] if i["id"] in prices and i["group"] in groups],
        "groups": groups, "views": views, "errors": errors,
    }
    atomic_json(output, dataset)
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/market.json")
    parser.add_argument("--offline", action="store_true", help="Recalcular desde caché, sin red")
    args = parser.parse_args()
    now = pd.Timestamp.now(tz="UTC")
    status_path = args.output.parent / "refresh-status.json"
    try:
        result = refresh(YahooProvider(), args.output, now, args.offline)
        atomic_json(status_path, {"ok": True, "attemptedAt": now.isoformat(), "errors": result["errors"]})
        print(f"Dataset listo: {args.output} ({args.output.stat().st_size:,} bytes)")
    except Exception as error:
        atomic_json(status_path, {"ok": False, "attemptedAt": now.isoformat(), "message": str(error)})
        raise


if __name__ == "__main__":
    main()
