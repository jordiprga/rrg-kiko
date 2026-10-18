import json
from hashlib import sha256

from scripts.current_freshness import current_report_is_fresh
from scripts.strategy_data import digest


def test_reuse_requires_same_calculation_universe_and_closed_session(tmp_path):
    folder=tmp_path/'public/data/strategies/run';folder.mkdir(parents=True)
    scripts=tmp_path/'scripts';scripts.mkdir()
    names=['current_study.py','strategy_allocation.py','strategy_data.py','strategy_engine.py','strategy_stats.py']
    for name in names:(scripts/name).write_text('# frozen calculation\n')
    code=digest({name:'# frozen calculation\n' for name in names})
    report=dict(version=2,scope='current-constituents',engineHash=code,latestSession='2026-10-16',universeCount=503,
        allocations=dict(candidates=[{}]*144),sources=[dict(hash=sha256(b'catalog').hexdigest())],
        cohortBenchmarkPeriods={p:dict(status='ok') for p in ['train','validation','test']})
    (folder/'current-study.json').write_text(json.dumps(report))
    (folder.parent/'manifest.json').write_text(json.dumps(dict(currentStudyUrl='run/current-study.json')))
    market=tmp_path/'public/data/market.json';market.write_text(json.dumps(dict(latestSession='2026-10-16')))
    assert current_report_is_fresh(tmp_path,b'catalog')
    assert not current_report_is_fresh(tmp_path,b'changed universe')
    market.write_text(json.dumps(dict(latestSession='2026-10-19')))
    assert not current_report_is_fresh(tmp_path,b'catalog')
    market.write_text(json.dumps(dict(latestSession='2026-10-16')))
    (scripts/'strategy_allocation.py').write_text('# different selection rule\n')
    assert not current_report_is_fresh(tmp_path,b'catalog')


def test_incomplete_or_wrong_scope_reports_are_never_reused(tmp_path):
    assert not current_report_is_fresh(tmp_path,b'catalog')
