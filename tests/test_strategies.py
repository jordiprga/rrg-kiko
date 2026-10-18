from dataclasses import replace, asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.strategy_data import (Bar, Source, Membership, SectorMembership, ResearchData, Delisting,
                                   audit, digest, load_research, period_calendar)
from scripts.strategy_engine import (Signal, detect, research_points, relative_volumes, cross_section,
                                     atr_values, simulate, suppress_overlaps, exit_candidates)
from scripts.strategy_stats import summary, portfolio, holm, bootstrap, choose_exit, walk_forward
from scripts.strategies import append_prospective, comparisons
from scripts.strategy_sources import inspect_candidates


def bar(day, close=100, opening=None, volume=1000, factor=1, split=1):
    opening = close if opening is None else opening
    return Bar(day, opening, max(opening, close) + 1, min(opening, close) - 1, close,
               close * factor, volume, day + "T22:30:00Z", "source", split=split, volume_basis='raw')


def signal(day="2020-01-06", **kwargs):
    return Signal("a" * 24, "A", "SPY", "daily", "turn-up", 1, day, day, day + "T22:30:00Z", 99, 99, **kwargs)


def test_four_entries_are_distinct_and_confirmation_is_later():
    days = [f"2020-01-{i:02d}" for i in range(1, 9)]
    rows = [[d, x, y, 100] for d, (x, y) in zip(days, [(98, 98), (97, 97), (96, 98), (97, 99), (98, 101), (99, 102), (101, 102), (102, 103)])]
    immediate = detect(rows, days, "A", "SPY", "daily")
    assert [(s.rule, s.date) for s in immediate] == [("turn-up", days[2]), ("turn-right", days[3]), ("lagging-improving", days[4]), ("improving-leading", days[6])]
    confirmed = detect(rows, days, "A", "SPY", "daily", 2)
    assert [(s.rule, s.origin_date, s.date) for s in confirmed] == [("turn-up", days[2], days[3]), ("lagging-improving", days[4], days[5]), ("improving-leading", days[6], days[7])]


def test_axis_bridge_is_one_cross_and_gap_breaks_it():
    days = ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09"]
    rows = [[d, 99, y, 100] for d, y in zip(days, [99, 100, 101, 102])]
    assert [s.rule for s in detect(rows, days, "A", "SPY", "daily")] == ["lagging-improving"]
    assert detect([rows[0], rows[2], rows[3]], days, "A", "SPY", "daily") == []


def test_future_never_changes_old_signals():
    days = pd.bdate_range("2020-01-01", periods=20).strftime("%Y-%m-%d").tolist()
    rows = [[d, 98 + np.sin(i), 98 + np.cos(i), 100] for i, d in enumerate(days)]
    old = detect(rows[:10], days[:10], "A", "SPY", "daily", 2)
    assert old == [s for s in detect(rows, days, "A", "SPY", "daily", 2) if s.date <= days[9]]


@pytest.mark.parametrize("tf,count", [("weekly", 110), ("daily", 500)])
def test_research_formula_causality_scale_and_identity(tf, count):
    days = pd.date_range("2010-01-01", periods=count, freq="W-FRI" if tf == "weekly" else "B").strftime("%Y-%m-%d").tolist()
    a = [bar(d, 100 + i * .2 + np.sin(i / 5)) for i, d in enumerate(days)]
    b = [bar(d, 100 + i * .1) for i, d in enumerate(days)]
    result = research_points(a, b, days, tf)
    same = research_points(a, a, days, tf)
    np.testing.assert_allclose([p[1:3] for p in same], 100, atol=1e-10)
    scaled = [replace(v, open=v.open * 10, high=v.high * 10, low=v.low * 10, close=v.close * 10, adjusted_close=v.adjusted_close * 10) for v in a]
    np.testing.assert_allclose([p[1:3] for p in result], [p[1:3] for p in research_points(scaled, b, days, tf)], atol=1e-10)
    cut = count - 20
    past = research_points(a[:cut], b[:cut], days[:cut], tf)
    assert past == [p for p in result if p[0] <= days[cut - 1]]


