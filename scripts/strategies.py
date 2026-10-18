"""Build the research laboratory; never promote an unaudited universe.

python -m scripts.strategies
python -m scripts.strategies --input .cache/strategies/input.json
All detailed stock research stays private unless every source permits publication.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from scripts.market import ROOT, atomic_json
from scripts.strategy_data import ResearchData, audit, digest, load_research, period_calendar
from scripts.strategy_engine import (ENTRY_NAMES, Signal, cross_section, detect, exit_candidates, quadrant,
                                     relative_volumes, research_points, simulate, suppress_overlaps, atr_values)
from scripts.strategy_stats import bootstrap, holm, portfolio, summary, walk_forward

PROTOCOL_PATH = ROOT / "research/strategies/protocol.json"
SOURCES_PATH = ROOT / "research/strategies/sources.json"


def engine_hash() -> str:
    return digest({name: (ROOT / 'scripts' / name).read_text(encoding='utf-8') for name in
                   ['strategies.py', 'strategy_engine.py', 'strategy_data.py', 'strategy_stats.py']})


def known_availability(data: ResearchData, identities: list[str], days: list[str]) -> dict[str, str]:
    result = {}
    rows = sorted((b for identity in identities for b in data.bars.get(identity, [])), key=lambda b: b.date)
    latest, cursor = "", 0
    for day in days:
        while cursor < len(rows) and rows[cursor].date <= day:
            latest = max(latest, rows[cursor].available_at)
            cursor += 1
        result[day] = latest or day + "T23:59:59Z"
    return result


def stock_signals(data: ResearchData, tf: str, reference_type: str, confirmation: int,
                  now: pd.Timestamp) -> tuple[list[Signal], dict, list[str]]:
    earliest = min(b.date for rows in data.bars.values() for b in rows)
    calendar = period_calendar(earliest, data.end, now, tf)
    weeks = period_calendar(earliest, data.end, now, "weekly")
    sector_etfs = sorted({s.etf for s in data.sectors})
    strength = {etf: research_points(data.bars.get(etf, []), data.bars["SPY"], weeks, "weekly") for etf in sector_etfs}
    strength_availability = {etf: known_availability(data, [etf, 'SPY'], weeks) for etf in sector_etfs}
    points_by_pair, signals, volume_by_id = {}, [], {}
    for security in data.securities:
        identity = security["id"]
        refs = ["SPY"] if reference_type == "market" else sorted({s.etf for s in data.sectors if s.security_id == identity})
        volumes = relative_volumes(data.bars.get(identity, []), calendar, tf)
        volume_by_id[identity] = volumes
        for ref in refs:
            points = research_points(data.bars.get(identity, []), data.bars.get(ref, []), calendar, tf)
            if reference_type == "sector":
                points = [p for p in points if (s := data.sector_at(identity, p[0])) is not None and s.etf == ref]
            points_by_pair[identity, ref] = points
            availability = known_availability(data, [identity, ref], calendar)
            events = detect(points, calendar, identity, ref, tf, confirmation, availability)
            for signal in events:
                if signal.date < data.start or not data.member(identity, signal.date):
                    continue
                sector = data.sector_at(identity, signal.date)
                previous = [p for p in strength.get(sector.etf if sector else "", []) if p[0] <= signal.date]
                p = previous[-1] if previous else None
                strong = quadrant(*p[1:3]) == "leading" if p else None
                available = signal.available_at
                if sector:
                    available = max(available, sector.available_at)
                if p and sector:
                    available = max(available, strength_availability[sector.etf][p[0]])
                signals.append(replace(signal, sector=sector.sector if sector else None,
                                       sector_strong=strong, relative_volume=volumes.get(signal.date), available_at=available))
    pools = {}
    for (identity, ref), points in points_by_pair.items():
        for p in points:
            if data.member(identity, p[0]):
                pools.setdefault((p[0], ref), []).append(dict(securityId=identity, date=p[0], reference=ref,
                    x=p[1], y=p[2], relativeVolume=volume_by_id[identity].get(p[0])))
    ranks = {(r['securityId'], r['date'], r['reference']): r for pool in pools.values() for r in cross_section(pool)}
    signals = [replace(s, x_percentile=r['xPercentile'], y_percentile=r['yPercentile'], volume_percentile=r['relativeVolumePercentile'],
                       zone=tuple(r['zone']), percentile_count=len(pools[s.date, s.reference]))
               for s in signals if (r := ranks.get((s.security_id, s.date, s.reference))) is not None]
    return signals, points_by_pair, calendar


def comparable_return(data: ResearchData, identity: str, entry: str, end: str) -> float | None:
    lookup = {b.date: b for b in data.bars.get(identity, [])}
    if entry not in lookup:
        return None
    first = lookup[entry].adjusted_open
    if end in lookup:
        return lookup[end].adjusted_open / first - 1
    payout = next((d for d in data.delistings if d.security_id == identity and entry <= d.last_trading_date and d.settlement_date <= end), None)
    if payout and payout.last_trading_date in lookup:
        return payout.settlement_price * lookup[payout.last_trading_date].factor / first - 1
    return None


def comparisons(trade: dict, signal: Signal, data: ResearchData, eligible_peers: set[str] | None = None) -> dict:
    if trade["status"] != "closed":
        return trade
    entry, end = trade["entryDate"], trade["exitDate"]
    cost = trade["costBps"] / 10000
    def net(r):
        return (1 + r) * (1 - cost) / (1 + cost) - 1 if r is not None else None
    market = net(comparable_return(data, "SPY", entry, end))
    sector = data.sector_at(signal.security_id, signal.date)
    sector_return = net(comparable_return(data, sector.etf, entry, end)) if sector else None
    peers = [s["id"] for s in data.securities if s["id"] != signal.security_id and data.member(s["id"], signal.date)
             and (eligible_peers is None or s['id'] in eligible_peers)
             and (other := data.sector_at(s["id"], signal.date)) is not None and sector is not None and other.sector == sector.sector]
    peer_returns = [net(comparable_return(data, s, entry, end)) for s in peers]
    peer = sum(peer_returns) / len(peer_returns) if peer_returns and all(r is not None for r in peer_returns) else None
    return {**trade, "marketReturn": market, "sectorReturn": sector_return, "peerReturn": peer,
            "peerCount": len(peers), "excessMarket": trade["netReturn"] - market if market is not None else None,
            "excessSector": trade["netReturn"] - sector_return if sector_return is not None else None,
            "excessPeers": trade["netReturn"] - peer if peer is not None else None}


def run_study(data: ResearchData, now: pd.Timestamp, protocol: dict) -> dict:
    coverage = audit(data, now)
    if coverage["status"] != "eligible":
        raise ValueError("El universo no supera la auditoría; no se calcula una muestra de supervivientes")
    daily = period_calendar(data.start, data.end, now, "daily")
    import exchange_calendars as xcals
    schedule = xcals.get_calendar("XNYS", start=data.start, end=data.end).schedule
    opens = {d.date().isoformat(): value.isoformat() for d, value in schedule["open"].items()}
    delistings = {d.security_id: d for d in data.delistings}
    atr = {s: atr_values(rows) for s, rows in data.bars.items()}
    variants, signal_rows, all_details = [], {}, {}
    for tf in ("weekly", "daily"):
        for ref_type in ("market", "sector"):
            for confirmation in protocol["confirmations"]:
                signals, pairs, point_calendar = stock_signals(data, tf, ref_type, confirmation, now)
                signal_rows.update({s.id: asdict(s) for s in signals})
                eligible = {}
                for (identity, ref), observations in pairs.items():
                    for p in observations:
                        if data.member(identity, p[0]):
                            eligible.setdefault((ref, p[0]), set()).add(identity)
                raw = {}
                for signal in signals:
                    by_exit = {}
                    for exit_rule in [*exit_candidates(), *[f"fixed-{h}" for h in protocol["horizonsWeeks"]]]:
                        fixed = exit_rule.startswith("fixed-")
                        t = simulate(signal, data.bars[signal.security_id], pairs[signal.security_id, signal.reference],
                                     "fixed" if fixed else exit_rule, protocol["primaryCostBps"],
                                     int(exit_rule.split("-")[1]) if fixed else None,
                                     daily, delistings.get(signal.security_id), opens, data.end,
                                     point_calendar, atr[signal.security_id])
                        # Eligibility must still hold at the actual next-open entry.
                        if t["entryDate"]:
                            sector_entry = data.sector_at(signal.security_id, t['entryDate'])
                            if not data.member(signal.security_id, t['entryDate']):
                                t = {**t, 'status':'suppressed', 'netReturn':None, 'reason':'not-member-at-entry'}
                            elif sector_entry is None or sector_entry.sector != signal.sector:
                                t = {**t, 'status':'suppressed', 'netReturn':None, 'reason':'sector-changed-before-entry'}
                        by_exit[exit_rule] = comparisons(t, signal, data, eligible.get((signal.reference, signal.date), set()))
                    raw[signal.id] = by_exit
                    all_details[signal.id] = by_exit
                for rule in protocol["entries"]:
                    for sector_filter in protocol["sectorFilters"]:
                        for volume_filter in protocol["volumeFilters"]:
                            selected = [s for s in signals if s.rule == rule
                                        and (not sector_filter or s.sector_strong is True)
                                        and (volume_filter is None or (s.relative_volume is not None and s.relative_volume >= volume_filter))]
                            candidates = {exit_rule: [raw[s.id][exit_rule] for s in selected] for exit_rule in exit_candidates()}
                            wf = walk_forward(candidates, data.bars, daily, protocol["primaryCostBps"])
                            horizons = {str(h): summary([raw[s.id][f"fixed-{h}"] for s in selected]) for h in protocol["horizonsWeeks"]}
                            fixed = [raw[s.id]["fixed-13"] for s in selected]
                            evidence = bootstrap(fixed, "excessMarket", protocol["bootstrapReplicates"], protocol["randomSeed"])
                            primary = tf == "weekly" and confirmation == 1 and not sector_filter and volume_filter is None
                            oid = digest([tf, ref_type, confirmation, rule, sector_filter, volume_filter])[:16]
                            stress = {}
                            for cost in protocol["costBps"]:
                                stress[str(cost)] = portfolio(wf["trades"], data.bars,
                                    [d for d in daily if not wf["folds"] or d >= wf["folds"][0]["testStart"]], cost)
                            uncertainty = bootstrap(wf["trades"], "excessMarket", protocol["bootstrapReplicates"], protocol["randomSeed"])
                            complete_years = sum(f["complete"] and f["chosenExit"] is not None for f in wf["folds"])
                            stats = summary(wf["trades"])
                            variants.append(dict(id=oid, timeframe=tf, reference=ref_type, confirmation=confirmation, rule=rule,
                                sectorFilter=sector_filter, volumeFilter=volume_filter, primary=primary,
                                summary=stats, horizons=horizons, entryEvidence=evidence, exitEvidence=uncertainty,
                                walkForward=wf, costs=stress, completeTestYears=complete_years, conclusion="inconclusive"))
    primary_rows = [r for r in variants if r["primary"]]
    adjusted = holm([r["exitEvidence"]["pValue"] for r in primary_rows])
    for row, p in zip(primary_rows, adjusted):
        row["adjustedPValue"] = p
        stats, evidence = row["summary"], row["exitEvidence"]
        sufficient = (row["completeTestYears"] >= protocol["minimumTestYears"] and stats["closed"] >= protocol["minimumTrades"]
                      and stats["dates"] >= protocol["minimumEntryDates"] and stats["missing"] == 0
                      and stats['comparisonMissing'] == 0 and evidence['interval'] is not None)
        positive = evidence["interval"] is not None and evidence["interval"][0] > 0 and p is not None and p < .05
        robust = all(c.get("totalReturn", -1) > 0 for c in row["costs"].values())
        if sufficient:
            row["conclusion"] = "historically-consistent" if positive and robust else "no-detectable-edge"
    return dict(version=1, universe=protocol["universe"], audit=coverage, signals=list(signal_rows.values()),
                variants=variants, details=all_details, snapshotHash=data.snapshot_hash, protocolHash=digest(protocol), engineHash=engine_hash())


def append_prospective(path: Path, signals: list[dict], snapshot_hash: str, protocol: dict, observed_at: str) -> dict:
    """Append-only, hash-linked registry. Historical rows never become prospective."""
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    previous = "0" * 64
    seen = set()
    for row in lines:
        hash_value = row.pop("hash")
        if row["previousHash"] != previous or digest(row) != hash_value:
            raise ValueError("Registro prospectivo alterado")
        row["hash"] = hash_value
        previous = hash_value
        seen.add((row["signal"]["id"], row["protocolHash"]))
    new = []
    for s in sorted(signals, key=lambda s: (s["date"], s["id"])):
        key = s["id"], digest(protocol)
        # Recording an old quote today is not independent prospective evidence.
        delay = pd.Timestamp(observed_at) - pd.Timestamp(s["available_at"])
        if key in seen or s["date"] <= protocol["frozenOn"] or not pd.Timedelta(0) <= delay <= pd.Timedelta(days=4):
            continue
        row = dict(version=1, signal=s, snapshotHash=snapshot_hash, protocolHash=key[1], observedAt=observed_at,
                   engineHash=engine_hash(),
                   executionAvailableAt=max(observed_at, s['available_at']), previousHash=previous)
        row["hash"] = digest(row)
        previous = row["hash"]
        new.append(row)
        seen.add(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    if new:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for row in new:
                handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    return dict(count=len(lines) + len(new), added=len(new), lastHash=previous, frozenOn=protocol["frozenOn"])


def prospective_outcomes(path: Path, data: ResearchData, protocol: dict, now: pd.Timestamp) -> dict:
    """Evaluate recorded signals, including ones a vendor revision later erased."""
    append_prospective(path, [], data.snapshot_hash, protocol, now.isoformat())  # verifies the chain
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    records = [r for r in records if r['protocolHash'] == digest(protocol)]
    import exchange_calendars as xcals
    schedule = xcals.get_calendar('XNYS', start=data.start, end=data.end).schedule
    opens = {d.date().isoformat(): t.isoformat() for d, t in schedule['open'].items()}
    calendar = period_calendar(data.start, data.end, now, 'daily')
    point_cache, trades = {}, []
    for row in records:
        s = Signal(**row['signal'])
        s = replace(s, available_at=row.get('executionAvailableAt', max(row['observedAt'], s.available_at)))
        key = s.security_id, s.reference, s.timeframe
        if key not in point_cache:
            days = period_calendar(min(b.date for b in data.bars[s.security_id]), data.end, now, s.timeframe)
            point_cache[key] = research_points(data.bars[s.security_id], data.bars[s.reference], days, s.timeframe)
        trade = simulate(s, data.bars[s.security_id], point_cache[key], 'fixed', protocol['primaryCostBps'],
                         horizon_weeks=13, expected_sessions=calendar,
                         delisting=next((d for d in data.delistings if d.security_id == s.security_id), None),
                         open_times=opens, as_of=data.end)
        trades.append(comparisons(trade, s, data))
    return dict(version=1, protocolHash=digest(protocol), snapshotHash=data.snapshot_hash,
                registeredSignals=len(records), summary=summary(trades), trades=trades,
                note='Se usan las señales registradas y su disponibilidad real, con precios del snapshot indicado. No se reconstruyen entradas retrospectivas.')


def build_examples(market: dict, folder: Path, protocol: dict, now: pd.Timestamp) -> tuple[list[dict], list[dict]]:
    cases, signal_rows = [], []
    catalog = {i["id"]: i for i in market["catalog"]}
    # These are real index examples from the existing dataset, not a stock study.
    for tf in ("weekly", "daily"):
        view = market["views"]["GSPC"][tf]
        calendar = period_calendar(view["benchmark"][0][0], market["latestSession"], now, tf)
        pools = {}
        for identity, points in view['assets'].items():
            if identity == 'GSPC':
                continue
            for p in points:
                pools.setdefault(p[0], []).append(dict(securityId=identity, date=p[0], reference='GSPC', x=p[1], y=p[2], relativeVolume=None))
        ranks = {(r['securityId'], r['date']): {**r, 'count': len(pool)} for pool in pools.values() for r in cross_section(pool)}
        for identity, points in view["assets"].items():
            if identity == "GSPC":
                continue
            signals = [s for n in protocol["confirmations"] for s in detect(points, calendar, identity, "GSPC", tf, n)]
            records = []
            for s in signals:
                rank = ranks[s.security_id, s.date]
                row = {**asdict(s), "ticker": catalog[identity]["ticker"], "name": catalog[identity]["name"],
                       "scope": "index-illustration", "method": view.get("method", market["method"]),
                       "x_percentile": rank['xPercentile'], "y_percentile": rank['yPercentile'], "zone": rank['zone'], 'percentile_count': rank['count']}
                records.append(row)
                signal_rows.append(row)
            filename = f"example-{identity}-{tf}.json"
            atomic_json(folder / filename, dict(version=1, scope="index-illustration", securityId=identity,
                        name=catalog[identity]["name"], reference="GSPC", timeframe=tf, method=view.get("method"),
                        points=points, benchmark=view["benchmark"], signals=records, lastSession=points[-1][0],
                        percentiles=[{**r, 'count': len(pools[r['date']])} for (ident, _), r in ranks.items() if ident == identity],
                        limitations="Cierres de índices: evolución descriptiva. Sin aperturas, volumen ni simulación neta; no demuestra una estrategia de acciones."))
            cases.append(dict(id=f"{identity}-{tf}", securityId=identity, name=catalog[identity]["name"], timeframe=tf,
                              url=filename, count=len(records), scope="index-illustration"))
    return cases, signal_rows


def build(output: Path, input_path: Path | None = None, now: pd.Timestamp | None = None) -> dict:
    now = now or pd.Timestamp.now(tz="UTC")
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    # A frozen protocol has its own immutable fingerprint; changing it starts a new run.
    source_audit = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    candidate_path = ROOT / '.cache/strategies/sources/candidate-coverage.json'
    candidate_coverage = json.loads(candidate_path.read_text(encoding='utf-8')) if candidate_path.exists() else source_audit.get('candidateSnapshot')
    data = load_research(input_path) if input_path else None
    coverage = audit(data, now)
    private = ROOT / ".cache/strategies"
    frozen = private / "protocols" / (digest(protocol)[:20] + ".json")
    if frozen.exists() and json.loads(frozen.read_text(encoding="utf-8")) != protocol:
        raise ValueError("El protocolo congelado no coincide")
    atomic_json(frozen, protocol)
    atomic_json(private / "audit.json", coverage)
    previous_manifest = output / 'manifest.json'
    if previous_manifest.exists() and coverage['status'] != 'eligible':
        previous = json.loads(previous_manifest.read_text(encoding='utf-8'))
        if previous.get('stockStudyUrl') and previous.get('protocolHash') == digest(protocol):
            atomic_json(output / 'refresh-status.json', dict(version=1, ok=False, attemptedAt=now.isoformat(), audit=coverage))
            return previous
    stock = None
    if data and coverage["status"] == "eligible":
        stock = run_study(data, now, protocol)
        stock["runId"] = digest([stock["snapshotHash"], digest(protocol), engine_hash()])
        atomic_json(private / "runs" / (stock["runId"] + ".json"), stock)
    # Build into a content-addressed directory; replace only the manifest last.
    market_path = ROOT / "public/data/market.json"
    market = json.loads(market_path.read_text(encoding="utf-8"))
    run_id = digest([digest(market), digest(protocol), data.snapshot_hash if data else None, digest(coverage), engine_hash()])[:20]
    folder = output / run_id
    cases, example_signals = build_examples(market, folder, protocol, now)
    prospective = append_prospective(private / "prospective.jsonl", stock["signals"] if stock else [],
                                     data.snapshot_hash if data else digest(market), protocol, now.isoformat())
    if stock:
        outcomes = prospective_outcomes(private / 'prospective.jsonl', data, protocol, now)
        atomic_json(private / 'prospective-outcomes.json', outcomes)
        prospective['summary'] = outcomes['summary']
    public_stock = None
    if stock and coverage["publicationAllowed"]:
        public_stock = f"{run_id}/study.json"
        # Details load separately; the landing report does not include raw bars.
        report = {k: v for k, v in stock.items() if k not in ("details", "signals", "variants")}
        report['variants'] = []
        for variant in stock['variants']:
            details_url = 'variant-' + variant['id'] + '.json'
            equity = variant['walkForward']['portfolio']['equity']
            spy = {b.date: b for b in data.bars['SPY']}
            first = spy[equity[0][0]].adjusted_open if equity and equity[0][0] in spy else None
            benchmark = [[d, spy[d].adjusted_close / first * (1 - protocol['primaryCostBps'] / 10000)] for d, _ in equity if d in spy] if first else []
            atomic_json(folder / details_url, dict(version=1, variant=variant, benchmarkEquity=benchmark))
            small = {k: v for k, v in variant.items() if k not in ('walkForward', 'costs')}
            small['detailsUrl'] = details_url
            small['walkForward'] = {**variant['walkForward'], 'trades':[], 'portfolio':{k:v for k,v in variant['walkForward']['portfolio'].items() if k not in ('returns','equity')}}
            small['costs'] = {c:{k:v for k,v in curve.items() if k not in ('returns','equity')} for c,curve in variant['costs'].items()}
            report['variants'].append(small)
        report["signalsUrl"] = "stock-signals.json"
        atomic_json(folder / "stock-signals.json", dict(version=1, signals=stock["signals"]))
        for identity, details in stock["details"].items():
            atomic_json(folder / (identity + ".json"), dict(version=1, trades=details))
        atomic_json(folder / "study.json", report)
        for tf in ('weekly', 'daily'):
            for ref_type in ('market', 'sector'):
                events, pairs, calendar = stock_signals(data, tf, ref_type, 1, now)
                for (identity, ref), points in pairs.items():
                    if not points:
                        continue
                    security = next(s for s in data.securities if s['id'] == identity)
                    filename = 'stock-' + digest([identity, ref, tf])[:24] + '.json'
                    relevant = [s for s in stock['signals'] if s['security_id'] == identity and s['reference'] == ref and s['timeframe'] == tf]
                    atomic_json(folder / filename, dict(version=1, scope='stock-study', securityId=identity,
                        name=security.get('name', identity), reference=ref, timeframe=tf, method=protocol['methods'][tf]['name'],
                        points=points, benchmark=[[b.date, b.adjusted_close] for b in data.bars[ref] if b.date in set(calendar)],
                        dailyPrices=[[b.date, b.adjusted_close] for b in data.bars[identity]],
                        signals=relevant, lastSession=points[-1][0], tradesBase='',
                        limitations='Precios ajustados. Las ejecuciones simuladas son a la siguiente apertura; consultar el detalle de operación.'))
                    cases.append(dict(id=digest([identity, ref, tf])[:24], securityId=identity, name=security.get('name', identity),
                        timeframe=tf, url=filename, count=len(relevant), scope='stock-study', referenceType=ref_type))
    manifest = dict(version=1, generatedAt=now.isoformat(), latestSession=market["latestSession"], runId=run_id,
                    protocolHash=digest(protocol), snapshotHash=data.snapshot_hash if public_stock else digest(market), protocol=protocol,
                    engineHash=engine_hash(), inputSources=[asdict(s) for s in data.sources] if public_stock else [],
                    audit=coverage, sources=source_audit["sources"], stockStudyUrl=public_stock,
                    studyState="published" if public_stock else "private-results" if stock else "not-evaluable",
                    cases=[{**c, "url": f"{run_id}/{c['url']}"} for c in cases], prospective=prospective,
                    entryNames=ENTRY_NAMES, stockSignals= len(stock["signals"]) if stock else 0, candidateCoverage=candidate_coverage,
                    priceProbes=source_audit.get('priceProbes', []))
    atomic_json(output / "manifest.json", manifest)
    atomic_json(output / 'refresh-status.json', dict(version=1, ok=True, attemptedAt=now.isoformat()))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Bundle privado versionado; nunca se certifica una lista actual como histórico")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/strategies")
    args = parser.parse_args()
    result = build(args.output, args.input)
    print(f"Estrategias: {result['studyState']}; {len(result['audit']['issues'])} incidencias; {len(result['cases'])} ejemplos reales")
