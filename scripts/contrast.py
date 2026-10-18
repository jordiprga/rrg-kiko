"""Offline StockCharts comparison. Never writes the public dataset or chooses on holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.market import ROOT, completed_week_ends, indicators, schedule_for

RESEARCH = ROOT / 'research/stockcharts'


def candidate(asset, benchmark, smooth, n, m, scale=(1., 1.)):
    pair = pd.concat([asset, benchmark], axis=1).dropna()
    rs = pair.iloc[:, 0] / pair.iloc[:, 1]
    smoothed = rs.ewm(span=smooth, adjust=False).mean()
    x = 100 * smoothed / smoothed.ewm(span=n, adjust=False).mean()
    y = 100 * x / x.ewm(span=m, adjust=False).mean()
    return pd.DataFrame({'x': 100 + scale[0] * (x - 100), 'y': 100 + scale[1] * (y - 100)})


def split_dates(dates):
    dates = sorted(set(dates))
    split = int(len(dates) * .7)
    return dates[:split], dates[split:]


def quadrant(values):
    labels = (values[:, 0] > 100).astype(int) * 2 + (values[:, 1] > 100).astype(int)
    labels[np.any(np.abs(values - 100) < 1e-9, axis=1)] = 4
    return labels


def metrics(predicted, reference, uncertainty):
    delta = predicted - reference
    distance = np.min(np.abs(reference - 100), axis=1)
    mask = distance > uncertainty + 1e-9
    far = distance >= .10
    agreement = quadrant(predicted) == quadrant(reference)
    return {'count': len(reference), 'rmse': np.sqrt(np.mean(delta ** 2, axis=0)).tolist(),
            'quadrantEligible': int(mask.sum()), 'quadrantAccuracy': float(agreement[mask].mean()) if mask.any() else None,
            'nearAxisCount': int((~far).sum()), 'farAxisAccuracy': float(agreement[far].mean()) if far.any() else None}


def run(baseline: Path, output: Path):
    manifest = json.loads((baseline / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((baseline / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen baseline changed: {name}')
    dataset = json.loads((baseline / 'market.json').read_text(encoding='utf-8'))
    refs = pd.read_csv(RESEARCH / 'observations.csv', parse_dates=['date']).set_index('date').sort_index()
    if not refs.index.is_unique or refs.isna().any().any():
        raise ValueError('Missing/duplicate references')
    protocol = json.loads((RESEARCH / 'protocol.json').read_text())
    uncertainty = json.loads((RESEARCH / 'source.json').read_text())['uncertaintyPerAxis']
    now = pd.Timestamp(dataset['generatedAt'])
    weeks = completed_week_ends(schedule_for(now), now)
    prices = {i: pd.read_csv(baseline / f'prices/{i}.csv', index_col=0, parse_dates=True).iloc[:, 0]
              for i in ['GSPC', 'IXIC', 'DJI']}
    prices = {i: p.loc[p.index.isin(weeks)] for i, p in prices.items()}
    if not refs.index.isin(weeks).all():
        raise ValueError('Reference date is not a completed weekly session')
    train, holdout = split_dates(refs.index)
    # Only Nasdaq training enters candidate choice and scale fitting.
    target = refs.loc[train, ['ixic_x', 'ixic_y']].to_numpy()
    best = None
    for smooth in range(1, 11):
        for n in range(10, 53):
            for m in range(2, 14):
                raw = candidate(prices['IXIC'], prices['GSPC'], smooth, n, m).loc[train].to_numpy() - 100
                scale = np.maximum(0, np.sum(raw * (target - 100), axis=0) / np.maximum(1e-15, np.sum(raw * raw, axis=0)))
                loss = float(np.mean((100 + raw * scale - target) ** 2))
                if best is None or loss < best[0]:
                    best = loss, smooth, n, m, scale
    loss, smooth, n, m, scale = best
    output.mkdir(parents=True, exist_ok=True)
    report = {'baseline': manifest, 'inputHashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [RESEARCH / 'observations.csv', RESEARCH / 'source.json', RESEARCH / 'protocol.json', Path(__file__)]},
              'protocol': protocol, 'trainingDates': [str(d.date()) for d in train],
              'holdoutDates': [str(d.date()) for d in holdout], 'candidate': {'method': 'smoothed-relative-ema-research-v1',
              'smooth': smooth, 'n': n, 'm': m, 'scale': scale.tolist(), 'trainingMSE': loss}, 'evaluation': {}, 'prices': {}}
    merged = []
    cases_ok = True
    for identity, prefix in [('IXIC', 'ixic'), ('DJI', 'dji')]:
        old = indicators(prices[identity], prices['GSPC'], 10, 4)
        frozen = pd.DataFrame(dataset['views']['GSPC']['weekly']['assets'][identity], columns=['date', 'x', 'y', 'price']).set_index('date')
        frozen.index = pd.to_datetime(frozen.index)
        np.testing.assert_allclose(old.loc[frozen.index, ['x', 'y', 'price']], frozen, atol=1e-6, rtol=0)
        new = candidate(prices[identity], prices['GSPC'], smooth, n, m, scale)
        dates = holdout if identity == 'IXIC' else list(refs.index)
        ref = refs.loc[dates, [prefix + '_x', prefix + '_y']].to_numpy()
        base_metrics = metrics(old.loc[dates, ['x', 'y']].to_numpy(), ref, uncertainty)
        new_metrics = metrics(new.loc[dates].to_numpy(), ref, uncertainty)
        report['evaluation'][identity] = {'baseline': base_metrics, 'candidate': new_metrics,
            'rmseReduction': (1 - np.array(new_metrics['rmse']) / np.array(base_metrics['rmse'])).tolist()}
        price_errors = prices[identity].loc[refs.index] - refs[prefix + '_close']
        benchmark_errors = prices['GSPC'].loc[refs.index] - refs.benchmark_close
        report['prices'][identity] = {'assetMaxAbsoluteError': float(abs(price_errors).max()),
                                     'benchmarkMaxAbsoluteError': float(abs(benchmark_errors).max())}
        frame = pd.DataFrame({'asset': identity, 'reference_x': refs[prefix + '_x'], 'reference_y': refs[prefix + '_y'],
            'old_x': old.x, 'old_y': old.y, 'candidate_x': new.x, 'candidate_y': new.y,
            'local_close': prices[identity], 'reference_close': refs[prefix + '_close'],
            'local_benchmark': prices['GSPC'], 'reference_benchmark': refs.benchmark_close}).loc[refs.index]
        for axis in ['x', 'y']:
            frame['delta_' + axis] = frame['candidate_' + axis] - frame['reference_' + axis]
            frame['reference_cross_' + axis] = np.sign(frame['reference_' + axis] - 100).diff().fillna(0) != 0
        frame['partition'] = ['training' if identity == 'IXIC' and d in train else 'holdout' for d in frame.index]
        frame['uncertainty'] = uncertainty
        merged.append(frame)
        if identity == 'IXIC':
            report['kikoCases'] = {}
            for date in protocol['kikoDates']:
                loc = refs.index.get_loc(pd.Timestamp(date))
                r = refs[[prefix + '_x', prefix + '_y']].iloc[loc-1:loc+1].to_numpy()
                c = new.loc[refs.index[loc-1:loc+1]].to_numpy()
                same_quadrant = bool(quadrant(c[-1:])[0] == quadrant(r[-1:])[0])
                same_direction = bool(np.all(np.sign(c[1] - c[0]) == np.sign(r[1] - r[0])))
                cases_ok &= same_quadrant and same_direction
                report['kikoCases'][date] = {'reference': r[-1].tolist(), 'candidate': c[-1].tolist(),
                    'sameQuadrant': same_quadrant, 'sameLastStepDirection': same_direction}
    checks = {i: (all(v <= .20 for v in e['candidate']['rmse']) and all(v >= .5 for v in e['rmseReduction'])
                    and (e['candidate']['quadrantAccuracy'] or 0) >= .95) for i, e in report['evaluation'].items()}
    report['criteriaPassed'] = len(refs) >= 40 and all(checks.values()) and cases_ok
    report['decision'] = 'REVIEW_REQUIRED' if report['criteriaPassed'] else 'KEEP_RELATIVE_EMA_V1'
    report['warmup'] = 'All frozen weekly prices from 2021; EMA adjust=False, same seed; evaluated dates after baseline 50 weeks. StockCharts warmup unknown.'
    pd.concat(merged).rename_axis('date').to_csv(output / 'differences.csv')
    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    plots(merged, output)
    lines = ['# Contraste StockCharts — 18/10/2026', '', f"Decisión: **{report['decision']}**. Dataset congelado; sin cambios en el cálculo público.", '',
        f'{len(refs)} semanas por activo; Nasdaq: {len(train)} ajuste / {len(holdout)} evaluación; Dow: {len(refs)} evaluación.', '',
        f'Candidato: suavizado EMA {smooth}, referencia EMA {n}, momentum EMA {m}; escalas centradas en 100: {scale.tolist()}.', '',
        'RS=activo/benchmark; S=EMA(RS,s); X0=100×S/EMA(S,n); Y0=100×X0/EMA(X0,m); X=100+ax×(X0−100); Y=100+ay×(Y0−100).', '',
        '5.160 variantes. Parámetros y escalas elegidos sólo con el primer 70% del Nasdaq. Ningún reajuste posterior con evaluación.', '',
        '| Evaluación | RMSE actual X/Y | RMSE candidato X/Y | Reducción X/Y | Cuadrantes |', '|---|---|---|---|---|']
    for i, e in report['evaluation'].items():
        pair = lambda values: ' / '.join(f'{v:.3f}' for v in values)
        lines.append(f"| {i} | {pair(e['baseline']['rmse'])} | {pair(e['candidate']['rmse'])} | {pair(e['rmseReduction'])} | {e['candidate']['quadrantAccuracy']:.1%} |")
    lines += ['', '## Datos y límites', '', f"Errores máximos de cierres: {report['prices']}", '',
        'Coordenadas reconstruidas del SVG, incertidumbre conservadora ±0,01 por eje; no son valores numéricos certificados de JdK. Se excluyen cuadrantes cuya incertidumbre alcanza 100; result.json separa también distancia <0,10.', '',
        'Semanas efectivas XNYS completadas; sin relleno. Cierres de índices sin ajustar. Cálculo semanal independiente. La copia congelada conserva precios diarios, dataset, código, parámetros y SHA-256.', '',
        'StockCharts: 10 intervalos = 10 círculos anteriores + cabeza. El rango visible no revela el calentamiento del proveedor. Algunas cabezas fuera de escala se fijan en el borde: se usaron sus círculos reales de cola.', '',
        f"Casos de Kiko: {json.dumps(report['kikoCases'], ensure_ascii=False)}", '',
        'Las curvas dibujadas usan segmentos rectos. No se usa suavizado gráfico para evaluar. Los cruces de 100 y diferencias están en differences.csv.', '',
        '![Comparación](comparison.png)', '',
        'Reproducir: `python -m scripts.contrast --baseline .cache/contrast/baseline --output .cache/contrast/results`.', '',
        'Fuente: [StockCharts](https://stockcharts.com/freecharts/rrg/) · [Ayuda](https://help.stockcharts.com/charts-and-tools/other-charting-tools/rrg-charts). Referencias y gráficos son investigación local; no se incluyen en dist.']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['candidate', 'evaluation', 'prices', 'kikoCases', 'decision']}, indent=2))


def plots(frames, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for row, frame in enumerate(frames):
        for name, label, color in [('reference', 'StockCharts (SVG)', '#222222'), ('old', 'Actual', '#bf7655'), ('candidate', 'Candidato', '#377da4')]:
            axes[row, 0].plot(frame[name + '_x'], frame[name + '_y'], '.-', label=label, color=color, linewidth=1)
            for col, axis in [(1, 'x'), (2, 'y')]:
                axes[row, col].plot(frame.index, frame[name + '_' + axis], label=label, color=color, linewidth=1.2)
        axes[row, 0].axvline(100, color='#aaa', linewidth=.7)
        axes[row, 0].set(xlabel='X', ylabel='Y', title=frame.asset.iloc[0] + ' / GSPC — mismos ejes')
        for col in [0, 1, 2]:
            axes[row, col].axhline(100, color='#aaa', linewidth=.7)
            axes[row, col].grid(alpha=.2)
            axes[row, col].legend(fontsize=8)
        for col in [1, 2]:
            axes[row, col].set_title('X por fecha' if col == 1 else 'Y por fecha')
            axes[row, col].tick_params(axis='x', rotation=30)
    fig.tight_layout()
    fig.savefig(output / 'comparison.png', dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, default=ROOT / '.cache/contrast/baseline')
    parser.add_argument('--output', type=Path, default=ROOT / '.cache/contrast/results')
    args = parser.parse_args()
    run(args.baseline, args.output)