def test_missing_week_is_not_compressed_into_an_adjacent_signal():
    days = pd.date_range("2010-01-01", periods=100, freq="W-FRI").strftime("%Y-%m-%d").tolist()
    a = [bar(d, 100 + i) for i, d in enumerate(days) if i != 65]
    b = [bar(d) for d in days]
    points = research_points(a, b, days, "weekly")
    assert not any(days[65] <= p[0] <= days[99] for p in points)


def test_rvol_excludes_current_period_and_split_normalizes_shares():
    days = pd.bdate_range("2020-01-01", periods=25).strftime("%Y-%m-%d").tolist()
    bars = [bar(d, volume=1000 if i < 21 else 2000, split=2 if i == 21 else 1) for i, d in enumerate(days)]
    volumes = relative_volumes(bars, days, "daily")
    assert volumes[days[21]] == pytest.approx(1)
    bars[-1] = replace(bars[-1], volume=4000)
    assert relative_volumes(bars, days, "daily")[days[-1]] == pytest.approx(2)
    bars[-1] = replace(bars[-1], volume=None)
    assert relative_volumes(bars, days, "daily")[days[-1]] is None


def test_provider_split_adjusted_volume_is_not_adjusted_twice():
    days = pd.bdate_range('2020-01-01', periods=25).strftime('%Y-%m-%d').tolist()
    bars = [replace(bar(d, volume=2000, split=2 if i == 21 else 1), volume_basis='split-adjusted') for i,d in enumerate(days)]
    assert relative_volumes(bars, days, 'daily')[days[21]] == 1
    bars[-1] = replace(bars[-1], volume_basis='unknown')
    assert relative_volumes(bars, days, 'daily')[days[-1]] is None


def test_short_holiday_week_uses_volume_per_session():
    weeks = pd.date_range("2020-01-03", periods=12, freq="W-FRI").strftime("%Y-%m-%d").tolist()
    rows = [bar(d.strftime("%Y-%m-%d")) for end in weeks for d in pd.bdate_range(end=pd.Timestamp(end), periods=4 if end == weeks[-1] else 5)]
    assert relative_volumes(rows, weeks, "weekly")[weeks[-1]] == pytest.approx(1)


def test_percentiles_are_contemporaneous_and_reference_specific():
    rows = [dict(date="2020-01-01", reference="SPY", x=x, y=200-x, relativeVolume=None) for x in [98, 99, 100]]
    ranked = cross_section(rows)
    assert [r["xPercentile"] for r in ranked] == [0, 50, 100]
    assert all(r["relativeVolumePercentile"] is None for r in ranked)
    with pytest.raises(ValueError):
        cross_section([rows[0], {**rows[1], "reference": "XLK"}])


def test_trade_uses_next_open_and_exact_two_sided_costs():
    days = ["2020-01-06", "2020-01-07", "2020-01-08"]
    bars = [bar(days[0], 100), bar(days[1], 120, 110), bar(days[2], 121, 115)]
    result = simulate(signal(), bars, [], "fixed", 10, horizon_weeks=0, expected_sessions=days)
    assert (result["entryDate"], result["entryPrice"], result["exitDate"], result["exitPrice"]) == (days[1], 110, days[2], 115)
    assert result["netReturn"] == pytest.approx(115 * .999 / (110 * 1.001) - 1)
    assert result["mfe"] == pytest.approx(121 / 110 - 1)  # no exit-day high


def test_trailing_is_close_based_and_gap_fill_is_next_open():
    days = ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10"]
    bars = [bar(days[0]), bar(days[1], 120, 100), bar(days[2], 115), bar(days[3], 107), bar(days[4], 95, 90)]
    result = simulate(signal(), bars, [], "pct-10", expected_sessions=days)
    assert result["exitDate"] == days[4] and result["exitPrice"] == 90
    assert result["reason"] == "pct-10"


def test_atr_wilder_seed_and_monotone_stop():
    days = pd.bdate_range('2020-01-01', periods=30).strftime('%Y-%m-%d').tolist()
    rows = [bar(d) for d in days]
    assert atr_values(rows)[days[21]] == 2
    rows[25] = bar(days[25], close=105, opening=100)
    rows[26] = replace(bar(days[26], close=103), high=140, low=50)
    rows[27] = bar(days[27], close=100)
    rows[28] = bar(days[28], close=95)
    t = simulate(signal(days[24]), rows, [], 'atr-2', expected_sessions=days)
    assert t['exitDate'] == days[28] and t['reason'] == 'atr-2'


