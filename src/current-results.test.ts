import { describe,it,expect } from 'vitest';
import { researchControls,exitName } from './current-results';
import { preserveStrategy } from './strategies-model';

describe('Capital research controls',()=>{
  it('defaults to the final temporal test, not the best historical result',()=>{
    expect(researchControls('')).toMatchObject({period:'test',mode:'allocation',capital:100000});
    expect(researchControls('?period=all&mode=allocation').period).toBe('test');
  });
  it('restores period, portfolio and capital across explorer navigation',()=>{
    const search='sv=1&universe=stocks&period=validation&capital=25000&mode=entries&exit=atr-3&portfolio=abc';
    const next=preserveStrategy(search,'v=1&b=GSPC&tail=30');
    expect(researchControls(next)).toEqual(researchControls(search));
    expect(new URLSearchParams(next).get('tail')).toBe('30');
  });
  it('bounds hypothetical capital and explains exit labels',()=>{
    expect(researchControls('?capital=-100').capital).toBe(100);
    expect(researchControls('?capital=1e99').capital).toBe(1e9);
    expect(exitName('pct-15+orbit')).toBe('Trailing 15 % + órbita');
    expect(exitName('atr-3+orbit')).toBe('ATR × 3 + órbita');
  });
});
