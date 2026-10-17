import json

import numpy as np
import pandas as pd
import pytest

from scripts import market


@pytest.fixture
def series():
    index = pd.bdate_range("2020-01-01", periods=900)
    return pd.Series(100 * np.exp(np.linspace(0, 0.8, 900)), index=index)


def test_benchmark_against_itself_is_center(series):
    result = market.indicators(series, series, 50, 20)
    np.testing.assert_allclose(result[["x", "y"]], 100, atol=1e-10)


def test_rescaling_does_not_change_rotation(series):
    benchmark = pd.Series(100.0, index=series.index)
    original = market.indicators(series, benchmark, 50, 20)
    scaled = market.indicators(series * 10, benchmark, 50, 20)
    np.testing.assert_allclose(original[["x", "y"]], scaled[["x", "y"]], atol=1e-10)


def test_future_does_not_change_past(series):
    benchmark = pd.Series(100.0, index=series.index)
    past = market.indicators(series.iloc[:700], benchmark.iloc[:700], 50, 20)
    full = market.indicators(series, benchmark, 50, 20)
    pd.testing.assert_frame_equal(past, full.loc[past.index])


def test_relative_trend_and_acceleration_have_consistent_direction(series):
    benchmark = pd.Series(100.0, index=series.index)
    accelerating = pd.Series(100 * np.exp(np.linspace(0, 1, len(series)) ** 2), index=series.index)
    result = market.indicators(accelerating, benchmark, 50, 20)
    assert result.iloc[-1].x > 100
    assert result.iloc[-1].y > 100
    decreasing = market.indicators(1 / accelerating, benchmark, 50, 20)
    assert decreasing.iloc[-1].x < 100
    assert decreasing.iloc[-1].y < 100


def test_missing_prices_are_intersected_not_forward_filled(series):
    benchmark = series.copy().drop(series.index[-2])
    result = market.indicators(series, benchmark, 50, 20)
    assert series.index[-2] not in result.index
    assert result.index[-1] == series.index[-1]


def test_thursday_does_not_close_normal_week():
    now = pd.Timestamp("2026-10-15T23:00:00Z")
    schedule = market.schedule_for(now)
    assert market.completed_week_ends(schedule, now)[-1] == pd.Timestamp("2026-10-09")


def test_friday_after_close_finishes_week():
    now = pd.Timestamp("2026-10-16T23:00:00Z")
    schedule = market.schedule_for(now)
    assert market.completed_week_ends(schedule, now)[-1] == pd.Timestamp("2026-10-16")


def test_good_friday_week_finishes_on_thursday():
    now = pd.Timestamp("2026-04-02T23:00:00Z")
    schedule = market.schedule_for(now)
    assert market.completed_week_ends(schedule, now)[-1] == pd.Timestamp("2026-04-02")


def test_intraday_is_not_a_completed_session():
    now = pd.Timestamp("2026-10-16T18:00:00Z")
    schedule = market.schedule_for(now)
    assert market.closed_schedule(schedule, now).index[-1] == pd.Timestamp("2026-10-15")


def test_early_close_holiday_and_publication_delay():
    now = pd.Timestamp("2025-11-28T18:30:00Z")
    schedule = market.schedule_for(now)
    assert market.closed_schedule(schedule, now).index[-1] == pd.Timestamp("2025-11-26")
    later = pd.Timestamp("2025-11-28T20:00:00Z")
    assert market.completed_week_ends(schedule, later)[-1] == pd.Timestamp("2025-11-28")


def test_daily_and_weekly_are_calculated_on_separate_series():
    now = pd.Timestamp("2026-10-17T10:00:00Z")
    schedule = market.schedule_for(now)
    sessions = market.closed_schedule(schedule, now).index
    series = pd.Series(np.exp(np.linspace(0, 2, len(sessions)) ** 2) * 100, index=sessions)
    prices = {"A": series, "B": pd.Series(100.0, index=sessions)}
    daily = market.make_view(prices, ["A"], "B", "daily", schedule, now)
    weekly = market.make_view(prices, ["A"], "B", "weekly", schedule, now)
    assert daily["parameters"] == {"n": 50, "m": 20}
    assert weekly["parameters"] == {"n": 10, "m": 4}
    assert len(weekly["assets"]["A"]) < len(daily["assets"]["A"])
    assert weekly["assets"]["A"][-1][1:3] != daily["assets"]["A"][-1][1:3]


def test_missing_last_session_is_not_used_to_close_week():
    now = pd.Timestamp("2026-10-17T10:00:00Z")
    schedule = market.schedule_for(now)
    sessions = market.closed_schedule(schedule, now).index
    full = pd.Series(100.0, index=sessions)
    incomplete = full.drop(pd.Timestamp("2026-10-16"))
    result = market.make_view({"A": incomplete, "B": full}, ["A"], "B", "weekly", schedule, now)
    assert result["assets"]["A"][-1][0] == "2026-10-09"


def test_invalid_prices_are_removed():
    values = pd.Series([100, float("nan"), -1, 0, float("inf"), 110], index=pd.bdate_range("2026-01-01", periods=6))
    assert market.clean_series(values).to_list() == [100, 110]


def test_failed_refresh_does_not_replace_previous_dataset(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/catalog.json").write_text(json.dumps({"instruments": [{"id": "A"}], "groups": {}}))
    monkeypatch.setattr(market, "ROOT", tmp_path)
    output = tmp_path / "market.json"
    output.write_text('{"valid":"previous snapshot"}')
    class BrokenProvider:
        def history(self, instrument):
            raise RuntimeError("Proveedor no disponible")
    with pytest.raises(ValueError, match="se conserva"):
        market.refresh(BrokenProvider(), output, pd.Timestamp("2026-10-17T10:00:00Z"))
    assert json.loads(output.read_text()) == {"valid": "previous snapshot"}


def test_nonfinite_serialization_preserves_previous_file(tmp_path):
    output = tmp_path / "market.json"
    output.write_text('{"valid":true}')
    with pytest.raises(ValueError):
        market.atomic_json(output, {"invalid": float("nan")})
    assert json.loads(output.read_text()) == {"valid": True}
