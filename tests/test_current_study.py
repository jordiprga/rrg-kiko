from copy import deepcopy
import math
import json

import numpy as np
import pandas as pd
import pytest

from scripts.current_study import FastMarket, fast_trade, metrics, prepare_trades, orbit_exits, EXITS
from scripts.strategy_allocation import Allocator, capped_weights, policies, select_candidate
from scripts.strategy_data import Bar
from scripts.strategy_engine import Signal, simulate
from scripts.strategy_stats import portfolio
from scripts.current_universe import supplement_fiserv


def market_fixture():
    dates=pd.bdate_range('2020-01-01',periods=400).strftime('%Y-%m-%d').tolist()
    bars={}
    for name,scale in [('A',1.),('B',2.),('SPY',1.4)]:
        bars[name]=[Bar(d,(100+i*.08+3*math.sin(i/13))*scale,(104+i*.08+3*math.sin(i/13))*scale,
            (96+i*.08+3*math.sin(i/13))*scale,(101+i*.08+3*math.sin(i/13))*scale,
            (101+i*.08+3*math.sin(i/13))*scale,1000,d+'T22:00:00Z','fixture',volume_basis='split-adjusted') for i,d in enumerate(dates)]
    return dates,bars,FastMarket(bars,dates,['A','B'])


@pytest.mark.parametrize('rule',['time-13','time-26','pct-10','pct-15+orbit','atr-3','atr-3+orbit','orbit'])
def test_fast_event_matches_independent_reference(rule):
    dates,bars,market=market_fixture()
    signal=Signal('a'*24,'A','SPY','weekly','lagging-improving',1,dates[30],dates[30],dates[30]+'T23:59:59Z',99,101)
    points=[[d,101,101 if i<20 else 99,100] for i,d in enumerate(dates[::5])]
    atr={d:5. for d in dates}
    fast=fast_trade(signal,market,points,rule,atr)
    reference=simulate(signal,bars['A'],points,rule,expected_sessions=dates,prepared_atr=atr)
    for key in ['status','entryDate','exitDate']: assert fast[key]==reference[key]
    for key in ['netReturn','entryPrice','exitPrice','mfe','mae']:
        assert fast[key]==pytest.approx(reference[key])


def test_vector_portfolio_preserves_overnight_drift_and_rebalancing_costs():
    dates,bars,market=market_fixture()
    trades=[dict(securityId='A',entryDate=dates[1],exitDate=dates[120],status='closed'),
        dict(securityId='B',entryDate=dates[10],exitDate=None,status='open')]
    expected=portfolio(trades,bars,dates,10)
    actual=market.portfolio(trades,start=dates[0])
    assert actual['totalReturn']==pytest.approx(expected['totalReturn'])
    assert actual['sharpe']==pytest.approx(expected['sharpe'])
    assert actual['maxDrawdown']==pytest.approx(expected['maxDrawdown'])
    assert actual['turnover']==pytest.approx(expected['turnover'])


def test_cagr_includes_cash_days_and_uses_calendar_time():
    m=metrics([['2020-01-01',0.],['2021-01-01',.1]])
    assert m['totalReturn']==pytest.approx(.1)
    assert m['cagr']==pytest.approx(1.1**(365.25/366)-1)


def test_missing_price_does_not_become_a_zero_return():
    dates,bars,_=market_fixture();bars['A']=[b for b in bars['A'] if b.date!=dates[20]]
    market=FastMarket(bars,dates,['A','B'])
    t=dict(securityId='A',entryDate=dates[1],exitDate=None,status='open')
    assert market.portfolio([t],start=dates[0])['status']=='not-evaluable'


def test_position_and_sector_caps_leave_residual_cash():
    config=policies()[0]
    weights=capped_weights(['A','B'],{'A':.1,'B':.2},{'A':'Technology','B':'Technology'},config)
    assert weights=={'A':.05,'B':.05}
    assert sum(weights.values())==pytest.approx(.1)
    names=[str(i) for i in range(20)]
    weights=capped_weights(names,{s:.2 for s in names},{s:'Technology' for s in names},config)
    assert sum(weights.values())==pytest.approx(.25)
    assert max(weights.values())<=.05