def test_combined_exit_uses_first_orbit_event():
    days = ['2020-01-06','2020-01-07','2020-01-08','2020-01-09']
    rows = [bar(d) for d in days]
    points = [[days[1],101,101,100],[days[2],101,99,100]]
    t = simulate(signal(), rows, points, 'pct-10+orbit', expected_sessions=days, point_calendar=days)
    assert t['exitDate'] == days[3] and t['reason'] == 'orbit'


def test_incomplete_or_missing_trade_is_never_zero_return():
    days = ["2020-01-06", "2020-01-07", "2020-01-08"]
    pending = simulate(signal(), [bar(days[0])], [], "orbit")
    missing = simulate(signal(), [bar(days[0]), bar(days[2])], [], "orbit", expected_sessions=days)
    assert pending["status"] == "pending" and pending["netReturn"] is None
    assert missing["status"] == "missing-data" and missing["netReturn"] is None
    assert summary([pending, missing])["total"] == 2
    assert summary([pending, missing])["mean"] is None


def test_delisting_uses_documented_payout_including_zero():
    days = ["2020-01-06", "2020-01-07", "2020-01-08"]
    bars = [bar(days[0]), bar(days[1], 100), bar(days[2], 20)]
    event = Delisting("A", days[-1], "2020-01-09", 0, "2020-01-09T22:00:00Z", "source")
    t = simulate(signal(), bars, [], "orbit", delisting=event, as_of="2020-01-10")
    assert t["status"] == "closed" and t["netReturn"] == -1 and t["exitPrice"] == 0
    assert t["reason"] == "delisting-settlement"


def test_adjusted_prices_do_not_count_dividend_twice():
    bars = [bar("2020-01-06", 100, factor=.9), bar("2020-01-07", 100, factor=.9),
            replace(bar("2020-01-08", 90), dividend=10), bar("2020-01-09", 90)]
    t = simulate(signal(), bars, [], "fixed", 0, horizon_weeks=0)
    assert t["netReturn"] == pytest.approx(0)


def test_overlap_suppression_keeps_records_and_prevents_pyramiding():
    original = dict(signalId="a", signalDate="2020-01-06", securityId="A", entryDate="2020-01-07", exitDate="2020-02-01", status="closed", netReturn=.1)
    later = {**original, "signalId": "b", "signalDate": "2020-01-08"}
    rows = suppress_overlaps([later, original])
    assert len(rows) == 2 and rows[1]["status"] == "suppressed" and rows[1]["netReturn"] is None


def test_portfolio_accounts_for_entry_drift_and_liquidation_costs():
    days = ["2020-01-06", "2020-01-07", "2020-01-08"]
    t = dict(signalId="a", signalDate="2020-01-05", securityId="A", entryDate=days[0], exitDate=days[-1], status="closed", reason="horizon")
    curve = portfolio([t], {"A": [bar(d, close=p) for d, p in zip(days, [100, 110, 100])]}, days, 10)
    assert curve["totalReturn"] == pytest.approx(.999 ** 2 - 1)
    assert curve["turnover"] == pytest.approx(2)


def test_missing_portfolio_price_invalidates_curve():
    t = dict(status="open", securityId="A", entryDate="2020-01-06", exitDate=None)
    assert portfolio([t], {"A": [bar("2020-01-06")]}, ["2020-01-06", "2020-01-07"], 10)["status"] == "not-evaluable"


def test_portfolio_includes_last_day_entry_cost_and_close_valuation():
    day = '2020-01-06'
    t = dict(status='open', securityId='A', entryDate=day, exitDate=None)
    curve = portfolio([t], {'A':[bar(day, close=110, opening=100)]}, [day], 10)
    assert curve['totalReturn'] == pytest.approx(.999 * 1.1 - 1)
    assert curve['turnover'] == 1


