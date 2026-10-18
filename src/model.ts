export type Timeframe = 'daily' | 'weekly';
export type Group = 'indices' | 'sectors';
export type Point = [date: string, x: number, y: number, price: number];
export interface Instrument {
  id: string; ticker: string; name: string; type: 'index' | 'etf' | 'stock';
  group: Group; market: string; currency: string; proxyOf?: string;
}
export interface GroupSettings {
  name: string; benchmarks: string[]; defaultBenchmark: string; defaults: string[];
}
export interface View {
  method?: 'relative-ema-v1' | 'relative-sma-10-30-9-v2'; calculationVersion?: 1 | 2;
  parameters: Record<string, number>;
  benchmark: [string, number][];
  assets: Record<string, Point[]>;
}
export interface Dataset {
  version: 1; generatedAt: string; source: string; sourceUrl: string;
  latestSession: string; expectedWeeklySession: string; priceConvention: string;
  method: string; usage: string; catalog: Instrument[];
  groups: Partial<Record<Group, GroupSettings>>;
  views: Record<string, Record<Timeframe, View>>; errors: Record<string, string>;
}
export interface State {
  group: Group; tf: Timeframe; benchmark: string; selected: string[];
  tail: number; arrows: boolean; hidden: string[]; date?: string;
}
export const quadrants = {
  leading: { name: 'Líder', color: '#39765e', fill: '#eff6ec', hint: 'Fuerza y momentum por encima de 100' },
  weakening: { name: 'Debilitándose', color: '#977526', fill: '#fbf5e6', hint: 'Fuerza sobre 100; momentum bajo 100' },
  lagging: { name: 'Rezagado', color: '#ac605f', fill: '#faf0ee', hint: 'Fuerza y momentum por debajo de 100' },
  improving: { name: 'Mejorando', color: '#4c7e9e', fill: '#eef4fa', hint: 'Fuerza bajo 100; momentum sobre 100' },
  neutral: { name: 'En el eje', color: '#68766f', fill: '#f3f4f1', hint: 'Alguno de los indicadores es 100' },
};
export function quadrant(x: number, y: number): keyof typeof quadrants {
  if (Math.abs(x - 100) < 1e-6 || Math.abs(y - 100) < 1e-6) return 'neutral';
  return x > 100 ? y > 100 ? 'leading' : 'weakening' : y > 100 ? 'improving' : 'lagging';
}
export function defaults(data: Dataset, group: Group): State {
  const settings = data.groups[group]!;
  return { group, tf: 'weekly', benchmark: settings.defaultBenchmark,
    selected: [...settings.defaults], tail: 17, arrows: true, hidden: [] };
}
export function parseState(search: string, data: Dataset): State {
  const p = new URLSearchParams(search);
  const first = Object.keys(data.groups)[0] as Group;
  const group = p.get('g') as Group;
  const base = defaults(data, data.groups[group] ? group : first);
  if (p.has('v') && p.get('v') !== '1') return base;
  const allowed = new Set(data.catalog.filter(i => i.group === base.group).map(i => i.id));
  const unique = (value: string) => [...new Set(value.split(',').filter(i => allowed.has(i)))];
  const selected = p.has('s') ? unique(p.get('s')!) : base.selected;
  const b = p.get('b') ?? base.benchmark;
  const rawTail = Number(p.get('tail'));
  return { ...base, tf: p.get('tf') === 'daily' ? 'daily' : 'weekly', selected,
    benchmark: data.groups[base.group]!.benchmarks.includes(b) ? b : base.benchmark,
    tail: p.has('tail') && Number.isFinite(rawTail) ? Math.max(1, Math.min(30, Math.round(rawTail))) : 17,
    ...(validDate(p.get('date')) ? { date: p.get('date')! } : {}),
    arrows: p.get('a') !== '0', hidden: unique(p.get('h') ?? '').filter(i => selected.includes(i)) };
}
export function validDate(value: string | null): boolean {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
export function serialize(state: State, date?: string): string {
  return new URLSearchParams({ v: '1', g: state.group, tf: state.tf, b: state.benchmark,
    s: state.selected.join(','), tail: String(state.tail), a: state.arrows ? '1' : '0',
    ...(validDate(date ?? null) ? { date: date! } : {}),
    ...(state.hidden.length ? { h: state.hidden.join(',') } : {}) }).toString();
}
export function indexAtOrBefore<T extends [string, ...unknown[]]>(points: T[], date: string): number {
  let low = 0, high = points.length;
  while (low < high) { const mid = (low + high) >>> 1; if (points[mid][0] <= date) low = mid + 1; else high = mid; }
  return low - 1;
}
export function trail(points: Point[], date: string, periods: number): Point[] {
  const end = indexAtOrBefore(points, date);
  return end < 0 ? [] : points.slice(Math.max(0, end - periods), end + 1);
}
export function scaleBounds(points: Point[], center = false): [number, number, number, number] {
  const xs = [100, ...points.map(p => p[1])], ys = [100, ...points.map(p => p[2])];
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  if (center) {
    const extent = Math.max(0.6, 100 - minX, maxX - 100, 100 - minY, maxY - 100) * 1.2;
    return [100 - extent, 100 + extent, 100 - extent, 100 + extent];
  }
  const px = Math.max(0.25, (maxX - minX) * 0.17), py = Math.max(0.25, (maxY - minY) * 0.17);
  return [minX - px, maxX + px, minY - py, maxY + py];
}

export function validateDataset(value: unknown): Dataset {
  const d = value as Dataset;
  if (!d || d.version !== 1 || !['relative-ema-v1', 'relative-models-v2'].includes(d.method) || !Array.isArray(d.catalog) || !d.catalog.length
    || !d.groups || !d.views || !Number.isFinite(Date.parse(d.generatedAt))) throw new Error('El dataset tiene un formato incompatible.');
  for (const group of Object.values(d.groups)) {
    if (!group || !group.benchmarks.includes(group.defaultBenchmark) || !group.defaults.length) throw new Error('Catálogo inválido.');
    for (const benchmark of group.benchmarks) for (const tf of ['daily', 'weekly'] as const) {
      const view = d.views[benchmark]?.[tf];
      if (!view || view.benchmark.length < 31 || !view.assets) throw new Error('Falta histórico válido.');
      const method = view.method ?? d.method, sma = method === 'relative-sma-10-30-9-v2';
      const parameters = sma ? { short: 10, long: 30, m: 9 } : { n: tf === 'weekly' ? 10 : 50, m: tf === 'weekly' ? 4 : 20 };
      if (!(method === 'relative-ema-v1' || (sma && benchmark === 'GSPC' && tf === 'weekly'))
        || (view.calculationVersion ?? 1) !== (sma ? 2 : 1)
        || !view.parameters || Object.keys(view.parameters).length !== Object.keys(parameters).length
        || Object.entries(parameters).some(([k, v]) => view.parameters[k] !== v)) throw new Error('Método o parámetros incompatibles.');
      const check = (rows: (string | number)[][], columns: number) => {
        let previous = '';
        for (const row of rows) {
          if (row.length !== columns || typeof row[0] !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row[0]) || row[0] <= previous
            || row.slice(1).some(v => typeof v !== 'number' || !Number.isFinite(v) || v <= 0)) throw new Error('Serie de datos inválida.');
          previous = row[0];
        }
      };
      check(view.benchmark, 2);
      for (const rows of Object.values(view.assets)) { if (rows.length < 31) throw new Error('Histórico insuficiente.'); check(rows, 4); }
      if (group.defaults.some(id => !view.assets[id])) throw new Error('Faltan los instrumentos iniciales.');
    }
  }
  return d;
}

// Visible range only; calculations always retain the complete history.
export function visibleWindow(series: [string, number][], anchor: number, full: boolean): [number, number] {
  if (full) return [0, series.length - 1];
  const date = new Date(series[anchor][0] + 'T12:00:00Z');
  date.setUTCFullYear(date.getUTCFullYear() - 1);
  return [Math.max(0, indexAtOrBefore(series, date.toISOString().slice(0, 10))), anchor];
}
export function draggedEnd(initial: number, deltaPixels: number, width: number, start: number, finish: number, count: number): number {
  return Math.max(0, Math.min(count - 1, initial + Math.round(deltaPixels / Math.max(1, width) * (finish - start))));
}
