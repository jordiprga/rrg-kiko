"""Versioned private research input and fail-closed point-in-time coverage audit.

No market downloads or public writes occur on import. A candidate membership CSV
is evidence to investigate, never automatic certification of a backtest universe.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.market import ROOT, closed_schedule, completed_week_ends


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def iso(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError(f"Fecha inválida: {value}")
    return value


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    retrieved_at: str
    content_hash: str
    publication_allowed: bool = False
    verified: bool = False
    role: str = "candidate"


@dataclass(frozen=True)
class Membership:
    security_id: str
    start: str
    end: str | None
    available_at: str
    source_id: str

    def contains(self, day: str) -> bool:
        return self.start <= day and (self.end is None or day < self.end) and self.available_at[:10] <= day


@dataclass(frozen=True)
class SectorMembership(Membership):
    sector: str
    etf: str


@dataclass(frozen=True, slots=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: float | None
    available_at: str
    source_id: str
    volume_basis: str = 'unknown'
    dividend: float = 0
    split: float = 1

    @property
    def factor(self) -> float:
        return self.adjusted_close / self.close

    @property
    def adjusted_open(self) -> float:
        return self.open * self.factor


@dataclass(frozen=True)
class Delisting:
    security_id: str
    last_trading_date: str
    settlement_date: str
    settlement_price: float
    available_at: str
    source_id: str


@dataclass
class ResearchData:
    version: int
    start: str
    end: str
    securities: list[dict]
    memberships: list[Membership]
    sectors: list[SectorMembership]
    bars: dict[str, list[Bar]]
    delistings: list[Delisting]
    sources: list[Source]
    # An audit ledger covers EVERY scheduled session, including zero changes.
    # Each entry has date, members (stable IDs), source_id and evidence_hash.
    universe_ledger: list[dict]

    def member(self, identity: str, day: str) -> bool:
        return any(m.security_id == identity and m.contains(day) for m in self.memberships)

    def sector_at(self, identity: str, day: str) -> SectorMembership | None:
        found = [s for s in self.sectors if s.security_id == identity and s.contains(day)]
        return found[0] if len(found) == 1 else None

    @property
    def snapshot_hash(self) -> str:
        return digest(asdict(self))


def load_research(path: Path) -> ResearchData:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("version") != 1:
        raise ValueError("Contrato de investigación incompatible")
    return ResearchData(
        version=1, start=iso(obj["start"]), end=iso(obj["end"]),
        securities=obj["securities"], memberships=[Membership(**m) for m in obj["memberships"]],
        sectors=[SectorMembership(**s) for s in obj["sectors"]],
        bars={k: [Bar(**b) for b in rows] for k, rows in obj["bars"].items()},
        delistings=[Delisting(**d) for d in obj["delistings"]],
        sources=[Source(**s) for s in obj["sources"]], universe_ledger=obj["universe_ledger"],
    )


def audit(data: ResearchData | None, now: pd.Timestamp, minimum_members: int = 480) -> dict:
    issues: list[dict] = []
    def problem(code: str, detail: str, identity: str | None = None, day: str | None = None):
        issues.append(dict(code=code, detail=detail, securityId=identity, date=day))
    if data is None:
        for code, detail in [
            ("membership", "Falta un libro diario contrastado de componentes históricos del S&P 500 e identidades estables."),
            ("sectors", "Faltan sectores históricos con fechas efectivas y de disponibilidad."),
            ("bars", "Faltan OHLCV, ajustes y eventos de las acciones actuales y excluidas desde 2010."),
            ("delistings", "Faltan liquidaciones documentadas de empresas desaparecidas."),
        ]:
            problem(code, detail)
        return dict(version=1, status="not-evaluable", issues=issues, coverage=None, publicationAllowed=False)
    if data.start > data.end:
        problem("range", "Intervalo invertido")
    # schedule_for normally covers six years; research must cover the entire input.
    import exchange_calendars as xcals
    schedule = xcals.get_calendar("XNYS", start=data.start, end=data.end).schedule
    sessions = [d.date().isoformat() for d in closed_schedule(schedule, now).index]
    if not sessions or sessions[-1] < data.end:
        problem("open-session", "El fin solicitado no es una sesión cerrada")
    sources = {s.id: s for s in data.sources}
    ids = {s["id"] for s in data.securities}
    if len(ids) != len(data.securities):
        problem("identity", "Identificadores de valores duplicados")
    for s in data.sources:
        if not s.url.startswith("https://") or len(s.content_hash) != 64 or any(c not in '0123456789abcdef' for c in s.content_hash):
            problem("provenance", "Fuente sin URL HTTPS o hash de evidencia", s.id)
        if not s.verified:
            problem("unverified-source", "Fuente candidata sin contraste documentado", s.id)
    def provenance(row):
        if row.source_id not in sources:
            problem("provenance", "Fuente desconocida", getattr(row, "security_id", None))
        if not row.available_at or not row.available_at.endswith(("Z", "+00:00")):
            problem("availability", "Se requiere instante UTC de disponibilidad", getattr(row, "security_id", None))
    for row in [*data.memberships, *data.sectors, *data.delistings]:
        provenance(row)
        if row.security_id not in ids:
            problem("identity", "Valor sin identidad estable", row.security_id)
        if row.source_id in sources and sources[row.source_id].role != "primary":
            problem("primary-evidence", "Composición, sector o liquidación sin evidencia primaria", row.security_id)
    for group in [data.memberships, data.sectors]:
        for identity in ids:
            rows = sorted([m for m in group if m.security_id == identity], key=lambda m: m.start)
            for previous, current in zip(rows, rows[1:]):
                if previous.end is None or previous.end > current.start:
                    problem("overlap", "Intervalos históricos solapados", identity, current.start)
    ledger = {r["date"]: r for r in data.universe_ledger}
    if len(ledger) != len(data.universe_ledger):
        problem("ledger", "Sesiones duplicadas en libro del universo")
    indexes: dict[str, dict[str, Bar]] = {}
    for identity, rows in data.bars.items():
        dates = [b.date for b in rows]
        if dates != sorted(set(dates)):
            problem("bars", "Barras desordenadas o duplicadas", identity)
        indexes[identity] = {b.date: b for b in rows}
        for b in rows:
            provenance(b)
            nums = [b.open, b.high, b.low, b.close, b.adjusted_close, b.split]
            if any(not math.isfinite(v) or v <= 0 for v in nums) or not b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high:
                problem("bars", "OHLC o ajuste inválido", identity, b.date)
            if b.volume is not None and (not math.isfinite(b.volume) or b.volume < 0):
                problem("volume", "Volumen inválido", identity, b.date)
            if b.volume is not None and b.volume_basis not in ('raw', 'split-adjusted'):
                problem('volume-basis', 'Falta documentar si el volumen ya está ajustado por splits', identity, b.date)
    for day in sessions:
        row = ledger.get(day)
        if (row is None or row.get("source_id") not in sources
            or sources[row["source_id"]].role != "primary"
            or row.get("evidence_hash") != sources[row["source_id"]].content_hash):
            problem("ledger", "Sesión sin evidencia contrastada del universo", day=day)
            continue
        expected = set(row["members"])
        if len(expected) < minimum_members:
            problem('universe-size', 'El libro no representa el universo completo del S&P 500', day=day)
        actual = {i for i in ids if data.member(i, day)}
        if not expected or expected != actual:
            problem("membership", "El universo no coincide con el libro contrastado", day=day)
        for identity in sorted(expected):
            s = data.sector_at(identity, day)
            if s is None:
                problem("sectors", "Sector histórico desconocido o ambiguo", identity, day)
            required = [identity, "SPY", *([s.etf] if s else [])]
            for symbol in required:
                bar = indexes.get(symbol, {}).get(day)
                if bar is None:
                    problem("missing-bar", "Sesión sin barra; requiere resolución, no se elimina", symbol, day)
                elif pd.Timestamp(bar.available_at) > now:
                    problem("availability", "Barra todavía no disponible", symbol, day)
                elif pd.Timestamp(bar.available_at) < pd.Timestamp(day, tz="UTC"):
                    problem("availability", "Barra disponible antes de su sesión", symbol, day)
    for s in data.securities:
        if s.get("delisted"):
            ds = [d for d in data.delistings if d.security_id == s["id"]]
            if len(ds) != 1:
                problem("delistings", "Baja sin liquidación única documentada", s["id"])
            elif not math.isfinite(ds[0].settlement_price) or ds[0].settlement_price < 0:
                problem("delistings", "Importe de liquidación inválido", s["id"])
    return dict(version=1, status="eligible" if not issues else "not-evaluable", issues=issues,
                coverage=dict(start=data.start, end=data.end, sessions=len(sessions), securities=len(ids),
                              delisted=sum(bool(s.get("delisted")) for s in data.securities), snapshotHash=data.snapshot_hash),
                publicationAllowed=bool(sources) and all(s.publication_allowed for s in sources.values()))


def period_calendar(start: str, end: str, now: pd.Timestamp, tf: str) -> list[str]:
    import exchange_calendars as xcals
    # Include the REST of the final week before deciding whether it is closed.
    extended_end = (pd.Timestamp(end) + pd.Timedelta(days=7)).date().isoformat()
    schedule = xcals.get_calendar("XNYS", start=start, end=extended_end).schedule
    index = completed_week_ends(schedule, now) if tf == "weekly" else closed_schedule(schedule, now).index
    return [d.date().isoformat() for d in index if d.date().isoformat() <= end]