def test_portfolio_zero_terminal_payout_does_not_recover_or_divide_by_zero():
    days = ['2020-01-06','2020-01-07','2020-01-08']
    t = dict(status='closed', securityId='A', entryDate=days[0], exitDate=days[1], exitPrice=0, reason='delisting-settlement')
    curve = portfolio([t], {'A':[bar(days[0])]}, days, 10)
    assert curve['totalReturn'] == -1 and curve['maxDrawdown'] == -1
    assert curve['equity'][-1][1] == 0


def test_holm_includes_missing_registered_comparisons():
    assert holm([.01, .04, None, .03]) == [.04, .09, None, .09]


def test_exit_selection_uses_risk_then_turnover_within_tolerance():
    rows = [dict(exitRule="a", sharpes=[1, 1, 1], maxDrawdown=-.2, turnover=1),
            dict(exitRule="b", sharpes=[.98, .98, .98], maxDrawdown=-.1, turnover=2)]
    assert choose_exit(rows) == "b"
    assert choose_exit([{**rows[0], "sharpes": [None, 1, 1]}]) is None


def test_bootstrap_uses_calendar_blocks_and_does_not_count_trades_as_independent():
    rows = [dict(status="closed", signalDate=d.strftime("%Y-%m-%d"), excessMarket=.02) for d in pd.date_range("2010-01-01", periods=160, freq="W-FRI")]
    result = bootstrap(rows, "excessMarket", replicates=30)
    assert result["interval"] == pytest.approx([.02, .02])
    assert bootstrap(rows[:20], "excessMarket")["interval"] is None
    rows.append(dict(status='closed', signalDate='2014-01-01', excessMarket=None))
    assert bootstrap(rows, 'excessMarket')['interval'] is None
    assert bootstrap(rows, 'excessMarket')['missing'] == 1


def test_no_input_is_not_evaluable():
    result = audit(None, pd.Timestamp("2026-10-18", tz="UTC"))
    assert result["status"] == "not-evaluable" and len(result["issues"]) == 4
    assert result["publicationAllowed"] is False


@pytest.fixture
def bundle():
    days = ["2020-01-06", "2020-01-07", "2020-01-08"]
    source = Source("source", "https://example.org/evidence", "2026-10-18T00:00:00Z", "a" * 64, verified=True, role='primary')
    data = ResearchData(1, days[0], days[-1], [{"id": "A", "delisted": False}],
        [Membership("A", days[0], None, "2020-01-01T00:00:00Z", "source")],
        [SectorMembership("A", days[0], None, "2020-01-01T00:00:00Z", "source", "Technology", "XLK")],
        {s: [bar(d) for d in days] for s in ["A", "SPY", "XLK"]}, [], [source],
        [dict(date=d, members=["A"], source_id="source", evidence_hash="a" * 64) for d in days])
    return data


def test_audit_rejects_sector_lookahead_unknown_identity_and_missing_bars(bundle):
    now = pd.Timestamp("2026-10-18", tz="UTC")
    assert audit(bundle, now, minimum_members=1)["status"] == "eligible"
    bundle.sectors[0] = replace(bundle.sectors[0], available_at="2020-02-01T00:00:00Z")
    assert "sectors" in {i["code"] for i in audit(bundle, now)["issues"]}
    bundle.bars["A"].pop()
    assert "missing-bar" in {i["code"] for i in audit(bundle, now)["issues"]}


def test_a_partial_stock_list_cannot_certify_the_sp500(bundle):
    assert any(i['code'] == 'universe-size' for i in audit(bundle, pd.Timestamp('2026-10-18', tz='UTC'))['issues'])


def test_weekly_calendar_does_not_close_a_week_at_a_truncated_wednesday():
    days = period_calendar('2026-10-01', '2026-10-14', pd.Timestamp('2026-10-14T23:00:00Z'), 'weekly')
    assert days[-1] == '2026-10-09'


def test_delayed_quote_cannot_execute_before_its_available_time():
    days = ['2020-01-06', '2020-01-07', '2020-01-08', '2020-01-09']
    s = replace(signal(), available_at='2020-01-07T20:00:00Z')
    opens = {d:d+'T14:30:00Z' for d in days}
    t = simulate(s, [bar(d) for d in days], [], 'fixed', 0, horizon_weeks=0, expected_sessions=days, open_times=opens)
    assert t['entryDate'] == '2020-01-08' and t['exitDate'] == '2020-01-09'


