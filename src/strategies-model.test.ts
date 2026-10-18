import { describe, it, expect } from 'vitest';
import { parseStrategy, strategySearch, preserveStrategy, safeArtifact, validateCase } from './strategies-model';

describe('Strategy sharing', () => {
  it('restores every setting while preserving explorer parameters and a subroute', () => {
    const state = { ...parseStrategy(''), universe: 'stocks' as const, reference: 'sector' as const,
      tf: 'daily' as const, symbol: 'BRK.B', rule: 'turn-right', confirmation: 2 as const,
      strong: true, volume: true, caseId: 'a'.repeat(24), page: 'case' as const };
    const search = strategySearch(state, 'v=1&b=GSPC&tail=30&date=2025-05-30');
    expect(parseStrategy(search)).toEqual(state);
    expect(new URLSearchParams(search).get('tail')).toBe('30');
    const updated = preserveStrategy(search, 'v=1&b=NDX&tail=17');
    expect(parseStrategy(updated)).toEqual(state);
    expect(new URLSearchParams(updated).get('b')).toBe('NDX');
    expect(new URL(`https://example.org/rrg-kiko/?${updated}#estrategias`).pathname).toBe('/rrg-kiko/');
  });
  it('rejects invalid controls, untrusted HTML and unknown versions', () => {
    expect(parseStrategy('?sv=99&universe=stocks')).toEqual(parseStrategy(''));
    expect(parseStrategy('?symbol=<script>&rule=wrong&confirm=999&case=oops')).toMatchObject({symbol:'RUT',rule:'all',confirmation:1,caseId:''});
  });
  it('does not serialize future reveal, so opening a shared case hides it', () => {
    expect(strategySearch(parseStrategy(''))).not.toContain('reveal');
  });
  it('restricts lazy report requests to relative artifacts', () => {
    for (const path of ['../input.json', 'https://bad.test/input.json', '/input.json', 'file.json?x=1']) expect(() => safeArtifact(path)).toThrow();
    expect(safeArtifact('abc/example-RUT-weekly.json')).toBe('abc/example-RUT-weekly.json');
  });
  it('rejects invalid or unordered case prices', () => {
    expect(() => validateCase({version:1,points:[['2025-06-06',99,101,100],['2025-05-30',99,99,99]], signals:[]})).toThrow();
  });
});
