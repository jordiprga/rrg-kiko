"""Round 2: select on Nasdaq development only, then evaluate frozen SMA on fresh NYA."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from scripts.market import ROOT, completed_week_ends, schedule_for, sma_indicators, indicators
from scripts.contrast import RESEARCH, split_dates, metrics


def search(rs, references, train):
    target = references.loc[train, 'ixic_x'].to_numpy() - 100
    ma = {(kind, n): rs.ewm(span=n, adjust=False).mean() if kind == 'ema' else rs.rolling(n).mean()
          for kind in ['ema', 'sma'] for n in range(1, 105)}
    ranking, count = [], 0
    for kind in ['ema', 'sma']:
        for short in range(1, 31):
            for long in range(max(10, short + 1), 105):
                for nested in [False, True]:
                    slow = (ma[kind, short].ewm(span=long, adjust=False).mean() if kind == 'ema'
                            else ma[kind, short].rolling(long).mean()) if nested else ma[kind, long]
                    raw = 100 * (ma[kind, short] / slow - 1)
                    values = raw.loc[train].to_numpy()
                    scale = float(values @ target / max(1e-15, values @ values))
                    count += 1
                    if scale > 0:
                        ranking.append({'mse': float(np.mean((values * scale - target) ** 2)),
                            'kind': kind, 'short': short, 'long': long, 'nested': nested, 'scale': scale})
    ranking.sort(key=lambda r: r['mse'])
    # The selected, unscaled 10/30 ratio was frozen in protocol-v2 before fresh collection.
    x = 100 * ma['sma', 10] / ma['sma', 30]
    target = references.loc[train, 'ixic_y'].to_numpy() - 100
    momentum = []
    def score(raw, kind, period, smoothing):
        v = raw.loc[train].to_numpy()
        scale = float(v @ target / max(1e-15, v @ v))
        if scale > 0:
            momentum.append({'mse': float(np.mean((v * scale - target) ** 2)), 'kind': kind,
                             'period': period, 'smoothing': smoothing, 'scale': scale})
    for kind in ['ema', 'sma']:
        for n in range(1, 53):
            avg = x.ewm(span=n, adjust=False).mean() if kind == 'ema' else x.rolling(n).mean()
            score(100 * (x / avg - 1), kind, n, 1)
    for lag in range(1, 27):
        raw = 100 * (x / x.shift(lag) - 1)
        for smoothing in range(1, 21):
            score(raw.ewm(span=smoothing, adjust=False).mean(), 'ema_roc', lag, smoothing)
            score(raw.rolling(smoothing).mean(), 'sma_roc', lag, smoothing)
    momentum.sort(key=lambda r: r['mse'])
    assert ranking[0]['kind'] == 'sma' and ranking[0]['short'] == 10 and ranking[0]['long'] == 30 and not ranking[0]['nested']
    assert momentum[0]['kind'] == 'sma' and momentum[0]['period'] == 9
    assert max(abs((x.loc[train] - 100) * (ranking[0]['scale'] - 1))) < .01
    return {'xTested': count, 'yTested': 1144, 'xTop': ranking[:10], 'yTop': momentum[:10],
            'selection': 'SMA10/SMA30; X/SMA9(X); no fitted scales or intercepts'}


def run():
    baseline = ROOT / '.cache/contrast/baseline'
    manifest = json.loads((baseline / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((baseline / name).read_bytes()).hexdigest() == digest
    dataset = json.loads((baseline / 'market.json').read_text(encoding='utf-8'))
    now = pd.Timestamp(dataset['generatedAt'])
    weeks = completed_week_ends(schedule_for(now), now)
    refs = pd.read_csv(RESEARCH / 'observations.csv', index_col=0, parse_dates=True).sort_index()
    train, holdout = split_dates(refs.index)
    prices = {i: pd.read_csv(baseline / f'prices/{i}.csv', index_col=0, parse_dates=True).iloc[:, 0].reindex(weeks).dropna()
              for i in ['GSPC', 'IXIC', 'DJI']}
    out = ROOT / '.cache/contrast/results-v2'
    out.mkdir(exist_ok=True)
    selection = search(prices['IXIC'] / prices['GSPC'], refs, train)
    (out / 'selection.json').write_text(json.dumps(selection, indent=2))
    # Fresh reference is only read after parameter selection has finished.
    confirmation = pd.read_csv(RESEARCH / 'confirmation-nya.csv', index_col=0, parse_dates=True).sort_index()
    prices['NYA'] = pd.read_csv(ROOT / '.cache/contrast/confirmation/NYA.csv', index_col=0, parse_dates=True).iloc[:, 0].reindex(weeks).dropna()
    report, frames = {'selection': selection, 'evaluations': {}, 'cases': {}, 'passed': True}, []
    report['inputHashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__), RESEARCH / 'protocol-v2.json', RESEARCH / 'observations.csv', RESEARCH / 'confirmation-nya.csv',
         ROOT / '.cache/contrast/confirmation/NYA.csv']}
    for identity in ['IXIC', 'DJI', 'NYA']:
        ref = confirmation if identity == 'NYA' else refs
        dates = holdout if identity == 'IXIC' else ref.index
        columns = ['x', 'y'] if identity == 'NYA' else [identity.lower() + '_x', identity.lower() + '_y']
        target = ref.loc[dates, columns].to_numpy()
        new = sma_indicators(prices[identity], prices['GSPC'])
        old = indicators(prices[identity], prices['GSPC'], 10, 4)
        result = metrics(new.loc[dates, ['x', 'y']].to_numpy(), target, .01)
        previous = metrics(old.loc[dates, ['x', 'y']].to_numpy(), target, .01)
        result['baselineRMSE'] = previous['rmse']
        result['rmseReduction'] = (1 - np.array(result['rmse']) / previous['rmse']).tolist()
        result['maxAbsError'] = np.max(abs(new.loc[dates, ['x', 'y']].to_numpy() - target), axis=0).tolist()
        close = ref['close'] if identity == 'NYA' else ref[identity.lower() + '_close']
        result['priceMaxError'] = float(abs(prices[identity].loc[ref.index] - close).max())
        if identity == 'NYA':
            # Data diagnostic only. Replace the entire observed price window in both
            # inputs, not a selected erroneous date. Formula/parameters remain fixed.
            matched_asset, matched_benchmark = prices[identity].copy(), prices['GSPC'].copy()
            matched_asset.loc[ref.index] = ref.close
            matched_benchmark.loc[ref.index] = ref.benchmark_close
            matched = sma_indicators(matched_asset, matched_benchmark).loc[ref.index, ['x', 'y']].to_numpy()
            result['matchedClosesDiagnostic'] = metrics(matched, target, .01)
            result['matchedClosesDiagnostic']['maxAbsError'] = np.max(abs(matched - target), axis=0).tolist()
        result['fresh'] = identity == 'NYA'
        result['passes'] = all(v <= .20 for v in result['rmse']) and all(v >= .5 for v in result['rmseReduction']) and result['quadrantAccuracy'] >= .95
        report['evaluations'][identity] = result
        report['passed'] &= result['passes']
        all_target = ref[columns].to_numpy()
        frame = pd.DataFrame({'asset': identity, 'reference_x': all_target[:, 0], 'reference_y': all_target[:, 1],
            'candidate_x': new.loc[ref.index].x, 'candidate_y': new.loc[ref.index].y,
            'old_x': old.loc[ref.index].x, 'old_y': old.loc[ref.index].y,
            'reference_close': close, 'local_close': prices[identity].loc[ref.index]}, index=ref.index)
        frame['partition'] = ['fresh_confirmation' if identity == 'NYA' else 'training' if identity == 'IXIC' and d in train else 'reused_evaluation' for d in frame.index]
        for axis in ['x', 'y']:
            frame['difference_' + axis] = frame['candidate_' + axis] - frame['reference_' + axis]
        frames.append(frame)
        if identity == 'IXIC':
            for date in ['2026-01-02', '2026-03-20']:
                idx = ref.index.get_loc(pd.Timestamp(date))
                predicted = new.loc[ref.index[idx-1:idx+1], ['x', 'y']].to_numpy()
                actual = ref[columns].iloc[idx-1:idx+1].to_numpy()
                same = bool(np.all(np.sign(np.diff(predicted, axis=0)) == np.sign(np.diff(actual, axis=0))))
                report['cases'][date] = {'reference': actual[-1].tolist(), 'candidate': predicted[-1].tolist(), 'sameLastStepDirection': same}
                report['passed'] &= same
    pd.concat(frames).rename_axis('date').to_csv(out / 'differences.csv')
    (out / 'result.json').write_text(json.dumps(report, indent=2))
    plot(frames, out)
    print(json.dumps({k: report[k] for k in ['evaluations', 'cases', 'passed']}, indent=2))


def plot(frames, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(frames), 3, figsize=(15, 4 * len(frames)))
    for row, frame in enumerate(frames):
        for method, label, color, style in [('old', 'Actual EMA', '#bb795d', '-'), ('reference', 'StockCharts SVG', '#222', '-'), ('candidate', 'SMA 10/30/9', '#2e8396', '--')]:
            axes[row, 0].plot(frame[method + '_x'], frame[method + '_y'], style, label=label, color=color, linewidth=1.2)
            for col, axis in [(1, 'x'), (2, 'y')]:
                axes[row, col].plot(frame.index, frame[method + '_' + axis], style, label=label, color=color, linewidth=1.2)
        for col in [0, 1, 2]:
            axes[row, col].axhline(100, color='#aaa', linewidth=.7)
            axes[row, col].grid(alpha=.15)
            axes[row, col].legend(fontsize=8)
        axes[row, 0].axvline(100, color='#aaa', linewidth=.7)
        axes[row, 0].set(xlabel='X', ylabel='Y', title=frame.asset.iloc[0] + ' / GSPC')
        for col in [1, 2]:
            axes[row, col].set_title(('X' if col == 1 else 'Y') + ' por fecha')
            axes[row, col].tick_params(axis='x', rotation=25)
    fig.tight_layout()
    fig.savefig(output / 'comparison.png', dpi=130)
    plt.close(fig)


if __name__ == '__main__':
    run()
