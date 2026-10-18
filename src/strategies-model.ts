import { validDate, type Point, type Timeframe } from './model';

export const entryNames: Record<string, string> = {
  'turn-up': 'Giro hacia arriba en Rezagado', 'turn-right': 'Giro hacia la derecha en Rezagado',
  'lagging-improving': 'Rezagado → Mejorando', 'improving-leading': 'Mejorando → Líder',
};
export interface StrategyState {
  tf: Timeframe; symbol: string; rule: string; confirmation: 1 | 2;
  universe: 'indices' | 'stocks'; reference: 'market' | 'sector';
  strong: boolean; volume: boolean; caseId: string; page: 'signals' | 'case' | 'results';
}
export interface SignalEvent {
  id: string; security_id: string; reference: string; timeframe: Timeframe; rule: string;
  confirmation: 1 | 2; origin_date: string; date: string; available_at: string;
  x: number; y: number; sector: string | null; sector_strong: boolean | null;
  relative_volume: number | null; ticker?: string; name?: string; scope?: string;
  x_percentile?: number | null; y_percentile?: number | null; volume_percentile?: number | null;
  zone?: number[] | null; percentile_count?: number;
}
export interface CaseData {
  version: 1; scope: string; securityId: string; name: string; reference: string;
  timeframe: Timeframe; method: string; points: Point[]; benchmark: [string, number][];
  signals: SignalEvent[]; lastSession: string; limitations: string;
  percentiles?: {date: string; xPercentile: number; yPercentile: number; count: number; zone: number[]}[];
  dailyPrices?: [string, number][];
}
export interface StrategyManifest {
  version: 1; generatedAt: string; latestSession: string; runId: string;
  protocolHash: string; snapshotHash: string; protocol: Record<string, any>;
  audit: { status: 'eligible' | 'not-evaluable'; issues: { code: string; detail: string; securityId?: string | null; date?: string | null }[];
    coverage: { start: string; end: string; sessions: number; securities: number; delisted: number; snapshotHash: string } | null;
    publicationAllowed: boolean };
  sources: { id: string; name: string; url: string; status: string; limitation: string }[];
  cases: { id: string; securityId: string; name: string; timeframe: Timeframe; url: string; count: number; scope: string; referenceType?: string }[];
  stockStudyUrl: string | null; studyState: string; prospective: { count: number; added: number; frozenOn: string; lastHash: string };
  currentStudyUrl?: string;
  currentCoverage?: {asOf: string; count: number; latestSession: string; start: string};
  candidateCoverage?: { intervalRows: number; tickersSince2010: number; closedIntervalsSince2010: number; latestChange: string; contentHash: string };
  priceProbes?: {ticker: string; status: string; sessions?: number; first?: string; last?: string}[];
}

export function parseStrategy(search: string): StrategyState {
  const p = new URLSearchParams(search);
  const base: StrategyState = { tf: 'weekly', symbol: 'RUT', rule: 'all', confirmation: 1, universe: 'indices',
    reference: 'market', strong: false, volume: false, caseId: '', page: 'signals' };
  if (p.has('sv') && p.get('sv') !== '1') return base;
  return { tf: p.get('stf') === 'daily' ? 'daily' : 'weekly',
    symbol: /^[A-Za-z0-9._-]{1,80}$/.test(p.get('symbol') ?? '') ? p.get('symbol')! : 'RUT',
    rule: p.get('rule') && entryNames[p.get('rule')!] ? p.get('rule')! : 'all',
    confirmation: p.get('confirm') === '2' ? 2 : 1,
    universe: p.get('universe') === 'stocks' ? 'stocks' : 'indices', reference: p.get('ref') === 'sector' ? 'sector' : 'market',
    strong: p.get('strong') === '1', volume: p.get('vol') === '1',
    caseId: /^[a-f0-9]{24}$/.test(p.get('case') ?? '') ? p.get('case')! : '',
    page: p.get('study') === 'case' ? 'case' : p.get('study') === 'results' ? 'results' : 'signals' };
}
export function strategySearch(state: StrategyState, search = ''): string {
  const p = new URLSearchParams(search);
  for (const [key, value] of Object.entries({ sv: '1', stf: state.tf, symbol: state.symbol, rule: state.rule,
    confirm: String(state.confirmation), universe: state.universe, ref: state.reference,
    strong: state.strong ? '1' : '0', vol: state.volume ? '1' : '0', study: state.page, case: state.caseId })) {
    if (value) p.set(key, value); else p.delete(key);
  }
  return p.toString();
}
export function preserveStrategy(search: string, explorer: string): string {
  const current = new URLSearchParams(search), next = new URLSearchParams(explorer);
  for (const key of ['sv', 'stf', 'symbol', 'rule', 'confirm', 'universe', 'ref', 'strong', 'vol', 'study', 'case', 'period', 'exit', 'capital', 'mode', 'portfolio']) {
    if (current.has(key)) next.set(key, current.get(key)!);
  }
  return next.toString();
}
export function safeArtifact(path: string): string {
  if (!/^[a-zA-Z0-9/-]+\.json$/.test(path) || path.includes('..') || path.startsWith('/')) throw new Error('Ruta de investigación inválida');
  return path;
}
export function validateManifest(value: unknown): StrategyManifest {
  const d = value as StrategyManifest;
  if (!d || d.version !== 1 || !d.audit || !['eligible', 'not-evaluable'].includes(d.audit.status)
    || !Array.isArray(d.audit.issues) || !Array.isArray(d.cases) || !Array.isArray(d.sources)
    || !d.protocol || !d.prospective || !validDate(d.latestSession) || !/^[a-f0-9]{64}$/.test(d.protocolHash)) throw new Error('Informe de estrategias incompatible');
  for (const c of d.cases) safeArtifact(c.url);
  for (const source of d.sources) if (!source.url.startsWith('https://')) throw new Error('Fuente con URL inválida');
  if (d.stockStudyUrl) {
    safeArtifact(d.stockStudyUrl);
    if (d.audit.status !== 'eligible' || !d.audit.publicationAllowed) throw new Error('Estudio sin auditoría o permiso de publicación');
  }
  if (d.currentStudyUrl) safeArtifact(d.currentStudyUrl);
  return d;
}
export function validateCase(value: unknown): CaseData {
  const d = value as CaseData;
  if (!d || d.version !== 1 || !Array.isArray(d.points) || !d.points.length || !Array.isArray(d.signals)) throw new Error('Caso incompatible');
  let last = '';
  for (const p of d.points) {
    if (p.length !== 4 || !validDate(p[0]) || p[0] <= last || p.slice(1).some(v => typeof v !== 'number' || !Number.isFinite(v) || v <= 0)) throw new Error('Serie de caso inválida');
    last = p[0];
  }
  for (const s of d.signals) {
    if (!/^[a-f0-9]{24}$/.test(s.id) || !entryNames[s.rule] || !validDate(s.date) || !validDate(s.origin_date)
      || s.origin_date > s.date || ![1, 2].includes(s.confirmation) || !d.points.some(p => p[0] === s.date)) throw new Error('Señal inválida');
  }
  return d;
}
