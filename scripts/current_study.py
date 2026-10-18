"""Real backtests on a dated snapshot of CURRENT S&P 500 constituents.

Survivorship and current-sector lookahead are disclosed assumptions, not reasons
to refuse this different research question. No point-in-time certification.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from datetime import date,timedelta
from dataclasses import asdict, replace
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.current_universe import CACHE, SECTOR_ETFS
from scripts.market import ROOT, atomic_json, closed_schedule
from scripts.strategy_data import Bar, digest, period_calendar
from scripts.strategy_engine import (ENTRY_NAMES, Signal, research_points, detect, quadrant,
    relative_volumes, atr_values, exit_candidates, suppress_overlaps)
from scripts.strategy_stats import bootstrap, holm, summary

EXITS = [*exit_candidates(), 'time-4', 'time-52']
START = '2010-01-01'
VALIDATION = '2019-01-01'
PERIODS={'train':('2010-01-01','2018-12-31'),'validation':('2019-01-01','2022-12-31'),'test':('2023-01-01',None)}


def thin_curve(rows: list[list]) -> list[list]:
    """Only chart transport is sampled; all metrics use every daily return."""
    return [r for i,r in enumerate(rows) if i==0 or i==len(rows)-1 or i%5==0]


def metrics(returns: list[list]) -> dict:
    """Calendar CAGR, daily zero-rate Sharpe and downside RMS Sortino."""
    if not returns:
        return dict(status='not-evaluable', cagr=None, sharpe=None, maxDrawdown=None)
    values = np.array([r[1] for r in returns], dtype=float)
    if not np.isfinite(values).all() or np.any(values < -1):
        return dict(status='not-evaluable', cagr=None, sharpe=None, maxDrawdown=None)
    equity = np.cumprod(1+values)
    peak = np.maximum.accumulate(np.r_[1.,equity])[1:]
    worst = float((equity/peak-1).min())
    years = max((pd.Timestamp(returns[-1][0])-pd.Timestamp(returns[0][0])).days/365.25,1/252)
    cagr = float(equity[-1]**(1/years)-1)
    std = float(values.std(ddof=1)) if len(values)>1 else 0
    downside = float(np.sqrt(np.mean(np.minimum(values,0)**2)))
    annual = {}
    for day, r in returns:
        annual[day[:4]] = (1+annual.get(day[:4],0))*(1+r)-1
    return dict(status='ok', start=returns[0][0], end=returns[-1][0], totalReturn=float(equity[-1]-1), cagr=cagr,
        sharpe=float(values.mean()/std*math.sqrt(252)) if std>1e-12 else None,
        sortino=float(values.mean()/downside*math.sqrt(252)) if downside>1e-12 else None,
        annualVolatility=std*math.sqrt(252), maxDrawdown=worst,
        calmar=cagr/abs(worst) if worst<0 else None, annualReturns=annual,
        equity=[[d,float(v)] for (d,_),v in zip(returns,equity)])


class FastMarket:
    """Prepared daily arrays; no price filling, and portfolio gaps fail explicitly."""
    def __init__(self, bars: dict[str,list[Bar]], calendar: list[str], stocks: list[str]):
        self.calendar, self.stocks = calendar, stocks
        self.day = {d:i for i,d in enumerate(calendar)}
        self.column = {s:i for i,s in enumerate(stocks)}
        self.series = {}
        for s, rows in bars.items():
            frame = pd.DataFrame([[b.adjusted_open,b.high*b.factor,b.low*b.factor,b.adjusted_close] for b in rows],index=[b.date for b in rows]).reindex(calendar)
            self.series[s] = frame.to_numpy(dtype=float)
        self.open = np.column_stack([self.series[s][:,0] for s in stocks])
        self.close = np.column_stack([self.series[s][:,3] for s in stocks])
        self.intraday = np.divide(self.close,self.open)-1
        self.overnight = np.zeros_like(self.open)
        self.overnight[1:] = self.open[1:]/self.close[:-1]-1
        self.clean_intra=np.nan_to_num(self.intraday)
        self.clean_overnight=np.nan_to_num(self.overnight)

    def portfolio(self, trades: list[dict], cost_bps: float=10, start: str=START, end: str|None=None) -> dict:
        dates = self.calendar
        lo = bisect_left(dates,start); hi=bisect_right(dates,end) if end else len(dates)
        chosen = [t for t in trades if t['status'] not in ('suppressed','pending') and t.get('entryDate') and start <= t['entryDate'] and (end is None or t['entryDate']<=end)]
        if any(t['status']=='missing-data' for t in chosen):
            return dict(status='not-evaluable',reason='Unresolved holding data',cagr=None,sharpe=None,maxDrawdown=None,equity=[])
        delta=np.zeros((hi-lo+1,len(self.stocks)),dtype=np.int16)
        for t in chosen:
            a=max(lo,self.day[t['entryDate']]); b=min(hi,self.day[t['exitDate']]) if t['exitDate'] else hi
            if a<b:
                col=self.column[t['securityId']]; delta[a-lo,col]+=1; delta[b-lo,col]-=1
        active=np.cumsum(delta[:-1],axis=0)>0
        count=active.sum(axis=1)
        target=np.divide(active,count[:,None],out=np.zeros(active.shape),where=count[:,None]>0)
        intra=self.intraday[lo:hi]; overnight=self.overnight[lo:hi]
        if np.any(active & ~np.isfinite(intra)):
            return dict(status='not-evaluable',reason='Missing held session',cagr=None,sharpe=None,maxDrawdown=None,equity=[])
        clean_intra=self.clean_intra[lo:hi]; clean_overnight=self.clean_overnight[lo:hi]
        gross=np.sum(target*clean_intra,axis=1)
        previous=np.zeros_like(target)
        previous[1:]=target[:-1]*(1+clean_intra[:-1])/(1+gross[:-1,None])
        if np.any((previous!=0)&~np.isfinite(overnight)):
            return dict(status='not-evaluable',reason='Missing overnight session',cagr=None,sharpe=None,maxDrawdown=None,equity=[])
        overnight_gross=np.sum(previous*clean_overnight,axis=1)
        open_weights=previous*(1+clean_overnight)/(1+overnight_gross[:,None])
        turnover=np.abs(target-open_weights).sum(axis=1)
        net=(1+overnight_gross)*(1-turnover*cost_bps/10000)*(1+gross)-1
        result=metrics([[d,float(r)] for d,r in zip(dates[lo:hi],net)])
        result.update(turnover=float(turnover.sum()), exposure=float((count>0).mean()), averagePositions=float(count.mean()),
                      costBps=cost_bps, rebalance='daily-equal-active-at-open')
        return result

    def benchmark(self, identity: str, cost_bps: float=10, start: str=START, end: str|None=None) -> dict:
        lo=bisect_left(self.calendar,start); hi=bisect_right(self.calendar,end) if end else len(self.calendar)
        p=self.series[identity][lo:hi]
        r=np.r_[p[0,3]/p[0,0]*(1-cost_bps/10000)-1,p[1:,3]/p[:-1,3]-1]
        return metrics([[d,float(v)] for d,v in zip(self.calendar[lo:hi],r)])


def orbit_exits(points: list[list]) -> set[str]:
    last=None; prev=None; result=set()
    for p in points:
        q=quadrant(*p[1:3])
        if prev is None or (pd.Timestamp(p[0])-pd.Timestamp(prev)).days>10: last=None
        if last=='leading' and q=='weakening': result.add(p[0])
        if q!='neutral': last=q
        prev=p[0]
    return result


def fast_trade(signal: Signal, market: FastMarket, points: list[list], rule: str, atr: dict[str,float], cost_bps: float=10,
               prepared_orbit: set[str]|None=None) -> dict:
    """Same close trigger/next-open semantics as the independent reference engine."""
    dates=market.calendar; n=len(dates); a=bisect_right(dates,signal.date)
    t=dict(version=1,signalId=signal.id,securityId=signal.security_id,rule=signal.rule,signalDate=signal.date,
        availableAt=signal.available_at,exitRule=rule,costBps=cost_bps,status='pending',netReturn=None,
        entryDate=None,exitDate=None,entryPrice=None,exitPrice=None,mfe=None,mae=None,durationDays=None,reason=None)
    if a>=n: return t
    rows=market.series[signal.security_id]
    t.update(entryDate=dates[a],entryPrice=float(rows[a,0]),status='open')
    if not np.isfinite(rows[a]).all(): return {**t,'status':'missing-data','reason':'missing-entry-session'}
    weeks=int(rule.split('-')[1]) if rule.startswith('time-') else 52
    due=(pd.Timestamp(dates[a])+pd.Timedelta(weeks=weeks)).date().isoformat()
    limit=min(n,bisect_left(dates,due)+1)
    values=rows[a:limit]; close=values[:,3]
    peak=np.maximum.accumulate(np.r_[rows[a,0],close])[1:]
    stop=np.full(len(values),-np.inf)
    base=rule.split('+')[0]
    if base.startswith('pct-'): stop=peak*(1-int(base.split('-')[1])/100)
    if base.startswith('atr-'):
        av=np.array([atr.get(d,np.nan) for d in dates[a:limit]])
        if not np.isfinite(av[0]): return {**t,'status':'missing-data','reason':'atr-warmup'}
        stop=np.maximum.accumulate(peak-int(base.split('-')[1])*av)
    triggers=close<=stop
    if rule=='orbit' or '+orbit' in rule:
        orbit=prepared_orbit if prepared_orbit is not None else orbit_exits(points)
        triggers |= np.array([d in orbit for d in dates[a:limit]])
    triggers |= np.array([d>=due for d in dates[a:limit]])
    hits=np.flatnonzero(triggers)
    j=a+int(hits[0]) if len(hits) else limit-1
    if not np.isfinite(rows[a:j+1]).all(): return {**t,'status':'missing-data','reason':'missing-holding-session'}
    if len(hits) and j+1<n:
        b=j+1; price=rows[b,0]
        if not np.isfinite(price): return {**t,'status':'missing-data','reason':'missing-exit-session'}
        t.update(status='closed',exitDate=dates[b],exitPrice=float(price),reason='horizon' if dates[j]>=due else rule,
            netReturn=float(price*(1-cost_bps/10000)/(rows[a,0]*(1+cost_bps/10000))-1),
            mfe=float(max(rows[a:j+1,1].max(),price)/rows[a,0]-1),
            mae=float(min(rows[a:j+1,2].min(),price)/rows[a,0]-1),
            durationDays=(pd.Timestamp(dates[b])-pd.Timestamp(dates[a])).days)
        for key,identity in [('Market','SPY'),('Sector',getattr(market,'sectors',{}).get(signal.security_id,'SPY'))]:
            p=market.series[identity]
            ret=p[b,0]*(1-cost_bps/10000)/(p[a,0]*(1+cost_bps/10000))-1
            t['excess'+key]=float(t['netReturn']-ret) if np.isfinite(ret) else None
        return t
    return {**t,'reason':'right-censored' if not len(hits) else 'awaiting-next-open'}


class PreparedTrades:
    """Compact shared simulation, expanded only for the cohort being evaluated."""
    fields=('status','entryDate','exitDate','entryPrice','exitPrice','netReturn','mfe','mae','durationDays','reason','excessMarket','excessSector')
    def __init__(self,signal,values): self.signal=signal; self.values=values
    def __getitem__(self,rule):
        s=self.signal
        return dict(version=1,signalId=s.id,securityId=s.security_id,rule=s.rule,signalDate=s.date,availableAt=s.available_at,
            exitRule=rule,costBps=10,**dict(zip(self.fields,self.values[rule])))


def prepare_trades(signal: Signal, market: FastMarket, orbit: set[str], atr: dict[str,float]) -> PreparedTrades:
    dates=market.calendar;n=len(dates);a=bisect_right(dates,signal.date)
    if a>=n: return PreparedTrades(signal,{r:('pending',None,None,None,None,None,None,None,None,None,None,None) for r in EXITS})
    rows=market.series[signal.security_id];entry=float(rows[a,0]);entry_day=dates[a]
    due={w:bisect_left(dates,(date.fromisoformat(entry_day)+timedelta(weeks=w)).isoformat()) for w in [4,13,26,52]}
    last=min(n,due[52]+1);close=rows[a:last,3];peak=np.maximum.accumulate(np.r_[entry,close])[1:]
    av=np.array([atr.get(d,np.nan) for d in dates[a:last]])
    orbit_mask=np.array([d in orbit for d in dates[a:last]])
    stops={f'pct-{p}':peak*(1-p/100) for p in [10,15,20]}
    stops.update({f'atr-{k}':np.maximum.accumulate(peak-k*av) for k in [2,3,4]})
    high=np.maximum.accumulate(np.maximum(rows[a:last,1],entry));low=np.minimum.accumulate(np.minimum(rows[a:last,2],entry))
    missing=np.flatnonzero(~np.isfinite(rows[a:last]).all(axis=1));first_missing=a+int(missing[0]) if len(missing) else n
    result={}
    for rule in EXITS:
        base=rule.split('+')[0]
        if not np.isfinite(entry):
            result[rule]=('missing-data',entry_day,None,None,None,None,None,None,None,'missing-entry-session',None,None);continue
        if base.startswith('atr-') and not np.isfinite(av[0]):
            result[rule]=('missing-data',entry_day,None,entry,None,None,None,None,None,'atr-warmup',None,None);continue
        weeks=int(base[5:]) if base.startswith('time-') else 52
        trigger=due[weeks]
        if base in stops:
            hits=np.flatnonzero(close<=stops[base])
            if len(hits):trigger=min(trigger,a+int(hits[0]))
        if rule=='orbit' or '+orbit' in rule:
            hits=np.flatnonzero(orbit_mask)
            if len(hits):trigger=min(trigger,a+int(hits[0]))
        j=min(n-1,trigger)
        if first_missing<=j:
            result[rule]=('missing-data',entry_day,None,entry,None,None,None,None,None,'missing-holding-session',None,None);continue
        if trigger+1<n:
            b=trigger+1;price=float(rows[b,0])
            if not np.isfinite(price):
                result[rule]=('missing-data',entry_day,None,entry,None,None,None,None,None,'missing-exit-session',None,None);continue
            net=price*.999/(entry*1.001)-1
            excess=[]
            for identity in ['SPY',market.sectors[signal.security_id]]:
                p=market.series[identity];ret=p[b,0]*.999/(p[a,0]*1.001)-1
                excess.append(float(net-ret) if np.isfinite(ret) else None)
            result[rule]=('closed',entry_day,dates[b],entry,price,float(net),float(max(high[j-a],price)/entry-1),
                float(min(low[j-a],price)/entry-1),(date.fromisoformat(dates[b])-date.fromisoformat(entry_day)).days,
                'horizon' if trigger==due[weeks] else rule,*excess)
        else:
            result[rule]=('open',entry_day,None,entry,None,None,None,None,None,
                'awaiting-next-open' if trigger<n else 'right-censored',None,None)
    return PreparedTrades(signal,result)


def load_data(folder: Path, now: pd.Timestamp):
    catalog=json.loads((folder/'catalog.json').read_text())
    acquisition=json.loads((folder/'acquisition.json').read_text())
    end=acquisition['latestSession']
    bars={}; coverage=[]
    for identity in ['SPY','QQQ','DIA','IWM',*SECTOR_ETFS.values(),*[s['id'] for s in catalog['securities']]]:
        path=folder/'prices'/(identity+'.json')
        if not path.exists():
            coverage.append(dict(ticker=identity,status='download-failed',sessions=0)); bars[identity]=[]; continue
        payload=json.loads(path.read_text())
        rows=[]
        for r in payload['bars']:
            if r[0]>end: continue
            rows.append(Bar(r[0],*r[1:7],r[0]+'T23:59:59Z',payload.get('sourceOverrides',{}).get(r[0],'yahoo-current'),volume_basis='split-adjusted',dividend=r[7],split=r[8]))
        bars[identity]=rows
        coverage.append(dict(ticker=identity,status='ok' if payload['last']==end else 'stale',sessions=len(rows),
            first=rows[0].date if rows else None,last=rows[-1].date if rows else None,corrections=payload.get('corrections',[])))
    return catalog,bars,coverage,end


def build(folder: Path=CACHE, output: Path=ROOT/'public/data/strategies', now: pd.Timestamp|None=None) -> dict:
    now=now or pd.Timestamp.now(tz='UTC')
    print('Cargando las 503 acciones actuales y referencias…',flush=True)
    catalog,bars,coverage,end=load_data(folder,now)
    stocks=[s['id'] for s in catalog['securities']]
    missing=[r for r in coverage if r['status']!='ok']
    if missing: raise ValueError('Descargas pendientes (se conserva el estudio anterior): '+','.join(r['ticker'] for r in missing))
    calendar=period_calendar('2008-01-01',end,now,'daily')
    weeks=period_calendar('2008-01-01',end,now,'weekly')
    market=FastMarket(bars,calendar,stocks)
    print('Matrices de precios preparadas; calculando huella y señales…',flush=True)
    market.sectors={s['id']:s['etf'] for s in catalog['securities']}
    protocol=dict(version=2,id='kiko-current-v2',frozenOn='2026-10-18',universe='SP500_CURRENT_SNAPSHOT',
        start=START,validationStart=VALIDATION,entries=list(ENTRY_NAMES),exits=EXITS,methods={'weekly':'SMA 10/30/9'},
        confirmations=[1,2],references=['market','sector'],sectorFilters=[False,True],volumeFilters=[None,1.2],
        primaryHorizonWeeks=13,costBps=[5,10,25],primaryCostBps=10,rebalance='daily-equal-active-at-open',
        cashRate=0,bootstrapBlockWeeks=52,bootstrapReplicates=2000,scope='Retrospective, current survivors and current sectors; no blind holdout')
    hash_input=digest({k:digest([[b.date,b.open,b.high,b.low,b.close,b.adjusted_close,b.volume] for b in v]) for k,v in bars.items()})
    code_hash=digest({f:(ROOT/'scripts'/f).read_text(encoding='utf-8') for f in ['current_study.py','strategy_allocation.py','strategy_data.py','strategy_engine.py','strategy_stats.py']})
    run_id=digest([hash_input,catalog['contentHash'],protocol,code_hash])[:20]
    dest=output/run_id
    sector_points={e:research_points(bars[e],bars['SPY'],weeks,'weekly') for e in SECTOR_ETFS.values()}
    sector_strength={e:{p[0]:quadrant(*p[1:3])=='leading' for p in points} for e,points in sector_points.items()}
    atr={s:atr_values(bars[s]) for s in stocks}
    variants=[]; cases=[]; signals_by_pair={}; prepared={}
    for index,security in enumerate(catalog['securities']):
        identity=security['id']; vol=relative_volumes(bars[identity],weeks,'weekly')
        for reference in ['SPY',security['etf']]:
            points=research_points(bars[identity],bars[reference],weeks,'weekly')
            first_week=bisect_left(weeks,bars[identity][0].date)
            eligible_start=weeks[min(len(weeks)-1,first_week+50)]
            points=[p for p in points if p[0]>=eligible_start]
            orbit=orbit_exits(points)
            events=[replace(s,sector=security['sector'],sector_strong=sector_strength[security['etf']].get(s.date),relative_volume=vol.get(s.date))
                for confirm in [1,2] for s in detect(points,weeks,identity,reference,'weekly',confirm) if s.date>=START]
            signals_by_pair[identity,reference]=events
            for s in events:
                prepared[s.id]=prepare_trades(s,market,orbit,atr[identity])
            # Publish calculated, dimensionless analytics rather than vendor OHLCV.
            if points:
                scale=100/points[0][3]
                indexed=[[p[0],p[1],p[2],p[3]*scale] for p in points]
                filename='current-'+digest([identity,reference])[:24]+'.json'
                atomic_json(dest/filename,dict(version=1,scope='stock-study',securityId=identity,name=security['name'],reference=reference,
                    timeframe='weekly',method='research-sma-10-30-9',points=indexed,benchmark=[],signals=[asdict(s) for s in events],
                    lastSession=points[-1][0],limitations='Precio ajustado indexado a 100 al inicio. Componente y sector actuales aplicados retrospectivamente; sesgo de supervivencia.'))
                cases.append(dict(id=digest([identity,reference])[:24],securityId=identity,name=security['name'],timeframe='weekly',
                    url=f'{run_id}/{filename}',count=len(events),scope='stock-study',referenceType='market' if reference=='SPY' else 'sector'))
        if (index+1)%25==0: print(f'Señales y operaciones: {index+1}/{len(stocks)}',flush=True)
    # Prepared trades are shared across filters; each cohort gets its own overlap policy.
    for ref_type in ['market','sector']:
      for confirm in [1,2]:
       for strong in [False,True]:
        for volume in [False,True]:
         for rule in ENTRY_NAMES:
            events=[s for (identity,ref),ss in signals_by_pair.items() if (ref=='SPY')==(ref_type=='market') for s in ss
                if s.rule==rule and s.confirmation==confirm and (not strong or s.sector_strong is True)
                and (not volume or s.relative_volume is not None and s.relative_volume>=1.2)]
            group=dict(timeframe='weekly',reference=ref_type,confirmation=confirm,sectorFilter=strong,volumeFilter=1.2 if volume else None,rule=rule)
            entries=[prepared[s.id]['time-13'] for s in events]
            evidence=bootstrap(entries,'excessMarket')
            period_evidence={period:bootstrap([t for t in entries if t['signalDate']>=begin and t['status']=='closed'
                and (finish is None or t['exitDate']<=finish)],'excessMarket') for period,(begin,finish) in PERIODS.items()}
            for exit_rule in EXITS:
                raw=[prepared[s.id][exit_rule] for s in events]
                trades=suppress_overlaps(raw)
                port=market.portfolio(trades)
                periods={}; period_curves={}
                for period,(begin,finish) in PERIODS.items():
                    subset=suppress_overlaps(t for t in raw if t['signalDate']>=begin and (finish is None or t['signalDate']<=finish))
                    p=market.portfolio(subset,start=begin,end=finish)
                    period_curves[period]=thin_curve(p.pop('equity',[]))
                    observed=[{**t,'status':'open','netReturn':None} if finish and t['exitDate'] and t['exitDate']>finish else t for t in subset]
                    p['trades']=summary(observed)
                    periods[period]=p
                stat=summary(trades)
                closed=[t for t in trades if t['status']=='closed']
                gains=sum(max(t['netReturn'],0) for t in closed); losses=-sum(min(t['netReturn'],0) for t in closed)
                stat.update(profitFactor=gains/losses if losses else None,
                    averageDuration=float(np.mean([t['durationDays'] for t in closed])) if closed else None,
                    meanExcessMarket=float(np.mean([t['excessMarket'] for t in closed if t.get('excessMarket') is not None])) if closed else None)
                identity=digest([group,exit_rule])[:24]
                curves=dict(version=2,equity=thin_curve(port.pop('equity',[])),periods=period_curves)
                costs={str(c):{k:v for k,v in market.portfolio(trades,c).items() if k!='equity'} for c in [5,25]}
                small={**group,'id':identity,'exitRule':exit_rule,'summary':stat,'portfolio':port,'periods':periods,
                    'costs':costs,'entryEvidence':evidence,'entryEvidencePeriods':period_evidence,'detailsUrl':f'{run_id}/curve-{identity}.json'}
                atomic_json(dest/f'curve-{identity}.json',curves)
                variants.append(small)
            print(f'Carteras: {ref_type} confirm={confirm} sector={strong} volumen={volume} {rule}',flush=True)
    primary=[v for v in variants if v['exitRule']=='time-13' and v['confirmation']==1 and not v['sectorFilter'] and v['volumeFilter'] is None]
    for v,p in zip(primary,holm([v['entryEvidence']['pValue'] for v in primary])): v['adjustedPValue']=p
    for period in PERIODS:
        for v,p in zip(primary,holm([v['entryEvidencePeriods'][period]['pValue'] for v in primary])):
            v.setdefault('adjustedPValuePeriods',{})[period]=p
    benchmark=market.benchmark('SPY'); benchmark_periods={}; benchmark_curves={}
    cohort_periods={}; cohort_curves={}
    for period,(begin,finish) in PERIODS.items():
        p=market.benchmark('SPY',start=begin,end=finish); benchmark_curves[period]=thin_curve(p.pop('equity')); benchmark_periods[period]=p
        controls=[]
        for identity in stocks:
            if len(bars[identity])<=252: continue
            entry=max(begin,bars[identity][252].date)
            at=bisect_left(calendar,entry)
            if at>=len(calendar) or finish and calendar[at]>finish: continue
            controls.append(dict(securityId=identity,entryDate=calendar[at],exitDate=None,status='open'))
        p=market.portfolio(controls,start=begin,end=finish)
        cohort_curves[period]=thin_curve(p.pop('equity',[]));cohort_periods[period]=p
    atomic_json(dest/'benchmark.json',dict(version=2,equity=thin_curve(benchmark.pop('equity')),periods=benchmark_curves,cohortPeriods=cohort_curves))
    report=dict(version=2,scope='current-constituents',runId=run_id,asOf=catalog['asOf'],latestSession=end,
        universeCount=len(stocks),companyCount=len({s['cik'] for s in catalog['securities']}),catalog=catalog['securities'],coverage=coverage,
        start=START,validationStart=VALIDATION,protocol=protocol,protocolHash=digest(protocol),snapshotHash=hash_input,engineHash=code_hash,
        sources=[dict(name='Componentes actuales · DataHub/Wikipedia',url=catalog['source'],hash=catalog['contentHash']),
                 dict(name='Precios ajustados · Yahoo Finance / yfinance',url='https://ranaroussi.github.io/yfinance/'),
                 dict(name='Suplemento FISV 12/11/2025 · barra diaria contrastada',url='https://www.quiverquant.com/stock/FISV/historical-prices/')],
        benchmark=benchmark,benchmarkPeriods=benchmark_periods,cohortBenchmarkPeriods=cohort_periods,benchmarkUrl=f'{run_id}/benchmark.json',variants=variants,
        limitations=['Universo fijado con los componentes actuales; excluye empresas que abandonaron el índice y contiene sesgo de supervivencia.',
            'Se aplica el sector actual a toda la historia. No se inventa histórico de XLC o XLRE anterior a su creación.',
            '2019 en adelante es una separación temporal retrospectiva para reglas fijas; no un holdout ciego ni un estudio prospectivo.',
            'Cartera equiponderada entre posiciones activas, rebalanceada cada apertura, sin apalancamiento; efectivo y tipo libre de riesgo 0%.',
            'Señales al cierre de semana completada, ejecución en siguiente apertura. Trailing diario de cierre, máximo 52 semanas. Coste 10 pb por lado y rebalanceo.',
            'Acciones con IPO posterior comienzan cuando tienen historial suficiente. Operaciones abiertas se valoran en cartera y se separan de las cerradas.'])
    from scripts.strategy_allocation import study_allocations
    report['allocations']=study_allocations(market,catalog['securities'],signals_by_pair,prepared,dest,run_id)
    atomic_json(dest/'current-study.json',report)
    manifest_path=output/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest.update(currentStudyUrl=f'{run_id}/current-study.json',currentCoverage=dict(asOf=catalog['asOf'],count=len(stocks),latestSession=end,start=START),
        cases=[c for c in manifest['cases'] if c['scope']!='stock-study']+cases)
    atomic_json(manifest_path,manifest)
    print(f'Estudio actual publicado: {len(stocks)} valores; {len(variants)} variantes',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'public/data/strategies')
    args=parser.parse_args(); build(output=args.output)