def test_audit_does_not_drop_delisted_members(bundle):
    bundle.securities[0]["delisted"] = True
    result = audit(bundle, pd.Timestamp("2026-10-18", tz="UTC"))
    assert any(i["code"] == "delistings" for i in result["issues"])


def test_bundle_round_trip_preserves_identity_and_provenance(bundle, tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(asdict(bundle)))
    assert load_research(path).snapshot_hash == bundle.snapshot_hash


def test_membership_and_sector_intervals_are_effective_not_current():
    m = Membership("A", "2020-01-06", "2020-02-01", "2020-01-01T00:00:00Z", "source")
    assert not m.contains("2020-01-03") and m.contains("2020-01-06") and not m.contains("2020-02-01")


def test_prospective_is_append_only_deduplicated_and_rejects_backfill(tmp_path):
    path = tmp_path / "registry.jsonl"
    p = dict(frozenOn="2026-10-18")
    old = asdict(signal("2025-06-06"))
    new = asdict(signal("2026-10-19"))
    observed = "2026-10-20T05:00:00Z"
    assert append_prospective(path, [old, new], "c" * 64, p, observed)["count"] == 1
    assert json.loads(path.read_text())['executionAvailableAt'] == observed
    original = path.read_bytes()
    assert append_prospective(path, [new], "c" * 64, p, observed)["added"] == 0
    assert path.read_bytes() == original
    path.write_text(path.read_text().replace('"security_id": "A"', '"security_id": "B"'))
    with pytest.raises(ValueError, match="alterado"):
        append_prospective(path, [], "c" * 64, p, observed)


def test_free_candidate_is_not_certified():
    result = inspect_candidates(b"ticker,start_date,end_date\nA,2010-01-01,2020-01-01\nB,2020-01-01,\n")
    assert result["tickersSince2010"] == 2 and result["stableIdentitiesVerified"] is False


def test_rut_known_case_and_thursday_cannot_see_friday():
    path = Path("public/data/market.json")
    if not path.exists():
        pytest.skip("El snapshot real local no se distribuye en Git")
    market = json.loads(path.read_text(encoding="utf-8"))
    points = market["views"]["GSPC"]["weekly"]["assets"]["RUT"]
    days = period_calendar(points[0][0], market["latestSession"], pd.Timestamp(market["generatedAt"]), "weekly")
    events = {(s.rule, s.date) for s in detect(points, days, "RUT", "GSPC", "weekly")}
    assert ("turn-up", "2025-04-25") in events
    assert ("turn-right", "2025-05-09") in events
    assert ("lagging-improving", "2025-06-06") in events
    past = [p for p in points if p[0] <= "2025-06-05"]
    assert past[-1][0] == "2025-05-30"
    assert not any(s.date == "2025-06-06" for s in detect(past, days, "RUT", "GSPC", "weekly"))


def test_full_suite_handles_audited_but_insufficient_history_without_a_false_winner(bundle):
    from scripts.strategies import run_study, PROTOCOL_PATH
    template = bundle.securities[0]
    rows = bundle.bars['A']
    ids = [f'TEST{i:04d}' for i in range(480)]
    bundle.securities = [dict(template, id=i) for i in ids]
    bundle.memberships = [replace(bundle.memberships[0], security_id=i) for i in ids]
    bundle.sectors = [replace(bundle.sectors[0], security_id=i) for i in ids]
    bundle.bars = {**bundle.bars, **{i: rows for i in ids}}
    for row in bundle.universe_ledger:
        row['members'] = ids
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding='utf-8'))
    protocol['confirmations'] = [1]
    protocol['bootstrapReplicates'] = 5
    result = run_study(bundle, pd.Timestamp('2026-10-18', tz='UTC'), protocol)
    assert result['audit']['status'] == 'eligible'
    assert len(result['variants']) == 64
    assert all(v['conclusion'] == 'inconclusive' for v in result['variants'])
    assert not result['signals']


