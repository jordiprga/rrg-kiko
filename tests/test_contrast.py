"""Independent properties and real reference checks; no frozen private cache needed in CI."""
import numpy as np
import pandas as pd

from scripts.contrast import RESEARCH, candidate, metrics, split_dates


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
