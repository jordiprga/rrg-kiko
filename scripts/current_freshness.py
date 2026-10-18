"""Reuse calculated reports, never cache original stock prices publicly."""
import json
import os
from pathlib import Path
import urllib.request
from hashlib import sha256

from scripts.market import ROOT
from scripts.current_universe import CATALOG_URL
from scripts.strategy_data import digest


def current_report_is_fresh(root: Path=ROOT, catalog_bytes: bytes|None=None) -> bool:
    try:
        folder=root/'public/data/strategies'
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        route=manifest.get('currentStudyUrl','')
        if not route or '..' in route or route.startswith('/'): return False
        report=json.loads((folder/route).read_text(encoding='utf-8'))
        if report.get('version')!=2 or report.get('scope')!='current-constituents': return False
        market=json.loads((root/'public/data/market.json').read_text(encoding='utf-8'))
        names=['current_study.py','strategy_allocation.py','strategy_data.py','strategy_engine.py','strategy_stats.py']
        code_hash=digest({name:(root/'scripts'/name).read_text(encoding='utf-8') for name in names})
        if report.get('engineHash')!=code_hash or report.get('latestSession')!=market['latestSession']: return False
        if report.get('universeCount',0)<490 or len(report.get('allocations',{}).get('candidates',[]))!=144: return False
        if any(report.get('cohortBenchmarkPeriods',{}).get(p,{}).get('status')!='ok' for p in ['train','validation','test']): return False
        if catalog_bytes is None:
            request=urllib.request.Request(CATALOG_URL,headers={'User-Agent':'Orbita/1.0'})
            catalog_bytes=urllib.request.urlopen(request,timeout=30).read(2_000_000)
        return report['sources'][0]['hash']==sha256(catalog_bytes).hexdigest()
    except (OSError,ValueError,KeyError,TypeError):
        return False


if __name__=='__main__':
    fresh=current_report_is_fresh()
    line='needed='+str(not fresh).lower()
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as target: target.write(line+'\n')
    print(line,flush=True)
