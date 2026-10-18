"""Acquire free candidate evidence. Never certify tickers as stable identities."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import urllib.request
import re

import pandas as pd
import yfinance as yf

from scripts.market import ROOT, atomic_json
from scripts.strategy_data import digest

URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"


def inspect_candidates(content: bytes) -> dict:
    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    if not rows or not {"ticker", "start_date", "end_date"} <= set(rows[0]):
        raise ValueError("El formato de la fuente de componentes ha cambiado")
    for row in rows:
        if not row["ticker"]:
            raise ValueError("Ticker vacío en la fuente candidata")
        for key in ["start_date", "end_date"]:
            if row[key]:
                datetime.strptime(row[key], "%Y-%m-%d")
    relevant = [r for r in rows if not r["end_date"] or r["end_date"] >= "2010-01-01"]
    return dict(version=1, status="candidate-only", intervalRows=len(rows),
                tickersSince2010=len({r["ticker"] for r in relevant}),
                closedIntervalsSince2010=sum(bool(r["end_date"]) for r in relevant),
                latestChange=max(max(r["start_date"], r["end_date"]) for r in rows),
                stableIdentitiesVerified=False, primaryEvidenceVerified=False,
                historicalSectorsVerified=False, delistingPricesVerified=False,
                limitation="Un fin de intervalo puede ser exclusión o cambio de ticker; no equivale a baja bursátil ni autoriza vender al último cierre.")


def acquire(folder: Path) -> dict:
    request = urllib.request.Request(URL, headers={"User-Agent": "Orbita-research/1.0 (free data coverage audit)"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read(4_000_001)
    if len(content) > 4_000_000:
        raise ValueError("La fuente candidata excede el tamaño esperado")
    result = inspect_candidates(content)
    content_hash = sha256(content).hexdigest()
    result.update(url=URL, contentHash=content_hash, retrievedAt=datetime.now(timezone.utc).isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / (content_hash + ".csv")
    if not snapshot.exists():
        snapshot.write_bytes(content)
    atomic_json(folder / "candidate-coverage.json", result)
    return result


def acquire_prices(ticker: str, folder: Path, start: str = '2009-01-01') -> dict:
    """Download an UNVERIFIED candidate with raw OHLCV and corporate actions.

    Historical EOD availability is a calendar assumption, not vendor evidence of
    original publication. Neither a successful download nor a ticker is proof of
    stable security identity, delisting coverage, or redistribution rights.
    """
    if not re.fullmatch(r'[A-Z0-9.^-]{1,24}', ticker):
        raise ValueError('Ticker inválido')
    now = pd.Timestamp.now(tz='UTC')
    import exchange_calendars as xcals
    from scripts.market import closed_schedule
    schedule = xcals.get_calendar('XNYS', start=start, end=now.date().isoformat()).schedule
    closed = closed_schedule(schedule, now)
    frame = yf.download(ticker, start=start, end=(now + pd.Timedelta(days=1)).date().isoformat(),
        interval='1d', auto_adjust=False, actions=True, progress=False, threads=False,
        timeout=20, multi_level_index=False)
    required = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    if frame is None or frame.empty or any(k not in frame for k in required):
        raise ValueError('El proveedor no entregó OHLCV ajustado; no acredita ausencia del valor')
    closes = {day.date().isoformat(): (row['close'] + pd.Timedelta(minutes=90)).isoformat() for day, row in closed.iterrows()}
    rows = []
    for day, row in frame.iterrows():
        stamp = day.date().isoformat()
        if stamp not in closes or any(pd.isna(row[k]) for k in required[:-1]):
            continue
        rows.append(dict(date=stamp, open=float(row['Open']), high=float(row['High']), low=float(row['Low']),
            close=float(row['Close']), adjusted_close=float(row['Adj Close']),
            volume=float(row['Volume']) if pd.notna(row['Volume']) else None,
            volume_basis='split-adjusted',
            dividend=float(row.get('Dividends', 0)), split=float(row.get('Stock Splits', 0)) or 1,
            available_at=closes[stamp], source_id='yahoo-candidate'))
    if not rows:
        raise ValueError('Sin sesiones cerradas válidas')
    h = digest(rows)
    payload = dict(version=1, ticker=ticker, status='candidate-only', bars=rows,
        retrievedAt=now.isoformat(), contentHash=h,
        availabilityBasis='Supuesto de calendario: cierre XNYS + 90 minutos; sin archivo de publicación original del proveedor.',
        source=dict(id='yahoo-candidate', url='https://finance.yahoo.com/', retrieved_at=now.isoformat(),
                    content_hash=h, publication_allowed=False, verified=False, role='market-data'))
    atomic_json(folder / 'prices' / digest(ticker)[:12] / (h + '.json'), payload)
    return dict(ticker=ticker, status='candidate-only', sessions=len(rows), first=rows[0]['date'],
                last=rows[-1]['date'], contentHash=h, publicationAllowed=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/strategies/sources")
    parser.add_argument('--tickers', nargs='*', help='Descargar candidatos OHLCV y eventos; no certifica identidades ni cobertura')
    parser.add_argument('--start', default='2009-01-01', help='Incluye calentamiento antes del objetivo 2010')
    args = parser.parse_args()
    if not args.tickers:
        print(json.dumps(acquire(args.output), ensure_ascii=False))
    else:
        results = []
        for ticker in args.tickers:
            try:
                results.append(acquire_prices(ticker, args.output, args.start))
            except Exception as error:
                results.append(dict(ticker=ticker, status='fetch-failed', detail=str(error)))
        atomic_json(args.output / 'price-probes.json', dict(version=1, probes=results))
        print(json.dumps(results, ensure_ascii=False))
