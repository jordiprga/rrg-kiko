"""Acquire today's S&P 500 snapshot and private adjusted daily market history.

This is deliberately a CURRENT-constituent cohort, never a point-in-time index.
Raw vendor prices remain in .cache; only calculated research is published.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import time
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

from scripts.market import ROOT, atomic_json, closed_schedule

CATALOG_URL = 'https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv'
SECTOR_ETFS = {'Communication Services':'XLC', 'Consumer Discretionary':'XLY', 'Consumer Staples':'XLP',
    'Energy':'XLE', 'Financials':'XLF', 'Health Care':'XLV', 'Industrials':'XLI',
    'Information Technology':'XLK', 'Materials':'XLB', 'Real Estate':'XLRE', 'Utilities':'XLU'}
CACHE = ROOT / '.cache/strategies/current'


def missing_sessions(rows: list[list], calendar: list[str], ticker: str) -> list[str]:
    if not rows: return []
    present={r[0] for r in rows}
    return [d for d in calendar if rows[0][0]<=d<=rows[-1][0] and d not in present
            and not (ticker=='FISV' and d=='2025-11-12')]


def supplement_fiserv(folder: Path) -> None:
    """Resolve one confirmed vendor gap with a sourced daily bar, not a fill.

    Fiserv/ Nasdaq document the FI -> FISV listing transfer on 11 Nov 2025.
    Yahoo omits 12 Nov in its daily feed; intraday bars omit auctions, so they
    are NOT substituted for a complete session's open/close/volume.
    """
    path=folder/'prices/FISV.json'
    if not path.exists(): return
    data=json.loads(path.read_text(encoding='utf-8'))
    lookup={r[0]:r for r in data['bars']}
    if '2025-11-12' in lookup: return
    url='https://www.quiverquant.com/stock/FISV/historical-prices/'
    evidence_path=folder/'evidence/fisv-supplement.json'
    if evidence_path.exists():
        evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
    else:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        content=urllib.request.urlopen(request,timeout=30).read(3_000_000)
        values={}
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',content.decode(),flags=re.S):
            cells=[re.sub('<[^>]+>','',x).strip() for x in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',row,flags=re.S)]
            if len(cells)==7:
                for label,day in [('Nov 10, 2025','2025-11-10'),('Nov 12, 2025','2025-11-12'),('Nov 13, 2025','2025-11-13'),('Nov 14, 2025','2025-11-14')]:
                    if cells[0]==label: values[day]=[float(x.replace(',','')) for x in cells[1:]]
        if len(values)!=4: raise ValueError('No se puede contrastar la sesión ausente de FISV')
        evidence=dict(url=url,retrievedAt=datetime.now(timezone.utc).isoformat(),contentHash=sha256(content).hexdigest(),rows=values)
        atomic_json(evidence_path,evidence)
        (folder/'evidence/fisv-quiver.html').write_bytes(content)
    for day in ['2025-11-10','2025-11-13','2025-11-14']:
        # Independent neighbouring OHLC agree to cents; small volume revisions
        # are retained as a provider difference, not silently averaged.
        if day not in lookup or any(abs(a-b)>.011 for a,b in zip(lookup[day][1:5],evidence['rows'][day][:4])):
            raise ValueError('El suplemento FISV ya no coincide con la escala del proveedor; revisar eventos')
    previous=lookup['2025-11-10'];following=lookup['2025-11-13']
    factor=previous[5]/previous[4]
    if abs(factor-following[5]/following[4])>1e-6: raise ValueError('Ajuste corporativo no resuelto en la sesión de FISV')
    o,h,l,c,adjusted,volume=evidence['rows']['2025-11-12']
    if abs(adjusted-c)>.001: raise ValueError('Escala de suplemento FISV desconocida')
    data['bars'].append(['2025-11-12',o,h,l,c,c*factor,volume,0.,1.])
    data['bars'].sort(key=lambda r:r[0])
    data.setdefault('corrections',[]).append(dict(date='2025-11-12',type='supplemental-bar',source=url,
        contentHash=evidence['contentHash'],reason='Missing Yahoo daily session; complete daily bar from Quiver; three neighbouring OHLC sessions cross-checked, Yahoo intraday also checked'))
    data.setdefault('sourceOverrides',{})['2025-11-12']='quiver-fisv-supplement'
    atomic_json(path,data)


def parse_catalog(content: bytes) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    if not rows or not {'Symbol','Security','GICS Sector','CIK'} <= rows[0].keys():
        raise ValueError('Formato de componentes incompatible')
    result = [dict(id=r['Symbol'].replace('.', '-'), ticker=r['Symbol'].replace('.', '-'),
        symbol=r['Symbol'], name=r['Security'], sector=r['GICS Sector'],
        cik=r['CIK'], etf=SECTOR_ETFS[r['GICS Sector']]) for r in rows]
    if any(not re.fullmatch(r'[A-Z][A-Z0-9-]{0,15}',r['id']) or not r['cik'].isdigit() for r in result):
        raise ValueError('Identificador de valor inválido en el catálogo')
    if not 490 <= len(result) <= 520 or len({r['id'] for r in result}) != len(result):
        raise ValueError('El catálogo no contiene un universo completo o contiene duplicados')
    return sorted(result, key=lambda r:r['id'])


def acquire(folder: Path = CACHE, refresh: bool = False) -> dict:
    now = pd.Timestamp.now(tz='UTC')
    import exchange_calendars as xcals
    schedule = closed_schedule(xcals.get_calendar('XNYS', start='2008-01-01', end=now.date().isoformat()).schedule, now)
    end = schedule.index[-1].date().isoformat()
    calendar=[d.date().isoformat() for d in schedule.index]
    folder.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CATALOG_URL, headers={'User-Agent':'Orbita/1.0'})
    content = urllib.request.urlopen(req, timeout=45).read(2_000_000)
    catalog = parse_catalog(content)
    snapshot = dict(version=1, asOf=now.date().isoformat(), retrievedAt=now.isoformat(),
                    source=CATALOG_URL, contentHash=sha256(content).hexdigest(), securities=catalog)
    atomic_json(folder/'catalog.json', snapshot)
    (folder/'constituents.csv').write_bytes(content)
    tickers = ['SPY', 'QQQ', 'DIA', 'IWM', *SECTOR_ETFS.values(), *[s['ticker'] for s in catalog]]
    needed = []
    for ticker in tickers:
        path = folder/'prices'/(ticker+'.json')
        previous = json.loads(path.read_text()) if path.exists() else None
        if refresh or not previous or previous.get('last') != end or missing_sessions(previous['bars'],calendar,ticker):
            needed.append(ticker)
    failures = []
    for offset in range(0, len(needed), 16):
        group = needed[offset:offset+16]
        frame = yf.download(group, start='2008-01-01', end=(pd.Timestamp(end)+pd.Timedelta(days=1)).date().isoformat(),
            auto_adjust=False, actions=True, group_by='ticker', threads=4, progress=False, timeout=30)
        for ticker in group:
            try:
                series = frame[ticker] if isinstance(frame.columns,pd.MultiIndex) else frame
                rows = []; corrections=[]
                for day, r in series.iterrows():
                    date = day.date().isoformat()
                    keys = ['Open','High','Low','Close','Adj Close']
                    if date > end or any(k not in r or not np.isfinite(r[k]) or r[k] <= 0 for k in keys):
                        continue
                    high=max(r['High'],r['Open'],r['Close']); low=min(r['Low'],r['Open'],r['Close'])
                    if high!=r['High'] or low!=r['Low']:
                        if max(high-r['High'],r['Low']-low)/r['Close']>.01: raise ValueError('OHLC incoherente > 1 %')
                        corrections.append(dict(date=date,originalHigh=float(r['High']),originalLow=float(r['Low']),high=float(high),low=float(low),
                            reason='Expand range to include reported open/close; no close or fill price alteration'))
                    values=[float(r[k]) for k in keys]; values[1]=float(high); values[2]=float(low)
                    rows.append([date, *values,
                        float(r['Volume']) if pd.notna(r.get('Volume')) else None,
                        float(r.get('Dividends',0) or 0), float(r.get('Stock Splits',0) or 1)])
                if not rows or rows[-1][0] != end:
                    raise ValueError('Sin último cierre válido')
                gaps=missing_sessions(rows,calendar,ticker)
                if gaps: raise ValueError('Sesiones ausentes sin resolver: '+','.join(gaps[:5]))
                atomic_json(folder/'prices'/(ticker+'.json'), dict(version=1,ticker=ticker,first=rows[0][0],last=rows[-1][0],
                    retrievedAt=now.isoformat(), corrections=corrections, columns=['date','open','high','low','close','adjustedClose','volume','dividend','split'], bars=rows))
            except (KeyError,ValueError) as error:
                failures.append(dict(ticker=ticker,detail=str(error)))
        print(f'Datos actuales: {min(offset+16,len(needed))}/{len(needed)}; incidencias {len(failures)}', flush=True)
        time.sleep(.3)
    supplement_fiserv(folder)
    result = dict(version=1, latestSession=end, catalogCount=len(catalog), requested=len(tickers), failures=failures,
                  completedAt=datetime.now(timezone.utc).isoformat(), catalogHash=snapshot['contentHash'])
    atomic_json(folder/'acquisition.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    result=acquire(refresh=args.refresh)
    for _ in range(2):
        if not result['failures']: break
        time.sleep(2)
        result=acquire()
    print(json.dumps(result,ensure_ascii=False))
    if result['failures']: raise SystemExit(1)
