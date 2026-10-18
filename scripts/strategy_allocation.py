"""Self-financing portfolio experiments with a predeclared, bounded search.

Orders are hypothetical. All ranking, volatility and regime inputs precede fills.
Holdings keep their birth exit, including when a walk-forward policy changes.
"""
from __future__ import annotations

from bisect import bisect_left
from itertools import product

import numpy as np
import pandas as pd

from scripts.market import atomic_json
from scripts.strategy_data import digest


def policies() -> list[dict]:
    return [dict(rule=rule,exitRule=exit_rule,allocation=allocation,sectorFilter=strong,regime=regime,
                 maxPositions=10 if allocation=='ranked-10' else 20,
                 stockCap=.1 if allocation=='ranked-10' else .05,sectorCap=.25)
        for rule,exit_rule,allocation,strong,regime in product(
            ['turn-up','turn-right','lagging-improving','improving-leading'],
            ['time-13','pct-15+orbit','atr-3+orbit'],
            ['equal-20','inverse-vol-20','ranked-10'],[False,True],[False,True])]


def select_candidate(candidates: list[dict]) -> tuple[list[dict],dict|None]:
    """The final test result is intentionally never read by this selection."""
    valid=[c for c in candidates if c['selectionScore'] is not None and c['periods']['validation']['status']=='ok']
    shortlist=sorted(valid,key=lambda c:(-c['selectionScore'],c['id']))[:3]
    chosen=min(shortlist,key=lambda c:(-(c['periods']['validation']['sharpe'] if c['periods']['validation']['sharpe'] is not None else -1e9),
        abs(c['periods']['validation']['maxDrawdown']),c['periods']['validation']['turnover'],c['id'])) if shortlist else None
    return shortlist,chosen


def capped_weights(identities: list[str], volatility: dict, sectors: dict, policy: dict) -> dict:
    if not identities: return {}
    raw={s:1/max(volatility.get(s,float('inf')),1e-6) if policy['allocation']=='inverse-vol-20' else 1. for s in identities}
    total=sum(raw.values())
    if not total: return {}
    weights={s:min(policy['stockCap'],v/total) for s,v in raw.items()}
    for sector in set(sectors[s] for s in identities):
        group=[s for s in identities if sectors[s]==sector]
        weight=sum(weights[s] for s in group)
        if weight>policy['sectorCap']:
            for s in group: weights[s]*=policy['sectorCap']/weight
    # Capacity shortfall deliberately remains cash; no leverage or hidden rescaling.
    return weights


