import { describe, it, expect } from 'vitest';
import { parseState, serialize, defaults, trail, indexAtOrBefore, quadrant, scaleBounds, type Dataset, type Point } from './model';

const data = {
  catalog: ['GSPC', 'NDX', 'IXIC', 'DJI', 'RUT'].map(id => ({ id, group: 'indices' })),
  groups: { indices: { benchmarks: ['GSPC', 'NDX'], defaultBenchmark: 'GSPC', defaults: ['NDX', 'IXIC', 'DJI', 'RUT'] } },
} as Dataset;
const points: Point[] = [
  ['2026-10-12', 99, 99, 100], ['2026-10-13', 100, 101, 101],
  ['2026-10-14', 101, 102, 102], ['2026-10-16', 102, 103, 104],
];

describe('Shared configuration', () => {
  it('restores every shared setting, including a 30-period daily tail', () => {
    const state = { ...defaults(data, 'indices'), tf: 'daily' as const, tail: 30, benchmark: 'NDX', arrows: false, hidden: ['IXIC'] };
    expect(parseState(serialize(state), data)).toEqual(state);
  });
  it('preserves the exact requested 17-period tail', () => expect(parseState('?v=1&tail=17', data).tail).toBe(17));
  it('validates unknown IDs, duplicates, benchmark, timeframe and extreme tails', () => {
    const state = parseState('?v=1&g=invalid&s=NDX,NDX,INVALID&b=EVIL&tf=hourly&tail=999&h=EVIL', data);
    expect(state).toMatchObject({ group: 'indices', selected: ['NDX'], benchmark: 'GSPC', tf: 'weekly', tail: 30, hidden: [] });
  });
  it('uses defaults for an unsupported URL version', () => expect(parseState('?v=99&s=&tail=2', data)).toEqual(defaults(data, 'indices')));
  it('preserves an intentionally empty selection', () => expect(parseState('?v=1&s=', data).selected).toEqual([]));
  it('rejects nonfinite tails and clamps negative values', () => {
    expect(parseState('?tail=NaN', data).tail).toBe(17);
    expect(parseState('?tail=-9', data).tail).toBe(1);
  });
});

describe('Historical navigation', () => {
  it('never advances to a future observation across a missing session', () => expect(indexAtOrBefore(points, '2026-10-15')).toBe(2));
  it('does not use future points before the first date', () => expect(trail(points, '2026-01-01', 30)).toEqual([]));
  it('represents n intervals with n+1 available points and does not use future data', () => expect(trail(points, '2026-10-14', 1)).toEqual(points.slice(1, 3)));
  it('uses the available history when the requested tail is longer', () => expect(trail(points, '2026-10-16', 30)).toEqual(points));
});

describe('Quadrants and chart scale', () => {
  it('places each quadrant correctly and treats the axes separately', () => {
    expect(quadrant(101, 101)).toBe('leading'); expect(quadrant(101, 99)).toBe('weakening');
    expect(quadrant(99, 99)).toBe('lagging'); expect(quadrant(99, 101)).toBe('improving');
    expect(quadrant(100, 101)).toBe('neutral'); expect(quadrant(100, 100)).toBe('neutral');
  });
  it('keeps the origin and extreme trails inside the initial scale', () => {
    const bounds = scaleBounds([['2026-10-16', 130, 60, 100]]);
    expect(bounds[0]).toBeLessThan(100); expect(bounds[1]).toBeGreaterThan(130);
    expect(bounds[2]).toBeLessThan(60); expect(bounds[3]).toBeGreaterThan(100);
  });
  it('centers symmetric bounds on 100', () => {
    const b = scaleBounds(points, true); expect(b[0] + b[1]).toBeCloseTo(200); expect(b[2] + b[3]).toBeCloseTo(200);
  });
});