def test_failed_research_refresh_preserves_last_valid_manifest(tmp_path, monkeypatch):
    from scripts import strategies
    protocol = json.loads(strategies.PROTOCOL_PATH.read_text(encoding='utf-8'))
    out = tmp_path / 'public'
    out.mkdir()
    manifest = dict(stockStudyUrl='abc/study.json', protocolHash=digest(protocol), studyState='published')
    path = out / 'manifest.json'
    path.write_text(json.dumps(manifest))
    previous = path.read_bytes()
    monkeypatch.setattr(strategies, 'ROOT', tmp_path)
    assert strategies.build(out, now=pd.Timestamp('2026-10-18', tz='UTC')) == manifest
    assert path.read_bytes() == previous
    assert json.loads((out/'refresh-status.json').read_text())['ok'] is False


def test_walk_forward_selection_is_unchanged_when_future_prices_change():
    days = pd.bdate_range('2010-01-04', '2017-12-29').strftime('%Y-%m-%d').tolist()
    rows, price = [], 100
    for i, day in enumerate(days):
        month = int(day[5:7])
        price *= 1 + (.002 if month <= 6 else -.001) + .0005 * np.sin(i)
        rows.append(bar(day, price))
    candidates = {'first-half':[], 'second-half':[]}
    for year in range(2010,2018):
        for name, first, last in [('first-half',f'{year}-01',f'{year}-06'),('second-half',f'{year}-07',f'{year}-12')]:
            entry = next(d for d in days if d.startswith(first))
            end = [d for d in days if d.startswith(last)][-1]
            candidates[name].append(dict(signalId=f'{name}-{year}', signalDate=entry, securityId='A', entryDate=entry,
                exitDate=end, status='closed', netReturn=.01, reason='horizon'))
    old = walk_forward(candidates, {'A':rows}, days, 10)
    changed = [replace(r, open=r.open*2, high=r.high*2, low=r.low*2, close=r.close*2, adjusted_close=r.adjusted_close*2) if r.date >= '2015-01-01' else r for r in rows]
    new = walk_forward(candidates, {'A':changed}, days, 10)
    assert old['folds'][0]['chosenExit'] == 'first-half'
    assert old['folds'][0]['candidates'] == new['folds'][0]['candidates']


def test_walk_forward_requires_full_training_years_and_recognizes_last_market_day():
    days = pd.bdate_range('2010-07-01', '2022-12-30').strftime('%Y-%m-%d').tolist()
    result = walk_forward({}, {}, days, 10)
    assert result['folds'][0]['testStart'] == '2016-01-01'
    assert result['folds'][-1]['complete'] is True


def test_study_pipeline_simulates_real_signals_and_keeps_incomplete_trades(bundle, monkeypatch):
    # Isolate the numerical pipeline with synthetic bars. Production audit still
    # requires the full universe; this fixture is never written to public/data.
    from scripts import strategies
    import exchange_calendars as xcals
    sessions = xcals.get_calendar('XNYS', start='2018-01-01', end='2020-12-31').sessions
    days = [d.date().isoformat() for d in sessions]
    bundle.start, bundle.end = days[0], days[-1]
    bundle.memberships[0] = replace(bundle.memberships[0], start=days[0], available_at='2017-01-01T00:00:00Z')
    bundle.sectors[0] = replace(bundle.sectors[0], start=days[0], available_at='2017-01-01T00:00:00Z')
    bundle.bars = {'A':[bar(d, 100 + i*.01 + 15*np.sin(i/23)) for i,d in enumerate(days)],
                   'SPY':[bar(d,100 + i*.02) for i,d in enumerate(days)],
                   'XLK':[bar(d,100 + i*.03) for i,d in enumerate(days)]}
    monkeypatch.setattr(strategies, 'audit', lambda *args: dict(status='eligible'))
    protocol = json.loads(strategies.PROTOCOL_PATH.read_text(encoding='utf-8'))
    protocol.update(confirmations=[1], sectorFilters=[False], volumeFilters=[None], bootstrapReplicates=5)
    result = strategies.run_study(bundle, pd.Timestamp('2021-01-01', tz='UTC'), protocol)
    assert result['signals']
    trades = [t for by_exit in result['details'].values() for t in by_exit.values()]
    assert any(t['status'] == 'closed' for t in trades)
    assert any(t['status'] == 'open' and t['netReturn'] is None for t in trades)
    assert all(v['conclusion'] == 'inconclusive' for v in result['variants'])