class Allocator:
    def __init__(self,market,catalog,signals,prepared):
        self.market=market; self.prepared=prepared
        self.sectors={s['id']:s['sector'] for s in catalog}
        self.events={}
        for (_,ref),events in signals.items():
            if ref!='SPY': continue
            for s in events:
                if s.confirmation!=1: continue
                t=prepared[s.id]['time-13']
                if t['entryDate']: self.events.setdefault(t['entryDate'],[]).append(s)
        self.volatility={}
        for identity in market.stocks:
            p=pd.Series(market.series[identity][:,3])
            self.volatility[identity]=p.pct_change(fill_method=None).rolling(60,min_periods=60).std().shift(1).to_numpy()
        regimes=[]
        for identity in ['SPY','QQQ','DIA','IWM']:
            close=pd.Series(market.series[identity][:,3])
            regimes.append((close>close.rolling(200,min_periods=200).mean()).shift(1,fill_value=False).to_numpy())
        self.regime=regimes[0] & (np.sum(regimes[1:],axis=0)>=2)

    def run(self,policy,start='2010-01-01',end=None,cost_bps=10,year_policies=None):
        from scripts.current_study import metrics
        market=self.market; dates=market.calendar; lo=bisect_left(dates,start)
        holdings={}; weights={}; returns=[]; ledger=[]; snapshots=[]; turnover=0.; missing=[]
        sector_peak=0.; individual_peak=0.; exposures=[]; counts=[]
        equity=1.
        config=policy
        for i in range(lo,len(dates)):
            day=dates[i]
            if end and day>end: break
            if year_policies is not None: config=year_policies.get(day[:4])
            overnight=0.; open_weights={}
            for s,w in weights.items():
                prev=market.series[s][i-1,3]; op=market.series[s][i,0]
                if not np.isfinite(prev) or not np.isfinite(op): missing.append(dict(ticker=s,date=day)); break
                overnight+=w*(op/prev-1)
            if missing: break
            for s,w in weights.items(): open_weights[s]=w*(market.series[s][i,0]/market.series[s][i-1,3])/(1+overnight)
            changed=False
            for s in list(holdings):
                t=holdings[s]
                if t['exitDate'] is not None and t['exitDate']<=day:
                    ledger.append({**t,'allocationExitDate':day}); del holdings[s]; changed=True
            risk_on=config is not None and (not config['regime'] or self.regime[i])
            if not risk_on and holdings:
                for s,t in holdings.items(): ledger.append({**t,'allocationExitDate':day,'allocationReason':'index-regime'})
                holdings={}; changed=True
            if risk_on:
                candidates=sorted([s for s in self.events.get(day,[]) if s.rule==config['rule']
                    and (not config['sectorFilter'] or s.sector_strong is True)],key=lambda s:(-(s.x+s.y),s.security_id))
                for signal in candidates:
                    s=signal.security_id
                    if s in holdings or len(holdings)>=config['maxPositions']: continue
                    t=self.prepared[signal.id][config['exitRule']]
                    if t['status']=='missing-data': missing.append(dict(ticker=s,date=day)); break
                    if t['status']=='pending': continue
                    vol=self.volatility[s][i]
                    if not np.isfinite(vol) or vol<=0: continue
                    holdings[s]={**t,'birthPolicy':digest(config)[:24]}; changed=True
            if missing: break
            weekly=i==lo or pd.Timestamp(day).to_period('W-FRI')!=pd.Timestamp(dates[i-1]).to_period('W-FRI')
            if changed or weekly:
                target=capped_weights(list(holdings),{s:self.volatility[s][i] for s in holdings},self.sectors,config) if config else {}
            else: target=open_weights
            change=sum(abs(target.get(s,0)-open_weights.get(s,0)) for s in set(target)|set(open_weights))
            intraday=0.
            for s,w in target.items():
                v=market.intraday[i,market.column[s]]
                if not np.isfinite(v): missing.append(dict(ticker=s,date=day)); break
                intraday+=w*v
            if missing: break
            net=(1+overnight)*(1-change*cost_bps/10000)*(1+intraday)-1
            capital_at_open=equity*(1+overnight)*(1-change*cost_bps/10000)
            equity*=1+net
            returns.append([day,float(net)]); turnover+=change
            weights={s:w*(1+market.intraday[i,market.column[s]])/(1+intraday) for s,w in target.items()}
            exposures.append(sum(target.values())); counts.append(len(target))
            if changed or weekly:
                individual_peak=max(individual_peak,max(target.values(),default=0))
                sector_peak=max(sector_peak,max((sum(w for s,w in target.items() if self.sectors[s]==sec) for sec in set(self.sectors.values())),default=0))
            if i==lo or day==dates[-1] or end is not None and i+1<len(dates) and dates[i+1]>end or day[:7]!=dates[i-1][:7]:
                snapshots.append(dict(date=day,cash=1-sum(target.values()),capitalIndex=capital_at_open,positions=[dict(ticker=s,weight=w,sector=self.sectors[s],
                    signalDate=holdings[s]['signalDate'],exitRule=holdings[s]['exitRule']) for s,w in target.items()]))
        result=metrics(returns) if not missing else dict(status='not-evaluable',cagr=None,sharpe=None,maxDrawdown=None,equity=[])
        result.update(turnover=turnover,meanExposure=float(np.mean(exposures)) if exposures else 0,
            meanPositions=float(np.mean(counts)) if counts else 0,closedTrades=len(ledger),openTrades=len(holdings),
            maxWeightAtRebalance=individual_peak,maxSectorWeightAtRebalance=sector_peak,missing=missing,costBps=cost_bps)
        return dict(metrics=result,returns=returns,snapshots=snapshots,lastHoldings=snapshots[-1] if snapshots else None)