def test_out_of_sample_returns_cannot_change_locked_selection():
    candidates=[dict(id=str(i),selectionScore=float(i),periods=dict(validation=dict(status='ok',sharpe=float(i),maxDrawdown=-.2,turnover=4),test=dict(sharpe=0))) for i in range(6)]
    first=select_candidate(candidates)[1]['id']
    changed=deepcopy(candidates)
    changed[0]['periods']['test']['sharpe']=999
    changed[5]['periods']['test']['sharpe']=-999
    assert select_candidate(changed)[1]['id']==first
    assert len(policies())==144


def test_adding_future_prices_preserves_closed_trade():
    dates,bars,market=market_fixture()
    signal=Signal('a'*24,'A','SPY','weekly','lagging-improving',1,dates[30],dates[30],dates[30]+'T23:59:59Z',99,101)
    earlier=FastMarket({s:v[:200] for s,v in bars.items()},dates[:200],['A','B'])
    assert fast_trade(signal,earlier,[],'time-13',{})==fast_trade(signal,market,[],'time-13',{})


def test_compact_preparation_matches_all_reference_exits():
    dates,bars,market=market_fixture();market.sectors={'A':'SPY','B':'SPY'}
    signal=Signal('a'*24,'A','SPY','weekly','lagging-improving',1,dates[30],dates[30],dates[30]+'T23:59:59Z',99,101)
    points=[[d,101,101 if i<20 else 99,100] for i,d in enumerate(dates[::5])]
    atr={d:5. for d in dates}
    prepared=prepare_trades(signal,market,orbit_exits(points),atr)
    for rule in EXITS:
        fast=prepared[rule];reference=fast_trade(signal,market,points,rule,atr)
        for key in ['status','entryDate','exitDate']:assert fast[key]==reference[key]
        for key in ['netReturn','mfe','mae']:assert fast[key]==pytest.approx(reference[key])


def test_missing_vendor_session_uses_sourced_bar_not_forward_fill(tmp_path):
    (tmp_path/'prices').mkdir();(tmp_path/'evidence').mkdir()
    before=['2025-11-10',63.91,64.18,62.67,63.80,63.80,8431600,0,1]
    after=['2025-11-13',64.85,66.95,64.37,64.53,64.53,9274500,0,1]
    last=['2025-11-14',64.,64.15,63.02,63.42,63.42,5596500,0,1]
    data=dict(bars=[before,after,last])
    path=tmp_path/'prices/FISV.json';path.write_text(json.dumps(data))
    evidence=dict(url='https://www.quiverquant.com/stock/FISV/historical-prices/',contentHash='a'*64,
        rows={'2025-11-10':before[1:7],'2025-11-13':after[1:7],'2025-11-14':last[1:7],
              '2025-11-12':[64.2,64.87,63.11,64.38,64.38,6244651]})
    (tmp_path/'evidence/fisv-supplement.json').write_text(json.dumps(evidence))
    supplement_fiserv(tmp_path);supplement_fiserv(tmp_path)
    result=json.loads(path.read_text())
    assert len(result['bars'])==4
    assert result['bars'][1][1:7]==[64.2,64.87,63.11,64.38,64.38,6244651]
    assert result['sourceOverrides']['2025-11-12']=='quiver-fisv-supplement'
    assert len(result['corrections'])==1


def test_allocator_starts_cash_obeys_caps_and_records_the_period_end():
    dates,bars,_=market_fixture()
    for identity in ['QQQ','DIA','IWM']:bars[identity]=bars['SPY']
    market=FastMarket(bars,dates,['A','B']);market.sectors={'A':'SPY','B':'SPY'}
    signal=Signal('a'*24,'A','SPY','weekly','lagging-improving',1,dates[250],dates[250],dates[250]+'T23:59:59Z',99,101)
    prepared={signal.id:prepare_trades(signal,market,set(),{d:4 for d in dates})}
    engine=Allocator(market,[dict(id='A',sector='Technology'),dict(id='B',sector='Financials')],{('A','SPY'):[signal]},prepared)
    policy={**policies()[0],'rule':'lagging-improving','exitRule':'time-13','regime':False,'sectorFilter':False}
    result=engine.run(policy,start=dates[230],end=dates[300])
    assert result['returns'][0][1]==0
    assert result['metrics']['maxWeightAtRebalance']<=.05+1e-12
    assert result['lastHoldings']['date']==dates[300]
    assert sum(p['weight'] for p in result['lastHoldings']['positions'])+result['lastHoldings']['cash']==pytest.approx(1)
    assert result['metrics']['equity'][-1][1]==pytest.approx(np.prod([1+r for _,r in result['returns']]))
