"""Independent properties and real reference checks; no frozen private cache needed in CI."""
import numpy as np
import pandas as pd

from scripts.contrast import RESEARCH, candidate, metrics, split_dates
from scripts.market import sma_indicators, make_view, schedule_for
from pathlib import Path


def test_holdout_is_chronological_and_never_overlaps_training():
    dates = pd.date_range('2025-01-03', periods=52, freq='W-FRI')
    train, test = split_dates(reversed(dates))
    assert len(train) == 36 and len(test) == 16
    assert max(train) < min(test)


def test_experimental_model_is_causal_scale_invariant_and_neutral():
    dates = pd.bdate_range('2021-01-01', periods=900)
    prices = pd.Series(100 * np.exp(np.sin(np.arange(900) / 50) / 10), index=dates)
    benchmark = pd.Series(100., index=dates)
    config = (10, 24, 13, (.93, 1.09))
    full = candidate(prices, benchmark, *config)
    np.testing.assert_allclose(full, candidate(prices * 17, benchmark * 3, *config))
    pd.testing.assert_frame_equal(full.iloc[:700], candidate(prices.iloc[:700], benchmark.iloc[:700], *config))
    np.testing.assert_allclose(candidate(prices, prices, *config), 100)
    missing = candidate(prices.drop(dates[-2]), benchmark, *config)
    assert dates[-2] not in missing.index


def test_reference_covers_cases_and_holiday_sessions():
    refs = pd.read_csv(RESEARCH / 'observations.csv').set_index('date')
    assert len(refs) == 52 and refs.index.is_unique
    assert refs.loc['2026-01-02', ['ixic_x', 'ixic_y']].tolist() == [101.46, 99.33]
    assert refs.loc['2026-03-20', ['ixic_x', 'ixic_y']].tolist() == [98.85, 99.06]
    assert {'2026-04-02', '2026-06-18', '2026-07-02'} <= set(refs.index)
    assert not {'2026-04-03', '2026-06-19', '2026-07-03'} & set(refs.index)


def test_quadrant_evaluation_separates_uncertainty_and_near_axis():
    refs = np.array([[100.005, 101], [100.05, 101], [101, 101.]])
    result = metrics(np.array([[99., 101], [101, 101], [101, 99]]), refs, .01)
    assert result['quadrantEligible'] == 2
    assert result['nearAxisCount'] == 2
    assert result['quadrantAccuracy'] == .5
    assert result['farAxisAccuracy'] == 0
    assert metrics(np.array([[101., 101]]), np.array([[100.01, 101.]]), .01)['quadrantEligible'] == 0


def weekly_fixture():
    return pd.read_csv(Path(__file__).parent / 'fixtures/weekly-prices.csv', index_col=0, parse_dates=True)


def test_sma_matches_real_stockcharts_references_and_fresh_confirmation():
    prices = weekly_fixture()
    refs = pd.read_csv(RESEARCH / 'observations.csv', index_col=0, parse_dates=True).sort_index()
    for identity in ['IXIC', 'DJI', 'NYA']:
        calculated = sma_indicators(prices[identity], prices.GSPC)
        if identity == 'NYA':
            ref = pd.read_csv(RESEARCH / 'confirmation-nya.csv', index_col=0, parse_dates=True).sort_index()
            expected = ref[['x', 'y']]
        else:
            expected = refs[[identity.lower() + '_x', identity.lower() + '_y']]
        error = calculated.loc[expected.index, ['x', 'y']].to_numpy() - expected.to_numpy()
        assert np.sqrt(np.mean(error ** 2, axis=0)).max() < .01
        assert np.max(abs(error)) < (.015 if identity == 'NYA' else .0051)


def test_sma_is_causal_scale_invariant_and_benchmark_neutral():
    prices = weekly_fixture()
    full = sma_indicators(prices.IXIC, prices.GSPC)
    np.testing.assert_allclose(full[['x', 'y']], sma_indicators(prices.IXIC * 13, prices.GSPC * .07)[['x', 'y']])
    np.testing.assert_allclose(sma_indicators(prices.GSPC, prices.GSPC)[['x', 'y']], 100)
    pd.testing.assert_frame_equal(full.iloc[:-15], sma_indicators(prices.IXIC.iloc[:-15], prices.GSPC.iloc[:-15]))
    missing = sma_indicators(prices.IXIC.drop(prices.index[-2]), prices.GSPC)
    assert prices.index[-2] not in missing.index and not missing.isna().any().any()


def test_sma_promotion_is_limited_to_weekly_gspc():
    prices = weekly_fixture()
    now = pd.Timestamp('2026-10-18T08:00:00Z')
    data = {'A': prices.IXIC, 'GSPC': prices.GSPC, 'OTHER': prices.GSPC}
    promoted = make_view(data, ['A'], 'GSPC', 'weekly', schedule_for(now), now)
    assert promoted['method'] == 'relative-sma-10-30-9-v2'
    assert promoted['parameters'] == dict(short=10, long=30, m=9)
    other = make_view(data, ['A'], 'OTHER', 'weekly', schedule_for(now), now)
    assert other['method'] == 'relative-ema-v1'
    assert other['parameters'] == dict(n=10, m=4)