def study_allocations(market,catalog,signals,prepared,dest,run_id):
    from scripts.current_study import PERIODS,metrics,thin_curve
    engine=Allocator(market,catalog,signals,prepared)
    candidates=[]; runs={}; policy_list=policies()
    # Freeze the entire finite family before computing or ranking test performance.
    atomic_json(dest/'allocation-protocol.json',dict(version=1,candidates=policy_list,
        train=['2010-01-01','2018-12-31'],validation=['2019-01-01','2022-12-31'],test=['2023-01-01',None],
        selection='Top three by median annual Sharpe in 2016–2018; choose by validation Sharpe, then lower drawdown, then turnover.',
        walkForward='Choose by median annual Sharpe in last three of the preceding five calendar years; next-year policy controls new positions; held positions retain birth exits.'))
    for n,policy in enumerate(policy_list):
        identity=digest(policy)[:24]; periods={}; details={}; arrays={}
        for period,(start,end) in PERIODS.items():
            run=engine.run(policy,start,end)
            curve=thin_curve(run['metrics'].pop('equity',[]))
            periods[period]=run['metrics']; arrays[period]=run['returns']; details[period]=dict(equity=curve,snapshots=run['snapshots'])
        scores=[]
        for year in ['2016','2017','2018']:
            score=metrics([r for r in arrays['train'] if r[0].startswith(year)])['sharpe']
            scores.append(score)
        selection_score=float(np.median(scores)) if all(v is not None for v in scores) else None
        candidate=dict(id=identity,policy=policy,periods=periods,selectionScore=selection_score,detailsUrl=f'{run_id}/allocation-{identity}.json')
        candidates.append(candidate); runs[identity]=arrays
        atomic_json(dest/f'allocation-{identity}.json',dict(version=1,periods=details))
        if (n+1)%12==0: print(f'Asignación de capital: {n+1}/{len(policy_list)}',flush=True)
    shortlist,chosen=select_candidate(candidates)
    # Train-only annual choices; test-year returns never enter that year's selection.
    year_policies={}; folds=[]
    for year in range(2015,int(market.calendar[-1][:4])+1):
        ranked=[]
        for c in candidates:
            rows=[r for part in runs[c['id']].values() for r in part]
            previous=[r for r in rows if f'{year-5}-01-01'<=r[0]<f'{year}-01-01']
            if len(previous)<1200: continue
            scores=[metrics([r for r in previous if r[0].startswith(str(y))])['sharpe'] for y in range(year-3,year)]
            if any(v is None for v in scores): continue
            p=metrics(previous)
            ranked.append((float(np.median(scores)),abs(p['maxDrawdown']),c['id'],c))
        if ranked:
            best=max(r[0] for r in ranked)
            pick=min((r for r in ranked if best-r[0]<.05),key=lambda r:(r[1],r[2]))[-1]
            year_policies[str(year)]=pick['policy']
            folds.append(dict(year=year,trainingStart=f'{year-5}-01-01',trainingEnd=f'{year-1}-12-31',chosen=pick['id']))
    walk=engine.run(None,start='2015-01-01',year_policies=year_policies)
    curve=thin_curve(walk['metrics'].pop('equity',[]))
    atomic_json(dest/'allocation-walk-forward.json',dict(version=1,equity=curve,snapshots=walk['snapshots']))
    # Cost stress is evaluated after the model was locked by train/validation.
    stress={}
    if chosen:
        for cost in [5,10,25]:
            r=engine.run(chosen['policy'],start=PERIODS['test'][0],cost_bps=cost)['metrics']; r.pop('equity',None); stress[str(cost)]=r
    return dict(version=1,candidateCount=len(candidates),candidates=candidates,shortlist=[c['id'] for c in shortlist],
        selectedId=chosen['id'] if chosen else None,selectionUses='train + validation only; test never used to select',
        costStress=stress,walkForward=dict(metrics=walk['metrics'],folds=folds,detailsUrl=f'{run_id}/allocation-walk-forward.json'),
        indexRegime='SPY above SMA200 and at least two of QQQ/DIA/IWM above SMA200 at previous close; ETFs are tradable proxies for broad indices.',
        allocationRules='Fresh weekly signals only; rank simultaneous candidates by X+Y; 10 or 20 slots, cap 10% or 5% per stock and 25% per current sector; unallocated capital remains cash; rebalance weekly and on entries/exits; no leverage.',
        validationWarning='Retrospective temporal validation on current survivors. All 144 trials remain visible; OOS results are not independent prospective evidence.')
